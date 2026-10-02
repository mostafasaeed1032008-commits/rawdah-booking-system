import io
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd

# استيراد الأدوات المساعدة
CURRENT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = CURRENT_DIR.parent
COMPANIES_DIR = PROJECT_ROOT / "الشركات"

import database
import email_pool
from visa_extractor import resolve_person_type, FEMALE_FIRST_NAMES, clean_arabic_name

def detect_columns(columns: List[str]) -> Dict[str, Optional[str]]:
    """
    التعرف التلقائي الذكي على أسماء الأعمدة في ملف الإكسيل بالعربية والإنجليزية
    """
    mapping = {
        "name": None,
        "passport": None,
        "visa": None,
        "type": None,
        "email": None,
        "birth_date": None
    }

    col_clean = {c: str(c).strip().lower() for c in columns}

    for orig, c in col_clean.items():
        if "unnamed" in c:
            continue
        # عمود الاسم
        if mapping["name"] is None:
            if any(k in c for k in ["اسم المعتمر", "الاسم بالعربي", "اسم المسافر", "الاسم كامل", "الاسم", "name", "passenger", "pilgrim"]):
                mapping["name"] = orig

        # عمود الجواز
        if mapping["passport"] is None:
            if any(k in c for k in ["رقم الجواز", "جواز السفر", "الجواز", "passport", "doc no"]):
                mapping["passport"] = orig

        # عمود التأشيرة
        if mapping["visa"] is None:
            if any(k in c for k in ["رقم التأشيرة", "التأشيرة", "الفيزا", "رقم الحدود", "الحدود", "visa", "border"]):
                mapping["visa"] = orig

        # عمود النوع / الجنس
        if mapping["type"] is None:
            if any(k in c for k in ["النوع", "الجنس", "الفئة", "نوع المعتمر", "gender", "type", "sex"]):
                mapping["type"] = orig

        # عمود الإيميل
        if mapping["email"] is None:
            if any(k in c for k in ["إيميل", "ايميل", "البريد الإلكتروني", "البريد", "email", "e-mail", "mail"]):
                mapping["email"] = orig

        # عمود تاريخ الميلاد
        if mapping["birth_date"] is None:
            if any(k in c for k in ["تاريخ الميلاد", "الميلاد", "birth", "dob"]):
                mapping["birth_date"] = orig

    return mapping

def normalize_gender_and_type(raw_type: str, name: str, raw_birth: str = "") -> str:
    """
    توحيد وتصنيف الشخص إلى: رجال / نساء / طفل / طفلة
    """
    s = str(raw_type).strip().lower() if raw_type and str(raw_type).lower() != "nan" else ""
    first_name = name.strip().split()[0] if name and name.strip() else ""

    birth_year = None
    if raw_birth and str(raw_birth).lower() != "nan":
        b_str = str(raw_birth)
        m = re.search(r"\b(19\d{2}|20\d{2})\b", b_str)
        if m:
            birth_year = int(m.group(1))

    # إذا كانت القيمة محددة مسبقاً بدقة
    if "طفلة" in s or "بنت" in s or "girl" in s:
        return "طفلة"
    if "طفل" in s or "ولد" in s or "boy" in s or "child" in s:
        if first_name in FEMALE_FIRST_NAMES:
            return "طفلة"
        return "طفل"
    if any(k in s for k in ["نساء", "انثى", "أنثى", "ست", "سيدة", "امراة", "امرأة", "female", "f"]):
        is_child = (birth_year is not None and birth_year >= 2014)
        return "طفلة" if is_child else "نساء"
    if any(k in s for k in ["رجال", "رجل", "ذكر", "male", "m"]):
        is_child = (birth_year is not None and birth_year >= 2014)
        return "طفل" if is_child else "رجال"

    # تحليل عبر الاسم وتاريخ الميلاد
    is_female = (first_name in FEMALE_FIRST_NAMES)
    return resolve_person_type(is_female, birth_year, first_name)

def read_excel_dataframe(file_source: Any, filename: str) -> pd.DataFrame:
    """قراءة ملف الإكسيل أو CSV وإرجاع DataFrame نظيف"""
    fn = filename.lower()
    if fn.endswith(".csv"):
        try:
            df = pd.read_csv(file_source, encoding="utf-8-sig")
        except Exception:
            df = pd.read_csv(file_source, encoding="cp1256")
    elif fn.endswith(".xls"):
        df = pd.read_excel(file_source, engine="xlrd")
    else:
        df = pd.read_excel(file_source, engine="openpyxl")

    # حذف الأسطر الفارغة بالكامل
    df = df.dropna(how="all")
    # تحويل أسماء الأعمدة لنصوص نظيفة
    df.columns = [str(c).strip() for c in df.columns]
    return df

