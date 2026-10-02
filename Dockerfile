# منظومة حجز الروضة الشريفة - Docker Image
# يحتوي على: Dashboard (Streamlit) + Telegram Bot + Core Engine
# البوت يتصل بالمحاكي عبر ADB عن بُعد (ADB over TCP)

FROM python:3.11-slim

# متغيرات البيئة
ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=utf-8
ENV DEBIAN_FRONTEND=noninteractive

# تثبيت الأدوات الضرورية
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    unzip \
    git \
    android-tools-adb \
    tesseract-ocr \
    tesseract-ocr-ara \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# إنشاء مجلد المشروع
WORKDIR /app

# نسخ ملفات المتطلبات أولاً (cache optimization)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# نسخ كامل المشروع
COPY . .

# إنشاء المجلدات الضرورية
RUN mkdir -p /app/database /app/auto_booking/cache /app/telegram_bot/temp_uploads

# منفذ الداشبورد
EXPOSE 8502

# الأمر الافتراضي: تشغيل الداشبورد
CMD ["python", "-m", "streamlit", "run", "dashboard/dashboard.py", \
     "--server.port=8502", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--browser.gatherUsageStats=false"]
