# -*- coding: utf-8 -*-
"""
منظومة حجز الروضة الشريفة - محرك مسارات وشاشات تطبيق نسك (Nusuk Flow Engine)
State Machine for Nusuk Onboarding, Login/Register, OTP, Profile Completion, Slot Sniping, and Confirmation
Directly calibrated from expert human session recording and supervised by the Gemini AI Brain.
"""

import time
import re
import sys
from pathlib import Path
from enum import Enum
from typing import Optional, Dict, Any, Tuple, Callable

CORE_DIR = Path(__file__).parent.parent / "core_engine"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

try:
    import otp_manager
except Exception:
    otp_manager = None

from auto_booking.ai_brain import GeminiSupervisor


class ScreenType(Enum):
    ONBOARDING = "ONBOARDING"              # شاشات الترحيب
    LANDING = "LANDING"                    # شاشة البداية
    AUTH_MODAL = "AUTH_MODAL"              # نافذة اختيار تسجيل الدخول أو إنشاء حساب
    REGISTER_FORM = "REGISTER_FORM"        # إنشاء حساب جديد
    LOGIN_FORM = "LOGIN_FORM"              # تسجيل دخول
    OTP = "OTP"                            # كود التحقق
    HOME = "HOME"                          # الواجهة الرئيسية
    WHO_FOR = "WHO_FOR"                    # اختيار الفئة (رجال / نساء)
    PROFILE_REQUIRED = "PROFILE_REQUIRED"  # إكمال الملف الشخصي (الجواز / التأشيرة / الجنسية)
    SELECT_PERSON = "SELECT_PERSON"        # اختيار المعتمر والمرافقين
    CALENDAR_SLOTS = "CALENDAR_SLOTS"      # جدول المواعيد المتاحة
    CONFIRMATION_SHEET = "CONFIRMATION_SHEET" # نافذة تأكيد الحجز النهائية
    RATING_MODAL = "RATING_MODAL"          # نافذة تقييم التجربة
    CONFIRMED = "CONFIRMED"                # تم تأكيد الحجز بنجاح
    ID_ALREADY_EXISTS = "ID_ALREADY_EXISTS"# الهوية مسجلة مسبقاً
    TERMS_POPUP = "TERMS_POPUP"            # نافذة شروط أو تنبيه
    UNEXPECTED = "UNEXPECTED"              # شاشة أخرى


