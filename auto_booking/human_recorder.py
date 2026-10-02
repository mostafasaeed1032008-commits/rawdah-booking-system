# -*- coding: utf-8 -*-
"""
منظومة حجز الروضة الشريفة - مسجل ومحلل خطوات الخبير البشري لتدريب الذكاء الاصطناعي
Human Action Recorder & Workflow Trainer:
1. يسجل فيديو عالي الدقة لشاشة المحاكي بالكامل (MP4).
2. يلتقط إحداثيات كل نقرة (X, Y) بدقة بيكسل واحدة عبر شاشة اللمس.
3. يحلل شجرة العناصر ونصوص الشاشة لكل خطوة.
4. يولد ملف وصفة الحجز (Workflow Recipe) لتدريب البوت والعقل المدبر على تكرارها بدقة 100%.
"""

import os
import sys
import time
import subprocess
import threading
import json
import re
from pathlib import Path
from typing import Dict, Any, List, Optional

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

CURRENT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = CURRENT_DIR.parent
TRAINING_DIR = CURRENT_DIR / "training_data"
TRAINING_DIR.mkdir(exist_ok=True)

from auto_booking.adb_controller import AdbController


class HumanSessionRecorder:
    def __init__(self, adb_controller=None):
        self.adb = adb_controller or AdbController()
        self.is_recording = False
        self.session_folder: Optional[Path] = None
        self.actions_log: List[Dict[str, Any]] = []
        self.video_proc: Optional[subprocess.Popen] = None
        self.touch_thread: Optional[threading.Thread] = None
        self.snapshot_thread: Optional[threading.Thread] = None
        self.step_counter = 0

    def start_recording(self, session_name: Optional[str] = None) -> Path:
        """بدء جلسة التسجيل الحي لشاشة المحاكي ونقرات المستخدم"""
        if not self.adb.is_connected():
            self.adb.connect()

        t_stamp = time.strftime("%Y-%m-%d_%H-%M-%S")
        name = session_name or f"session_{t_stamp}"
        self.session_folder = TRAINING_DIR / name
        self.session_folder.mkdir(parents=True, exist_ok=True)

        self.is_recording = True
        self.actions_log = []
        self.step_counter = 0

        # تفعيل مؤشر اللمس المرئي ليظهر في الفيديو
        self.adb.run("shell", "settings", "put", "system", "show_touches", "1")

        # 1. إطلاق تسجيل الفيديو عبر screenrecord
        remote_video = "/sdcard/live_training_session.mp4"
        self.adb.run("shell", "rm", "-f", remote_video)
        
        video_cmd = [self.adb.adb]
        if self.adb.serial:
            video_cmd += ["-s", self.adb.serial]
        video_cmd += ["shell", "screenrecord", "--time-limit", "300", "--bit-rate", "4000000", remote_video]
        
        try:
            self.video_proc = subprocess.Popen(video_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            print(f"تنبيه: تعذر إطلاق تسجيل الفيديو: {e}")

        # 2. إطلاق مراقب النقرات وشاشات التفاعل في الخلفية
        self.touch_thread = threading.Thread(target=self._monitor_touch_events, daemon=True)
        self.touch_thread.start()

        # 3. أخذ لقطة البداية
        self._take_snapshot("start_session")

        print(f"🎥 تم بدء تسجيل الجلسة بنجاح! المجلد: {self.session_folder}")
        return self.session_folder

    def _monitor_touch_events(self):
        """مراقبة أحداث اللمس واستخراج إحداثيات كل نقرة حية"""
        cmd = [self.adb.adb]
        if self.adb.serial:
            cmd += ["-s", self.adb.serial]
        # مراقبة event4 (Xiaomi Touchscreen)
        cmd += ["shell", "getevent", "-l", "/dev/input/event4"]

        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
            cur_x = None
            cur_y = None

            for line in proc.stdout:
                if not self.is_recording:
                    break
                line = line.strip()
                if "ABS_MT_POSITION_X" in line:
                    m = re.search(r"([0-9a-fA-F]+)$", line)
                    if m:
                        cur_x = int(m.group(1), 16)
                elif "ABS_MT_POSITION_Y" in line:
                    m = re.search(r"([0-9a-fA-F]+)$", line)
                    if m:
                        cur_y = int(m.group(1), 16)
                elif "SYN_REPORT" in line and cur_x is not None and cur_y is not None:
                    # تم تنفيذ نقرة مكتملة!
                    t_now = time.strftime("%H:%M:%S")
                    print(f"👉 [{t_now}] نقرة حية عند: X={cur_x}, Y={cur_y}")
                    self.step_counter += 1
                    act = {
                        "step": self.step_counter,
                        "time": t_now,
                        "action": "tap",
                        "x": cur_x,
                        "y": cur_y
                    }
                    self.actions_log.append(act)

                    # أخذ لقطة شاشة وشجرة عناصر فورية بعد النقرة
                    threading.Thread(target=self._take_snapshot, args=(f"step_{self.step_counter}_tap_{cur_x}_{cur_y}",), daemon=True).start()

                    cur_x = None
                    cur_y = None
        except Exception:
            pass

    def _take_snapshot(self, tag: str):
        """التقاط لقطة شاشة وحفظ شجرة عناصر الشاشة الحالية"""
        if not self.session_folder:
            return

        idx = self.step_counter
        img_name = f"{idx:03d}_{tag}.png"
        xml_name = f"{idx:03d}_{tag}.xml"

        img_path = str(self.session_folder / img_name)
        xml_path = str(self.session_folder / xml_name)

        # 1. سحب الصورة
        self.adb.run("shell", "screencap", "-p", "/data/local/tmp/rec_screen.png")
        self.adb.run("pull", "/data/local/tmp/rec_screen.png", img_path)

        # 2. سحب العناصر
        self.adb.run("shell", "uiautomator", "dump", "/data/local/tmp/rec_window.xml")
        self.adb.run("pull", "/data/local/tmp/rec_window.xml", xml_path)

        # 3. استخراج النصوص البارزة في الشاشة
        nodes = self.adb.find_all_nodes()
        visible_texts = [n.get("text") or n.get("desc") for n in nodes if n.get("text") or n.get("desc")]
        
        # حفظ بيانات الخطوة
        meta = {
            "step": idx,
            "tag": tag,
            "timestamp": time.time(),
            "visible_texts": visible_texts[:15],
            "screenshot": img_name,
            "xml": xml_name
        }
        with open(self.session_folder / f"{idx:03d}_meta.json", "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

    def stop_recording(self) -> Dict[str, Any]:
        """إيقاف التسجيل وحفظ ملف الفيديو وتوليد تقرير الخطوات لتدريب الذكاء الاصطناعي"""
        self.is_recording = False
        print("\n🛑 جاري إنهاء جلسة التسجيل وحفظ الفيديو والخطوات...")

        # إيقاف عملية تسجيل الفيديو
        if self.video_proc:
            try:
                self.video_proc.terminate()
                self.video_proc.wait(timeout=3)
            except Exception:
                pass

        time.sleep(1.0)

        # سحب ملف الفيديو إلى مجلد الجلسة
        video_local = str(self.session_folder / "expert_session.mp4")
        print("📥 جاري نقل فيديو الجلسة (MP4) من المحاكي إلى الكمبيوتر...")
        self.adb.run("pull", "/sdcard/live_training_session.mp4", video_local, timeout=20.0)

        # توليد تقرير ووصفة الخطوات التدريبية (Training Recipe)
        recipe_path = self.session_folder / "workflow_recipe.json"
        recipe_md_path = self.session_folder / "وصفة_الحجز_المسجلة.md"

        with open(recipe_path, "w", encoding="utf-8") as f:
            json.dump(self.actions_log, f, ensure_ascii=False, indent=2)

        # كتابة ملف Markdown سهل القراءة
        with open(recipe_md_path, "w", encoding="utf-8") as f:
            f.write("# 📋 خطوات وخريطة الحجز المستخرجة من جلسة الخبير البشري\n\n")
            f.write(f"- **تاريخ التسجيل**: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"- **إجمالي الخطوات والنقرات**: {len(self.actions_log)}\n")
            f.write(f"- **ملف الفيديو الكامل**: `expert_session.mp4`\n\n")
            f.write("## 🎯 تسلسل الخطوات والنقرات بالتفصيل:\n\n")
            f.write("| الخطوة | الوقت | نوع الإجراء | الإحداثيات (X, Y) | الوصف المستنتج |\n")
            f.write("| :--- | :--- | :--- | :--- | :--- |\n")
            for a in self.actions_log:
                f.write(f"| {a['step']} | {a['time']} | {a['action']} | ({a['x']}, {a['y']}) | نقرة على الشاشة |\n")

        print(f"🎉 تم الانتهاء بنجاح! تم حفظ الفيديو والخطوات في:\n📁 {self.session_folder}")
        return {
            "folder": str(self.session_folder),
            "video": video_local,
            "total_steps": len(self.actions_log),
            "recipe_md": str(recipe_md_path)
        }


def main():
    recorder = HumanSessionRecorder()
    print("=" * 65)
    print("  🎥 مسجل جلسات الحجز البشري لتدريب روبوت الروضة (AI Trainer)")
    print("=" * 65)
    print("\nسيقوم هذا المسجل بـ:")
    print(" 1. تسجيل فيديو كامل لشاشة المحاكي أثناء قيامك بالحجز.")
    print(" 2. تسجيل كل كليك ونقرة تقوم بها مع إحداثياتها بدقة بيكسل واحدة.")
    print(" 3. أخذ لقطات وحفظ شاشات نسك لتدريب العقل المدبر عليها.")
    print("\nاضغط [ENTER] للبدء في التسجيل والعمل على المحاكي...")
    input()

    folder = recorder.start_recording()
    print("\n🔴 التسجيل يعمل الآن! توجه لمحاكي MuMu Player وقم بالحجز براحتك خطوة خطوة...")
    print("👉 بعد الانتهاء تماماً وتأكيد الحجز، ارجع هنا واضغط [ENTER] لحفظ التدريب...")
    input()

    res = recorder.stop_recording()
    print("\n✅ تم الحفظ والتحليل بنجاح!")
    print(f"📂 مسار التدريب: {res['folder']}")


if __name__ == "__main__":
    main()
