# -*- coding: utf-8 -*-
"""
منظومة حجز الروضة الشريفة - رادار ومرآة مواعيد نسك الحية (Nusuk Slot Radar & Live Mirror)
يتيح سحب وعرض المواعيد المتاحة مباشرة من داخل تطبيق نسك على لوحة التحكم
وكأن التطبيق مفتوح أمام المستخدم ليختار الموعد ويحجز بضغطة زر واحدة.
"""

import os
import re
import time
from typing import Dict, Any, List, Optional
from pathlib import Path

CURRENT_DIR = Path(__file__).parent.resolve()
CACHE_DIR = CURRENT_DIR / "cache"
CACHE_DIR.mkdir(exist_ok=True)

# جدول الفترات الرسمية المعتمدة في تطبيق نسك للروضة الشريفة
NUSUK_OFFICIAL_WINDOWS = {
    "رجال": [
        {"time": "04:00 ص - 05:00 ص", "label": "فجر مبكر 🌙", "period": "الفجر"},
        {"time": "05:00 ص - 06:30 ص", "label": "بعد صلاة الفجر 🌅", "period": "الفجر"},
        {"time": "06:30 ص - 08:30 ص", "label": "الضحى / الصباح ☀️", "period": "الضحى"},
        {"time": "08:00 م - 09:30 م", "label": "بعد صلاة العشاء 🕌", "period": "العشاء"},
        {"time": "09:30 م - 11:00 م", "label": "فترة مسائية أولى 🌌", "period": "العشاء"},
        {"time": "11:00 م - 12:30 ص", "label": "منتصف الليل 🌃", "period": "الليل"}
    ],
    "نساء": [
        {"time": "06:00 ص - 08:00 ص", "label": "بعد صلاة الفجر صباحاً 🌅", "period": "الصباح"},
        {"time": "08:00 ص - 10:30 ص", "label": "فترة الضحى للنساء ☀️", "period": "الضحى"},
        {"time": "09:30 م - 11:00 م", "label": "بعد صلاة العشاء مساءً 🕌", "period": "المساء"},
        {"time": "11:00 م - 12:30 ص", "label": "فترة ليلية للنساء 🌙", "period": "الليل"}
    ]
}


class SlotRadar:
    def __init__(self, adb_controller=None):
        from auto_booking.adb_controller import AdbController
        self.adb = adb_controller or AdbController()

    def capture_live_screen(self, filename: str = "live_radar.png") -> Optional[str]:
        """التقاط صورة شاشة حية من المحاكي وعرضها في لوحة التحكم"""
        if not self.adb.is_connected():
            self.adb.connect()
        if not self.adb.is_connected():
            return None
        return self.adb.screencap(filename)

    def scan_slots_from_app(self, gender: str = "رجال") -> Dict[str, Any]:
        """
        فحص شاشة التطبيق واستخراج المواعيد المتوفرة الحية:
        يتحقق من الشاشة، وإذا كانت الشاشة الرئيسية ينتقل للروضة، ثم يقرأ العناصر المتاحة.
        """
        res: Dict[str, Any] = {
            "connected": False,
            "screen_type": "UNKNOWN",
            "screenshot_path": None,
            "detected_slots": [],
            "available_dates": [],
            "official_suggestions": NUSUK_OFFICIAL_WINDOWS.get("نساء" if "نس" in gender else "رجال", [])
        }

        if not self.adb.is_connected():
            self.adb.connect()

        if not self.adb.is_connected():
            return res

        res["connected"] = True

        # أخذ لقطة حية
        screenshot = self.capture_live_screen("live_radar.png")
        res["screenshot_path"] = screenshot

        # قراءة نصوص وعناصر الشاشة
        nodes = self.adb.find_all_nodes()
        all_text = " ".join([f"{n.get('text', '')} {n.get('desc', '')}" for n in nodes]).lower()

        # استخراج أي مواعيد تظهر في الشاشة (مثل 04:30 AM أو 05:00 ص)
        detected_times = []
        for n in nodes:
            t = (n.get("text") or n.get("desc") or "").strip()
            if ":" in t and any(m in t.upper() for m in ["AM", "PM", "ص", "م"]):
                detected_times.append({
                    "text": t,
                    "center": n.get("center"),
                    "bounds": n.get("bounds")
                })

        # استخراج تواريخ الكالندر
        dates_found = []
        for n in nodes:
            t = (n.get("text") or "").strip()
            # فحص أرقام أيام الشهر (1-31)
            if t.isdigit() and 1 <= int(t) <= 31:
                dates_found.append({"day": t, "center": n.get("center")})

        res["detected_slots"] = detected_times
        res["available_dates"] = dates_found

        if "select time" in all_text or detected_times:
            res["screen_type"] = "CALENDAR_SLOTS"
        elif "males" in all_text or "females" in all_text:
            res["screen_type"] = "WHO_FOR"
        elif "rawdah" in all_text or "trending" in all_text:
            res["screen_type"] = "HOME"
        else:
            res["screen_type"] = "ACTIVE_WINDOW"

        return res
