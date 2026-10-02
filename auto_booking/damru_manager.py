# -*- coding: utf-8 -*-
"""
منظومة حجز الروضة الشريفة - مدير أجهزة Damru & Redroid السحابية الخفية (Damru Cloud Pool Manager)
يتيح إدارة وتشغيل والاتصال بمجموعة هواتف أندرويد سحابية خفية مبنية على Redroid + Damru
بحيث تعمل الحجوزات 100% على السيرفر السحابي بدون استهلاك أي بايت من رامات اللاب توب،
مع تخفٍ كامل من أنظمة كشف المحاكيات (OS-level Device Spoofing).
"""

import os
import re
import time
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from auto_booking.adb_controller import AdbController

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
TOOLS_DIR = PROJECT_ROOT / "auto_booking" / "tools" / "platform-tools"

class DamruDevice:
    """يمثل هاتف سحابي واحد (Damru / Redroid Instance)"""
    def __init__(self, host: str, port: int, device_name: str = ""):
        self.host = host
        self.port = port
        self.serial = f"{host}:{port}"
        self.name = device_name or f"Damru-{port}"
        self.controller = AdbController(serial=self.serial)
        self.is_ready = False
        self.battery = 100
        self.model = "Pixel 7 Pro (Spoofed)"

    def connect(self) -> bool:
        """الاتصال بالجهاز وفحص استجابته"""
        ok = self.controller.connect()
        if ok:
            self.is_ready = self.controller.is_connected()
            if self.is_ready:
                # قراءة موديل الجهاز المستعار من Damru
                out, _ = self.controller.run("shell", "getprop", "ro.product.model")
                if out and out.strip():
                    self.model = out.strip()
        return self.is_ready

    def check_nusuk_installed(self) -> bool:
        """التحقق من تثبيت تطبيق نسك على هذا الجهاز السحابي"""
        out, _ = self.controller.run("shell", "pm", "list", "packages", "com.moh.nusukapp")
        return "com.moh.nusukapp" in out

    def install_nusuk(self, apk_path: str) -> bool:
        """تثبيت تطبيق نسك على الجهاز السحابي عن بُعد"""
        if not os.path.exists(apk_path):
            return False
        out, code = self.controller.run("install", "-r", apk_path)
        return code == 0

class DamruCloudManager:
    """مدير مجموعة الهواتف السحابية (Pool) للحجز المتوازي والسريع"""
    def __init__(self, host: str = "127.0.0.1", base_port: int = 5555, device_count: int = 1):
        self.host = host
        self.base_port = base_port
        self.device_count = device_count
        self.devices: List[DamruDevice] = []
        self._setup_pool()

    def _setup_pool(self):
        """تهيئة قائمة الأجهزة"""
        self.devices = []
        for i in range(self.device_count):
            p = self.base_port + i
            dev = DamruDevice(host=self.host, port=p, device_name=f"هاتف سحابي #{i+1} ({p})")
            self.devices.append(dev)

    def scan_and_connect_all(self) -> List[Dict[str, Any]]:
        """فحص والاتصال بكافة الهواتف السحابية المتوفرة"""
        report = []
        for dev in self.devices:
            connected = dev.connect()
            nusuk_ready = dev.check_nusuk_installed() if connected else False
            report.append({
                "name": dev.name,
                "serial": dev.serial,
                "connected": connected,
                "model": dev.model if connected else "غير متصل",
                "nusuk_installed": nusuk_ready
            })
        return report

    def get_first_ready_device(self) -> Optional[DamruDevice]:
        """الحصول على أول هاتف جاهز للعمل فوراً"""
        for dev in self.devices:
            if dev.is_ready or dev.connect():
                return dev
        return None

    def get_all_ready_controllers(self) -> List[AdbController]:
        """الحصول على جميع متحكمات الأجهزة الجاهزة للحجز المتزامن المتوازي"""
        ready = []
        for dev in self.devices:
            if dev.is_ready or dev.connect():
                ready.append(dev.controller)
        return ready
