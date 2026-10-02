# 🕌 دليل ديبلوي منظومة الروضة الشريفة على VPS

## 📦 ملفات الديبلوي الجاهزة

| الملف | الغرض |
|-------|--------|
| `requirements.txt` | كل المتطلبات |
| `Dockerfile` | بناء Docker image |
| `docker-compose.yml` | تشغيل كل الخدمات بأمر واحد |
| `deploy_linux.sh` | سكريبت الديبلوي التلقائي |
| `.env.example` | نموذج متغيرات البيئة |
| `rawdah_deploy.zip` | حزمة المشروع جاهزة للرفع |

---

## 🚀 الديبلوي على VPS (الطريقة السريعة)

### الخطوة 1 — رفع الملف على الـ VPS

**من جهازك:** ارفع `rawdah_deploy.zip` على الـ VPS:
```bash
scp "D:\مصطفي\شغل الروضة\rawdah_deploy.zip" root@IP_الـVPS:/opt/rawdah/
```

**داخل الـ VPS:**
```bash
mkdir -p /opt/rawdah
cd /opt/rawdah
unzip rawdah_deploy.zip
```

---

### الخطوة 2 — تثبيت ADB على الـ VPS

```bash
apt-get update && apt-get install android-tools-adb -y
```

---

### الخطوة 3 — إعداد .env

```bash
cp .env.example .env
nano .env
```

عدّل هذه القيم الإجبارية:
```env
GEMINI_API_KEY=مفتاحك
TELEGRAM_BOT_TOKEN=توكن_البوت
ADB_HOST=IP_جهازك_المحلي    ← المحاكي على جهازك
```

> **⚠️ ملاحظة مهمة عن البوت:**
> المحاكي (MuMu Player) يشتغل على جهازك المحلي.
> الـ VPS يتصل بيه عن بُعد عبر ADB TCP.
>
> **على جهازك المحلي شغّل:**
> ```
> adb tcpip 16384
> ```
> ثم في `.env` على الـ VPS:
> ```
> ADB_HOST=IP_جهازك_المحلي
> ADB_PORT=16384
> ```

---

### الخطوة 4 — الديبلوي التلقائي

```bash
chmod +x deploy_linux.sh
./deploy_linux.sh
```

---

## 🐳 طريقة Docker (الأسهل)

```bash
# تثبيت Docker
curl -fsSL https://get.docker.com | bash

# تشغيل كل الخدمات
docker-compose up -d

# فحص الحالة
docker-compose ps

# اللوقز المباشرة
docker-compose logs -f
```

---

## 🌐 فتح الـ Firewall على الـ VPS

```bash
ufw allow 8502/tcp && ufw reload
```

---

## 📊 الوصول للداشبورد

```
http://IP_الـVPS:8502
```

---

## 🔄 تحديث المشروع لاحقاً

```bash
docker-compose down
# ارفع الملفات الجديدة بـ scp
docker-compose up -d --build
```

---

## ❓ مشاكل شائعة

| المشكلة | الحل |
|---------|------|
| البوت مش بيتصل | تأكد `ADB_HOST` و `adb tcpip 16384` على جهازك |
| الداشبورد مش بيفتح | افتح port 8502 في firewall |
| خطأ OCR | `apt install tesseract-ocr tesseract-ocr-ara` |
| خطأ PDF | `apt install libgl1-mesa-glx` |
