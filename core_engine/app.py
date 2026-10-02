import io
import json
import os
import re
import shutil
from datetime import date, datetime
from pathlib import Path

import fitz  # PyMuPDF
import pandas as pd
import pytesseract
import streamlit as st
from PIL import Image, ImageOps

# ------------------------------------------------------------------
# قاموس تحويل الأسماء الإنجليزية/اللاتينية إلى العربية بدقة تامة
# ------------------------------------------------------------------
ARABIC_NAME_MAP = {
    # أسماء مركبة (عبد ...)
    "abdelhakim": "عبد الحكيم", "abdelmohsen": "عبد المحسن", "abdelnohsen": "عبد المحسن",
    "abdelatti": "عبد العاطي", "abdelmotal": "عبد المطلب", "abdelmoteleb": "عبد المطلب",
    "abdelmotaleb": "عبد المطلب", "abdelrahman": "عبد الرحمن", "abdellatif": "عبد اللطيف",
    "abdelhamid": "عبد الحميد", "abdelha": "عبد الحميد", "abdelghany": "عبد الغني",
    "abdelaziz": "عبد العزيز", "abdelhafez": "عبد الحافظ", "abdallah": "عبد الله",
    "abdalla": "عبد الله", "abdallak": "عبد الله", "abdelazim": "عبد العظيم",
    "abdelnasser": "عبد الناصر", "abdelkader": "عبد القادر", "abdelmoneim": "عبد المنعم",
    "abdelhalim": "عبد الحليم", "abdelrazek": "عبد الرازق", "abdelrehim": "عبد الرحيم",
    "abdelghaffar": "عبد الغفار", "abdelwahab": "عبد الوهاب", "abdelhady": "عبد الهادي",
    "abdelshafy": "عبد الشافي", "abdelgawad": "عبد الجواد", "abdelmawgoud": "عبد الموجود",
    "abdelbaset": "عبد الباسط", "abdelraouf": "عبد الرؤوف", "abdelmonsef": "عبد المنصف",
    "abdelfattah": "عبد الفتاح", "abdelfatta": "عبد الفتاح", "abdelfattar": "عبد الفتاح",
    "abdelshafi": "عبد الشافي", "abdelghani": "عبد الغني", "abdelkhalek": "عبد الخالق",
    "abdelshakoor": "عبد الشكور", "abdelwakeel": "عبد الوكيل", "abdelbar": "عبد البار",
    "abdeldayem": "عبد الدايم", "abdelbary": "عبد الباري", "abdelghafour": "عبد الغفور",
    "abdelsattar": "عبد الستار", "abdelmagid": "عبد المجيد", "abdelnaby": "عبد النبي",
    "abdelkarim": "عبد الكريم",

    # أسماء ذكور
    "mohamed": "محمد", "ahmed": "أحمد", "ahme": "أحمد", "mahmoud": "محمود", "ali": "علي",
    "hassan": "حسن", "hassank": "حسن", "hussein": "حسين", "husseinkaly": "حسين علي",
    "mostafa": "مصطفى", "mustafa": "مصطفى", "ibrahim": "إبراهيم", "ibrahimk": "إبراهيم",
    "ibrahi": "إبراهيم", "omar": "عمر", "amr": "عمرو", "khaled": "خالد", "khalid": "خالد",
    "tarek": "طارق", "tariq": "طارق", "wael": "وائل", "karim": "كريم", "kareem": "كريم",
    "hossam": "حسام", "walid": "وليد", "waleed": "وليد", "ashraf": "أشرف", "samer": "سامر",
    "samir": "سمير", "essam": "عصام", "issam": "عصام", "emad": "عماد", "gamal": "جمال",
    "jamal": "جمال", "sayed": "سيد", "sayid": "سيد", "elsayed": "السيد", "elsay": "السيد",
    "hamdy": "حمدي", "reda": "رضا", "alaa": "علاء", "saber": "صابر", "ramadan": "رمضان",
    "ramadank": "رمضان", "ramadankx": "رمضان", "ramadanksaad": "رمضان سعد", "shaaban": "شعبان",
    "shaabank": "شعبان", "afify": "عفيفي", "aflfy": "عفيفي", "afilfy": "عفيفي", "ayoub": "أيوب",
    "ayoubc": "أيوب", "ayoubcali": "أيوب علي", "raheem": "رحيم", "rahim": "رحيم", "raheen": "رحيم",
    "ziad": "زياد", "zeyad": "زياد", "adam": "آدم", "youssef": "يوسف", "yousef": "يوسف",
    "yahya": "يحيى", "hamza": "حمزة", "belal": "بلال", "bilal": "بلال", "anas": "أنس",
    "malek": "مالك", "seif": "سيف", "saif": "سيف", "eyad": "إياد", "yassin": "ياسين",
    "fady": "فادي", "mina": "مينا", "george": "جورج", "peter": "بيتر", "mikhail": "ميخائيل",
    "bishoy": "بيشوي", "shenouda": "شنودة", "nabil": "نبيل", "medhat": "مدحت", "safwat": "صفوت",
    "osama": "أسامة", "ayman": "أيمن", "hany": "هاني", "sameh": "سامح", "yasser": "ياسر",
    "atef": "عاطف", "adel": "عادل", "ezzat": "عزت", "magdy": "مجدي", "nasser": "ناصر",
    "badr": "بدر", "shahat": "الشحات", "elshahat": "الشحات", "gad": "جاد", "soliman": "سليمان",
    "farouk": "فاروق", "shawky": "شوقي", "fouad": "فؤاد", "said": "سعيد", "saeed": "سعيد",
    "elsaid": "السعيد", "badawy": "بدوي", "badawe": "بدوي", "abdou": "عبده", "abdo": "عبده",
    "elaraby": "العربي", "araby": "العربي", "eltouny": "التوني", "touny": "التوني",
    "elganady": "الجنادي", "ganady": "الجنادي", "marouf": "معروف", "kenawy": "قناوي",
    "elshafey": "الشافعي", "shafey": "الشافعي", "awad": "عوض", "amer": "عامر", "rezk": "رزق",
    "elsafy": "الصافي", "safy": "الصافي", "khalifa": "خليفة", "sedik": "صديق", "ismail": "إسماعيل",
    "attac": "عطا", "atta": "عطا", "attia": "عطية", "hebaish": "حبيش", "mohyeldin": "محي الدين",
    "mohyeldinsahmed": "محي الدين أحمد", "shehata": "شحاتة", "metwally": "متولي",
    "metwaly": "متولي", "sabry": "صبري", "fawzy": "فوزي", "lotfy": "لطفي", "fekry": "فكري",
    "shokry": "شكري", "magid": "ماجد", "taher": "طاهر", "fathy": "فتحي", "fathi": "فتحي",
    "morsy": "مرسي", "salem": "سالم", "kamel": "كامل", "anwar": "أنور", "ezz": "عز",
    "ezzeldin": "عز الدين", "khalil": "خليل", "galal": "جلال", "gaber": "جابر", "zaki": "زكي",
    "zaky": "زكي", "nady": "نادي", "qenawy": "قناوي", "mabrouk": "مبروك", "eid": "عيد",
    "zain": "زين", "khattab": "خطاب", "bekhit": "بخيت", "tayel": "طايل", "mohamedkaly": "محمد علي",
    "ghaith": "غيث", "tolba": "طلبة", "elkhouly": "الخولي", "khouly": "الخولي", "farghaly": "فرغلي",
    "saad": "سعد", "saa": "سعد", "elatroush": "الأطروش", "elsewy": "السيوي", "elsiwy": "السيوي",
    "embih": "إمبيه", "elhalafawy": "الحلفاوي", "goha": "جحا", "ads": "عدس",
    "elsharkawy": "الشرقاوي", "sheir": "شغير", "othman": "عثمان", "ammar": "عمار",
    "habila": "هابيلة", "abousaad": "أبو سعد", "abosaad": "أبو سعد", "aborabeh": "أبو رابح",
    "eleryan": "العريان", "elzayat": "الزيات", "tohamy": "تهامي", "khair": "خير",
    "khairalla": "خير الله", "eldenshaly": "الدنشالي", "ragab": "رجب", "gomaa": "جمعة",
    "gomaak": "جمعة", "sherif": "شريف", "helmy": "حلمي", "ebeid": "عبيد", "abbas": "عباس",
    "sobhy": "صبحي", "sobhi": "صبحي",
    "aly": "علي", "hosny": "حسني", "hosni": "حسني", "hossny": "حسني",
    "elewa": "عليوة", "elewah": "عليوة", "eliwa": "عليوة",
    "gerida": "جريدة", "greda": "جريدة",
    "kattia": "قطية", "katia": "قطية", "kotia": "قطية",
    "alrab": "الرب", "elrab": "الرب", "gad": "جاد",
    "amin": "أمين", "amink": "أمين", "mahmoudk": "محمود",
    "salah": "صلاح", "saleh": "صالح", "esmail": "إسماعيل", "ismaeel": "إسماعيل",
    "hafez": "حافظ", "hafiz": "حافظ", "hafezk": "حافظ",
    "mahgoub": "محجوب", "mahjoub": "محجوب",
    "abdelbaky": "عبد الباقي", "abdelbaki": "عبد الباقي",
    "abdelgawad": "عبد الجواد", "abdelgawwad": "عبد الجواد",
    "abdelsalam": "عبد السلام", "abdelslam": "عبد السلام",
    "abdelbary": "عبد الباري", "abdelbaryk": "عبد الباري",
    "abdelmaksoud": "عبد المقصود", "korany": "قرني", "qorany": "قرني",
    "ishak": "إسحاق", "ishaq": "إسحاق", "rashid": "راشد", "rashed": "راشد",
    "souad": "سعاد", "yehia": "يحيى", "yahia": "يحيى", "elrouby": "الروبي", "rouby": "الروبي",
    "elkareem": "الكريم", "elkerm": "الكريم", "elqerm": "القرم",
    "thoraya": "ثريا", "soraya": "ثريا", "thoria": "ثريا",
    "hebatallah": "هبة الله", "hebatalla": "هبة الله", "hebatallak": "هبة الله",
    "zahran": "زهران", "zahrank": "زهران", "gaballah": "جاب الله", "gadallah": "جاد الله",
    "feteira": "فطيرة", "fatira": "فطيرة", "salama": "سلامة", "salameh": "سلامة",
    "aboutabl": "أبو طبل", "abotabl": "أبو طبل", "nahrawy": "النحراوي", "okasha": "عكاشة",
    "sayad": "الصياد", "demerdash": "الدمرداش", "mansour": "منصور",
    "selhouby": "السلهوبي", "salhouby": "السلهوبي", "enayat": "عنايات", "haniat": "هنيات",
    "mossbah": "مصباح", "mesbah": "مصباح", "darwish": "درويش", "ghazy": "غازي", "ghazi": "غازي",
    "mosaad": "مسعد", "fathallah": "فتح الله", "fathalla": "فتح الله",
    "fereig": "فريج", "freig": "فريج", "nassar": "نصار", "alawy": "علوي",

    # أسماء إناث
    "amal": "آمال", "afkar": "أفكار",
    "rania": "رانيا", "fatma": "فاطمة", "fatima": "فاطمة", "mariam": "مريم", "maryam": "مريم",
    "sara": "سارة", "sarah": "سارة", "nour": "نور", "noura": "نورة", "aya": "آية",
    "hoda": "هدى", "mona": "منى", "salma": "سلمى", "zeinab": "زينب", "zainab": "زينب",
    "khadija": "خديجة", "yasmin": "ياسمين", "yasmine": "ياسمين", "reem": "ريم",
    "dina": "دينا", "eman": "إيمان", "heba": "هبة", "mai": "مي", "nada": "ندى",
    "asmaa": "أسماء", "doaa": "دعاء", "hanan": "حنان", "sahar": "سحر", "manal": "منال",
    "shaimaa": "شيماء", "samah": "سماح", "marwa": "مروة", "amira": "أميرة", "nahla": "نهلة",
    "basma": "بسمة", "radwa": "رضوى", "ghada": "غادة", "omnia": "أمنية", "habiba": "حبيبة",
    "menna": "منة", "mennatallah": "منة الله", "malak": "ملك", "jana": "جنى", "retaj": "ريتاج",
    "farida": "فريدة", "karma": "كارما", "joudy": "جودي", "arwa": "أروى", "salwa": "سلوى",
    "tasneem": "تسنيم", "shahd": "شهد", "sondos": "سندس", "wafaa": "وفاء", "soha": "سها",
    "dalia": "داليا", "nagwa": "نجوى", "noha": "نهى", "ola": "علا", "gehan": "جيهان",
    "jehan": "جيهان", "nesreen": "نسرين", "nesrin": "نسرين", "naglaa": "نجلاء", "sabah": "صباح",
    "samira": "سميرة", "samia": "سامية", "faten": "فاتن", "magda": "ماجدة", "soheir": "سهير",
    "laila": "ليلى", "layla": "ليلى", "hagar": "هاجر", "donia": "دنيا", "dunia": "دنيا",
    "rahaf": "رهف", "kenzy": "كنزي", "dareen": "دارين", "lina": "لينا", "safaa": "صفاء",
    "somaya": "سمية", "fayrouz": "فيروز", "rawan": "روان", "nouran": "نوران", "yasmina": "ياسمينة",
    "safia": "صفية", "safiaa": "صفية", "awatef": "عواطف", "nabila": "نبيلة", "basima": "باسمة",
    "fawzia": "فوزية", "fawziasmohamed": "فوزية محمد", "abeir": "عبير", "abir": "عبير", "nadra": "نادرة",
    "mervat": "ميرفت", "sohir": "سهير", "tahany": "تهاني", "sanaa": "سناء", "soad": "سعاد",
    "karima": "كريمة", "zawat": "زوات", "assrana": "عصرانة", "hend": "هند", "samar": "سمر",
    "masouda": "مسعودة", "madiha": "مديحة", "rawia": "راوية", "anisa": "أنيسة",
    "afnan": "أفنان", "rasha": "رشا", "saadia": "سعدية", "hekmat": "حكمت", "mayada": "ميادة",
    "nadya": "نادية", "morada": "مراد"
}

