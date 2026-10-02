# -*- coding: utf-8 -*-
"""
خادم التسجيل الحي في الخلفية (Background Live Recorder Daemon)
يبدأ التسجيل فوراً ويستمر في التقاط الفيديو والنقرات والشاشات حتى وصول أمر الإيقاف.
"""

import os
import sys
import time
import json
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

CURRENT_DIR = Path(__file__).parent.resolve()
if str(CURRENT_DIR.parent) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR.parent))

from auto_booking.human_recorder import HumanSessionRecorder

STATUS_FILE = CURRENT_DIR / "cache" / "active_recording.json"
STATUS_FILE.parent.mkdir(exist_ok=True)


def main():
    recorder = HumanSessionRecorder()
    session_folder = recorder.start_recording()

    meta = {
        "is_active": True,
        "folder": str(session_folder),
        "start_time": time.time(),
        "video_pid": recorder.video_proc.pid if recorder.video_proc else None
    }
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"RECORDER_STARTED: {session_folder}")
    sys.stdout.flush()

    # يبقى الخادم نشطاً يستمع للنقرات حتى يتم حذف ملف الحالة أو تغييرها
    try:
        while True:
            if not STATUS_FILE.exists():
                break
            with open(STATUS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if not data.get("is_active", True):
                    break
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass
    finally:
        res = recorder.stop_recording()
        if STATUS_FILE.exists():
            STATUS_FILE.unlink()
        print(f"RECORDER_FINISHED: {res['folder']}")


if __name__ == "__main__":
    main()
