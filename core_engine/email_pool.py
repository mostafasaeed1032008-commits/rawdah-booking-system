# -*- coding: utf-8 -*-
"""
منظومة حجز الروضة الشريفة - إدارة رصيد وشيت الإيميلات والتأشيرات المتاحة
Email & Visa Pool Manager
-------------------------------------------------------------
- دعم ديناميكي لأسماء ملفات الشيت (التأشيرات المتاحة.xlsx / شيت_الإيميلات_المتاحة.xlsx / CSV).
- كاش ذكي في الذاكرة (In-Memory Cache with mtime validation) لتسريع قراءة مئات الآلاف من الإيميلات في أجزاء من الثانية.
- حفظ وتحديث الملف الفعلي المستخدم دون تكرار أو إنشاء ملفات مكررة.
- استهلاك وتوزيع إيميلات فريدة لكل معتمر.
"""

import json
import re
from pathlib import Path
from typing import List, Tuple, Optional
import pandas as pd

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
CORE_ENGINE_DIR = PROJECT_ROOT / "core_engine"
USED_EMAILS_FILE = CORE_ENGINE_DIR / "used_emails.json"

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")

# ذاكرة تخزين مؤقت للسرعة الفائقة
_CACHED_EMAILS: Optional[List[str]] = None
_CACHED_MTIME: float = 0.0
_CACHED_POOL_PATH: Optional[Path] = None

def get_pool_file() -> Path:
    """البحث الديناميكي عن ملف شيت الإيميلات / التأشيرات المتاحة"""
    candidate_names = [
        "التأشيرات المتاحة.xlsx",
        "التأشيرات_المتاحة.xlsx",
        "التأشيرات المتاحة.csv",
        "التأشيرات_المتاحة.csv",
        "شيت_الإيميلات_المتاحة.xlsx",
        "شيت_الإيميلات_المتاحة.csv",
        "شيت الإيميلات المتاحة.xlsx",
        "الإيميلات_المتاحة.xlsx",
        "الإيميلات المتاحة.xlsx",
        "الإيميلات_المتاحة.csv",
        "الإيميلات المتاحة.csv"
    ]

    for name in candidate_names:
        p = PROJECT_ROOT / name
        if p.exists() and p.is_file():
            return p

    # بحث مرن عن أي ملف إكسيل يحتوي على كلمة تأشيرات أو إيميل
    for f in PROJECT_ROOT.glob("*.xlsx"):
        fn = f.name.lower()
        if any(k in fn for k in ["تأشير", "إيميل", "ايميل", "email", "visa"]):
            return f

    for f in PROJECT_ROOT.glob("*.csv"):
        fn = f.name.lower()
        if any(k in fn for k in ["تأشير", "إيميل", "ايميل", "email", "visa"]):
            return f

    # افتراضي
    return PROJECT_ROOT / "التأشيرات المتاحة.xlsx"

def load_used_emails() -> set:
    if USED_EMAILS_FILE.exists():
        try:
            return set(json.loads(USED_EMAILS_FILE.read_text(encoding="utf-8")))
        except Exception:
            pass
    return set()