# ------------------------------------------------------------------
# العثور على Tesseract تلقائياً
# ------------------------------------------------------------------
def _configure_tesseract():
    if shutil.which("tesseract"):
        return True
    standalone = Path(r"D:\Tesseract-OCR\tesseract.exe")
    if standalone.exists():
        pytesseract.pytesseract.tesseract_cmd = str(standalone)
        _setup_tessdata(standalone.parent)
        return True
    script_dir = Path(__file__).parent
    candidates = [
        script_dir / "tesseract.exe",
        script_dir.parent / "Python tool" / "tesseract.exe",
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
        "/usr/bin/tesseract",
        "/usr/local/bin/tesseract",
    ]
    for c in candidates:
        p = Path(c)
        if p.exists():
            pytesseract.pytesseract.tesseract_cmd = str(p)
            _setup_tessdata(p.parent)
            return True
    return False


def _setup_tessdata(source_dir: Path):
    tessdata_src = source_dir / "tessdata"
    if not tessdata_src.exists():
        return
    try:
        str(tessdata_src).encode("ascii")
        os.environ["TESSDATA_PREFIX"] = str(tessdata_src)
        return
    except UnicodeEncodeError:
        pass
    safe_tessdata = Path(r"C:\TessData")
    if not safe_tessdata.exists():
        try:
            safe_tessdata.mkdir(parents=True, exist_ok=True)
            for f in tessdata_src.glob("*.traineddata"):
                shutil.copy2(f, safe_tessdata / f.name)
        except Exception:
            os.environ["TESSDATA_PREFIX"] = str(tessdata_src)
            return
    os.environ["TESSDATA_PREFIX"] = str(safe_tessdata)


