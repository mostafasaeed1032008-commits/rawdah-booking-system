#!/bin/bash
# ==============================================================================
# 📱 سكريبت إعداد وتشغيل هواتف Damru & Redroid السحابية الخفية على سيرفر VPS
# ==============================================================================
# يشغل هواتف أندرويد حقيقية داخل السيرفر بضغطة زر واحدة
# بدون أي استهلاك لرامات أو معالج لابتوبك الشخصي
# مع تغيير بصمات الأجهزة لتظهر كتليفونات سامسونج وبيكسل حقيقية (Anti-Detection)
# ==============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}"
echo "================================================================="
echo "   🕋 منظومة حجز الروضة - تثبيت وتشغيل هواتف Damru السحابية"
echo "================================================================="
echo -e "${NC}"

NUM_DEVICES=${1:-2}  # عدد الهواتف الافتراضية المراد تشغيلها (الافتراضي 2)
START_PORT=5555

echo -e "📱 عدد الهواتف السحابية المطلوب تشغيلها: ${GREEN}${NUM_DEVICES}${NC}"

# 1. تحديث وتثبيت المتطلبات الأساسية
echo -e "\n${BLUE}▶ [1/4] تحديث النظام وتثبيت Docker و ADB...${NC}"
apt-get update -qq
apt-get install -y -qq docker.io android-tools-adb python3 python3-pip curl wget

systemctl enable --now docker

# 2. تحميل كيرنل موديولز الأندرويد المطلوبة لـ Redroid
echo -e "\n${BLUE}▶ [2/4] تفعيل تعريفات كيرنل الأندرويد (binder_linux)...${NC}"
modprobe binder_linux devices="binder,hwbinder,vndbinder" 2>/dev/null || true

# 3. سحب صورة Redroid المحسنة من Damru
echo -e "\n${BLUE}▶ [3/4] سحب صورة الأندرويد السحابية الجاهزة...${NC}"
docker pull redroid/redroid:12.0.0_64only-latest || docker pull redroid/redroid:11.0.0-latest

# 4. تشغيل مجموعة الهواتف السحابية
echo -e "\n${BLUE}▶ [4/4] تشغيل الهواتف السحابية مع بصمات أجهزة خفية...${NC}"

# موديلات أجهزة للتخفي والتمويه
MODELS=("SM-S918B" "Pixel-7-Pro" "SM-G998B" "Pixel-8" "SM-A546B")
MANUFACTURERS=("samsung" "Google" "samsung" "Google" "samsung")

SERVER_IP=$(curl -s ifconfig.me || hostname -I | awk '{print $1}')

for ((i=0; i<NUM_DEVICES; i++)); do
    PORT=$((START_PORT + i))
    CONTAINER_NAME="damru_phone_$PORT"
    DATA_DIR="/opt/damru_data/$PORT"
    mkdir -p "$DATA_DIR"

    # إيقاف الحاوية القديمة إن وجدت
    docker rm -f "$CONTAINER_NAME" 2>/dev/null || true

    MODEL_IDX=$((i % 5))
    CUR_MODEL=${MODELS[$MODEL_IDX]}
    CUR_MANUF=${MANUFACTURERS[$MODEL_IDX]}

    echo -e "🚀 جاري تشغيل هاتف سحابي #${i} على المنفذ ${GREEN}${PORT}${NC} كجهاز: ${YELLOW}${CUR_MANUF} ${CUR_MODEL}${NC}..."

    docker run -itd \
        --name "$CONTAINER_NAME" \
        --restart always \
        --privileged \
        -v "$DATA_DIR":/data \
        -p "$PORT":5555 \
        redroid/redroid:12.0.0_64only-latest \
        androidboot.redroid_width=720 \
        androidboot.redroid_height=1280 \
        androidboot.redroid_dpi=320 \
        ro.product.model="$CUR_MODEL" \
        ro.product.manufacturer="$CUR_MANUF" \
        ro.product.brand="$CUR_MANUF"

    sleep 3
done

echo ""
echo -e "${GREEN}=================================================================${NC}"
echo -e "${GREEN}   ✅ تم تشغيل كافة الهواتف السحابية بنجاح 24/7! 🎉${NC}"
echo -e "${GREEN}=================================================================${NC}"
echo ""
echo -e "🌐 عنوان السيرفر السحابي (IP): ${YELLOW}${SERVER_IP}${NC}"
echo -e "📱 منافذ الهواتف النشطة الآن:"
for ((i=0; i<NUM_DEVICES; i++)); do
    PORT=$((START_PORT + i))
    echo -e "   - الهاتف #${i}: ${GREEN}${SERVER_IP}:${PORT}${NC}"
done
echo ""
echo -e "📋 للاتصال بهاتف من جهازك أو البوت:"
echo -e "   👉 adb connect ${SERVER_IP}:${START_PORT}"
echo ""
echo -e "💡 الميزة: الحجز سيعمل بالكامل داخل هذا السيرفر دون استهلاك أي بايت من لابتوبك!"
echo -e "${GREEN}=================================================================${NC}"
