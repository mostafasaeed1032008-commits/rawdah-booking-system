#!/bin/bash
# ===================================================
# 🕌 منظومة حجز الروضة الشريفة - سكريبت الديبلوي على Linux/VPS
# ===================================================
# طريقة التشغيل:
#   chmod +x deploy_linux.sh
#   ./deploy_linux.sh
# ===================================================

set -e  # وقف عند أي خطأ

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_step() { echo -e "\n${BLUE}▶ $1${NC}"; }
print_ok()   { echo -e "${GREEN}✅ $1${NC}"; }
print_warn() { echo -e "${YELLOW}⚠️  $1${NC}"; }
print_err()  { echo -e "${RED}❌ $1${NC}"; }

echo -e "${BLUE}"
echo "  🕌 منظومة حجز الروضة الشريفة"
echo "  🚀 Deployment Script for Linux/VPS"
echo "  ======================================"
echo -e "${NC}"

# ===== 1. فحص المتطلبات =====
print_step "فحص المتطلبات الأساسية..."

command -v python3 >/dev/null 2>&1 || { print_err "Python3 غير مثبت! شغّل: apt install python3"; exit 1; }
command -v pip3 >/dev/null 2>&1 || { print_err "pip3 غير مثبت! شغّل: apt install python3-pip"; exit 1; }
print_ok "Python3 و pip3 موجودين"

# فحص Docker (اختياري)
if command -v docker >/dev/null 2>&1; then
    print_ok "Docker متاح"
    USE_DOCKER=true
else
    print_warn "Docker غير موجود - سيتم التثبيت المباشر بدون Docker"
    USE_DOCKER=false
fi

# ===== 2. إنشاء ملف .env =====
print_step "إعداد متغيرات البيئة..."

if [ ! -f ".env" ]; then
    cp .env.example .env
    print_warn "تم إنشاء .env من النموذج - يرجى تعديله بمفاتيحك الحقيقية!"
    echo ""
    echo "  🔑 افتح الملف: nano .env"
    echo "  وعدّل المتغيرات التالية:"
    echo "    - TELEGRAM_BOT_TOKEN"
    echo "    - GEMINI_API_KEY"
    echo "    - ADB_HOST (لو المحاكي على جهاز تاني)"
    echo ""
    read -p "هل تريد تعديل .env الآن؟ (y/n): " edit_env
    if [[ $edit_env == "y" ]]; then
        nano .env
    fi
else
    print_ok "ملف .env موجود"
fi

# تحميل متغيرات البيئة
source .env

# ===== 3. تثبيت المتطلبات =====
print_step "تثبيت متطلبات Python..."

if [ "$USE_DOCKER" = false ]; then
    # تثبيت ADB
    if ! command -v adb >/dev/null 2>&1; then
        print_step "تثبيت ADB..."
        apt-get update -q && apt-get install -y android-tools-adb
    fi

    # تثبيت Tesseract (لاستخراج التأشيرات)
    if ! command -v tesseract >/dev/null 2>&1; then
        print_step "تثبيت Tesseract OCR..."
        apt-get install -y tesseract-ocr tesseract-ocr-ara
    fi

    # إنشاء venv
    if [ ! -d ".venv" ]; then
        python3 -m venv .venv
    fi
    source .venv/bin/activate
    pip install --upgrade pip -q
    pip install -r requirements.txt -q
    print_ok "تم تثبيت كل المتطلبات"
fi

# ===== 4. إعداد قاعدة البيانات =====
print_step "إعداد قاعدة البيانات..."
mkdir -p database auto_booking/cache telegram_bot/temp_uploads
print_ok "المجلدات جاهزة"

# ===== 5. الديبلوي =====
if [ "$USE_DOCKER" = true ]; then
    print_step "بناء وتشغيل Docker Containers..."
    docker-compose down 2>/dev/null || true
    docker-compose build --no-cache
    docker-compose up -d
    print_ok "الكونتينرات شغالة!"
    echo ""
    echo "  📊 الداشبورد: http://$(hostname -I | awk '{print $1}'):8502"
    echo "  🐳 الحالة: docker-compose ps"
    echo "  📋 اللوقز: docker-compose logs -f"
else
    print_step "إعداد systemd services للتشغيل التلقائي..."

    WORK_DIR=$(pwd)
    PYTHON_BIN="$WORK_DIR/.venv/bin/python"

    # Dashboard Service
    cat > /etc/systemd/system/rawdah-dashboard.service << EOF
[Unit]
Description=Rawdah Dashboard (Streamlit)
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$WORK_DIR
Environment="PYTHONIOENCODING=utf-8"
EnvironmentFile=$WORK_DIR/.env
ExecStart=$PYTHON_BIN -m streamlit run dashboard/dashboard.py --server.port=8502 --server.address=0.0.0.0 --server.headless=true --browser.gatherUsageStats=false
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

    # Telegram Bot Service
    cat > /etc/systemd/system/rawdah-telegram.service << EOF
[Unit]
Description=Rawdah Telegram Bot
After=network.target rawdah-dashboard.service

[Service]
Type=simple
User=$USER
WorkingDirectory=$WORK_DIR
Environment="PYTHONIOENCODING=utf-8"
EnvironmentFile=$WORK_DIR/.env
ExecStart=$PYTHON_BIN telegram_bot/bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable rawdah-dashboard rawdah-telegram
    systemctl start rawdah-dashboard rawdah-telegram
    
    print_ok "Services شغالة!"
    echo ""
    echo "  📊 الداشبورد: http://$(hostname -I | awk '{print $1}'):8502"
    echo "  🔍 فحص الحالة: systemctl status rawdah-dashboard"
    echo "  📋 اللوقز: journalctl -u rawdah-dashboard -f"
fi

echo ""
echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}  ✅ الديبلوي اكتمل بنجاح! 🎉${NC}"
echo -e "${GREEN}======================================${NC}"
echo ""
echo "  🔑 ملاحظة مهمة عن البوت (ADB):"
echo "  البوت يحتاج محاكي Android متصل."
echo "  لو المحاكي على جهازك المحلي:"
echo "    1. شغّل: adb tcpip 16384"
echo "    2. في .env: ADB_HOST=IP_جهازك_المحلي"
echo ""