TESSERACT_OK = _configure_tesseract()

# ------------------------------------------------------------------
# الإعدادات العامة
# ------------------------------------------------------------------
STATE_FILE = Path(__file__).parent / "used_emails.json"
PROCESSED_FILE = Path(__file__).parent / "processed_records.json"
PAGE_RENDER_SCALE = 2.5

st.set_page_config(page_title="مطابقة التأشيرات بالإيميلات", layout="wide")
st.markdown('<div dir="rtl">', unsafe_allow_html=True)


# ------------------------------------------------------------------
# تنظيف وتوحيد الأسماء العربية واستخراج البيانات الرقمية من PDF
# ------------------------------------------------------------------
def clean_arabic_name(name: str) -> str:
    """تنظيف وتوحيد الاسم العربي وإصلاح شذوذ خطوط الـ PDF والتشكيلات"""
    if not name:
        return ""
    name = re.sub(r"^(?:Full\s*Name|الاسم|اإلسم|الإسم|اسم\s*الزائر|الاسم\s*الكامل)\s*[:\-]?\s*", "", name, flags=re.I)
    name = re.sub(r"عبدهللا\b", "عبد الله", name)
    name = re.sub(r"جاب\s*هللا\b", "جاب الله", name)
    name = re.sub(r"هبه\s*هللا\b", "هبة الله", name)
    name = re.sub(r"نعمة\s*هللا\b", "نعمة الله", name)
    name = re.sub(r"فضل\s*هللا\b", "فضل الله", name)
    name = re.sub(r"فتح\s*هللا\b", "فتح الله", name)
    name = re.sub(r"سعد\s*هللا\b", "سعد الله", name)
    name = re.sub(r"خير\s*هللا\b", "خير الله", name)
    name = re.sub(r"\bهللا\b", "الله", name)
    name = re.sub(r"\bعبدالسالم\b", "عبد السلام", name)
    name = re.sub(r"\bعبدال([^\s]+)", r"عبد ال\1", name)
    words = [re.sub(r"[^\u0600-\u06FF]", "", w) for w in name.split()]
    unwanted = {"تأشيرة", "السعودية", "السفارة", "مصر", "عمرة", "الرقمية", "المملكة", "تقويم", "الوزارة", "حسب", "يوم", "جواز", "سفر"}
    words = [w for w in words if w and w not in unwanted]
    return " ".join(words)


