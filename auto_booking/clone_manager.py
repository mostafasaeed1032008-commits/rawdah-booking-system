# -*- coding: utf-8 -*-
"""
منظومة حجز الروضة الشريفة - مدير النسخ المتعددة على المحاكي (Clone Manager)
Manages multiple Nusuk app clones across MuMu Player instances and multi-user profiles
"""

import re
import subprocess
import time
from typing import Dict, List, Optional, Tuple

class CloneManager:
    def __init__(self, adb_controller):
        self.adb = adb_controller
        self.package = "com.moh.nusukapp"
        self.activity = f"{self.package}.MainActivity"
        self._user_map: Dict[int, int] = {0: 0}
        self.discover_clones()

    def discover_clones(self) -> Dict[int, int]:
        """فحص واكتشاف جميع الـ Clones المتوفرة على المحاكي"""
        out, code = self.adb.run("shell", "pm", "list", "users")
        self._user_map = {0: 0}

        matches = re.findall(r"UserInfo\{(\d+):([^:]+):", out)
        for uid_str, uname in matches:
            uid = int(uid_str)
            if uid == 0:
                self._user_map[0] = 0
            elif "nemu_multi_user_" in uname:
                try:
                    num = int(uname.replace("nemu_multi_user_", ""))
                    clone_num = num - 9
                    self._user_map[clone_num] = uid
                except ValueError:
                    pass
            elif uid >= 10:
                clone_num = uid - 9
                self._user_map[clone_num] = uid

        return self._user_map

    def get_available_clones_count(self) -> int:
        return max(1, len(self._user_map))

    def launch_clone(self, clone_id: int = 0, wait_sec: float = 3.5) -> bool:
        """تشغيل النسخة المحددة"""
        user_id = self._user_map.get(clone_id, 0 if clone_id == 0 else 9 + clone_id)

        # محاولة التشغيل عبر user_id
        cmd = ["shell", "am", "start", "-n", f"{self.package}/{self.activity}"]
        if user_id > 0:
            cmd = ["shell", "am", "start", "--user", str(user_id), "-n", f"{self.package}/{self.activity}"]

        out, code = self.adb.run(*cmd)
        time.sleep(wait_sec)
        return code == 0

    def stop_clone(self, clone_id: int = 0):
        """إيقاف النسخة المحددة"""
        user_id = self._user_map.get(clone_id, 0 if clone_id == 0 else 9 + clone_id)
        if user_id > 0:
            self.adb.run("shell", "am", "force-stop", "--user", str(user_id), self.package)
        else:
            self.adb.run("shell", "am", "force-stop", self.package)

    def stop_all_clones(self):
        """إيقاف كافة النسخ المفتوحة"""
        for clone_id in list(self._user_map.keys()):
            self.stop_clone(clone_id)
