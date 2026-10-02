# -*- coding: utf-8 -*-
"""
منظومة حجز الروضة الشريفة - المشغل الميداني للحجز الآلي (Booking Runner)
Orchestrates single-instance or parallel multi-clone booking runs
Supervised by the Gemini AI Brain
"""

import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable

CURRENT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = CURRENT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "core_engine") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "core_engine"))

from auto_booking.adb_controller import AdbController
from auto_booking.clone_manager import CloneManager
from auto_booking.nusuk_flow import NusukFlow
from auto_booking.ai_brain import GeminiSupervisor


class BookingRunner:
    def __init__(self, log_callback: Optional[Callable[[str], None]] = None, gemini_key: Optional[str] = None):
        self.log_cb = log_callback
        self.is_running = False
        self.results: List[Dict[str, Any]] = []
        self.supervisor = GeminiSupervisor(api_key=gemini_key, log_callback=self.log)

    def log(self, msg: str):
        t = time.strftime("%H:%M:%S")
        entry = f"[{t}] {msg}"
        print(entry, flush=True)
        if self.log_cb:
            try:
                self.log_cb(entry)
            except Exception:
                pass

    def run_single_pilgrim_test(self, pilgrim_data: Dict[str, Any], session_settings: Dict[str, Any]) -> Dict[str, Any]:
        """
        تشغيل حجز فوري تجريبي لنسخة واحدة فقط (النسخة الرئيسية للمحاكي)
        """
        self.is_running = True
        pilgrim_data.setdefault("password", "Zxcv1234$")
        name = pilgrim_data.get("name", "معتمر")
        self.log(f"🚀 بدء التشغيل التجريبي للمعتمر: {name} بإشراف العقل المدبر...")

        adb = AdbController()
        if not adb.is_connected():
            self.log("⏳ محاولة الاتصال بالمحاكي (127.0.0.1:16384)...")
            adb.connect()

        if not adb.is_connected():
            self.log("❌ تعذر الاتصال بمحاكي MuMu. تأكد من فتح المحاكي أولاً.")
            self.is_running = False
            return {"status": "FAILED", "reason": "المحاكي غير متصل"}

        self.log("🟢 المحاكي متصل بنجاح! جاري تشغيل تطبيق نسك...")
        adb.launch_app()
        time.sleep(3.5)

        flow = NusukFlow(adb, supervisor=self.supervisor, log_callback=self.log)
        ok, details = flow.execute_booking(pilgrim_data, session_settings)

        res = {
            "name": name,
            "status": "SUCCESS" if ok else "FAILED",
            "details": details,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        self.results.append(res)
        self.is_running = False
        return res

    def run_with_natural_instructions(self, trip_instruction_prompt: str, pilgrims: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        تشغيل الحجز بناءً على تعليمات الرحلة باللغة العربية الطبيعية كما لو كنت تخاطب موظفاً!
        يقوم العقل المدبر بفهم النص، واستخراج التاريخ، والصلاة، والأولوية، وتوزيع الحجز فوراً.
        """
        self.log(f"🗣 تلقي تعليمات الرحلة: '{trip_instruction_prompt}'")
        parsed_settings = self.supervisor.interpret_trip_prompt(trip_instruction_prompt)

        num_clones = parsed_settings.get("num_clones", 10)
        return self.run_multi_clone_batch(
            pilgrims=pilgrims,
            num_clones=num_clones,
            session_settings=parsed_settings
        )

    def organize_pilgrims(self, pilgrims: List[Dict[str, Any]], priority: str = "نساء_أولا", link_children: bool = True) -> List[Dict[str, Any]]:
        """
        ترتيب المعتمرين وربط الأطفال:
        - الأطفال الذكور (طفل) مع الرجال
        - الأطفال الإناث (طفلة) مع النساء
        - تقديم النساء أولاً أو الرجال أولاً
        """
        men = []
        women = []
        male_children = []
        female_children = []

        for p in pilgrims:
            ptype = str(p.get("person_type", "")).strip()
            if "طفلة" in ptype or ("بنت" in ptype):
                female_children.append(p)
            elif "طفل" in ptype or ("ولد" in ptype):
                male_children.append(p)
            elif "نس" in ptype or "fem" in ptype.lower():
                women.append(p)
            else:
                men.append(p)

        # ربط الأطفال بالمرافقين
        if link_children:
            for idx, c in enumerate(male_children):
                if men:
                    target_man = men[idx % len(men)]
                    target_man.setdefault("dependents", []).append(c)
                else:
                    men.append(c)

            for idx, c in enumerate(female_children):
                if women:
                    target_woman = women[idx % len(women)]
                    target_woman.setdefault("dependents", []).append(c)
                else:
                    women.append(c)
        else:
            men.extend(male_children)
            women.extend(female_children)

        # الترتيب حسب الأولوية
        if priority == "نساء_أولا":
            return women + men
        elif priority == "رجال_أولا":
            return men + women
        else:
            return pilgrims

    def run_multi_clone_batch(self, pilgrims: List[Dict[str, Any]], num_clones: int = 10, session_settings: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        تشغيل الحجز المتوازي على عدد محدد من النسخ (حتى 10 نسخ)
        """
        self.is_running = True
        session_settings = session_settings or {}
        organized = self.organize_pilgrims(
            pilgrims,
            priority=session_settings.get("priority", "نساء_أولا"),
            link_children=session_settings.get("link_children", True)
        )

        self.log(f"🚀 بدء حملة الحجز الآلي على {num_clones} نسخة متزامنة لـ {len(organized)} معتمر تحت إشراف العقل المدبر...")
        self.results = []

        def worker(p_data, clone_idx):
            adb = AdbController()
            flow = NusukFlow(adb, supervisor=self.supervisor, log_callback=self.log)
            ok, det = flow.execute_booking(p_data, session_settings)
            return {"name": p_data.get("name"), "status": "SUCCESS" if ok else "FAILED", "details": det}

        with ThreadPoolExecutor(max_workers=min(num_clones, len(organized) or 1)) as executor:
            futures = [executor.submit(worker, p, i % num_clones) for i, p in enumerate(organized)]
            for f in futures:
                self.results.append(f.result())

        self.is_running = False
        return self.results
