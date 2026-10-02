# -*- coding: utf-8 -*-
"""
منظومة حجز الروضة الشريفة - مشغل النفق السحابي الذكي (Cloudflare Tunnel Launcher)
يربط لوحة التحكم مباشرة بالإنترنت برابط مشفر HTTPS مجاني يعمل على أي موبايل في العالم
مع تزامن لحظي 100% مع قاعدة بيانات اللاب توب ومحاكي الأندرويد.
"""

import os
import re
import sys
import time
import subprocess
import webbrowser
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.resolve()
CLOUDFLARED = PROJECT_ROOT / "tools" / "cloudflared.exe"
PYTHON_EXE = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
DASHBOARD_SCRIPT = PROJECT_ROOT / "dashboard" / "dashboard.py"
PORT = 8502
LINK_FILE = PROJECT_ROOT / "رابط_الداشبورد_للموبايل.txt"

def print_banner():
    print("=" * 65)
    print("   🕋 منظومة إدارة معتمري الروضة الشريفة - البث السحابي المباشر")
    print("=" * 65)
    print("  🚀 جاري تشغيل لوحة التحكم وربطها بنفق سحابي عالمي (Cloudflare)...")
    print("  📱 الميزة: نفس بيانات اللابتوب 100% + إمكانية تشغيل البوت من الموبايل!")
    print("=" * 65)
    print()

def start_streamlit():
    """تشغيل خادم Streamlit محلياً"""
    cmd = [
        str(PYTHON_EXE),
        "-m", "streamlit", "run",
        str(DASHBOARD_SCRIPT),
        f"--server.port={PORT}",
        "--server.headless=true",
        "--browser.gatherUsageStats=false"
    ]
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.Popen(
        cmd,
        cwd=str(PROJECT_ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    return proc

def start_tunnel():
    """تشغيل Cloudflare Tunnel واستخراج الرابط العام المشفر"""
    if not CLOUDFLARED.exists():
        print(f"❌ لم يتم العثور على أداة cloudflared في {CLOUDFLARED}")
        return None, None

    cmd = [
        str(CLOUDFLARED),
        "tunnel",
        "--url", f"http://127.0.0.1:{PORT}"
    ]
    
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1
    )

    public_url = None
    start_time = time.time()

    # قراءة مخرجات cloudflared للبحث عن رابط .trycloudflare.com
    for line in proc.stdout:
        # البحث عن رابط trycloudflare
        m = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line)
        if m:
            public_url = m.group(0)
            break
        if time.time() - start_time > 30:
            break

    return proc, public_url

def copy_to_clipboard(text: str):
    """نسخ الرابط تلقائياً لحافظة الويندوز لسهولة اللصق"""
    try:
        subprocess.run(["clip"], input=text, text=True, check=True)
    except Exception:
        pass

def main():
    print_banner()

    # 1. تشغيل Streamlit
    print(f"⏳ [1/2] جاري تشغيل لوحة التحكم المحلية على المنفذ {PORT}...")
    streamlit_proc = start_streamlit()
    time.sleep(3)

    # 2. تشغيل نفق Cloudflare
    print("⏳ [2/2] جاري إنشاء النفق السحابي الآمن واستخراج الرابط...")
    tunnel_proc, public_url = start_tunnel()

    if public_url:
        # حفظ الرابط في ملف نصي على سطح المشروع
        with open(LINK_FILE, "w", encoding="utf-8") as f:
            f.write(f"رابط لوحة التحكم المباشر للموبايل:\n{public_url}\n\n(تم إنشاؤه في: {time.strftime('%Y-%m-%d %H:%M:%S')})")

        copy_to_clipboard(public_url)

        print()
        print("🎉" * 25)
        print("   ✅ تم إنشاء الرابط العالمي بنجاح والتزامن لحظي 100%!")
        print("🎉" * 25)
        print()
        print(f"   📲 رابط الموبايل (افتحه من أي مكان في العالم):")
        print(f"   👉 {public_url}")
        print()
        print(f"   💻 الرابط المحلي على اللاب توب:")
        print(f"   👉 http://localhost:{PORT}")
        print()
        print("   📋 (تم نسخ رابط الموبايل تلقائياً لحافظتك - فقط الصقه على واتساب أو متصفحك)")
        print(f"   📁 تم حفظ الرابط أيضاً في الملف: {LINK_FILE.name}")
        print("=" * 65)
        print("   ⚠️  تنبيه: اترك هذه الشاشة مفتوحة طالما تريد بقاء الرابط شغالاً.")
        print("   (للإيقاف في أي وقت: اضغط Ctrl+C)")
        print("=" * 65)

        # فتح الرابط المحلي في المتصفح تلقائياً
        webbrowser.open(f"http://localhost:{PORT}")

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 جاري إيقاف الخادم والنفق السحابي...")
    else:
        print("❌ تعذر استخراج رابط النفق السحابي. يمكنك تصفح الداشبورد محلياً على:")
        print(f"👉 http://localhost:{PORT}")
        webbrowser.open(f"http://localhost:{PORT}")

    # إغلاق العمليات عند الإنهاء
    try:
        tunnel_proc.terminate()
        streamlit_proc.terminate()
    except Exception:
        pass

if __name__ == "__main__":
    main()
