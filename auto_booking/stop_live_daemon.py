# -*- coding: utf-8 -*-
"""
إيقاف تسجيل الجلسة واستخراج التقرير
"""

import json
from pathlib import Path

CURRENT_DIR = Path(__file__).parent.resolve()
STATUS_FILE = CURRENT_DIR / "cache" / "active_recording.json"


def stop_daemon():
    if STATUS_FILE.exists():
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["is_active"] = False
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        print("STOP_SIGNAL_SENT")
    else:
        print("NO_ACTIVE_RECORDING")


if __name__ == "__main__":
    stop_daemon()
