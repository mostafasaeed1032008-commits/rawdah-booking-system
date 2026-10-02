# -*- coding: utf-8 -*-
"""
منظومة حجز الروضة الشريفة - وحدة التحكم في أجهزة ومحاكي الأندرويد (ADB Controller)
Low-level ADB Controller for MuMu Player and Android Devices
"""

import os
import re
import shutil
import subprocess
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any

TOOLS_ADB = str(Path(__file__).parent / "tools" / "platform-tools" / "adb.exe")

POSSIBLE_ADB_PATHS = [
    TOOLS_ADB,
    r"C:\Program Files\Netease\MuMuPlayer\nx_device\15.0\shell\adb.exe",
    r"C:\Program Files\Netease\MuMuPlayer\nx_main\adb.exe",
    r"C:\Program Files\Netease\MuMuPlayerGlobal\nx_device\15.0\shell\adb.exe",
    r"C:\Program Files (x86)\Netease\MuMuPlayer\nx_device\15.0\shell\adb.exe",
]

COMMON_MUMU_SERIALS = [
    "127.0.0.1:16384",  # MuMu 12 Instance 0
    "127.0.0.1:7555",   # MuMu 6 / Classic
    "127.0.0.1:16416",  # MuMu Instance 1
    "127.0.0.1:16448",  # MuMu Instance 2
    "127.0.0.1:5555",
    "emulator-5554"
]