def extract_from_pdf_page(page):
    """استخراج بيانات التأشيرة رقمياً من ملف الـ PDF مباشرة بدقة تامة وبدون OCR"""
    try:
        blocks = page.get_text("blocks")
    except Exception:
        return None

    name_y = None
    for b in blocks:
        t = b[4].strip()
        if any(k in t for k in ["Full Name", "اإلسم", "الإسم", "الاسم", "اسم الزائر"]):
            name_y = b[1]
            break

    name = ""
    if name_y is not None:
        for b in blocks:
            t = b[4].strip()
            if abs(b[1] - name_y) < 10:
                if not any(k in t for k in ["Full Name", "اإلسم", "الإسم", "الاسم", "Birth Date", "تاريخ", "اسم الزائر"]):
                    cand = clean_arabic_name(t.replace("\n", " "))
                    if len(cand.split()) >= 2:
                        name = cand
                        break

    full_text = page.get_text()

    if not name:
        lines = [l.strip() for l in full_text.split("\n") if l.strip()]
        for idx, l in enumerate(lines):
            if any(k in l for k in ["Full Name", "اإلسم", "الإسم", "الاسم", "اسم الزائر"]):
                for offset in [-3, -2, -1, 1, 2, 3]:
                    t_idx = idx + offset
                    if 0 <= t_idx < len(lines):
                        cand = clean_arabic_name(lines[t_idx])
                        if len(cand.split()) >= 2:
                            name = cand
                            break
                if name:
                    break

    v_m = re.findall(r"\b(6\d{9})\b", full_text)
    if not v_m:
        v_m = re.findall(r"\b(\d{10})\b", full_text)
    visa = v_m[0] if v_m else ""

    p_m = re.findall(r"\b([A-Z]\d{8})\b", full_text)
    passport = p_m[0] if p_m else ""

    p_type = "رجال"
    birth_year = None
    m_icao = re.search(r"EGY(\d{2})(\d{2})(\d{2})\d([MF])", full_text)
    if m_icao:
        yy = int(m_icao.group(1))
        birth_year = 2000 + yy if yy <= 26 else 1900 + yy
        p_type = "نساء" if m_icao.group(4) == "F" else "رجال"
    else:
        m_saudi = re.search(r"EGY(\d{2})(\d{2})(\d{4})\d([12])", full_text)
        if m_saudi:
            birth_year = int(m_saudi.group(3))
            p_type = "نساء" if m_saudi.group(4) == "2" else "رجال"

    if not birth_year:
        m_b = re.search(r"\b(19\d{2}|20\d{2})[-/]\d{2}[-/]\d{2}\b", full_text)
        if m_b:
            birth_year = int(m_b.group(1))

    if birth_year and birth_year >= 2014:
        p_type = "طفلة" if p_type == "نساء" else "طفل"

    if name:
        return name, passport, visa, p_type, full_text
    return None