def save_used_emails(used: set):
    try:
        USED_EMAILS_FILE.write_text(json.dumps(sorted(used), ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

def clear_used_emails():
    """تصفير قائمة الإيميلات المستخدمة للبدء برصيد كامل"""
    save_used_emails(set())
    global _CACHED_EMAILS, _CACHED_MTIME
    _CACHED_EMAILS = None
    _CACHED_MTIME = 0.0

def read_raw_emails_from_pool() -> List[str]:
    """قراءة كافة الإيميلات من ملف الشيت مع التخزين المؤقت الذكي"""
    global _CACHED_EMAILS, _CACHED_MTIME, _CACHED_POOL_PATH

    pool_file = get_pool_file()
    if not pool_file.exists():
        return []

    try:
        current_mtime = pool_file.stat().st_mtime
    except Exception:
        current_mtime = 0.0

    # إذا كانت البيانات مخزنة في الذاكرة والملف لم يتغير، نرجعها فوراً في 0.001 ثانية
    if _CACHED_EMAILS is not None and _CACHED_POOL_PATH == pool_file and current_mtime == _CACHED_MTIME:
        return _CACHED_EMAILS

    emails = []
    try:
        if pool_file.suffix.lower() in [".xlsx", ".xls"]:
            # فحص إذا كان هناك عمود باسم Email
            df = pd.read_excel(pool_file)
            col_target = None
            for c in df.columns:
                c_str = str(c).strip().lower()
                if c_str in ["email", "الإيميل", "ايميل", "البريد", "البريد الإلكتروني"]:
                    col_target = c
                    break

            if col_target is not None:
                series = df[col_target].dropna().astype(str)
                for s in series:
                    val = s.strip().lower().strip("\"' \t\r\n")
                    if "@" in val and EMAIL_REGEX.match(val):
                        emails.append(val)
            else:
                # إذا لم يكن هناك ترويسة صريحة نفحص كافة القيم
                for val in df.values.flatten():
                    s = str(val).strip().lower().strip("\"' \t\r\n")
                    if s and s != "nan" and "@" in s and EMAIL_REGEX.match(s):
                        emails.append(s)
        else:
            df = pd.read_csv(pool_file, header=None)
            for val in df.values.flatten():
                s = str(val).strip().lower().strip("\"' \t\r\n")
                if s and s != "nan" and "@" in s and EMAIL_REGEX.match(s):
                    emails.append(s)

    except Exception as e:
        print(f"Error reading email pool: {e}")

    # تفادي التكرار الداخلي مع الحفاظ على الترتيب
    seen = set()
    deduped = []
    for e in emails:
        if e not in seen:
            seen.add(e)
            deduped.append(e)

    # حفظ في الكاش
    _CACHED_EMAILS = deduped
    _CACHED_MTIME = current_mtime
    _CACHED_POOL_PATH = pool_file

    return deduped

def get_available_emails_count() -> int:
    """معرفة عدد الإيميلات المتاحة حالياً في الشيت (غير المستخدمة)"""
    used = load_used_emails()
    raw = read_raw_emails_from_pool()
    return sum(1 for e in raw if e not in used)

def allocate_and_consume_emails(count: int) -> List[str]:
    """
    سحب عدد معين من الإيميلات للمعتمرين الجدد:
    1. تخصيص إيميل فريد لكل معتمر غير مستخدم سابقاً.
    2. تسجيله في قائمة الإيميلات المستخدمة used_emails.json.
    3. حفظ التحديث على نفس ملف الشيت الفعلي.
    """
    global _CACHED_EMAILS, _CACHED_MTIME

    if count <= 0:
        return []

    pool_file = get_pool_file()
    all_emails = read_raw_emails_from_pool()
    used = load_used_emails()

    # استخراج الإيميلات المتاحة
    allocated = []
    remaining = []

    for e in all_emails:
        if e not in used and len(allocated) < count:
            allocated.append(e)
            used.add(e)
        else:
            if e not in used:
                remaining.append(e)

    # حفظ حالة الإيميلات المستخدمة
    save_used_emails(used)

    # حفظ الشيت بالإيميلات المتبقية فقط في نفس الملف الفعلي
    try:
        df_rem = pd.DataFrame({"Email": remaining})
        if pool_file.suffix.lower() == ".csv":
            df_rem.to_csv(pool_file, index=False, encoding="utf-8-sig")
        else:
            df_rem.to_excel(pool_file, index=False, engine="openpyxl")

        # تحديث الكاش
        _CACHED_EMAILS = remaining
        try:
            _CACHED_MTIME = pool_file.stat().st_mtime
        except Exception:
            _CACHED_MTIME = 0.0

    except PermissionError:
        # الملف مفتوح في برنامج Excel أو برنامج آخر
        # تم حفظ الإيميلات المستهلكة في used_emails.json بنجاح، فلا يوجد أي خطر لتكرار الإيميلات
        pass
    except Exception as e:
        pass

    return allocated

def add_emails_to_pool(new_emails: List[str]) -> Tuple[int, int]:
    """إضافة إيميلات جديدة إلى الشيت الفعلي"""
    global _CACHED_EMAILS, _CACHED_MTIME

    pool_file = get_pool_file()
    current_emails = read_raw_emails_from_pool()
    used = load_used_emails()
    current_set = set(current_emails)

    added = 0
    for raw in new_emails:
        e = str(raw).strip().lower().strip("\"' \t\r\n")
        if EMAIL_REGEX.match(e) and e not in current_set and e not in used:
            current_emails.append(e)
            current_set.add(e)
            added += 1

    df = pd.DataFrame({"Email": current_emails})
    if pool_file.suffix.lower() == ".csv":
        df.to_csv(pool_file, index=False, encoding="utf-8-sig")
    else:
        df.to_excel(pool_file, index=False, engine="openpyxl")

    _CACHED_EMAILS = current_emails
    try:
        _CACHED_MTIME = pool_file.stat().st_mtime
    except Exception:
        _CACHED_MTIME = 0.0

    return added, len(current_emails)

def return_unused_emails(unused_emails: List[str]):
    """إرجاع إيميلات تم تخصيصها مسبقاً للدفعة ولم تُستخدم"""
    global _CACHED_EMAILS, _CACHED_MTIME

    if not unused_emails:
        return
    used = load_used_emails()
    for e in unused_emails:
        used.discard(e)
    save_used_emails(used)

    pool_file = get_pool_file()
    current = read_raw_emails_from_pool()
    current_set = set(current)
    to_restore = [e for e in unused_emails if e not in current_set]
    if to_restore:
        updated = to_restore + current
        try:
            df = pd.DataFrame({"Email": updated})
            if pool_file.suffix.lower() == ".csv":
                df.to_csv(pool_file, index=False, encoding="utf-8-sig")
            else:
                df.to_excel(pool_file, index=False, engine="openpyxl")

            _CACHED_EMAILS = updated
            try:
                _CACHED_MTIME = pool_file.stat().st_mtime
            except Exception:
                _CACHED_MTIME = 0.0
        except PermissionError:
            pass
        except Exception as e:
            pass

def get_pool_preview(limit: int = 50) -> List[str]:
    """معاينة أول عدد من الإيميلات المتاحة للاستخدام"""
    pool_file = get_pool_file()
    if not pool_file.exists():
        return []
    try:
        used = load_used_emails()
        all_emails = read_raw_emails_from_pool()
        preview = []
        for e in all_emails:
            if e not in used:
                preview.append(e)
                if len(preview) >= limit:
                    break
        return preview
    except Exception:
        return []
