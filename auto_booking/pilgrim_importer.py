# -*- coding: utf-8 -*-
"""
منظومة حجز الروضة الشريفة - معالج ومستورد كشوف وبيانات المعتمرين (Pilgrim Importer)
يدعم استيراد كشوف الإكسيل ولصق النصوص المباشرة وتوحيد الأعمدة تلقائياً بدقة متناهية ودون تداخل الأعمدة.
"""

import re
import io
from typing import List, Dict, Any, Optional
import pandas as pd


def clean_scalar(val: Any) -> str:
    """تنظيف وتجريد القيم الفردية من NaN وفواصل الـ float غير المرغوبة"""
    if val is None or pd.isna(val):
        return ""
    s = str(val).strip()
    if s.endswith(".0"):
        s = s[:-2]
    if s.lower() in ["nan", "none", "null", "<na>"]:
        return ""
    return s


def auto_map_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    التعرف التلقائي الذكي على أسماء الأعمدة في ملف الإكسيل بالعربية والإنجليزية
    مع منع التداخل تماماً ومنع أي عمود Unnamed من احتلال عمود الاسم أو غيره.
    """
    col_mapping = {}
    used_targets = set()

    for col in df.columns:
        c_str = str(col).strip().lower()
        # تجاهل تام لأي أعمدة فارغة أو غير مسماة من إكسيل (Unnamed)
        if "unnamed" in c_str:
            continue

        # 1. عمود الاسم
        if "name" not in used_targets and any(k in c_str for k in ["اسم المعتمر", "اسم المسافر", "الاسم كامل", "الاسم بالعربي", "الاسم", "اسم", "passenger", "pilgrim", "full name"]):
            col_mapping[col] = "name"
            used_targets.add("name")

        # 2. عمود رقم الجواز
        elif "passport" not in used_targets and any(k in c_str for k in ["رقم الجواز", "جواز السفر", "الجواز", "passport", "doc no", "وثيقة"]):
            col_mapping[col] = "passport"
            used_targets.add("passport")

        # 3. عمود رقم التأشيرة
        elif "visa" not in used_targets and any(k in c_str for k in ["رقم التأشيرة", "التأشيرة", "الفيزا", "تاشيرة", "تأشيرة", "visa", "border", "الحدود", "رقم الحدود"]):
            col_mapping[col] = "visa"
            used_targets.add("visa")

        # 4. عمود النوع / الفئة
        elif "gender" not in used_targets and any(k in c_str for k in ["نوع المعتمر", "النوع", "الجنس", "الفئة", "gender", "type", "sex"]):
            col_mapping[col] = "gender"
            used_targets.add("gender")

        # 5. عمود البريد الإلكتروني
        elif "email" not in used_targets and any(k in c_str for k in ["البريد الإلكتروني", "البريد الالكتروني", "البريد", "إيميل", "ايميل", "email", "e-mail", "mail"]):
            col_mapping[col] = "email"
            used_targets.add("email")

    return df.rename(columns=col_mapping)


def parse_excel_file(file_bytes_or_path) -> List[Dict[str, Any]]:
    """قراءة ملف إكسيل أو CSV وتحويله لقائمة معتمرين منظمة ونظيفة 100%"""
    try:
        if isinstance(file_bytes_or_path, (str, bytes, io.BytesIO)):
            try:
                df = pd.read_excel(file_bytes_or_path)
            except Exception:
                df = pd.read_csv(file_bytes_or_path)
        else:
            try:
                df = pd.read_excel(file_bytes_or_path)
            except Exception:
                df = pd.read_csv(file_bytes_or_path)

        df = auto_map_columns(df)
        return _clean_pilgrim_records(df.to_dict(orient="records"))
    except Exception as e:
        print(f"Error parsing Excel: {e}")
        return []


def parse_pasted_text(raw_text: str) -> List[Dict[str, Any]]:
    """
    تحليل نصوص منسوخة من إكسيل أو الواتساب أو التقارير:
    يدعم الفواصل: Tab, Comma, Pipe (|), Semicolon
    """
    if not raw_text or not raw_text.strip():
        return []

    lines = [l.strip() for l in raw_text.strip().splitlines() if l.strip()]
    records = []

    for l in lines:
        parts = [clean_scalar(p) for p in re.split(r"[\t,|;]", l) if clean_scalar(p)]
        if not parts:
            continue

        name = parts[0]
        # إذا كان أول حقل رقماً تسلسلياً (مثل 0 أو 1 أو 2)، نتجاوزه للحقل التالي
        if name.isdigit() and len(parts) > 1:
            parts = parts[1:]
            name = parts[0]

        visa = ""
        passport = ""
        gender = "رجال"
        email = ""

        for part in parts[1:]:
            p_clean = part.replace(" ", "")
            # فحص رقم التأشيرة (10 أرقام تبدأ بـ 6)
            if re.match(r"^6\d{9}$", p_clean) or (p_clean.startswith("6") and len(p_clean) == 10 and p_clean.isdigit()):
                visa = p_clean
            # فحص رقم الجواز (حرف متبوع بأرقام أو 7-10 محارف أبجدية رقمية)
            elif re.match(r"^[A-Za-z]\d{7,9}$", p_clean) or (p_clean.isalnum() and 7 <= len(p_clean) <= 10 and not p_clean.startswith("6")):
                passport = p_clean.upper()
            # فحص النوع
            elif any(g in part for g in ["نساء", "أنثى", "انثى", "طفلة", "بنت", "female"]):
                gender = "نساء"
            elif any(g in part for g in ["رجال", "ذكر", "طفل", "ولد", "male"]):
                gender = "رجال"
            # فحص الإيميل
            elif "@" in part:
                email = part

        records.append({
            "name": name,
            "gender": gender,
            "visa": visa,
            "passport": passport,
            "email": email
        })

    return _clean_pilgrim_records(records)


def _clean_pilgrim_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """تنظيف وتدقيق السجلات وإضافة القيم الافتراضية وحذف التكرار أو الصفوف التالفة"""
    cleaned = []

    for idx, r in enumerate(records):
        name = clean_scalar(r.get("name", ""))
        # تخطي الصفوف الفارغة أو رؤوس الجداول أو التوقيتات
        if not name or name.lower() in ["nan", "none", "الاسم", "name", "null"]:
            continue
        # إذا كان الاسم مجرد وقت (مثل 11:40:00) نتخطاه أو نحاول علاجه
        if re.match(r"^\d{1,2}:\d{2}(?::\d{2})?$", name):
            continue

        raw_gender = clean_scalar(r.get("gender", "رجال"))
        is_female = any(k in raw_gender for k in ["نس", "fem", "طفلة", "بنت", "أنث"])
        gender = "نساء" if is_female else "رجال"

        passport = clean_scalar(r.get("passport", "")).upper()
        visa = clean_scalar(r.get("visa", ""))

        # تنقية رقم التأشيرة ليكون 10 أرقام مجردة
        m_visa = re.search(r"\b(6\d{9})\b", visa)
        if m_visa:
            visa = m_visa.group(1)

        email = clean_scalar(r.get("email", ""))

        # في حال عدم وجود إيميل، يتم استخدام نظام Gmail Dot Trick لتوليد إيميل مستقل
        if not email or "@" not in email:
            dots_name = "most.a.f.asaee.d" if idx % 2 == 0 else "m.o.st.afasaeed"
            email = f"{dots_name}travel5+{idx+1}@gmail.com" if idx > 0 else "most.a.f.asaee.dtravel5@gmail.com"

        cleaned.append({
            "id": idx + 1,
            "name": name,
            "gender": gender,
            "passport": passport,
            "visa": visa,
            "email": email,
            "password": "Zxcv1234$",
            "is_registered": False
        })

    return cleaned