def load_visa_items_from_upload(uploaded_file):
    name = uploaded_file.name
    data = uploaded_file.getvalue()
    out = []
    if name.lower().endswith(".pdf"):
        doc = fitz.open(stream=data, filetype="pdf")
        mat = fitz.Matrix(PAGE_RENDER_SCALE, PAGE_RENDER_SCALE)
        for i, page in enumerate(doc):
            label = name if doc.page_count == 1 else f"{name} - صفحة {i + 1}"
            extracted = extract_from_pdf_page(page)
            if extracted and extracted[0]:
                out.append((label, None, extracted))
            else:
                pix = page.get_pixmap(matrix=mat)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                out.append((label, img, None))
        doc.close()
    else:
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img)
        out.append((name, img, None))
    return out


def preprocess_for_ocr(img: Image.Image) -> Image.Image:
    gray = img.convert("L")
    if max(gray.size) < 2200:
        ratio = 2200 / max(gray.size)
        gray = gray.resize(
            (int(gray.width * ratio), int(gray.height * ratio)), Image.LANCZOS
        )
    return gray


# ------------------------------------------------------------------
# تحويل مقاطع الاسم الإنجليزية إلى العربية
# ------------------------------------------------------------------
def _transliterate_token(t: str) -> str:
    s = t.lower().strip()
    if not s or s in ("re", "kx", "k", "c", "x"):
        return ""
    if s in ARABIC_NAME_MAP:
        return ARABIC_NAME_MAP[s]

    # إزالة حرف k أو x الزائد في نهاية مقاطع MRZ (مثل mahmoudk, amink, hassank)
    if (s.endswith("k") or s.endswith("x")) and len(s) > 3:
        base = s[:-1]
        if base in ARABIC_NAME_MAP:
            return ARABIC_NAME_MAP[base]

    # معالجة بادئة "ال" (el / al)
    for pfx in ("el", "al"):
        if s.startswith(pfx) and len(s) > 2 and s[len(pfx):] in ARABIC_NAME_MAP:
            base = ARABIC_NAME_MAP[s[len(pfx):]]
            return "ال" + base if not base.startswith("ال") else base

    # معالجة الأسماء المركبة الملتصقة بمقاطع أخرى (مثل abdelnasserkattia, abdelrahman...)
    compound_prefixes = [
        ("abdelnasser", "عبد الناصر"),
        ("abdelrahman", "عبد الرحمن"),
        ("abdelrahim", "عبد الرحيم"),
        ("abdelrehim", "عبد الرحيم"),
        ("abdelfattah", "عبد الفتاح"),
        ("abdelaziz", "عبد العزيز"),
        ("abdelhalim", "عبد الحليم"),
        ("abdelkader", "عبد القادر"),
        ("abdelmoneim", "عبد المنعم"),
        ("abdelhamid", "عبد الحميد"),
        ("abdelazim", "عبد العظيم"),
        ("abdelbaset", "عبد الباسط"),
        ("abdelghany", "عبد الغني"),
        ("abdelwahab", "عبد الوهاب"),
        ("abdelhady", "عبد الهادي"),
        ("abdallah", "عبد الله"),
        ("abdalla", "عبد الله"),
        ("abdelmawgoud", "عبد الموجود"),
        ("mohyeldin", "محي الدين"),
        ("ezzeldin", "عز الدين"),
        ("salaheldin", "صلاح الدين"),
        ("gadalla", "جاد الله"),
        ("khairalla", "خير الله"),
        ("saadalla", "سعد الله"),
    ]
    for pfx, ar_pfx in compound_prefixes:
        if s.startswith(pfx) and len(s) > len(pfx):
            rem = s[len(pfx):].lstrip("k").lstrip("x").lstrip("<")
            if rem:
                rem_ar = _transliterate_token(rem)
                if rem_ar:
                    return f"{ar_pfx} {rem_ar}"
            return ar_pfx

    if (s.startswith("abdel") or s.startswith("abdul")) and len(s) > 5:
        rem = s[5:].lstrip("k").lstrip("x")
        if rem in ARABIC_NAME_MAP:
            return "عبد " + ARABIC_NAME_MAP[rem]

    for pfx in ("abou", "abo", "abu"):
        if s.startswith(pfx) and len(s) > len(pfx):
            rem = s[len(pfx):]
            if rem in ARABIC_NAME_MAP:
                return "أبو " + ARABIC_NAME_MAP[rem]

    # قواعد التحويل الصوتي
    rules = [
        ("shahat", "شحات"), ("fattah", "فتاح"), ("fattar", "فتاح"), ("din", "الدين"),
        ("mohy", "محي"), ("khalil", "خليل"), ("galal", "جلال"), ("gaber", "جابر"),
        ("shehata", "شحاتة"), ("zaki", "زكي"), ("zaky", "زكي"), ("nady", "نادي"),
        ("metwally", "متولي"), ("metwaly", "متولي"), ("fawzy", "فوزي"), ("sabry", "صبري"),
        ("lotfy", "لطفي"), ("fekry", "فكري"), ("shokry", "شكري"), ("magid", "ماجد"),
        ("taher", "طاهر"), ("fathy", "فتحي"), ("shawky", "شوقي"), ("morsy", "مرسي"),
        ("salem", "سالم"), ("kamel", "كامل"), ("fouad", "فؤاد"), ("anwar", "أنور"),
        ("ezz", "عز"), ("sh", "ش"), ("kh", "خ"), ("gh", "غ"), ("th", "ث"), ("ph", "ف"),
        ("aa", "ا"), ("ee", "ي"), ("oo", "و"), ("ou", "و"),
        ("a", "ا"), ("b", "ب"), ("t", "ت"), ("g", "ج"), ("j", "ج"),
        ("h", "ه"), ("d", "د"), ("r", "ر"), ("z", "ز"), ("s", "س"),
        ("f", "ف"), ("k", "ك"), ("q", "ق"), ("l", "ل"), ("m", "م"),
        ("n", "ن"), ("w", "و"), ("y", "ي"), ("i", "ي"), ("u", "و"),
        ("o", "و"), ("e", "ي"), ("v", "ف"), ("c", "ك")
    ]
    res = s
    for eng, ar in rules:
        res = res.replace(eng, ar)
    return res