class NusukFlow:
    def __init__(self, adb_controller, supervisor: Optional[GeminiSupervisor] = None, log_callback: Optional[Callable[[str], None]] = None):
        self.adb = adb_controller
        self.log_cb = log_callback
        self.supervisor = supervisor or GeminiSupervisor(log_callback=self.log)
        self.current_pilgrim: Dict[str, Any] = {}

    def log(self, msg: str):
        t = time.strftime("%H:%M:%S")
        entry = f"[{t}] {msg}"
        print(entry, flush=True)
        if self.log_cb:
            try:
                self.log_cb(entry)
            except Exception:
                pass

    def detect_screen(self) -> ScreenType:
        """
        فحص الشاشة الحالية بدقة هندسية تمنع الأخطاء الكاذبة نهائياً:
        يتم ترتيب الفحص من الخاص إلى العام لمنع أي تداخل بين الشاشات.
        """
        nodes = self.adb.find_all_nodes()
        all_text = " ".join([f"{n.get('text', '')} {n.get('desc', '')}" for n in nodes]).lower()

        # 1. نافذة تقييم التجربة (تظهر فور إتمام الحجز)
        if any(k in all_text for k in ["rate your experience", "share your rating", "remind me later", "تقييم"]):
            return ScreenType.RATING_MODAL

        # 2. نافذة تأكيد الحجز السفلية (Bottom Sheet قبل التصريح)
        if any(k in all_text for k in ["your blessed visit to the prophet", "choose another time", "زيارتك المباركة"]):
            return ScreenType.CONFIRMATION_SHEET

        # 3. شاشة المواعيد والكالندر
        if any(k in all_text for k in ["appointments for men only", "appintments for women only", "confirm slots", "select a time slot first"]) or \
           ("friday" in all_text and any(k in all_text for k in ["midnight", "fajir", "dhuhr", "asr", "maghrib"])):
            return ScreenType.CALENDAR_SLOTS

        # 4. شاشة اختيار الفئة (رجال / نساء)
        if "males" in all_text and "females" in all_text:
            return ScreenType.WHO_FOR

        # 5. شاشة استكمال بيانات الملف الشخصي (Build Your Profile / Complete Profile)
        if any(k in all_text for k in ["build your profile", "select id type", "verify using", "verify your account"]) or \
           ("complete profile" in all_text and "trending" not in all_text and "zamzam" not in all_text):
            return ScreenType.PROFILE_REQUIRED

        # 6. تصريح مؤكد حقيقي (يمنع تماماً الخلط مع عبارة You have no active permits)
        if "you have no active permits" not in all_text and "males" not in all_text and "females" not in all_text:
            if ("rawdah permit" in all_text and ("permit issued to" in all_text or "visit date" in all_text)) or \
               any(k in all_text for k in ["reservation confirmed", "حجز مؤكد", "تم الحجز بنجاح"]):
                return ScreenType.CONFIRMED

        # 7. الهوية مسجلة مسبقاً
        if any(k in all_text for k in ["this id already exists", "linked to another account", "هذا الجواز مسجل", "مسجل مسبق"]):
            return ScreenType.ID_ALREADY_EXISTS

        # 8. شاشات الترحيب
        if any(k in all_text for k in ["enter the prophet", "garden", "the qur’an", "time to pray", "umrah in minutes", "reserve your moment", "تخطي"]):
            return ScreenType.ONBOARDING

        # 9. شاشة البداية
        if any(k in all_text for k in ["are you ready to start", "login or register", "continue as guest", "تسجيل الدخول أو إنشاء حساب"]):
            return ScreenType.LANDING

        # 10. القائمة المنبثقة
        if any(k in all_text for k in ["log in to continue", "login with email", "register new account", "تسجيل الدخول بالبريد", "إنشاء حساب جديد"]):
            return ScreenType.AUTH_MODAL

        # 11. نموذج إنشاء الحساب
        if any(k in all_text for k in ["create your account", "start your spiritual journey with", "full name", "الاسم الكامل", "إنشاء حسابك"]):
            return ScreenType.REGISTER_FORM

        # 12. نموذج تسجيل الدخول
        if any(k in all_text for k in ["sign in", "تسجيل الدخول"]) and "password" in all_text:
            return ScreenType.LOGIN_FORM

        # 13. رمز التحقق OTP
        if any(k in all_text for k in ["verify your email", "verification code", "رمز التحقق", "enter otp", "أدخل الرمز"]):
            return ScreenType.OTP

        # 14. شاشة اختيار المعتمر والمرافقين
        if any(k in all_text for k in ["add friend", "add dependent", "select user", "إضافة مرافق", "اختر المستخدمين"]):
            return ScreenType.SELECT_PERSON

        # 15. الشاشة الرئيسية
        if any(k in all_text for k in ["trending", "zamzam", "prayer times", "thikr", "rawdah", "umrah", "hajj", "rituals", "شعائر", "visit rawdah", "زيارة الروضة الشريفة"]):
            return ScreenType.HOME

        # 16. تنبيه أو شروط
        if any(k in all_text for k in ["terms and conditions", "i agree", "موافق", "أوافق على الشروط"]):
            return ScreenType.TERMS_POPUP

        return ScreenType.UNEXPECTED

    def execute_booking(self, pilgrim_data: Dict[str, Any], session_settings: Dict[str, Any]) -> Tuple[bool, str]:
        """
        تنفيذ مسار الحجز الكامل لمعتمر محدد تحت إشراف العقل المدبر:
        pilgrim_data: {'name': ..., 'email': ..., 'password': ..., 'gender': 'رجال'/'نساء', 'passport': ..., 'visa': ...}
        """
        self.current_pilgrim = pilgrim_data
        name = pilgrim_data.get("name", "المعتمر")
        gender = pilgrim_data.get("gender", "رجال")
        dependents = pilgrim_data.get("dependents", [])

        self.log(f"🚀 [مسار الحجز الذكي]: بدء التنفيذ للمعتمر {name} ({gender})")

        # 1. التنقل الأولي حتى الواجهة الرئيسية وتسجيل الدخول / إنشاء الحساب
        ready = self._navigate_to_home(pilgrim_data)
        if not ready:
            return False, "تعذر تجهيز التطبيق وتسجيل الدخول"

        # 2. الحجز وقنص الموعد الفعلي (شامل إكمال الملف الشخصي واختيار الموعد والتأكيد)
        success, details = self._snipe_slot_and_confirm(gender, dependents, session_settings)

        # 3. تسجيل الخروج إذا تم طلب ذلك
        if session_settings.get("auto_logout", True) and success:
            self._logout()

        return success, details

    def _navigate_to_home(self, pilgrim_data: Dict[str, Any]) -> bool:
        """التنقل التلقائي حتى الواجهة الرئيسية أو استكمال الحساب بإشراف العقل المدبر"""
        name = pilgrim_data.get("name", "المعتمر")
        email = pilgrim_data.get("email", "")
        password = pilgrim_data.get("password", "Zxcv1234$")

        for step in range(35):
            st = self.detect_screen()

            if st in [ScreenType.HOME, ScreenType.WHO_FOR, ScreenType.PROFILE_REQUIRED, ScreenType.CALENDAR_SLOTS]:
                self.log("🏠 تم الوصول للواجهة بنجاح والبدء في إجراءات الحجز.")
                return True

            if st == ScreenType.ONBOARDING:
                self.log(f"⏩ تخطي شاشة الترحيب (خطوة {step+1})...")
                self.adb.tap(908, 1500, delay=0.8)
                self.adb.tap(815, 1515, delay=0.8)
                self.adb.click_text("تخطي") or self.adb.click_text("Skip")
                continue

            if st == ScreenType.LANDING:
                self.log("🔘 الضغط على Login Or Register...")
                self.adb.tap(450, 1472, delay=1.5)
                continue

            if st == ScreenType.AUTH_MODAL:
                nodes = self.adb.find_all_nodes()
                decision = self.supervisor.supervise_screen_action("AUTH_MODAL", nodes, pilgrim_data, {})
                self.log(f"🧠 قرار العقل المدبر: {decision.get('reason')}")
                target_text = decision.get("target", "Register New Account")
                fallback = decision.get("fallback_coords", (450, 1410))
                if not self.adb.click_text(target_text):
                    self.adb.tap(fallback[0], fallback[1], delay=1.5)
                continue

            if st == ScreenType.REGISTER_FORM:
                self.log(f"✍ تعبئة بيانات إنشاء الحساب ({email})...")
                nodes = self.adb.find_all_nodes()
                full_name_clean = re.sub(r'[^a-zA-Z0-9 ]', '', name).strip() or "Mohamed Ahmed"

                # البحث عن الحقول بالـ resource-id أو placeholder text
                def tap_field_by_hint(hints):
                    """البحث عن حقل بنصه الإرشادي والنقر عليه"""
                    for n in nodes:
                        t = (n.get("text","") + " " + n.get("desc","")).lower()
                        for h in hints:
                            if h in t and n.get("center"):
                                cx, cy = n["center"]
                                self.adb.tap(cx, cy, delay=0.4)
                                return True
                    return False

                # 1. حقل الاسم الكامل
                if not tap_field_by_hint(["full name", "الاسم"]):
                    self.adb.tap(450, 340, delay=0.4)
                self.adb.clear_field(40)
                self.adb.type_text(full_name_clean, delay=0.3)

                # 2. حقل البريد الإلكتروني
                if not tap_field_by_hint(["email address", "البريد", "email"]):
                    self.adb.tap(450, 470, delay=0.4)
                self.adb.clear_field(60)
                self.adb.type_text(email, delay=0.3)

                # 3. حقل كلمة المرور
                if not tap_field_by_hint(["password", "كلمة المرور"]):
                    self.adb.tap(450, 575, delay=0.4)
                self.adb.clear_field(30)
                self.adb.type_text(password, delay=0.3)

                # 4. إغلاق لوحة المفاتيح وضغط Create Your Account
                self.adb.press_key(4, delay=0.3)   # BACK لإغلاق الكيبورد
                time.sleep(0.5)

                # البحث عن زر إنشاء الحساب
                if not self.adb.click_text("Create Your Account", delay=2.5):
                    if not self.adb.click_text("إنشاء حسابك", delay=2.5):
                        self.adb.tap(450, 1000, delay=2.5)
                continue

            if st == ScreenType.LOGIN_FORM:
                self.log(f"✍ إدخال بيانات تسجيل الدخول ({email})...")
                self.adb.tap(450, 360, delay=0.3)
                self.adb.clear_field(50)
                self.adb.type_text(email, delay=0.3)

                self.adb.tap(450, 480, delay=0.3)
                self.adb.clear_field(30)
                self.adb.type_text(password, delay=0.3)

                self.adb.tap(450, 675, delay=3.0)
                continue

            if st == ScreenType.OTP:
                self.log("⏳ شاشة كود الـ OTP: جاري سحب أحدث كود تلقائياً من البريد...")
                code = self._fetch_otp_code(email)
                if code:
                    self.log(f"🔢 تم استلام كود التحقق ({code})، إدخاله في الخانة (428, 809)...")
                    self.adb.tap(428, 809, delay=0.3)
                    self.adb.type_text(code, delay=0.4)
                    time.sleep(0.5)
                    self.adb.tap(556, 895, delay=3.0)
                else:
                    self.log("⚠ في انتظار وصول الكود من البريد...")
                continue

            if st == ScreenType.ID_ALREADY_EXISTS:
                self.log("💡 العقل المدبر: تم اكتشاف أن الهوية مسجلة مسبقاً! التبديل لتسجيل الدخول...")
                pilgrim_data["is_registered"] = True
                self.adb.tap(450, 1423, delay=2.0)
                continue

            time.sleep(1.2)

        return False

    def _handle_profile_completion(self, pilgrim_data: Dict[str, Any]) -> bool:
        """
        معالجة خطوات إكمال الملف الشخصي (Build Your Profile) بدقة 100%
        الخطوات 33 إلى 41 من التسجيل البشري
        """
        nodes = self.adb.find_all_nodes()
        all_t = " ".join([n.get("text", "") for n in nodes]).lower()

        # الخطوة 33: الضغط على زر استكمال الملف بالأسفل إذا ظهرت النافذة المنبثقة
        if "you're almost there" in all_t or ("complete profile" in all_t and "select id type" not in all_t and "build your profile" not in all_t):
            self.log("  🔘 النقر على زر استكمال الملف (Complete profile)...")
            self.adb.tap(450, 1493, delay=2.0)
            return True

        # الخطوة 34: اختيار فئة الزوار الدوليين (International or GCC Visitor)
        if "select id type" in all_t or "gulf id or passport" in all_t:
            self.log("  🌍 اختيار فئة الزوار الدوليين (International or GCC Visitor)...")
            self.adb.tap(272, 725, delay=2.0)
            return True

        # الخطوات 35-41: إدخال الجنسية والجواز والتأشيرة
        if "build your profile" in all_t or "passport" in all_t or "visa number" in all_t:
            passport = str(pilgrim_data.get("passport", "")).strip()
            visa = str(pilgrim_data.get("visa", "")).strip()

            self.log(f"  🛂 إدخال بيانات المعتمر: جواز: {passport} | تأشيرة: {visa}...")

            # 1. قائمة الجنسية (الخطوة 35-38)
            # نتحقق إذا كانت الجنسية مصر غير محددة
            if "egypt" not in all_t:
                self.log("  🇪🇬 اختيار الدولة: مصر (Egypt)...")
                self.adb.tap(450, 425, delay=1.0)
                self.adb.tap(279, 77, delay=0.3)
                self.adb.type_text("Egypt", delay=0.5)
                self.adb.tap(250, 232, delay=0.5)
                self.adb.tap(536, 1549, delay=1.5)

            # 2. حقل رقم الجواز (الخطوة 39: عند 450, 527)
            if passport:
                self.log(f"  ✍ كتابة رقم الجواز ({passport})...")
                self.adb.tap(450, 527, delay=0.3)
                self.adb.clear_field(30)
                self.adb.type_text(passport, delay=0.3)

            # 3. حقل رقم التأشيرة (الخطوة 40: عند 450, 775)
            if visa:
                self.log(f"  ✍ كتابة رقم التأشيرة ({visa})...")
                self.adb.tap(450, 775, delay=0.3)
                self.adb.clear_field(30)
                self.adb.type_text(visa, delay=0.3)

            # 4. النقر على زر Verify Your Account (الخطوة 41: عند 429, 892)
            self.log("  ✅ النقر على Verify Your Account...")
            self.adb.tap(429, 892, delay=3.0)
            return True

        return False

    def _snipe_slot_and_confirm(self, gender: str, dependents: list, session_settings: dict) -> Tuple[bool, str]:
        """مسار قنص الموعد وتأكيد الحجز المستخرج بدقة 100% من التسجيل البشري"""
        is_female = ("نس" in gender or "fem" in gender.lower() or "طفلة" in gender)

        for step in range(40):
            st = self.detect_screen()

            # 1. تم تأكيد الحجز وظهور التصريح الحقيقي بنجاح
            if st == ScreenType.CONFIRMED:
                self.log("🎉 تم تأكيد التصريح بنجاح 100% ومطابق للتسجيل البشري!")
                return True, "تم تأكيد الحجز بنجاح وإصدار التصريح"

            # 2. نافذة تقييم التجربة (تظهر فور إتمام الحجز)
            if st == ScreenType.RATING_MODAL:
                self.log("⭐ إغلاق نافذة التقييم فوراً...")
                self.adb.tap(450, 1534, delay=1.0)
                continue

            # 3. نافذة التأكيد السفلية (Your Blessed Visit to the Prophet’s Rawdah ﷺ)
            if st == ScreenType.CONFIRMATION_SHEET:
                self.log("🕋 نافذة تأكيد الزيارة: النقر على زر التأكيد النهائي (الخطوة 51)...")
                self.adb.tap(450, 1440, delay=2.5)
                continue

            # 4. الشاشة الرئيسية: الدخول لخدمة الروضة
            if st == ScreenType.HOME:
                self.log("🕌 الدخول إلى خدمة الروضة الشريفة (الخطوة 30 من التسجيل البشري)...")
                self.adb.tap(122, 224, delay=2.5)
                continue

            # 5. اختيار الفئة (رجال / نساء)
            if st == ScreenType.WHO_FOR:
                label = "النساء 👩" if is_female else "الرجال 👨"
                self.log(f"👥 اختيار الفئة المطلوبة: {label} (الخطوات 31-32)...")
                if is_female:
                    self.adb.tap(519, 1000, delay=1.0)
                else:
                    self.adb.tap(310, 974, delay=1.0)

                self.adb.tap(138, 1090, delay=2.5)
                continue

            # 6. استكمال بيانات الملف الشخصي (Build Your Profile / Complete Profile)
            if st == ScreenType.PROFILE_REQUIRED:
                self.log("👤 استكمال الملف الشخصي للمعتمر (الجواز / التأشيرة)...")
                self._handle_profile_completion(self.current_pilgrim)
                continue

            # 7. اختيار المعتمر والمرافقين
            if st == ScreenType.SELECT_PERSON:
                self.log("👤 تحديد المعتمر الأساسي والمتابعة...")
                self.adb.tap(800, 280, delay=0.5)

                if dependents:
                    for dep in dependents:
                        self.log(f"  👶 إضافة التابع/الطفل: {dep.get('name', 'طفل')}")
                        self.adb.tap(800, 360, delay=0.5)

                self.adb.tap(450, 1484, delay=2.5)
                continue

            # 8. شاشة المواعيد والكالندر
            if st == ScreenType.CALENDAR_SLOTS:
                self.log("🎯 شاشة المواعيد نشطة: تطبيق خطوات التسجيل البشري الدقيقة...")

                # أ. التنقل بين الأيام إذا لزم الأمر (زر السهم التالي عند (819, 199))
                target_date = session_settings.get("target_date", "")
                nodes = self.adb.find_all_nodes()
                screen_text = " ".join([n.get("text", "") for n in nodes])

                if target_date and target_date not in screen_text:
                    self.log(f"  📅 التنقل للأمام بالكالندر بحثاً عن {target_date}...")
                    self.adb.tap(819, 199, delay=1.5)

                # ب. اختيار نافذة الصلاة المطلوبة (الخطوة 47-48)
                prayer_choice = session_settings.get("prayer_window", "أي وقت")
                prayer_coords = {
                    "الفجر": (270, 325),
                    "الظهر": (445, 325),
                    "العصر": (620, 325),
                    "المغرب": (798, 325),
                    "العشاء": (90, 325),
                    "Midnight": (90, 325),
                }

                if prayer_choice in prayer_coords:
                    ptap = prayer_coords[prayer_choice]
                    self.log(f"  🕌 التبديل لنافذة صلاة {prayer_choice} عند ({ptap[0]}, {ptap[1]})...")
                    self.adb.tap(ptap[0], ptap[1], delay=1.0)
                else:
                    self.adb.tap(90, 325, delay=1.0)

                # ج. اختيار وقت الموعد (Slot Chip) من الشبكة
                nodes = self.adb.find_all_nodes()
                slot_tapped = False
                for n in nodes:
                    t = n.get("text", "")
                    if re.search(r"\d{1,2}:\d{2}\s*(?:AM|PM)", t):
                        b = n.get("bounds", "")
                        m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", b)
                        if m:
                            cx = (int(m.group(1)) + int(m.group(3))) // 2
                            cy = (int(m.group(2)) + int(m.group(4))) // 2
                            self.log(f"  ⏱ النقر على الموعد المتاح ({t}) عند ({cx}, {cy})...")
                            self.adb.tap(cx, cy, delay=1.0)
                            slot_tapped = True
                            break

                if not slot_tapped:
                    self.log("  ⏱ اختيار الموعد عبر إحداثيات التسجيل البشري (232, 752)...")
                    self.adb.tap(232, 752, delay=1.0)

                # د. النقر على زر Confirm Slots بالأسفل (الخطوة 50: عند 450, 1540)
                self.log("  🔘 النقر على زر Confirm Slots (الخطوة 50)...")
                self.adb.tap(450, 1540, delay=2.5)
                continue

            time.sleep(1.5)

        return False, "لم يتم العثور على موعد متاح أو تأكيد الحجز"

    def _fetch_otp_code(self, email_target: str, timeout_sec: int = 40) -> Optional[str]:
        """سحب كود OTP فوراً عبر مدير الـ OTP المتصل بخادم البريد وتليجرام"""
        start_t = time.time()
        while time.time() - start_t < timeout_sec:
            if otp_manager:
                q = otp_manager.get_latest_queued_otp()
                if q and q.get("otp"):
                    return str(q["otp"]).strip()

            try:
                import imaplib
                cfg = otp_manager.load_otp_config() if otp_manager else {}
                srv = cfg.get("imap_server", "imap.gmail.com")
                prt = int(cfg.get("imap_port", 993))
                usr = cfg.get("email_user", "mostafasaeedtravel5@gmail.com")
                pwd = cfg.get("email_password", "olszmkakibrwqkgk")

                mail = imaplib.IMAP4_SSL(srv, prt, timeout=8)
                mail.login(usr, pwd)
                mail.select("INBOX")
                status, msgs = mail.search(None, "ALL")
                if status == "OK" and msgs[0]:
                    ids = msgs[0].split()
                    for mid in reversed(ids[-6:]):
                        _, d = mail.fetch(mid, "(RFC822)")
                        raw = d[0][1] if isinstance(d[0], tuple) else None
                        if raw:
                            txt = raw.decode("utf-8", errors="ignore")
                            if any(k in txt.lower() for k in ["nusuk", "نسك", "verification code", "رمز التحقق"]):
                                m = re.search(r"\[\s*(\d{4})\s*\]", txt) or re.search(r"(?:otp|رمز|كود|code)[^\d]{0,25}(\d{4})", txt, re.IGNORECASE)
                                if m:
                                    mail.logout()
                                    return m.group(1)
                mail.logout()
            except Exception:
                pass

            time.sleep(2.0)
        return None

    def _logout(self):
        """تسجيل الخروج من الحساب وفق تسلسل التسجيل البشري الدقيق (الخطوات 55-59)"""
        self.log("🚪 جاري تسجيل الخروج من الحساب وفق التسجيل البشري...")
        # الخطوة 55: أيقونة الملف الشخصي أعلى اليمين عند (851, 102)
        self.adb.tap(851, 102, delay=2.0)

        # الخطوة 58: التمرير والنقر على Sign Out عند (474, 1458)
        self.adb.tap(474, 1458, delay=1.5)

        # الخطوة 59: تأكيد تسجيل الخروج 'Yes, Sign Out' عند (483, 1413)
        self.adb.tap(483, 1413, delay=2.0)
        self.log("✅ تم تسجيل الخروج بنجاح والعودة لشاشة البداية.")