def parse_pilgrim_sheet(
    df: pd.DataFrame,
    mapping: Dict[str, Optional[str]],
    auto_allocate_emails: bool = True
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """
    استخراج وتجهيز سجلات المعتمرين من الجدول وتخصيص إيميلات فريدة
    """
    records = []
    missing_email_indices = []

    name_col = mapping.get("name")
    pass_col = mapping.get("passport")
    visa_col = mapping.get("visa")
    type_col = mapping.get("type")
    email_col = mapping.get("email")
    birth_col = mapping.get("birth_date")

    for idx, row in df.iterrows():
        raw_name = str(row[name_col]).strip() if name_col and pd.notna(row[name_col]) else ""
        if raw_name.lower() == "nan" or not raw_name:
            # إذا لم يوجد اسم وكان الجواز فارغاً نتجاهل السطر
            raw_pass_check = str(row[pass_col]).strip() if pass_col and pd.notna(row[pass_col]) else ""
            if not raw_pass_check or raw_pass_check.lower() == "nan":
                continue

        clean_name = clean_arabic_name(raw_name) if any('\u0600' <= c <= '\u06FF' for c in raw_name) else raw_name

        passport = str(row[pass_col]).strip().upper() if pass_col and pd.notna(row[pass_col]) else ""
        if passport.lower() == "nan": passport = ""

        visa = str(row[visa_col]).strip() if visa_col and pd.notna(row[visa_col]) else ""
        if visa.lower() == "nan": visa = ""
        # إزالة الفواصل العشرية إذا قرأ الإكسيل رقم التأشيرة كـ float
        if visa.endswith(".0"): visa = visa[:-2]

        raw_type = str(row[type_col]).strip() if type_col and pd.notna(row[type_col]) else ""
        raw_birth = str(row[birth_col]).strip() if birth_col and pd.notna(row[birth_col]) else ""
        person_type = normalize_gender_and_type(raw_type, clean_name, raw_birth)

        # استخراج الإيميل
        email = str(row[email_col]).strip().lower() if email_col and pd.notna(row[email_col]) else ""
        if email.lower() in ["nan", "لا يوجد إيميل متاح", "متجاهل - مكرر", "none", ""]:
            email = ""

        rec = {
            "الاسم": clean_name or "معتمر بدون اسم",
            "النوع": person_type,
            "رقم الجواز": passport,
            "رقم التأشيرة": visa,
            "الإيميل": email,
            "الحالة": "تم الاستيراد",
            "المصدر": "كشف إكسيل"
        }
        records.append(rec)
        if not email:
            missing_email_indices.append(len(records) - 1)

    # تخصيص إيميلات فريدة لمن لا يملكون إيميل
    emails_allocated_count = 0
    if auto_allocate_emails and missing_email_indices:
        needed = len(missing_email_indices)
        allocated = email_pool.allocate_and_consume_emails(needed)
        for i, assigned_mail in zip(missing_email_indices, allocated):
            records[i]["الإيميل"] = assigned_mail
            emails_allocated_count += 1

    # حساب الإحصائيات
    stats = {
        "total": len(records),
        "men": sum(1 for r in records if r["النوع"] == "رجال"),
        "women": sum(1 for r in records if r["النوع"] == "نساء"),
        "boys": sum(1 for r in records if r["النوع"] == "طفل"),
        "girls": sum(1 for r in records if r["النوع"] == "طفلة"),
        "emails_allocated": emails_allocated_count
    }
    return records, stats

def import_and_save_sheet(
    records: List[Dict[str, Any]],
    stats: Dict[str, int],
    company_name: str,
    filename: str,
    original_file_bytes: bytes,
    trip_details: str = "كشف مستورد من شيت إكسيل"
) -> int:
    """
    حفظ السجلات في قاعدة البيانات وتنظيم ملف الإكسيل في مجلد الشركة
    """
    company_name = company_name.strip()
    database.add_or_get_company(company_name)

    # إنشاء مجلد الشركة المنظم
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    dest_dir = COMPANIES_DIR / company_name / f"كشوفات_مستوردة_{timestamp}"
    dest_dir.mkdir(parents=True, exist_ok=True)

    # حفظ الملف الأصلي
    orig_path = dest_dir / f"الملف_الأصلي_{filename}"
    orig_path.write_bytes(original_file_bytes)

    # تصدير كشف إكسيل موحد للمنظومة
    export_path = dest_dir / f"كشف_معتمري_{company_name}_{timestamp}.xlsx"
    df_export = pd.DataFrame(records)
    df_export.to_excel(str(export_path), index=False, engine="openpyxl")

    # حفظ ملف الملاحظات
    notes_path = dest_dir / "تفاصيل_الاستيراد.txt"
    notes_content = (
        f"====================================================\n"
        f"كشف معتمرين مستورد يدوياً من ملف إكسيل\n"
        f"====================================================\n"
        f"الشركة: {company_name}\n"
        f"اسم الملف: {filename}\n"
        f"تاريخ الاستيراد: {datetime.now().strftime('%Y-%m-%d %I:%M %p')}\n"
        f"إجمالي المعتمرين: {stats['total']}\n"
        f"رجال: {stats['men']} | نساء: {stats['women']} | أطفال (ذكور): {stats['boys']} | طفلات (إناث): {stats['girls']}\n"
        f"إيميلات تم تخصيصها تلقائياً: {stats.get('emails_allocated', 0)}\n"
        f"----------------------------------------------------\n"
        f"الملاحظات:\n{trip_details}\n"
        f"====================================================\n"
    )
    notes_path.write_text(notes_content, encoding="utf-8")

    # حفظ في قاعدة البيانات المركزية
    request_id = database.save_booking_record(
        company_name=company_name,
        telegram_user_id=0,
        telegram_username="استيراد يدوي (Dashboard)",
        trip_details=trip_details or f"كشف مستورد ({filename})",
        summary_stats=stats,
        excel_path=str(export_path),
        notes_path=str(notes_path),
        pilgrim_records=records
    )

    return request_id