# ------------------------------------------------------------------
# استخراج الاسم والنوع من سطور الـ MRZ
# ------------------------------------------------------------------
def parse_mrz_data(text: str) -> tuple[str, str, str, str]:
    """
    يستخرج:
      arabic_name: الاسم بالعربي
      person_type: رجال / نساء / طفل
      passport: رقم الجواز
      visa: رقم التأشيرة
    """
    lines = text.split("\n")
    mrz_line1 = ""
    mrz_line2 = ""

    for line in lines:
        cleaned = re.sub(r"[\s]+", "", line)
        if ("<EGY" in cleaned or "<E6Y" in cleaned or "<E86" in cleaned) and ("<<" in cleaned or cleaned.count("<") >= 3):
            mrz_line1 = line
        elif ("EGY" in cleaned or "E6Y" in cleaned or "E86" in cleaned or "686" in cleaned) and any(c.isdigit() for c in cleaned):
            mrz_line2 = cleaned

    arabic_name = ""
    person_type = "رجال"
    passport = ""
    visa = ""

    # 1. استخراج الاسم من MRZ Line 1 مع دعم الألقاب المركبة (مثل GAD<ALRAB) والأسماء الملتصقة وتنقية الضوضاء
    if mrz_line1 and "<<" in mrz_line1:
        parts = mrz_line1.split("<<")
        left = parts[0]
        right = parts[1] if len(parts) > 1 else ""

        # استخراج اللقب بعد بادئة الدولة
        surname_clean = re.sub(r"^(?:[P1V<I]{1,2}<)?[A-Z0-9]{3}", "", left)
        surnames = []
        for p in surname_clean.split("<"):
            m = re.match(r"^([A-Za-z]{2,})", p.strip())
            if m and not m.group(1).islower():
                surnames.append(m.group(1))

        # استخراج الأسماء الأولى مع تجاهل الحروف والكلمات المشوشة الناتجة من OCR
        givens = []
        for p in right.split("<"):
            m = re.match(r"^([A-Za-z]{2,})", p.strip())
            if m and not m.group(1).islower():
                token_word = m.group(1)
                if token_word.lower() not in ("ill", "all", "sf", "guea", "gill", "ges", "arg", "gua"):
                    givens.append(token_word)

        full_tokens = givens + surnames
        arabic_tokens = [_transliterate_token(t) for t in full_tokens]
        arabic_name = " ".join([t for t in arabic_tokens if t])

    # 2. استخراج النوع (رجال / نساء / طفل) من MRZ Line 2
    birth_year = None
    if mrz_line2:
        # نمط ICAO (YYMMDD + check + M/F)
        m_icao = re.search(r"EGY(\d{2})(\d{2})(\d{2})\d([MF])", mrz_line2)
        if m_icao:
            yy = int(m_icao.group(1))
            birth_year = 2000 + yy if yy <= 26 else 1900 + yy
            gender_char = m_icao.group(4)
            person_type = "نساء" if gender_char == "F" else "رجال"
        else:
            # نمط التأشيرة السعودية الفردية (DDMMYYYY + check + 1/2)
            m_saudi = re.search(r"EGY(\d{2})(\d{2})(\d{4})\d([12])", mrz_line2)
            if m_saudi:
                birth_year = int(m_saudi.group(3))
                gender_num = m_saudi.group(4)
                person_type = "نساء" if gender_num == "2" else "رجال"
            else:
                m_any = re.search(r"(\d{2})(\d{2})(19\d{2}|20\d{2})", mrz_line2)
                if m_any:
                    birth_year = int(m_any.group(3))

    # إذا لم نجد تاريخ الميلاد من MRZ نفحص سطر Birth Date
    if not birth_year:
        for line in lines:
            if re.search(r"Birth\s*Date", line, re.IGNORECASE):
                m_b = re.search(r"\b(19\d{2}|20\d{2})\b", line)
                if m_b:
                    birth_year = int(m_b.group(1))
                    break

    # تحديد ما إذا كان طفلاً أو طفلة (مواليد 2014 فما بعد / أقل من 12 سنة)
    if birth_year and birth_year >= 2014:
        person_type = "طفلة" if person_type == "نساء" else "طفل"

    # 3. رقم التأشيرة
    v_m = re.search(r"Visa\s*No\.?\s*[:\-.]?\s*(\d{8,12})", text, re.IGNORECASE)
    if not v_m:
        v_m = re.search(r"[Vv]is[ao]\s*[Nn]o\.?\s*[:\-.]?\s*([A-Z0-9]{6,15})", text, re.IGNORECASE)
    visa = v_m.group(1).strip().upper() if v_m else ""

    # 4. رقم الجواز
    p_m = re.search(r"Passport\s*No\.?\s*[:\-.]?\s*([A-Z0-9]{7,10})", text, re.IGNORECASE)
    if not p_m:
        p_m = re.search(r"[Pp]assp?ort\s*[Nn]o\.?\s*[:\-.]?\s*([A-Z0-9]{5,12})", text, re.IGNORECASE)
    if p_m:
        passport = p_m.group(1).strip().upper()
    elif mrz_line2:
        p_mrz = re.match(r"^([A-Z]\d{8})", mrz_line2)
        if p_mrz:
            passport = p_mrz.group(1).upper()

    return arabic_name, passport, visa, person_type


