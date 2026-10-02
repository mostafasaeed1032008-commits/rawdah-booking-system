# -*- coding: utf-8 -*-
"""
منظومة حجز الروضة الشريفة - العقل المدبر ومراقب الذكاء الاصطناعي (Gemini AI Brain & Supervisor)
المسؤول عن:
1. فهم تعليمات الرحلة باللغة العربية الطبيعية (Natural Language Trip Interpreter).
2. الإشراف اللحظي على شاشات التطبيق وتوجيه البوت بالقرارات الصحيحة (Screen Supervisor).
3. معالجة الحالات الشاذة والأخطاء واختيار المواعيد بذكاء.
"""

import os
import sys
import re
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple, Callable

# المفتاح الافتراضي المقدم من المستخدم
DEFAULT_GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")

# المكتبات المدعومة
try:
    import google.generativeai as genai_legacy
except ImportError:
    genai_legacy = None

try:
    from google import genai
except ImportError:
    genai = None


class GeminiSupervisor:
    """
    العقل المدبر المشرف على حجز الروضة الشريفة.
    يعمل بنظام هجين (Hybrid Architecture):
    - ذكاء اصطناعي فائق عبر Gemini API (سحابي).
    - محرك قواعد ومعالجة لغة عربية متقدم محلي فائق السرعة (Local Engine) لضمان العمل اللحظي دون أي تأخير أو انقطاع.
    """

    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-3.5-flash-lite", log_callback: Optional[Callable[[str], None]] = None):
        self.api_key = (api_key or DEFAULT_GEMINI_KEY).strip()
        self.model_name = model_name
        self.log_cb = log_callback
        self.is_gemini_active = False
        self.client = None

        if self.api_key:
            os.environ["GOOGLE_API_KEY"] = self.api_key
            os.environ["GEMINI_API_KEY"] = self.api_key

        self._init_gemini()

    def log(self, msg: str):
        t = time.strftime("%H:%M:%S")
        entry = f"[{t}] [🧠 العقل المدبر]: {msg}"
        print(entry, flush=True)
        if self.log_cb:
            try:
                self.log_cb(entry)
            except Exception:
                pass

    def _init_gemini(self):
        """تهيئة الاتصال بنموذج Gemini واختبار الصلاحية"""
        if not self.api_key:
            self.log("ℹ يعمل العقل المدبر بالمحرك المحلي فائق السرعة.")
            return

        # 1. تهيئة google.genai الحديثة
        if genai:
            try:
                self.client = genai.Client(api_key=self.api_key)
                self.is_gemini_active = True
                self.log("🟢 تم ربط محرك Google GenAI بنجاح.")
                return
            except Exception as e:
                pass

        # 2. تهيئة google.generativeai
        if genai_legacy:
            try:
                genai_legacy.configure(api_key=self.api_key)
                self.is_gemini_active = True
                self.log("🟢 تم ربط محرك Google GenerativeAI بنجاح.")
                return
            except Exception as e:
                pass

        self.is_gemini_active = False

    def test_connection(self) -> Tuple[bool, str]:
        """فحص حي لصلاحية الاتصال بـ Gemini API"""
        if not self.api_key:
            return False, "مفتاح API غير موجود"

        try:
            if genai:
                client = genai.Client(api_key=self.api_key)
                resp = client.models.generate_content(
                    model=self.model_name,
                    contents="جاهز؟ رد بكلمة نعم"
                )
                if resp and resp.text:
                    self.is_gemini_active = True
                    return True, f"متصل بنجاح مع {self.model_name}: {resp.text.strip()}"
        except Exception as e:
            err_msg = str(e)
            if "PERMISSION_DENIED" in err_msg or "403" in err_msg:
                self.is_gemini_active = False
                return False, "تم رفض الوصول (403 Permission Denied) لهذا المشروع من Google. يعمل العقل المدبر بالمحرك المحلي الفوري (Zero Latency)."
            self.is_gemini_active = False
            return False, f"خطأ الاتصال بـ Gemini: {err_msg[:120]}"

        return False, "مكتبة Google GenAI غير مهيأة"

    # =========================================================================
    # 1. فهم تعليمات الرحلة باللغة الطبيعية (Natural Language Trip Parser)
    # =========================================================================
    def interpret_trip_prompt(self, user_prompt: str) -> Dict[str, Any]:
        """
        يترجم أوامر المستخدم باللغة العربية كأنه يكلم موظفاً (مثل:
        'احجز لحملة النور يوم السبت الجاي بعد العصر، النساء أولاً والأطفال مع أمهاتهم')
        إلى كائن بيانات تنفيذي دقيق يتحكم في البوت.
        """
        self.log(f"📝 استلام تعليمات الرحلة: '{user_prompt}'")

        # 1. تجربة سحابية إذا كانت مفعلة ونشطة
        if self.is_gemini_active:
            try:
                ai_res = self._ask_gemini_trip_parser(user_prompt)
                if ai_res and isinstance(ai_res, dict):
                    self.log(f"✅ تم تحليل التعليمات عبر Gemini سحابياً: {json.dumps(ai_res, ensure_ascii=False)}")
                    return ai_res
            except Exception as e:
                # إيقاف المحاولات السحابية اللاحقة لتفادي أي انتظار زمني
                self.is_gemini_active = False
                self.log(f"⚡ تحويل التوجيه إلى المحرك المحلي اللحظي الفوري...")

        # 2. المحرك المحلي فائق السرعة والدقة (Instant 0.01s)
        parsed = self._local_arabic_trip_parser(user_prompt)
        self.log(f"✅ تم استخراج أوامر التنفيذ بدقة: موعد: {parsed['target_date']} ({parsed['prayer_window']}) | أولوية: {parsed['priority']}")
        return parsed

    def _ask_gemini_trip_parser(self, prompt: str) -> Optional[Dict[str, Any]]:
        """طلب تحليل التعليمات من Gemini API"""
        system_instruction = (
            "أنت المساعد الذكي والمشرف على منظومة حجز الروضة الشريفة بتطبيق نسك. "
            "قم بتحليل تعليمات المستخدم باللغة العربية وتحويلها إلى JSON فقط بالصيغة التالية:\n"
            "{\n"
            '  "target_date": "YYYY-MM-DD أو أول موعد متاح",\n'
            '  "prayer_window": "الفجر / الظهر / العصر / المغرب / العشاء / أي وقت",\n'
            '  "priority": "نساء_أولا أو رجال_أولا أو ترتيب_الكشف",\n'
            '  "link_children": true / false,\n'
            '  "auto_logout": true / false,\n'
            '  "company_name": "اسم الحملة أو الشركة إن وجدت أو فارغ",\n'
            '  "num_clones": عدد النسخ المقترح (1-10)\n'
            "}"
        )
        query = f"{system_instruction}\n\nتعليمات المستخدم: {prompt}\nJSON Response:"

        if self.client and hasattr(self.client, "models"):
            resp = self.client.models.generate_content(
                model=self.model_name,
                contents=query
            )
            txt = resp.text.strip()
            json_match = re.search(r"\{.*\}", txt, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
        return None

    def _local_arabic_trip_parser(self, text: str) -> Dict[str, Any]:
        """
        محلل قواعد لغة عربية متقدم يفهم كل صيغ شركات السياحة والحملات المصرية والسعودية
        """
        clean = text.strip().lower()
        now = datetime.now()

        # 1. استخراج التاريخ المستهدف
        target_date = ""
        date_explicit = re.search(r"\b(202\d[-/]\d{1,2}[-/]\d{1,2})\b", clean)
        if date_explicit:
            target_date = date_explicit.group(1).replace("/", "-")
        else:
            if "النهارده" in clean or "اليوم" in clean:
                target_date = now.strftime("%Y-%m-%d")
            elif "بكرة" in clean or "غدا" in clean or "غداً" in clean:
                target_date = (now + timedelta(days=1)).strftime("%Y-%m-%d")
            elif "بعد بكرة" in clean:
                target_date = (now + timedelta(days=2)).strftime("%Y-%m-%d")
            else:
                days_map = {
                    "السبت": 5, "الأحد": 6, "الاحد": 6, "الاثنين": 0, "الإثنين": 0,
                    "الثلاثاء": 1, "الأربعاء": 2, "الاربعاء": 2, "الخميس": 3, "الجمعة": 4
                }
                for day_name, target_weekday in days_map.items():
                    if day_name in clean:
                        cur_weekday = now.weekday()
                        days_ahead = (target_weekday - cur_weekday) % 7
                        if days_ahead == 0 and ("الجاي" in clean or "القادم" in clean):
                            days_ahead = 7
                        target_date = (now + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
                        break

        # 2. تحديد نافذة الصلاة أو الوقت
        prayer_window = "أي وقت متاح"
        if "فجر" in clean:
            prayer_window = "الفجر"
        elif "ضحى" in clean or "صبح" in clean:
            prayer_window = "الضحى"
        elif "ظهر" in clean:
            prayer_window = "الظهر"
        elif "عصر" in clean:
            prayer_window = "العصر"
        elif "مغرب" in clean:
            prayer_window = "المغرب"
        elif "عشاء" in clean or "عشا" in clean or "ليل" in clean:
            prayer_window = "العشاء"

        # 3. أولوية الحجز (رجال / نساء)
        priority = "نساء_أولا"
        if any(w in clean for w in ["رجال أولا", "رجال اول", "ابدأ بالرجال", "الرجالة الأول", "ذكور أولا"]):
            priority = "رجال_أولا"
        elif any(w in clean for w in ["نساء أولا", "حريم أولا", "الستات الأول", "ابدأ بالحريم", "بنات أولا"]):
            priority = "نساء_أولا"
        elif "ترتيب الكشف" in clean or "بدون أولوية" in clean:
            priority = "ترتيب_الكشف"

        # 4. ربط الأطفال
        link_children = True
        if "بدون ربط" in clean or "متربطش" in clean or "فصل الأطفال" in clean:
            link_children = False

        # 5. تسجيل الخروج التلقائي
        auto_logout = True
        if "متخرجش" in clean or "سيب الحساب مفتوح" in clean or "بدون تسجيل خروج" in clean:
            auto_logout = False

        # 6. استخراج اسم الشركة أو الحملة
        company_name = ""
        comp_match = re.search(r"(?:حملة|شركة|فوج|كشف)\s+([^\s,،]+)", clean)
        if comp_match:
            company_name = comp_match.group(1).strip()

        # 7. عدد النسخ المقترح
        num_clones = 10
        clones_match = re.search(r"(\d+)\s*(?:نسخ|نسخة|محاكي|كلون)", clean)
        if clones_match:
            try:
                num_clones = max(1, min(10, int(clones_match.group(1))))
            except ValueError:
                num_clones = 10

        return {
            "target_date": target_date or "أول موعد متاح",
            "prayer_window": prayer_window,
            "priority": priority,
            "link_children": link_children,
            "auto_logout": auto_logout,
            "company_name": company_name,
            "num_clones": num_clones,
            "raw_prompt": text
        }

    # =========================================================================
    # 1.1 استخراج بيانات المعتمرين بالذكاء الاصطناعي (Smart Pilgrim NLP Extractor)
    # =========================================================================
    def extract_pilgrims_from_text(self, text: str) -> List[Dict[str, Any]]:
        """
        استخراج بيانات المعتمرين من أي نص عشوائي أو رسائل واتساب عبر Gemini أو المحرك المحلي
        """
        if not text or not text.strip():
            return []

        # 1. محاولة استخراج ذكي عبر Gemini
        if self.is_gemini_active and self.client and hasattr(self.client, "models"):
            try:
                system_instruction = (
                    "أنت خبير استخراج وتدقيق بيانات معتمري الروضة الشريفة بتطبيق نسك. "
                    "قم باستخراج بيانات المعتمرين من النص التالي وتنسيقها في مصفوفة JSON من الكائنات:\n"
                    "كل كائن يحتوي على:\n"
                    "- name: اسم المعتمر\n"
                    "- passport: رقم الجواز\n"
                    "- visa: رقم التأشيرة (10 أرقام)\n"
                    "- gender: 'رجال' أو 'نساء' أو 'طفل' أو 'طفلة'\n"
                    "أرجع JSON فقط بصيغة [ {...} ] دون أي نصوص إضافية."
                )
                resp = self.client.models.generate_content(
                    model=self.model_name,
                    contents=f"{system_instruction}\n\nالنص المطلوب تحليله:\n{text}"
                )
                if resp and resp.text:
                    m = re.search(r"\[\s*\{.*\}\s*\]", resp.text, re.DOTALL)
                    if m:
                        data = json.loads(m.group(0))
                        if isinstance(data, list) and len(data) > 0:
                            from auto_booking.pilgrim_importer import _clean_pilgrim_records
                            return _clean_pilgrim_records(data)
            except Exception as e:
                self.log(f"⚡ التبديل للمحلل المحلي للاستخراج: {e}")

        # 2. الاستخراج المحلي كبديل فوري
        from auto_booking.pilgrim_importer import parse_pasted_text
        return parse_pasted_text(text)

    # =========================================================================
    # 1.2 تقديم المشورة والتوجيه الذكي للمعتمر (Smart Slot Recommendation)
    # =========================================================================
    def recommend_best_slot_and_timing(self, pilgrim_info: Dict[str, Any], user_hint: str = "") -> Dict[str, Any]:
        """
        يقوم العقل المدبر بتحليل المعتمر واقتراح أفضل توقيت وتاريخ مناسب لنسك
        """
        gender = pilgrim_info.get("gender", "رجال")
        is_female = any(k in gender for k in ["نس", "fem", "طفلة", "بنت"])

        interpreted = self.interpret_trip_prompt(user_hint) if user_hint else {}
        target_date = interpreted.get("target_date", "")
        if target_date == "أول موعد متاح":
            target_date = ""

        prayer_win = interpreted.get("prayer_window", "")

        if is_female:
            # النساء: (05:40 AM - 08:40 AM ص)
            recommended_slot = "06:00 AM (الفجر - الضحى)"
            advice = f"المعتمرة ({pilgrim_info.get('name', 'أنثى')}): تم توجيه الحجز إلى الفترة الصباحية للنساء (06:00 AM) وهي الأنسب تنظيماً وأقل ازدحاماً وفق شروط نسك."
            prayer_target = "الفجر"
        else:
            # الرجال: (09:00 AM - 11:00 AM أو 04:00 AM)
            if "فجر" in prayer_win or "ليل" in prayer_win or "سحر" in prayer_win:
                recommended_slot = "04:00 AM (منتصف الليل - الفجر)"
                prayer_target = "Midnight"
                advice = f"المعتمر ({pilgrim_info.get('name', 'ذكر')}): تم توجيه الحجز لفترة السحر/الفجر (04:00 AM) المطابقة تماماً لخطوات التسجيل البشري الخبير."
            else:
                recommended_slot = "09:20 AM (الضحى)"
                prayer_target = "الضحى"
                advice = f"المعتمر ({pilgrim_info.get('name', 'ذكر')}): تم توجيه الحجز إلى فترة الضحى (09:20 AM) لتفادي أوقات الذروة والتكدس."

        return {
            "target_date": target_date,
            "target_slot": recommended_slot,
            "prayer_window": prayer_target,
            "advice": advice
        }

    # =========================================================================
    # 2. الإشراف اللحظي على الشاشات وقرارات البوت (Screen Decision Supervisor)
    # =========================================================================
    def supervise_screen_action(
        self,
        screen_type_name: str,
        screen_nodes: List[Dict[str, Any]],
        pilgrim_info: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        يتخذ القرار الفوري المشرف (Sub-second Decision) على الشاشة الحالية:
        يحدد الخطوة التالية بدقة ويحل المعضلات مثل:
        - هل نختار Register أم Login؟
        - ماذا نفعل لو ظهر خطأ 'Account already exists'؟
        - اختيار الموعد المناسب لنافذة الصلاة المحددة.
        """
        all_text = " ".join([f"{n.get('text', '')} {n.get('desc', '')}" for n in screen_nodes]).lower()
        is_registered = pilgrim_info.get("is_registered", False)

        # قرار 1: شاشة الاختيار (Auth Modal)
        if screen_type_name == "AUTH_MODAL":
            if is_registered:
                return {
                    "action": "click_text",
                    "target": "Login with Email",
                    "fallback_coords": (235, 1200),
                    "reason": "المعتمر يمتلك حساباً مسبقاً، الدخول بالبريد الإلكتروني."
                }
            else:
                return {
                    "action": "click_text",
                    "target": "Register New Account",
                    "fallback_coords": (450, 1394),
                    "reason": "المعتمر جديد، الانتقال فوراً لنموذج إنشاء الحساب."
                }

        # قرار 2: معالجة خطأ 'Account already exists' أو 'This ID Already Exists'
        if any(err in all_text for err in ["already exists", "account exists", "this id already exists", "linked to another account", "مسجل مسبقا", "البريد مسجل"]):
            self.log("💡 اكتشاف أن بيانات المعتمر (الجواز أو الإيميل) مسجلة مسبقاً بنسك! التبديل الذكي فوراً إلى تسجيل الدخول...")
            pilgrim_info["is_registered"] = True
            return {
                "action": "click_text",
                "target": "Logout & Recover Your Account",
                "fallback_coords": (450, 1423),
                "reason": "استعادة الحساب وتسجيل الدخول بعد اكتشاف تسجيل الهوية مسبقاً."
            }

        # قرار 2.1: شاشة إكمال الملف الشخصي (Complete Your Profile)
        if any(k in all_text for k in ["complete your profile", "complete profile", "build your profile"]):
            if "select id type" in all_text:
                return {
                    "action": "tap",
                    "coords": (272, 725),
                    "reason": "اختيار فئة الزوار الدوليين (International or GCC Visitor)."
                }
            elif "select your nationality" in all_text:
                return {
                    "action": "fill_visitor_profile",
                    "reason": "استكمال بيانات الزائر الدولي (الجنسية، رقم الجواز، والتأشيرة)."
                }

        # قرار 3: شاشة المواعيد والكالندر
        if screen_type_name == "CALENDAR_SLOTS":
            prayer_target = context.get("prayer_window", "أي وقت متاح")
            matched_node = None
            any_available_node = None

            for n in screen_nodes:
                t = n.get("text", "")
                if ":" in t and any(m in t for m in ["AM", "PM", "ص", "م"]):
                    any_available_node = n
                    if self._matches_prayer(t, prayer_target):
                        matched_node = n
                        break

            chosen = matched_node or any_available_node
            if chosen:
                return {
                    "action": "tap_node",
                    "node": chosen,
                    "reason": f"تم اختيار الموعد ({chosen.get('text')}) المطابق لطلب المستخدم."
                }
            else:
                return {
                    "action": "tap",
                    "coords": (450, 800),
                    "reason": "لم يتوفر موعد في اليوم الحالي، الضغط على اليوم المتاح التالي بالكالندر."
                }

        # قرار 3.1: نافذة تأكيد الحجز النهائية (Your Blessed Visit Bottom Sheet)
        if screen_type_name == "CONFIRMATION_SHEET" or any("your blessed visit" in n.get("text", "").lower() for n in screen_nodes):
            return {
                "action": "tap",
                "coords": (450, 1440),
                "reason": "تأكيد الحجز النهائي من القائمة المنبثقة بالأسفل (الخطوة 51 من التسجيل البشري)."
            }

        # قرار 3.2: نافذة تقييم التجربة (Rate Your Experience)
        if screen_type_name == "RATING_MODAL" or any("remind me later" in n.get("text", "").lower() for n in screen_nodes):
            return {
                "action": "tap",
                "coords": (450, 1534),
                "reason": "إغلاق نافذة التقييم فوراً عبر الضغط على Remind me later."
            }

        # قرار 4: شاشة مجهولة أو تنبيه منبثق مفاجئ
        if screen_type_name == "UNEXPECTED":
            for ok_btn in ["ok", "agree", "continue", "موافق", "استمرار", "حسنا", "تأكيد", "dismiss", "close", "إلغاء"]:
                for n in screen_nodes:
                    if ok_btn in n.get("text", "").lower() or ok_btn in n.get("desc", "").lower():
                        return {
                            "action": "tap_node",
                            "node": n,
                            "reason": f"حل التنبيه المنبثق بالنقر على '{ok_btn}'."
                        }

            return {
                "action": "keyevent",
                "keycode": 4,  # KEYCODE_BACK
                "reason": "شاشة غير متوقعة، الرجوع للخلف خطوة واحدة للعودة للمسار."
            }

        return {
            "action": "standard_flow",
            "reason": "متابعة المسار القياسي فائق السرعة."
        }

    def _matches_prayer(self, slot_str: str, prayer_name: str) -> bool:
        """مطابقة الموعد مع وقت الصلاة المطلوب"""
        if prayer_name == "أي وقت متاح" or not prayer_name:
            return True

        m = re.search(r"(\d{1,2}):(\d{2})\s*(AM|PM|ص|م)?", slot_str, re.IGNORECASE)
        if not m:
            return True

        hour = int(m.group(1))
        meridiem = (m.group(3) or "").upper()
        if meridiem in ["PM", "م"] and hour < 12:
            hour += 12
        elif meridiem in ["AM", "ص"] and hour == 12:
            hour = 0

        if prayer_name == "الفجر" and 3 <= hour <= 6:
            return True
        elif prayer_name == "الضحى" and 7 <= hour <= 11:
            return True
        elif prayer_name == "الظهر" and 12 <= hour <= 14:
            return True
        elif prayer_name == "العصر" and 15 <= hour <= 17:
            return True
        elif prayer_name == "المغرب" and 17 <= hour <= 19:
            return True
        elif prayer_name == "العشاء" and (20 <= hour or hour <= 2):
            return True

        return False