class AdbController:
    def __init__(self, adb_path: str = "", serial: str = "", package_name: str = "com.moh.nusukapp"):
        if adb_path and (":" in adb_path or "emulator" in adb_path):
            serial = adb_path
            adb_path = ""
        self.adb = adb_path or self._find_adb()
        self.serial = serial or self._detect_active_device()
        self.package = package_name
        self.cache_dir = Path(__file__).parent / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.last_ui_root: Optional[ET.Element] = None
        # ضمان الاتصال النشط مباشرة عند التهيئة
        self._ensure_connected()

    def _find_adb(self) -> str:
        for p in POSSIBLE_ADB_PATHS:
            if os.path.exists(p):
                return p
        which_adb = shutil.which("adb")
        if which_adb:
            return which_adb
        return "adb"

    def _detect_active_device(self) -> str:
        """اكتشاف تلقائي للجهاز المتصل عبر ADB"""
        try:
            res = subprocess.run([self.adb, "devices"], capture_output=True, text=True, timeout=5.0, encoding="utf-8", errors="replace")
            for line in res.stdout.splitlines()[1:]:
                parts = line.strip().split()
                if len(parts) >= 2 and parts[1] == "device":
                    return parts[0]
        except Exception:
            pass

        # محاولة الاتصال بالمنافذ الشائعة لـ MuMu
        for s in COMMON_MUMU_SERIALS:
            try:
                res = subprocess.run([self.adb, "connect", s], capture_output=True, text=True, timeout=3.0, encoding="utf-8", errors="replace")
                if "connected" in res.stdout.lower() or "already" in res.stdout.lower():
                    return s
            except Exception:
                pass

        return "127.0.0.1:16384"

    def _ensure_connected(self):
        """ضمان الاتصال النشط بالجهاز في نفس العملية"""
        try:
            # اتصال مباشر بالـ serial المختار
            if self.serial:
                subprocess.run(
                    [self.adb, "connect", self.serial],
                    capture_output=True, text=True, timeout=5.0,
                    encoding="utf-8", errors="replace"
                )
        except Exception:
            pass

    def run(self, *args, timeout: float = 8.0) -> Tuple[str, int]:
        cmd = [self.adb]
        if self.serial:
            cmd += ["-s", self.serial]
        cmd += list(args)
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")
            return res.stdout + res.stderr, res.returncode
        except subprocess.TimeoutExpired:
            return "TIMEOUT", -1
        except Exception as e:
            return str(e), -1

    def is_connected(self) -> bool:
        out, code = self.run("get-state", timeout=3.0)
        return "device" in out.lower()

    def connect(self) -> bool:
        if not self.serial:
            self.serial = self._detect_active_device()
        out, code = self.run("connect", self.serial, timeout=5.0)
        return self.is_connected()

    def screencap(self, filename: str = "current_screen.png") -> str:
        """أخذ لقطة شاشة وحفظها محلياً"""
        local_path = str(self.cache_dir / filename)
        remote_path = "/data/local/tmp/screen.png"
        self.run("shell", "screencap", "-p", remote_path, timeout=5.0)
        self.run("pull", remote_path, local_path, timeout=5.0)
        return local_path

    def dump_ui(self) -> Optional[ET.Element]:
        """سحب شجرة العناصر التفاعلية للشاشة الحالية"""
        remote_xml = "/data/local/tmp/window_dump.xml"
        local_xml = str(self.cache_dir / "window_dump.xml")

        self.run("shell", "uiautomator", "dump", remote_xml, timeout=5.0)
        _, code = self.run("pull", remote_xml, local_xml, timeout=4.0)

        if code == 0 and os.path.exists(local_xml):
            try:
                tree = ET.parse(local_xml)
                self.last_ui_root = tree.getroot()
                return self.last_ui_root
            except Exception:
                pass
        return None

    def find_all_nodes(self) -> List[Dict[str, Any]]:
        """استخراج كافة عناصر الشاشة مع إحداثياتها ونصوصها"""
        root = self.dump_ui()
        if root is None:
            return []

        results = []
        for elem in root.iter():
            text = elem.get("text", "")
            desc = elem.get("content-desc", "")
            res_id = elem.get("resource-id", "")
            bounds = elem.get("bounds", "")

            center = None
            if bounds:
                m = re.findall(r"\[(\d+),(\d+)\]", bounds)
                if len(m) == 2:
                    center = ((int(m[0][0]) + int(m[1][0])) // 2, (int(m[0][1]) + int(m[1][1])) // 2)

            if text or desc or res_id:
                results.append({
                    "text": text,
                    "desc": desc,
                    "id": res_id,
                    "bounds": bounds,
                    "center": center,
                    "clickable": elem.get("clickable", "false") == "true"
                })
        return results

    def find_node(self, text: str = "", resource_id: str = "", desc: str = "") -> Optional[Dict[str, Any]]:
        """البحث عن عنصر محدد ومطابق في الشاشة"""
        nodes = self.find_all_nodes()
        t_low = text.lower() if text else ""
        r_low = resource_id.lower() if resource_id else ""
        d_low = desc.lower() if desc else ""

        for n in nodes:
            if t_low and t_low in n["text"].lower():
                return n
            if r_low and r_low in n["id"].lower():
                return n
            if d_low and d_low in n["desc"].lower():
                return n
        return None

    def tap(self, x: int, y: int, delay: float = 0.5):
        """نقر إحداثيات محددة على الشاشة"""
        self.run("shell", "input", "tap", str(x), str(y))
        if delay > 0:
            time.sleep(delay)

    def tap_node(self, node: Dict[str, Any], delay: float = 0.5) -> bool:
        if node and node.get("center"):
            self.tap(node["center"][0], node["center"][1], delay=delay)
            return True
        return False

    def click_text(self, text: str, delay: float = 0.5) -> bool:
        """البحث عن نص محدد على الشاشة والنقر عليه مباشرة"""
        n = self.find_node(text=text)
        if n and n.get("center"):
            self.tap(n["center"][0], n["center"][1], delay=delay)
            return True
        return False

    def type_text(self, text: str, delay: float = 0.3):
        """كتابة نص داخل الحقل المحدد"""
        escaped = str(text).replace(" ", "%s").replace("&", "\&").replace("<", "\<").replace(">", "\>")
        self.run("shell", "input", "text", escaped)
        if delay > 0:
            time.sleep(delay)

    def press_key(self, keycode: int, delay: float = 0.2):
        """إرسال زر أندرويد (مثل Enter=66, Back=4, Home=3)"""
        self.run("shell", "input", "keyevent", str(keycode))
        if delay > 0:
            time.sleep(delay)

    def clear_field(self, count: int = 40):
        """مسح محتوى الحقل بالكامل بدقة: Select All ثم Delete"""
        # KEYCODE_CTRL_A = 29 مع CTRL، أو نستخدم SELECT_ALL = 277
        self.run("shell", "input", "keyevent", "277")   # KEYCODE_CTRL_A → Select All
        time.sleep(0.1)
        self.run("shell", "input", "keyevent", "67")    # KEYCODE_DEL → Delete selected
        time.sleep(0.1)
        # بديل احتياطي: backspace عدد كافٍ من المرات (مع move end أولاً)
        self.run("shell", "input", "keyevent", "123")   # KEYCODE_MOVE_END
        time.sleep(0.05)
        for _ in range(min(count, 60)):
            self.run("shell", "input", "keyevent", "67")  # KEYCODE_DEL
        time.sleep(0.1)


    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300, delay: float = 0.5):
        """سحب الشاشة (Scroll/Swipe)"""
        self.run("shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(duration_ms))
        if delay > 0:
            time.sleep(delay)

    def launch_app(self, package: str = "", activity: str = ""):
        pkg = package or self.package
        if activity:
            # تشغيل activity محدد
            self.run("shell", "am", "start", "-n", f"{pkg}/{activity}")
        else:
            # استخدام monkey لتشغيل تطبيق نسك (الطريقة الأموثق عملها 100%)
            out, code = self.run("shell", "monkey", "-p", pkg, "-c", "android.intent.category.LAUNCHER", "1", timeout=10.0)
            if "injected: 0" in out or "error" in out.lower():
                # بديل: SplashActivity المعروفة من تحليل الـ package
                self.run("shell", "am", "start", "-n", f"{pkg}/com.almatar.splash.SplashActivity")

    def force_stop(self, package: str = ""):
        pkg = package or self.package
        self.run("shell", "am", "force-stop", pkg)