def extract_visa_fields(img: Image.Image):
    gray = preprocess_for_ocr(img)
    try:
        text = pytesseract.image_to_string(gray, lang="ara+eng")
    except Exception:
        text = pytesseract.image_to_string(gray, lang="eng")

    # 1. البحث عن الاسم العربي المكتوب مباشرة في التأشيرة
    arabic_name = ""
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    for idx, l in enumerate(lines):
        if any(kw in l for kw in ["Full Name", "الاسم", "اإلسم", "الإسم", "اسم الزائر"]):
            m_same = re.search(r"(?:Full\s*Name|الاسم|اإلسم|الإسم|اسم\s*الزائر)\s*[:\-]?\s*([^\n\r]+)", l)
            if m_same and any('\u0600' <= c <= '\u06FF' for c in m_same.group(1)):
                cand = clean_arabic_name(m_same.group(1))
                if len(cand.split()) >= 2:
                    arabic_name = cand
                    break
            for offset in [-2, -1, 1, 2]:
                t_idx = idx + offset
                if 0 <= t_idx < len(lines):
                    cand_line = lines[t_idx]
                    cand = clean_arabic_name(cand_line)
                    if len(cand.split()) >= 2:
                        arabic_name = cand
                        break
            if arabic_name:
                break

    # 2. استخراج بيانات MRZ كـ Fallback
    mrz_name, mrz_pass, mrz_visa, mrz_type = parse_mrz_data(text)

    final_name = arabic_name if arabic_name else mrz_name
    final_passport = mrz_pass
    if not final_passport:
        p_m = re.findall(r"\b([A-Z]\d{8})\b", text)
        if p_m:
            final_passport = p_m[0]

    final_visa = mrz_visa
    if not final_visa:
        v_m = re.findall(r"\b(6\d{9})\b", text)
        if v_m:
            final_visa = v_m[0]

    final_type = mrz_type
    return final_name, final_passport, final_visa, final_type, text


# ------------------------------------------------------------------
# إدارة الإيميلات والسجلات
# ------------------------------------------------------------------
def load_used_emails():
    if STATE_FILE.exists():
        try:
            return set(json.loads(STATE_FILE.read_text(encoding="utf-8")))
        except Exception:
            return set()
    return set()


def save_used_emails(used: set):
    STATE_FILE.write_text(json.dumps(sorted(used), ensure_ascii=False), encoding="utf-8")


def dedup_key(name: str, passport: str) -> str:
    if passport:
        return f"passport:{passport.strip().upper()}"
    if name:
        clean_name = re.sub(r'[^a-zA-Z\u0600-\u06FF]', '', name.lower())
        return f"name:{clean_name}"
    return ""


