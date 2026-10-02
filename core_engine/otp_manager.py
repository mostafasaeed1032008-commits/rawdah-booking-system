# -*- coding: utf-8 -*-
"""
منظومة حجز الروضة الشريفة - مدير أكواد التحقق السريع (OTP Manager)
-----------------------------------------------------------------
يربط بين مصادر استلام الأكواد المتعددة:
1. خادم البريد المباشر (IMAP)
2. بوت التليجرام (عند إرسال أو توجيه الكود للبوت)
3. لوحة التحكم (Streamlit Dashboard)
4. الأداة العائمة بجوار المحاكي (Mini Floating Tool)
"""

import json
import time
from pathlib import Path
from typing import Optional, Dict, Any

CORE_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = CORE_DIR.parent
OTP_QUEUE_FILE = CORE_DIR / "otp_queue.json"
OTP_CONFIG_FILE = PROJECT_ROOT / "otp_tool" / "mini_otp_config.json"

DEFAULT_CONFIG = {
    "imap_server": "imap.gmail.com",
    "imap_port": 993,
    "email_user": "mostafasaeedtravel5@gmail.com",
    "email_password": "olszmkakibrwqkgk",
    "always_on_top": True,
    "auto_copy": True,
    "general_mode": True,
    "sound_enabled": True
}

def load_otp_config() -> dict:
    if OTP_CONFIG_FILE.exists():
        try:
            data = json.loads(OTP_CONFIG_FILE.read_text(encoding="utf-8"))
            return {**DEFAULT_CONFIG, **data}
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()

def save_otp_config(cfg: dict) -> bool:
    try:
        OTP_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        OTP_CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    except Exception:
        return False

def push_otp(code: str, source: str = "تليجرام / لوحة التحكم", recipient: str = "") -> bool:
    """إرسال كود OTP جديد إلى الطابور اللحظي لتلتقطه الأداة العائمة فوراً"""
    clean_code = str(code).strip()
    if not clean_code:
        return False
    
    payload = {
        "otp": clean_code,
        "source": source,
        "recipient": recipient or "نسك (Nusuk)",
        "timestamp": time.time(),
        "time_str": time.strftime("%I:%M:%S %p")
    }
    
    try:
        OTP_QUEUE_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    except Exception as e:
        print(f"Error pushing OTP: {e}")
        return False

def get_latest_queued_otp() -> Optional[Dict[str, Any]]:
    """قراءة أحدث كود OTP موجود في الطابور اللحظي"""
    if not OTP_QUEUE_FILE.exists():
        return None
    try:
        data = json.loads(OTP_QUEUE_FILE.read_text(encoding="utf-8"))
        # إذا كان الكود مر عليه أكثر من 5 دقائق نتجاهله
        if time.time() - data.get("timestamp", 0) < 300:
            return data
    except Exception:
        pass
    return None