def load_processed_records():
    if PROCESSED_FILE.exists():
        try:
            return json.loads(PROCESSED_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_processed_records(records: dict):
    PROCESSED_FILE.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")


if "processed_records" not in st.session_state:
    st.session_state.processed_records = load_processed_records()
if "used_emails" not in st.session_state:
    st.session_state.used_emails = load_used_emails()
if "results" not in st.session_state:
    st.session_state.results = []

# ------------------------------------------------------------------
# واجهة الأداة
# ------------------------------------------------------------------
st.title("مطابقة التأشيرات بالإيميلات")

if not TESSERACT_OK:
    st.error("⚠ برنامج Tesseract OCR مش متثبت على الجهاز أو الأداة مش لاقياه.")
    st.stop()

col1, col2 = st.columns(2)

with col1:
    st.subheader("١. صور أو ملفات PDF للتأشيرات")
    uploaded_files = st.file_uploader(
        "ارفع صور أو ملفات PDF (كل صفحة PDF هتتحسب تأشيرة لوحدها). الترتيب = ترتيب الربط بالإيميلات.",
        type=["pdf", "png", "jpg", "jpeg", "webp", "bmp", "tiff"],
        accept_multiple_files=True,
    )

with col2:
    st.subheader("٢. الإيميلات")
    emails_text = st.text_area(
        "الصق الإيميلات هنا (إيميل في كل سطر) أو ارفع ملف بالأسفل",
        height=150,
        placeholder="email1@example.com\nemail2@example.com",
    )
    emails_file = st.file_uploader(
        "أو استورد من ملف Excel/CSV", type=["xlsx", "xls", "csv"], key="emails_file"
    )

    emails = []
    if emails_file is not None:
        if emails_file.name.lower().endswith(".csv"):
            df = pd.read_csv(emails_file, header=None)
        else:
            df = pd.read_excel(emails_file, header=None)
        email_re = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
        for val in df.values.flatten():
            v = str(val).strip()
            if email_re.match(v):
                emails.append(v)
    else:
        emails = [e.strip() for e in emails_text.split("\n") if e.strip()]

    used = st.session_state.used_emails
    available = [e for e in emails if e not in used]
    st.caption(f"إجمالي الإيميلات: {len(emails)} — المستخدم سابقاً: {len(emails) - len(available)} — المتاح: {len(available)}")

    if st.button("إعادة تعيين الإيميلات المستخدمة"):
        st.session_state.used_emails = set()
        save_used_emails(set())
        st.rerun()

st.caption(f"عدد المسجلين مسبقاً (منع التكرار): {len(st.session_state.processed_records)}")
if st.button("مسح سجل الأشخاص المعالَجين"):
    st.session_state.processed_records = {}
    save_processed_records({})
    st.rerun()

st.divider()

run = st.button("▶ ابدأ الاستخراج", type="primary", disabled=not uploaded_files)

if run:
    all_items = []
    for uf in uploaded_files:
        try:
            all_items.extend(load_visa_items_from_upload(uf))
        except Exception as e:
            all_items.append((f"{uf.name} (فشل الفتح)", None, None))
            st.warning(f"⚠ تعذر فتح {uf.name}: {e}")

    available_now = [e for e in emails if e not in st.session_state.used_emails]

    results = []
    progress = st.progress(0.0, text="جاري المعالجة...")
    next_email_idx = 0

    for i, (label, img, direct_data) in enumerate(all_items):
        progress.progress((i + 1) / len(all_items), text=f"جاري معالجة {label} ({i + 1}/{len(all_items)})")
        if direct_data is not None:
            name, passport, visa, person_type, raw_text = direct_data
            found_data = bool(name or passport or visa)
        elif img is not None:
            try:
                name, passport, visa, person_type, raw_text = extract_visa_fields(img)
                found_data = bool(name or passport or visa)
            except Exception as e:
                name, passport, visa, person_type, raw_text, found_data = (
                    "", "", "", "رجال", "", False
                )
                status = f"خطأ: {e}"
        else:
            results.append({
                "الاسم": label, "النوع": "", "الإيميل": "",
                "رقم الجواز": "", "رقم التأشيرة": "", "الحالة": "فشل فتح الملف",
                "الملف المصدر": label,
            })
            continue

        key = dedup_key(name, passport)
        is_duplicate = bool(key) and key in st.session_state.processed_records

        if not found_data:
            status = "لم يتم العثور على بيانات"
            email = "لا يوجد إيميل متاح"
        elif is_duplicate:
            prev = st.session_state.processed_records[key]
            status = f"مكرر - سبق معالجته (إيميل سابق: {prev.get('email', '؟')})"
            email = "متجاهل - مكرر"
        else:
            if next_email_idx < len(available_now):
                email = available_now[next_email_idx]
                st.session_state.used_emails.add(email)
                next_email_idx += 1
            else:
                email = "لا يوجد إيميل متاح"

            status = "تم" if name else "⚠ تم (الاسم غير واضح)"
            if key:
                st.session_state.processed_records[key] = {
                    "name": name, "passport": passport, "visa": visa,
                    "type": person_type, "email": email,
                }

        results.append({
            "الاسم": name or "غير معروف",
            "النوع": person_type,
            "رقم الجواز": passport,
            "رقم التأشيرة": visa,
            "الإيميل": email,
            "الحالة": status,
            "الملف المصدر": label,
            "_raw_ocr": raw_text,
        })

    save_used_emails(st.session_state.used_emails)
    save_processed_records(st.session_state.processed_records)
    st.session_state.results = results
    progress.empty()

if st.session_state.results:
    st.subheader("النتائج")

    results = st.session_state.results
    total = len(results)
    men = sum(1 for r in results if r.get("النوع") == "رجال")
    women = sum(1 for r in results if r.get("النوع") == "نساء")
    boys = sum(1 for r in results if r.get("النوع") == "طفل")
    girls = sum(1 for r in results if r.get("النوع") == "طفلة")

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("إجمالي", total)
    c2.metric("رجال 👨", men)
    c3.metric("نساء 👩", women)
    c4.metric("أطفال (ذكور) 👦", boys)
    c5.metric("طفلات (إناث) 👧", girls)

    st.divider()

    df_results = pd.DataFrame(results)
    display_df = df_results.drop(columns=["_raw_ocr"], errors="ignore")
    st.dataframe(display_df, use_container_width=True)

    with st.expander("عاين نص الـ OCR الخام لأي ملف"):
        for r in results:
            st.markdown(f"**{r['الاسم']}** ({r['الملف المصدر']})")
            st.code(r.get("_raw_ocr", ""), language=None)

    c1, c2 = st.columns(2)
    with c1:
        csv_bytes = display_df.to_csv(index=False).encode("utf-8-sig")
        st.download_button("⬇ تحميل CSV", csv_bytes, "visa_email_results.csv", "text/csv")
    with c2:
        buf = io.BytesIO()
        display_df.to_excel(buf, index=False, engine="openpyxl")
        st.download_button(
            "⬇ تحميل Excel",
            buf.getvalue(),
            "visa_email_results.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    remaining = [e for e in emails if e not in st.session_state.used_emails]
    if remaining:
        rem_df = pd.DataFrame({"Email": remaining})
        buf2 = io.BytesIO()
        rem_df.to_excel(buf2, index=False, engine="openpyxl")
        st.download_button("⬇ الإيميلات المتبقية", buf2.getvalue(), "remaining_emails.xlsx")

st.markdown("</div>", unsafe_allow_html=True)
