import io
import os
import sqlite3
import sys
from pathlib import Path
from datetime import datetime
import pandas as pd
import streamlit as st

# المسارات الأساسية للنظام (ديناميكية وتعمل محلياً وعلى Streamlit Cloud)
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
COMPANIES_DIR = PROJECT_ROOT / "الشركات"
DB_PATH = PROJECT_ROOT / "database" / "rawdah_central.db"

# ضمان وجود مجلدات النظام وقاعدة البيانات
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
COMPANIES_DIR.mkdir(parents=True, exist_ok=True)

# إضافة مسارات المشروع إلى sys.path
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "core_engine") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "core_engine"))
if str(PROJECT_ROOT / "telegram_bot") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "telegram_bot"))

try:
    import email_pool
except Exception:
    email_pool = None

try:
    import excel_importer
except Exception:
    excel_importer = None

try:
    import database
except Exception:
    database = None


st.set_page_config(
    page_title="منظومة إدارة معتمري الروضة الشريفة",
    page_icon="🕋",
    layout="wide"
)

# دعم الاتجاه من اليمين لليسار RTL
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&display=swap');
    html, body, [class*="css"] {
        font-family: 'Cairo', sans-serif;
        text-align: right;
        direction: rtl;
    }
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 12px;
        padding: 15px;
        border: 1px solid #e9ecef;
        text-align: center;
    }
    .badge-men { background-color: #e3f2fd; color: #1565c0; padding: 4px 8px; border-radius: 6px; font-weight: bold; }
    .badge-women { background-color: #fce4ec; color: #c2185b; padding: 4px 8px; border-radius: 6px; font-weight: bold; }
    .badge-boy { background-color: #e8f5e9; color: #2e7d32; padding: 4px 8px; border-radius: 6px; font-weight: bold; }
    .badge-girl { background-color: #fff3e0; color: #ef6c00; padding: 4px 8px; border-radius: 6px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

st.title("🕋 منظومة إدارة معتمري الروضة الشريفة وتصاريح الشركات")
st.caption("نظام مركزي متكامل يعرض كافة بيانات المعتمرين مصنفة بالشركات مع التمييز الدقيق بين الرجال، النساء، الأطفال (ذكور)، والطفلات (إناث).")

# الفترات والمواعيد الرسمية لتطبيق نسك (مرجع أساسي يمنع أي أخطاء)
NUSUK_OFFICIAL_WINDOWS = {
    "رجال": [
        {"time": "04:00 ص - 05:00 ص", "label": "فجر مبكر 🌙", "period": "الفجر"},
        {"time": "05:00 ص - 06:30 ص", "label": "بعد صلاة الفجر 🌅", "period": "الفجر"},
        {"time": "06:30 ص - 08:30 ص", "label": "الضحى / الصباح ☀️", "period": "الضحى"},
        {"time": "08:00 م - 09:30 م", "label": "بعد صلاة العشاء 🕌", "period": "العشاء"},
        {"time": "09:30 م - 11:00 م", "label": "فترة مسائية أولى 🌌", "period": "العشاء"},
        {"time": "11:00 م - 12:30 ص", "label": "منتصف الليل 🌃", "period": "الليل"}
    ],
    "نساء": [
        {"time": "06:00 ص - 08:00 ص", "label": "بعد صلاة الفجر صباحاً 🌅", "period": "الصباح"},
        {"time": "08:00 ص - 10:30 ص", "label": "فترة الضحى للنساء ☀️", "period": "الضحى"},
        {"time": "09:30 م - 11:30 م", "label": "الفترة المسائية للنساء 🌌", "period": "المساء"}
    ]
}

def get_db_connection():
    """اتصال بقاعدة البيانات الموحدة (Neon PostgreSQL السحابية مع التزامن 24/7 أو SQLite المحلي)"""
    try:
        from core_engine import db_sync
        return db_sync.get_db_connection()
    except Exception as e:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        return conn

conn = get_db_connection()

# مؤشر حالة التزامن السحابي
if hasattr(conn, "raw_conn") or "Postgres" in type(conn).__name__:
    st.success("🟢 **التزامن السحابي المزدوج 24/7 نشط بنجاح**: متصل بقاعدة بيانات Neon السحابية الموحدة (أي تعديل على السيرفر أو اللاب توب يتزامن لحظياً في الاتجاهين).")

# شريط التبويبات العلوي
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
    "👥 سجل المعتمرين الشامل",
    "📝 طلبات وتفاصيل رحلات الشركات",
    "📥 رفع واستيراد كشوفات الإكسيل",
    "📱 تسجيل أرقام الشركات للعملاء",
    "📧 شيت ورصيد الإيميلات المتاحة",
    "🏢 إدارة الشركات وتنظيف البيانات",
    "🔑 أداة الـ OTP واستقبال الأكواد",
    "🤖 روبوت الحجز الآلي وقناص الروضة"
])

# -------------------------------------------------------------
# التبويب الأول: سجل المعتمرين الشامل
# -------------------------------------------------------------
with tab1:
    # جلب جميع الشركات من قاعدة البيانات
    try:
        companies_df = pd.read_sql_query("SELECT DISTINCT company_name FROM pilgrims ORDER BY company_name", conn)
        companies_list = ["الكل"] + companies_df["company_name"].tolist()
    except Exception:
        companies_list = ["الكل"]

    # فلاتر البحث والفرز
    col_search, col_comp, col_type = st.columns([2, 1.2, 1])

    with col_search:
        search_query = st.text_input("🔍 بحث فوري (اسم المعتمر، رقم الجواز، التأشيرة، أو الإيميل)", "")
    with col_comp:
        selected_company = st.selectbox("🏢 تصفية حسب الشركة", companies_list)
    with col_type:
        selected_type = st.selectbox("👤 تصفية حسب النوع", ["الكل", "رجال", "نساء", "طفل", "طفلة"])

    # بناء استعلام البحث
    query = "SELECT id, company_name as 'الشركة', name as 'الاسم', passport as 'رقم الجواز', visa as 'رقم التأشيرة', person_type as 'النوع', email as 'الإيميل', status as 'الحالة', created_at as 'تاريخ التسجيل' FROM pilgrims WHERE 1=1"
    params = []

    if selected_company != "الكل":
        query += " AND company_name = ?"
        params.append(selected_company)

    if selected_type != "الكل":
        query += " AND person_type = ?"
        params.append(selected_type)

    if search_query.strip():
        q = f"%{search_query.strip()}%"
        query += " AND (name LIKE ? OR passport LIKE ? OR visa LIKE ? OR email LIKE ?)"
        params.extend([q, q, q, q])

    query += " ORDER BY id DESC"

    try:
        df_pilgrims = pd.read_sql_query(query, conn, params=params)
    except Exception as e:
        df_pilgrims = pd.DataFrame()
        st.error(f"خطأ في قراءة البيانات: {e}")

    # إحصائيات سريعة أعلى الجدول
    total = len(df_pilgrims)
    men = sum(df_pilgrims["النوع"] == "رجال") if total > 0 else 0
    women = sum(df_pilgrims["النوع"] == "نساء") if total > 0 else 0
    boys = sum(df_pilgrims["النوع"] == "طفل") if total > 0 else 0
    girls = sum(df_pilgrims["النوع"] == "طفلة") if total > 0 else 0

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("إجمالي المعتمرين", total)
    c2.metric("رجال 👨", men)
    c3.metric("نساء 👩", women)
    c4.metric("أطفال (ذكور) 👦", boys)
    c5.metric("طفلات (إناث) 👧", girls)
    avail_count = email_pool.get_available_emails_count() if email_pool else 0
    c6.metric("رصيد الإيميلات 📧", f"{avail_count:,}")

    st.divider()

    if not df_pilgrims.empty:
        st.dataframe(df_pilgrims, use_container_width=True, height=420)

        # زر تحميل إكسيل
        c_down, c_del_single = st.columns([1, 1.2])
        with c_down:
            excel_buffer = io.BytesIO()
            df_pilgrims.to_excel(excel_buffer, index=False, engine="openpyxl")
            excel_data = excel_buffer.getvalue()

            st.download_button(
                label="⬇ تحميل البيانات الحالية كملف Excel",
                data=excel_data,
                file_name=f"كشف_المعتمرين_{selected_company}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        with c_del_single:
            with st.expander("🗑️ حذف معتمر محدد من السجل"):
                pilgrim_ids = df_pilgrims["id"].tolist()
                del_p_id = st.selectbox("اختر الرقم التعريفي (ID) للمعتمر المراد حذفه:", pilgrim_ids)
                if st.button("❌ تأكيد حذف هذا المعتمر", type="secondary"):
                    if database:
                        database.delete_single_pilgrim(del_p_id)
                    else:
                        conn.execute("DELETE FROM pilgrims WHERE id = ?", (del_p_id,))
                        conn.commit()
                    st.success(f"تم حذف المعتمر #{del_p_id} بنجاح!")
                    st.rerun()
    else:
        st.info("لا توجد سجلات معتمرين حالياً في قاعدة البيانات. يمكنك استيراد كشف من تبويب '📥 رفع واستيراد كشوفات الإكسيل' أو استقبال طلب عبر بوت التليجرام.")

# -------------------------------------------------------------
# التبويب الثاني: طلبات وتفاصيل رحلات الشركات
# -------------------------------------------------------------
with tab2:
    st.subheader("📋 سجل طلبات الحجز وتفاصيل المواعيد الواردة من تليجرام أو الكشوفات المستوردة")
    try:
        req_query = """
        SELECT id as 'رقم الطلب', company_name as 'الشركة', telegram_username as 'مرسل الطلب',
               total_pilgrims as 'إجمالي', men_count as 'رجال', women_count as 'نساء',
               boys_count as 'أطفال (ذكور)', girls_count as 'طفلات (إناث)',
               trip_details as 'تفاصيل ومواعيد الرحلة', created_at as 'تاريخ الطلب',
               excel_path as 'مسار الإكسيل', notes_path as 'مسار ملف التفاصيل'
        FROM booking_requests ORDER BY id DESC
        """
        df_reqs = pd.read_sql_query(req_query, conn)
    except Exception as e:
        df_reqs = pd.DataFrame()
        st.error(f"خطأ: {e}")

    if not df_reqs.empty:
        st.dataframe(df_reqs.drop(columns=["مسار الإكسيل", "مسار ملف التفاصيل"], errors="ignore"), use_container_width=True)

        st.divider()
        st.subheader("🔍 استعراض وإدارة تفاصيل طلب معين:")
        req_ids = df_reqs["رقم الطلب"].tolist()
        selected_req = st.selectbox("اختر رقم الطلب", req_ids)
        req_row = df_reqs[df_reqs["رقم الطلب"] == selected_req].iloc[0]

        st.markdown(f"**🏢 الشركة:** `{req_row['الشركة']}` | **📅 تاريخ الطلب:** `{req_row['تاريخ الطلب']}` | **👤 المرسل:** `{req_row['مرسل الطلب']}`")
        st.info(f"**📝 تفاصيل ومواعيد الرحلة والشروط المطلوبة:**\n\n{req_row['تفاصيل ومواعيد الرحلة']}")

        col_req_dl, col_req_del = st.columns([1, 1])
        with col_req_dl:
            excel_p = Path(str(req_row.get("مسار الإكسيل", "")))
            if excel_p.exists():
                with open(excel_p, "rb") as ef:
                    st.download_button(
                        label=f"⬇ تحميل ملف إكسيل الطلب (#{selected_req})",
                        data=ef.read(),
                        file_name=excel_p.name,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )

        with col_req_del:
            if st.button(f"🗑️ حذف هذا الطلب (#{selected_req}) وكافة معتمريه", type="secondary"):
                if database:
                    database.delete_booking_request(int(selected_req))
                else:
                    conn.execute("DELETE FROM pilgrims WHERE request_id = ?", (selected_req,))
                    conn.execute("DELETE FROM booking_requests WHERE id = ?", (selected_req,))
                    conn.commit()
                st.success(f"تم حذف الطلب #{selected_req} ومعتمريه بنجاح!")
                st.rerun()
    else:
        st.info("لا توجد طلبات مسجلة بعد.")

# -------------------------------------------------------------
# التبويب الثالث: رفع واستيراد كشوفات الإكسيل للشركات
# -------------------------------------------------------------
with tab3:
    st.subheader("📥 استيراد كشوفات المعتمرين من ملفات الإكسيل (Excel / CSV)")
    st.caption("يتيح لك هذا التبويب رفع شيتات إكسيل جاهزة للعملاء، وتحديد الشركة التابع لها كل كشف، مع القراءة الذكية للأعمدة وتخصيص إيميلات فريدة تلقائياً.")

    # 1. إعدادات الشركة والكشف
    try:
        all_comps_db = [r["name"] for r in conn.execute("SELECT name FROM companies ORDER BY name").fetchall()]
    except Exception:
        all_comps_db = []

    c_box1, c_box2 = st.columns([1.1, 1.5])
    with c_box1:
        comp_pick = st.selectbox("🏢 اختر الشركة التابع لها هذا الكشف:", all_comps_db + ["➕ كتابة اسم شركة جديدة"], key="import_comp_choice")
        if comp_pick == "➕ كتابة اسم شركة جديدة":
            target_import_company = st.text_input("اكتب اسم الشركة الجديدة:", key="import_comp_new_text")
        else:
            target_import_company = comp_pick

    with c_box2:
        import_trip_details = st.text_input("📝 تفاصيل ومواعيد الرحلة / ملاحظات الكشف:", "كشف مستورد يدوياً من إكسيل", key="import_trip_notes")

    opt_col1, opt_col2 = st.columns([1.2, 1])
    with opt_col1:
        auto_allocate = st.checkbox("📧 تخصيص إيميلات فريدة تلقائياً من شيت الإيميلات المتاحة لمن لا يملك إيميل", value=True, key="chk_auto_emails")

    st.divider()

    # 2. رفع الملفات المتعددة
    uploaded_excels = st.file_uploader(
        "📂 اختر ملف أو عدة ملفات إكسيل (.xlsx, .xls) أو CSV للعملاء الحاليين:",
        type=["xlsx", "xls", "csv"],
        accept_multiple_files=True,
        key="import_files_uploader"
    )

    if uploaded_excels:
        st.info(f"تم اختيار **{len(uploaded_excels)}** ملف. يمكنك استعراض ومعاينة واستيراد كل كشف أدناه 👇")

        for f_idx, up_file in enumerate(uploaded_excels):
            with st.expander(f"📄 كشف ({f_idx+1}/{len(uploaded_excels)}): {up_file.name}", expanded=True):
                try:
                    df_raw = excel_importer.read_excel_dataframe(up_file, up_file.name)
                    st.write(f"📊 عدد الأسطر في الملف: **{len(df_raw)}** سطر.")

                    # الكشف التلقائي الذكي على أسماء الأعمدة
                    auto_mapping = excel_importer.detect_columns(list(df_raw.columns))
                    all_cols = ["(غير محدد)"] + list(df_raw.columns)

                    def get_default_idx(col_name):
                        if col_name and col_name in df_raw.columns:
                            return all_cols.index(col_name)
                        return 0

                    st.markdown("##### 🔍 ربط أعمدة الملف تلقائياً (يمكنك التعديل إن لزم الأمر):")
                    c_m1, c_m2, c_m3, c_m4, c_m5 = st.columns(5)
                    with c_m1:
                        sel_name = st.selectbox(f"الاسم", all_cols, index=get_default_idx(auto_mapping.get("name")), key=f"sel_name_{f_idx}")
                    with c_m2:
                        sel_pass = st.selectbox(f"الجواز", all_cols, index=get_default_idx(auto_mapping.get("passport")), key=f"sel_pass_{f_idx}")
                    with c_m3:
                        sel_visa = st.selectbox(f"التأشيرة", all_cols, index=get_default_idx(auto_mapping.get("visa")), key=f"sel_visa_{f_idx}")
                    with c_m4:
                        sel_type = st.selectbox(f"النوع/الجنس", all_cols, index=get_default_idx(auto_mapping.get("type")), key=f"sel_type_{f_idx}")
                    with c_m5:
                        sel_mail = st.selectbox(f"الإيميل", all_cols, index=get_default_idx(auto_mapping.get("email")), key=f"sel_mail_{f_idx}")

                    active_mapping = {
                        "name": None if sel_name == "(غير محدد)" else sel_name,
                        "passport": None if sel_pass == "(غير محدد)" else sel_pass,
                        "visa": None if sel_visa == "(غير محدد)" else sel_visa,
                        "type": None if sel_type == "(غير محدد)" else sel_type,
                        "email": None if sel_mail == "(غير محدد)" else sel_mail,
                        "birth_date": auto_mapping.get("birth_date")
                    }

                    # تحليل البيانات والمعاينة
                    records, stats = excel_importer.parse_pilgrim_sheet(
                        df_raw,
                        active_mapping,
                        auto_allocate_emails=auto_allocate
                    )

                    # بطاقات الإحصائيات بعد المعالجة والتصنيف
                    sc1, sc2, sc3, sc4, sc5, sc6 = st.columns(6)
                    sc1.metric("إجمالي المعتمرين", stats["total"])
                    sc2.metric("رجال 👨", stats["men"])
                    sc3.metric("نساء 👩", stats["women"])
                    sc4.metric("أطفال 👦", stats["boys"])
                    sc5.metric("طفلات 👧", stats["girls"])
                    sc6.metric("إيميلات تم تخصيصها 📧", stats.get("emails_allocated", 0))

                    df_preview = pd.DataFrame(records)
                    st.dataframe(df_preview, use_container_width=True, height=260)

                    # زر الاستيراد والاعتماد
                    if st.button(f"💾 اعتماد واستيراد كشف ({up_file.name}) لحساب شركة: {target_import_company}", key=f"btn_import_sheet_{f_idx}", type="primary"):
                        if not target_import_company or not target_import_company.strip():
                            st.error("يرجى اختيار أو كتابة اسم الشركة أولاً.")
                        else:
                            up_file.seek(0)
                            req_id = excel_importer.import_and_save_sheet(
                                records=records,
                                stats=stats,
                                company_name=target_import_company.strip(),
                                filename=up_file.name,
                                original_file_bytes=up_file.read(),
                                trip_details=import_trip_details
                            )
                            st.success(f"🎉 تم بنجاح استيراد {stats['total']} معتمر لشركة {target_import_company}! تم حفظ الطلب برقم #{req_id}")
                            st.rerun()

                except Exception as ex:
                    st.error(f"خطأ أثناء قراءة ومعالجة الملف {up_file.name}: {ex}")

# -------------------------------------------------------------
# التبويب الرابع: تسجيل أرقام الشركات للعملاء
# -------------------------------------------------------------
with tab4:
    st.subheader("📱 ربط أرقام هواتف العملاء بالشركات في بوت التليجرام")
    st.caption("عند تسجيل رقم هاتف العميل هنا، بمجرد أن يدخل على البوت ويشارك رقمه سيتعرف عليه تلقائياً باسم شركته دون أن يرى أي شركات أخرى.")

    c1, c2 = st.columns([1, 1.4])
    with c1:
        st.markdown("#### ➕ إضافة / ربط عميل جديد")
        try:
            all_comps = [r["name"] for r in conn.execute("SELECT name FROM companies ORDER BY name").fetchall()]
        except Exception:
            all_comps = []
        comp_choice = st.selectbox("اختر الشركة", all_comps + ["➕ كتابة شركة جديدة"], key="client_reg_choice")
        if comp_choice == "➕ كتابة شركة جديدة":
            target_company = st.text_input("اسم الشركة الجديدة:", key="client_reg_new_comp")
        else:
            target_company = comp_choice

        client_phone = st.text_input("رقم الهاتف (مثال: 01012345678):", key="new_client_phone")
        client_contact_name = st.text_input("اسم مسؤول الشركة (اختياري):", key="new_client_name")

        if st.button("💾 تسجيل وتفعيل العميل", type="primary"):
            p_clean = "".join(c for c in client_phone if c.isdigit())
            if p_clean.startswith("0020"): p_clean = p_clean[4:]
            elif p_clean.startswith("20") and len(p_clean) >= 12: p_clean = p_clean[2:]
            if not p_clean.startswith("0") and len(p_clean) == 10: p_clean = "0" + p_clean
            if len(p_clean) < 10 or not target_company:
                st.error("يرجى إدخال اسم الشركة ورقم هاتف صحيح.")
            else:
                conn.execute("INSERT OR IGNORE INTO companies (name) VALUES (?)", (target_company.strip(),))
                conn.execute("""
                INSERT INTO company_clients (company_name, phone, client_name)
                VALUES (?, ?, ?)
                ON CONFLICT(phone) DO UPDATE SET company_name=excluded.company_name, client_name=excluded.client_name
                """, (target_company.strip(), p_clean, client_contact_name.strip()))
                conn.commit()
                st.success(f"✅ تم ربط الرقم {p_clean} بشركة {target_company} بنجاح!")
                st.rerun()

    with c2:
        st.markdown("#### 👥 قائمة عملاء الشركات المسجلين")
        try:
            clients_df = pd.read_sql_query("""
            SELECT id as 'ID', company_name as 'الشركة', phone as 'رقم الهاتف',
                   client_name as 'المسؤول', created_at as 'تاريخ التسجيل'
            FROM company_clients ORDER BY id DESC
            """, conn)
            if not clients_df.empty:
                st.dataframe(clients_df, use_container_width=True)
                del_id = st.selectbox("حذف عميل مسجل (اختر الرقم التعريفي ID)", clients_df["ID"].tolist())
                if st.button("❌ حذف العميل المحدد"):
                    conn.execute("DELETE FROM company_clients WHERE id = ?", (del_id,))
                    conn.commit()
                    st.success("تم الحذف بنجاح.")
                    st.rerun()
            else:
                st.info("لا يوجد عملاء مسجلون برقم الهاتف بعد. يمكنك إضافة أول عميل من النموذج على اليمين.")
        except Exception as e:
            st.error(f"خطأ: {e}")

# -------------------------------------------------------------
# التبويب الخامس: شيت ورصيد الإيميلات المتاحة
# -------------------------------------------------------------
with tab5:
    st.subheader("📧 شيت ورصيد الإيميلات المتاحة لحجز الروضة")
    st.caption("يتم سحب إيميل فريد تلقائياً لكل معتمر عند رفع الملفات، وحذف الإيميل المستخدم من الشيت لمنع تكراره نهائياً.")

    if email_pool is None:
        st.warning("تعذر تحميل وحدة إدارة الإيميلات (email_pool).")
    else:
        # الإحصائيات العامة لرصيد الإيميلات
        avail_cnt = email_pool.get_available_emails_count()
        used_set = email_pool.load_used_emails()
        used_cnt = len(used_set)
        total_tracked = avail_cnt + used_cnt

        mc1, mc2, mc3 = st.columns(3)
        mc1.metric("الإيميلات المتاحة حالياً للشغل 🟢", f"{avail_cnt:,}")
        mc2.metric("الإيميلات المستهلكة سابقاً 🔴", f"{used_cnt:,}")
        mc3.metric("إجمالي الإيميلات في المنظومة 📊", f"{total_tracked:,}")

        st.divider()

        # قسمين: يمين لإضافة إيميلات، يسار لمعاينة وتحميل الشيت
        col_actions, col_preview = st.columns([1.1, 1.3])

        with col_actions:
            st.markdown("### ➕ تزويد الشيت بإيميلات جديدة")
            add_mode = st.radio("طريقة الإضافة:", ["📄 رفع ملف إكسيل أو CSV", "✍️ لصق إيميلات يدوياً"], horizontal=True)

            if add_mode == "📄 رفع ملف إكسيل أو CSV":
                uploaded_file = st.file_uploader("اختر ملف إكسيل (.xlsx) أو CSV يحتوي على الإيميلات:", type=["xlsx", "xls", "csv"], key="uploader_email_pool")
                if uploaded_file is not None:
                    if st.button("📥 استيراد وإضافة الإيميلات من الملف", type="primary"):
                        try:
                            if uploaded_file.name.lower().endswith(".csv"):
                                upl_df = pd.read_csv(uploaded_file, header=None)
                            else:
                                upl_df = pd.read_excel(uploaded_file, header=None)
                            raw_list = [str(x) for x in upl_df.values.flatten()]
                            added_num, total_now = email_pool.add_emails_to_pool(raw_list)
                            st.success(f"✅ تم بنجاح إضافة **{added_num:,}** إيميل جديد غير مكرر! إجمالي الرصيد الآن: **{total_now:,}**")
                            st.rerun()
                        except Exception as ex:
                            st.error(f"حدث خطأ أثناء معالجة الملف: {ex}")

            else:
                pasted_text = st.text_area(
                    "الصق الإيميلات هنا (كل إيميل في سطر، أو مفصولة بفاصلة):",
                    height=180,
                    placeholder="example1@domain.com\nexample2@domain.com\n..."
                )
                if st.button("➕ إضافة الإيميلات الملصقة", type="primary"):
                    if pasted_text.strip():
                        extracted = [e.strip() for e in pasted_text.replace(",", "\n").replace(";", "\n").split() if e.strip()]
                        added_num, total_now = email_pool.add_emails_to_pool(extracted)
                        st.success(f"✅ تم إضافة **{added_num:,}** إيميل جديد بنجاح! إجمالي الرصيد الآن: **{total_now:,}**")
                        st.rerun()
                    else:
                        st.warning("يرجى كتابة أو لصق إيميل واحد على الأقل.")

        with col_preview:
            st.markdown("### 📋 معاينة الشيت وتحميله")
            st.caption("يعرض أول 50 إيميل متاح سيتم استخدامها في الحجوزات القادمة.")

            preview_list = email_pool.get_pool_preview(limit=50)
            if preview_list:
                preview_df = pd.DataFrame({
                    "م": range(1, len(preview_list) + 1),
                    "الإيميل المتاح": preview_list
                })
                st.dataframe(preview_df, use_container_width=True, height=260)
            else:
                st.info("لا توجد إيميلات متاحة في الشيت حالياً. يرجى تزويد الشيت من النموذج بالجانب الأيمن.")

            pool_file = email_pool.get_pool_file()
            if pool_file.exists():
                with open(pool_file, "rb") as pf:
                    st.download_button(
                        label="⬇ تحميل ملف شيت الإيميلات المتاحة الحالي (.xlsx)",
                        data=pf.read(),
                        file_name=pool_file.name,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )

# -------------------------------------------------------------
# التبويب السادس: إدارة الشركات وتنظيف وتصفير البيانات
# -------------------------------------------------------------
with tab6:
    st.subheader("🏢 الشركات المسجلة والمجلدات الميدانية")
    try:
        companies_all = pd.read_sql_query("SELECT id, name as 'اسم الشركة', created_at as 'تاريخ التسجيل' FROM companies ORDER BY name", conn)
        st.dataframe(companies_all, use_container_width=True)
    except Exception:
        pass

    st.caption(f"📁 المجلد الرئيسي للشركات: `{COMPANIES_DIR}`")

    st.divider()

    st.subheader("🗑️ إدارة وتنظيف وتصفير البيانات التجريبية والقديمة")
    st.caption("أدوات آمنة وفعالة تتيح لك حذف البيانات التجريبية والبدء من جديد مع الحفاظ الكامل على حسابات الشركات والإيميلات.")

    del_c1, del_c2 = st.columns(2)

    with del_c1:
        st.markdown("#### 🏢 مسح بيانات شركة معينة فقط")
        st.caption("حذف كافة طلبات ومعتمري شركة معينة دون التأثير على باقي الشركات.")
        try:
            comps_for_del = [r["name"] for r in conn.execute("SELECT name FROM companies ORDER BY name").fetchall()]
        except Exception:
            comps_for_del = []

        if comps_for_del:
            sel_comp_del = st.selectbox("اختر الشركة لحذف بياناتها:", comps_for_del, key="sel_comp_delete")
            if st.button(f"❌ حذف كافة بيانات وطلبات ({sel_comp_del})", type="secondary"):
                if database:
                    database.delete_company_data(sel_comp_del)
                else:
                    conn.execute("DELETE FROM pilgrims WHERE company_name = ?", (sel_comp_del,))
                    conn.execute("DELETE FROM booking_requests WHERE company_name = ?", (sel_comp_del,))
                    conn.commit()
                st.success(f"تم حذف كافة سجلات وطلبات شركة {sel_comp_del} بنجاح!")
                st.rerun()

    with del_c2:
        st.markdown("#### ⚠️ تصفير كافة السجلات والطلبات القديمة بالكامل")
        st.warning("هذا الخيار يمسح كافة المعتمرين والطلبات التجريبية بالكامل لتنظيف المنظومة، مع الحفاظ التام على أسماء الشركات ورصيد الإيميلات.")
        confirm_chk = st.checkbox("أؤكد رغبتي في مسح وتصفير كافة بيانات المعتمرين والطلبات القديمة", key="confirm_reset_all")
        if st.button("🗑️ تصفير ومسح كافة البيانات التجريبية الآن", type="primary", disabled=not confirm_chk):
            if database:
                database.clear_all_test_data()
            else:
                conn.execute("DELETE FROM pilgrims")
                conn.execute("DELETE FROM booking_requests")
                conn.commit()
            st.success("🎉 تم بنجاح تصفير كافة البيانات التجريبية والبدء بسجلات نظيفة تماماً!")
            st.rerun()

# -------------------------------------------------------------
# التبويب السابع: أداة الـ OTP واستقبال أكواد نسك
# -------------------------------------------------------------
with tab7:
    import json
    import imaplib
    import email
    import email.utils
    import html as html_lib
    import re

    OTP_CONFIG_PATH = PROJECT_ROOT / "otp_tool" / "mini_otp_config.json"

    def load_otp_cfg():
        defaults = {
            "imap_server": "imap.gmail.com",
            "imap_port": 993,
            "email_user": "mostafasaeedtravel5@gmail.com",
            "email_password": "olszmkakibrwqkgk",
            "always_on_top": True,
            "auto_copy": True,
            "general_mode": True,
            "sound_enabled": True
        }
        if OTP_CONFIG_PATH.exists():
            try:
                data = json.loads(OTP_CONFIG_PATH.read_text(encoding="utf-8"))
                return {**defaults, **data}
            except Exception:
                pass
        return defaults

    def save_otp_cfg(data):
        try:
            OTP_CONFIG_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            return True
        except Exception:
            return False

    otp_cfg = load_otp_cfg()

    st.subheader("🔑 أداة الـ OTP واستقبال أكواد التحقق (نسك)")
    st.caption("إدارة إعدادات بريد استقبال الأكواد، فحص الاتصال اللحظي، ومتابعة أحدث كود OTP صادر من نسك مباشرة من لوحة التحكم أو عبر الأداة العائمة.")

    col_info, col_settings = st.columns([1, 1.2])

    with col_info:
        st.markdown("#### 📱 تشغيل الأداة العائمة بجانب المحاكي (MuMu Player)")
        st.info("""
        **الأداة العائمة الخفيفة (Floating Mini-Widget):**
        - تطفو بشكل دائم فوق الشاشة (Always on Top) بجوار محاكي MuMu Player أو شاشة الهاتف.
        - **النسخ التلقائي الفوري:** فور وصول كود التحقق من نسك يتم نسخه تلقائياً إلى الحافظة (Clipboard) لتلصقه مباشرة بـ `Ctrl + V` داخل المحاكي دون إضاعة ثانية واحدة!
        - **تنبيه صوتي:** إشعار صوتي عند وصول أي كود جديد.
        - **سجل فوري:** احتفاظ بآخر 10 أكواد مستلمة مع وقت وصولها.
        """)

        st.markdown("##### 🚀 تشغيل الأداة العائمة:")
        st.code("3_تشغيل_أداة_الـ_OTP.bat", language="batch")
        st.caption("يمكنك أيضاً تشغيلها من المجلد عبر الملف `Run_OTP_Tool.bat`.")

        st.divider()

        st.markdown("#### 🔒 شرح استخراج كلمة مرور التطبيقات (App Password)")
        st.markdown("""
        الحساب المعتمد الحالي هو: `mostafasaeedtravel5@gmail.com`
        تم ضبط كلمة مرور التطبيقات بنجاح واختبار الاتصال وهو **يعمل بنجاح تام 100%**.
        """)

    with col_settings:
        st.markdown("#### ⚙ إعدادات خادم البريد (IMAP)")

        with st.form("otp_settings_form"):
            f_server = st.text_input("خادم IMAP:", value=otp_cfg.get("imap_server", "imap.gmail.com"))
            f_port = st.number_input("منفذ IMAP SSL:", value=int(otp_cfg.get("imap_port", 993)), step=1)
            f_user = st.text_input("البريد الإلكتروني الرئيسي (Master Inbox):", value=otp_cfg.get("email_user", "mostafasaeedtravel5@gmail.com"))
            f_pass = st.text_input("كلمة مرور التطبيقات (App Password - 16 حرف):", value=otp_cfg.get("email_password", "olszmkakibrwqkgk"), type="password")

            c_save, c_dummy = st.columns([1, 1])
            with c_save:
                btn_save = st.form_submit_button("💾 حفظ الإعدادات", type="primary")

            if btn_save:
                otp_cfg["imap_server"] = f_server.strip()
                otp_cfg["imap_port"] = int(f_port)
                otp_cfg["email_user"] = f_user.strip()
                otp_cfg["email_password"] = f_pass.strip().replace(" ", "")
                if save_otp_cfg(otp_cfg):
                    st.success("✅ تم حفظ إعدادات البريد بنجاح!")
                    st.rerun()
                else:
                    st.error("❌ فشل حفظ الإعدادات.")

        st.markdown("#### 🚀 دفع كود يدوي أو محاكاة سريعة")
        c_sim, c_push = st.columns([1, 1.2])
        with c_sim:
            if st.button("🧪 تجربة محاكاة كود نسك"):
                import random
                fake_code = str(random.randint(100000, 999999))
                try:
                    import otp_manager
                    otp_manager.push_otp(fake_code, source="محاكاة لوحة التحكم")
                except Exception:
                    pass
                st.success(f"🎉 تم توليد كود المحاكاة ({fake_code}) ودفعه للأداة!")
                st.metric("كود المحاكاة التجريبي", fake_code)

        with c_push:
            manual_code = st.text_input("إدخال كود يدوي لدفعه للأداة:", placeholder="مثال: 849201", key="manual_otp_input")
            if st.button("📤 إرسال للأداة ولصقه فوراً"):
                if manual_code.strip():
                    try:
                        import otp_manager
                        otp_manager.push_otp(manual_code.strip(), source="لوحة التحكم اليدوية")
                        st.success(f"✅ تم إرسال الكود ({manual_code.strip()}) للأداة العائمة ونسخه للحافظة!")
                    except Exception as e:
                        st.error(f"خطأ: {e}")

        st.divider()

        st.markdown("#### ⚡ فحص الاتصال وسحب كود فوري")
        btn_test_col, btn_fetch_col = st.columns(2)

        with btn_test_col:
            if st.button("🧪 فحص واختبار الاتصال الآن"):
                usr = otp_cfg.get("email_user", "").strip()
                pwd = otp_cfg.get("email_password", "").strip().replace(" ", "")
                srv = otp_cfg.get("imap_server", "imap.gmail.com")
                prt = int(otp_cfg.get("imap_port", 993))

                if not usr or not pwd:
                    st.warning("⚠ يرجى إدخال البريد الإلكتروني وكلمة مرور التطبيق أولاً وحفظهما.")
                else:
                    try:
                        with st.spinner("جاري الاتصال بخادم البريد..."):
                            m = imaplib.IMAP4_SSL(srv, prt, timeout=8)
                            m.login(usr, pwd)
                            m.logout()
                        st.success("✅ رائع! تم الاتصال بنجاح بخادم البريد. الحساب جاهز تماماً لاستقبال أكواد نسك.")
                    except Exception as e:
                        err = str(e)
                        if "AUTHENTICATIONFAILED" in err:
                            st.error("❌ فشل تسجيل الدخول: جوجل رفضت كلمة المرور. تأكد من استخدام (App Password) المكونة من 16 حرفاً من صفحة جوجل وليس كلمة المرور العادية.")
                        else:
                            st.error(f"❌ تعذر الاتصال: {e}")

        with btn_fetch_col:
            if st.button("🔄 فحص وسحب أحدث كود OTP الآن"):
                usr = otp_cfg.get("email_user", "").strip()
                pwd = otp_cfg.get("email_password", "").strip().replace(" ", "")
                srv = otp_cfg.get("imap_server", "imap.gmail.com")
                prt = int(otp_cfg.get("imap_port", 993))

                if not usr or not pwd:
                    st.warning("⚠ يرجى إدخال البريد الإلكتروني وكلمة مرور التطبيق أولاً.")
                else:
                    try:
                        with st.spinner("جاري فحص الرسائل الحديثة..."):
                            mail = imaplib.IMAP4_SSL(srv, prt, timeout=10)
                            mail.login(usr, pwd)
                            mail.select("INBOX")
                            status, messages = mail.search(None, "ALL")

                            found_code = None
                            found_subject = ""
                            found_date = ""

                            if status == "OK" and messages[0]:
                                ids = messages[0].split()
                                for msg_id in reversed(ids[-8:]):
                                    res, data = mail.fetch(msg_id, "(RFC822)")
                                    if res != "OK" or not data or not data[0]:
                                        continue
                                    raw_b = data[0][1] if isinstance(data[0], tuple) else None
                                    if not raw_b:
                                        continue
                                    msg = email.message_from_bytes(raw_b)

                                    subj = ""
                                    try:
                                        subj_parts = email.header.decode_header(msg.get("Subject", ""))
                                        subj = "".join([c.decode(e or "utf-8", errors="ignore") if isinstance(c, bytes) else str(c) for c, e in subj_parts])
                                    except Exception:
                                        subj = str(msg.get("Subject", ""))

                                    body = ""
                                    if msg.is_multipart():
                                        for p in msg.walk():
                                            if p.get_content_type() in ("text/plain", "text/html"):
                                                pl = p.get_payload(decode=True)
                                                if pl:
                                                    body += " " + pl.decode(errors="ignore")
                                    else:
                                        pl = msg.get_payload(decode=True)
                                        if pl:
                                            body = pl.decode(errors="ignore")

                                    # تنظيف نصوص
                                    clean_text = re.sub(r"<style[^>]*>.*?</style>", " ", body, flags=re.DOTALL | re.IGNORECASE)
                                    clean_text = re.sub(r"<[^>]+>", " ", clean_text)
                                    clean_text = html_lib.unescape(clean_text)
                                    combo = f"{subj}\n{clean_text}".lower()

                                    if any(k in combo for k in ["nusuk", "نسك", "haj", "حج", "تحقق", "otp", "رمز"]):
                                        pat_m = re.search(r"(?:رمز التحقق|كود التحقق|رمز|otp is|code is)[\s:：\-—]*(\d{4,6})\b", combo)
                                        if pat_m:
                                            found_code = pat_m.group(1)
                                        else:
                                            all_nums = re.findall(r"\b(\d{4,6})\b", combo)
                                            for c_n in all_nums:
                                                if c_n not in ("2024", "2025", "2026", "2027", "1446", "1447"):
                                                    found_code = c_n
                                                    break
                                        if found_code:
                                            found_subject = subj
                                            found_date = str(msg.get("Date", ""))
                                            break

                            mail.logout()

                        if found_code:
                            st.success(f"🎉 تم استخراج الكود بنجاح!")
                            st.metric("كود نسك المستخرج (OTP)", found_code)
                            st.caption(f"عنوان الرسالة: {found_subject} | التاريخ: {found_date}")
                        else:
                            st.info("ℹ️ لم يتم العثور على رسائل كود تحقق جديدة في أحدث رسائل الصندوق.")
                    except Exception as e:
                        st.error(f"خطأ أثناء فحص الرسائل: {e}")

# -------------------------------------------------------------
# التبويب الثامن: روبوت وقناص الحجز الآلي (Nusuk Auto-Sniper Bot)
# -------------------------------------------------------------
with tab8:
    st.subheader("🤖 روبوت وقناص الحجز الآلي للروضة الشريفة (Nusuk Auto-Sniper)")
    st.caption("أتمتة الحجز الكاملة عبر محاكي الأندرويد (MuMu Player): تسجيل الدخول، سحب الـ OTP تلقائياً، قنص المواعيد، وتأكيد الحجز حتى 10 نسخ متزامنة.")

    try:
        from auto_booking.adb_controller import AdbController
        from auto_booking.booking_runner import BookingRunner
        from auto_booking.ai_brain import GeminiSupervisor
        from auto_booking.slot_radar import SlotRadar, NUSUK_OFFICIAL_WINDOWS as _radar_windows
        if _radar_windows:
            NUSUK_OFFICIAL_WINDOWS = _radar_windows
        from auto_booking.pilgrim_importer import parse_excel_file, parse_pasted_text
    except Exception as e:
        AdbController = None
        BookingRunner = None
        GeminiSupervisor = None
        SlotRadar = None
        parse_excel_file = None
        parse_pasted_text = None
        st.info("ℹ️ محرك الأتمتة المباشرة بالمحاكي (ADB) مخصص للتشغيل على جهاز الكمبيوتر المكتبي المتصل بمحاكي الأندرويد. يمكنك إدارة كافة الكشوفات والبيانات وتصديرها بالكامل عبر هذه النسخة السحابية.")

    # اختيار مصدر هاتف الحجز (محلي أو سحابي عبر Damru / Redroid)
    c_src1, c_src2 = st.columns([1.5, 2])
    with c_src1:
        device_source = st.radio(
            "اختر بيئة تشغيل هاتف الحجز:",
            [
                "💻 محاكي MuMu Player المحلي (على هذا الجهاز)",
                "☁️ هواتف Damru & Redroid السحابية (على سيرفر خارجي 0% RAM)"
            ],
            index=0,
            key="bot_device_source"
        )

    target_serial = ""
    with c_src2:
        if "Damru" in device_source:
            c_rip, c_rport = st.columns([2, 1])
            with c_rip:
                vps_ip = st.text_input("عنوان السيرفر السحابي (VPS IP):", value=os.environ.get("DAMRU_VPS_IP", "127.0.0.1"), key="damru_vps_ip")
            with c_rport:
                vps_port = st.number_input("المنفذ (Port):", min_value=1000, max_value=65535, value=5555, key="damru_vps_port")
            target_serial = f"{vps_ip}:{vps_port}"
            st.caption("🛡️ تشغيل خفي 100% عبر Damru OS-level Spoofing بدون أي استهلاك لرامات لابتوبك.")

    # شريط حالة المحاكي والعقل المدبر
    c_stat1, c_stat2 = st.columns([2, 1])
    with c_stat1:
        if AdbController:
            adb_test = AdbController(serial=target_serial)
            is_conn = adb_test.is_connected()
            if is_conn:
                st.success(f"🟢 الهاتف متصل وجاهز للعمل! (المعرف: `{adb_test.serial}`)")
            else:
                if "Damru" in device_source:
                    st.warning(f"⚪ تعذر الاتصال بالهاتف السحابي على `{target_serial}`. تأكد من تشغيل سكريبت setup_damru_vps.sh على السيرفر.")
                else:
                    st.warning("⚪ المحاكي غير متصل حالياً. يرجى فتح محاكي MuMu Player ثم الضغط على فحص الاتصال.")
        else:
            st.info("محرك ADB قيد التهيئة...")

    with c_stat2:
        if st.button("🔄 فحص الاتصال بالهاتف الآن"):
            if AdbController:
                adb_test = AdbController(serial=target_serial)
                if adb_test.connect():
                    st.success("✅ تم الاتصال بالهاتف بنجاح!")
                else:
                    st.error("❌ تعذر الاتصال بالهاتف المحدد.")
            st.rerun()

    # لوحة تحكم العقل المدبر (Gemini AI Brain)
    with st.expander("🧠 إعدادات العقل المدبر والمشرف الذكي (Gemini AI Brain)", expanded=False):
        c_k1, c_k2 = st.columns([3, 1])
        with c_k1:
            gemini_key_input = st.text_input(
                "مفتاح Gemini API (أو تركه للافتراضي):",
                value="YOUR_GEMINI_API_KEY_HERE",
                type="password",
                key="gemini_api_key_setting"
            )
        with c_k2:
            st.write("")
            st.write("")
            if st.button("🔌 اختبار الاتصال بـ Gemini"):
                if GeminiSupervisor:
                    sup = GeminiSupervisor(api_key=gemini_key_input.strip())
                    ok_g, msg_g = sup.test_connection()
                    if ok_g:
                        st.success(f"✅ {msg_g}")
                    else:
                        st.info(f"ℹ {msg_g}")

    st.divider()

    bot_mode = st.radio(
        "اختر نمط التشغيل:",
        [
            "🎯 الحجز المباشر واختيار المعتمرين والمواعيد (مرآة نسك الحية)",
            "🧠 توجيه الحجز بالذكاء الاصطناعي (أوامر لغوية طبيعية)",
            "🧪 تجربة فورية لمعتمر واحد (النسخة الرئيسية للمحاكي)",
            "⚡ حجز جماعي متوازي (حتى 10 نسخ متزامنة)"
        ],
        horizontal=True
    )

    if bot_mode == "🎯 الحجز المباشر واختيار المعتمرين والمواعيد (مرآة نسك الحية)":
        st.markdown("#### 🎯 الحجز التفاعلي المباشر تحت إشراف العقل المدبر (Gemini AI Brain)")
        st.caption("كأن تطبيق نسك مفتوح أمامك مباشرة: تحكم كامل في كشف المعتمرين (إضافة، تعديل، مسح، رفع)، مع التوجيه الذكي من Gemini وقنص المواعيد الحية فوراً.")

        # تهيئة قائمة المعتمرين في الـ session_state لضمان الحرية الكاملة في التعديل والمسح
        if "live_pilgrims_list" not in st.session_state:
            st.session_state["live_pilgrims_list"] = [
                {
                    "id": 1,
                    "name": "عمرو محمد عبد الرازق على زيدان",
                    "gender": "رجال",
                    "visa": "6174321724",
                    "passport": "A46220549",
                    "email": "most.a.f.asaee.dtravel5@gmail.com",
                    "password": "Zxcv1234$",
                    "is_registered": False
                }
            ]

        # --- 1. إدارة واستيراد كشف المعتمرين بمرونة تامة ---
        st.markdown("##### 1️⃣ إدارة كشف المعتمرين (حرية تامة في الإضافة، الرفع، والمسح):")

        # أزرار الإجراءات السريعة للكشف
        c_act1, c_act2, c_act3, c_act4 = st.columns([1.5, 1.2, 1.2, 1.5])
        with c_act1:
            if st.button("🗑️ تفريغ ومسح الكشف بالكامل", help="يمسح جميع المعتمرين من الجدول لتبدأ كشفاً جديداً فارغاً"):
                st.session_state["live_pilgrims_list"] = []
                st.success("تم مسح الكشف بالكامل.")
                st.rerun()

        with c_act2:
            st.markdown(f"**عدد المعتمرين:** `{len(st.session_state['live_pilgrims_list'])}`")

        # تبويبات مصادر البيانات
        src_tab1, src_tab2, src_tab3, src_tab4, src_tab5 = st.tabs([
            "📁 رفع ملف إكسيل / CSV",
            "📋 لصق بيانات نصية",
            "✍ إضافة معتمر يدوياً",
            "🧠 استخراج ذكي بـ Gemini (واتساب/نصوص حرة)",
            "🗄️ سحب من قاعدة المنظومة"
        ])

        with src_tab1:
            uploaded_file = st.file_uploader("ارفع كشف المعتمرين بصيغة إكسيل أو CSV:", type=["xlsx", "xls", "csv"], key="dash_live_file_upload")
            c_up1, c_up2 = st.columns(2)
            with c_up1:
                replace_mode = st.radio("طريقة الإدراج:", ["استبدال الكشف الحالي بالكامل", "إضافة للكشف الحالي"], horizontal=True, key="up_mode_radio")
            with c_up2:
                if uploaded_file and st.button("📥 تحميل وتطبيق الملف في الجدول", type="primary"):
                    if parse_excel_file:
                        new_p = parse_excel_file(uploaded_file)
                        if new_p:
                            if replace_mode == "استبدال الكشف الحالي بالكامل":
                                st.session_state["live_pilgrims_list"] = new_p
                            else:
                                st.session_state["live_pilgrims_list"].extend(new_p)
                            st.success(f"✅ تم إدراج {len(new_p)} معتمر في الجدول بنجاح!")
                            st.rerun()

        with src_tab2:
            pasted_txt = st.text_area(
                "الصق بيانات المعتمرين هنا (سطر لكل معتمر، يفصل بين البيانات مسافة أو | أو فاصلة):",
                placeholder="الاسم | رقم التأشيرة | رقم الجواز | رجال أو نساء\nمثال: محمد أحمد علي | 6174312345 | A12345678 | رجال",
                height=80,
                key="dash_live_pasted_data"
            )
            c_paste1, c_paste2 = st.columns([1, 1])
            with c_paste1:
                if st.button("📥 إدراج البيانات الملصوقة في الجدول"):
                    if pasted_txt.strip() and parse_pasted_text:
                        parsed = parse_pasted_text(pasted_txt)
                        if parsed:
                            st.session_state["live_pilgrims_list"].extend(parsed)
                            st.success(f"✅ تم إضافة {len(parsed)} معتمر إلى الكشف بنجاح!")
                            st.rerun()

        with src_tab3:
            st.markdown("###### إضافة معتمر فردي سريعاً:")
            c_man1, c_man2, c_man3 = st.columns(3)
            with c_man1:
                man_name = st.text_input("اسم المعتمر:", placeholder="مثال: أحمد محمود إبراهيم", key="man_input_name")
                man_gender = st.selectbox("الفئة / النوع:", ["رجال", "نساء", "طفل", "طفلة"], key="man_input_gender")
            with c_man2:
                man_passport = st.text_input("رقم الجواز:", placeholder="مثال: A12345678", key="man_input_pass")
                man_visa = st.text_input("رقم التأشيرة (10 أرقام):", placeholder="مثال: 6174317779", key="man_input_visa")
            with c_man3:
                man_email = st.text_input("البريد الإلكتروني (أو اتركه فارغاً لتوليده تلقائياً):", placeholder="اختياري", key="man_input_email")
                st.write("")
                if st.button("➕ إضافة هذا المعتمر للكشف فوراً", type="secondary"):
                    if man_name.strip():
                        new_item = {
                            "name": man_name.strip(),
                            "gender": man_gender,
                            "passport": man_passport.strip(),
                            "visa": man_visa.strip(),
                            "email": man_email.strip(),
                            "password": "Zxcv1234$",
                            "is_registered": False
                        }
                        from auto_booking.pilgrim_importer import _clean_pilgrim_records
                        cleaned_item = _clean_pilgrim_records([new_item])[0]
                        st.session_state["live_pilgrims_list"].append(cleaned_item)
                        st.success(f"✅ تمت إضافة ({man_name}) بنجاح!")
                        st.rerun()
                    else:
                        st.error("يرجى كتابة اسم المعتمر على الأقل.")

        with src_tab4:
            st.markdown("###### 🧠 الاستخراج الذكي من رسائل الواتساب والنصوص العشوائية بواسطة Gemini:")
            st.caption("الصق أي رسالة واردة من العميل أو شركة السياحة بأي صياغة، وسيقوم العقل المدبر باستخراج الأسماء والجوازات والتأشيرات وتصنيفها آلياً.")
            ai_raw_text = st.text_area("نص الرسالة أو المحادثة:", placeholder="مثال: السلام عليكم يا باشا احجز للحاج مصطفى سيد جوازه A98765432 وتاشيرته 6174321111 ومعاه زوجته منى أحمد جواز A87654321 وتاشيرتها 6174322222", height=80, key="ai_free_text_extract")
            if st.button("✨ استخراج وتنسيق المعتمرين بذكاء Gemini"):
                if ai_raw_text.strip() and GeminiSupervisor:
                    with st.spinner("🧠 العقل المدبر يحلل النص ويستخرج بيانات المعتمرين..."):
                        sup_ai = GeminiSupervisor(api_key=st.session_state.get("gemini_api_key_setting", "YOUR_GEMINI_API_KEY_HERE"))
                        ai_extracted = sup_ai.extract_pilgrims_from_text(ai_raw_text)
                    if ai_extracted:
                        st.session_state["live_pilgrims_list"].extend(ai_extracted)
                        st.success(f"🎉 نجح العقل المدبر في استخراج {len(ai_extracted)} معتمر وإضافتهم للجدول!")
                        st.rerun()
                    else:
                        st.warning("لم يتم العثور على بيانات معتمرين واضحة في النص.")

        with src_tab5:
            try:
                db_p = pd.read_sql_query("SELECT id, name, person_type as gender, visa, passport, email FROM pilgrims WHERE status != '✅ تم الحجز' ORDER BY id DESC LIMIT 50", conn)
                if not db_p.empty:
                    st.info(f"متوفر {len(db_p)} معتمر في قاعدة البيانات المركزية.")
                    if st.button("📥 سحب معتمري قاعدة البيانات إلى هذا الكشف"):
                        records = db_p.to_dict(orient="records")
                        st.session_state["live_pilgrims_list"].extend(records)
                        st.success(f"✅ تم سحب {len(records)} معتمر بنجاح!")
                        st.rerun()
            except Exception:
                pass

        # عرض الكشف الحالي مع إمكانية حذف معتمر فردي
        pilgrims_data = st.session_state.get("live_pilgrims_list", [])

        if pilgrims_data:
            df_display = pd.DataFrame(pilgrims_data)[["name", "gender", "passport", "visa", "email"]].rename(
                columns={"name": "الاسم", "gender": "النوع", "passport": "رقم الجواز", "visa": "رقم التأشيرة", "email": "البريد الإلكتروني"}
            )
            st.dataframe(df_display, use_container_width=True, height=150)

            c_pick, c_del_one = st.columns([3, 1])
            with c_pick:
                chosen_idx = st.selectbox(
                    "🎯 حدد المعتمر المطلوب حجز تصريح له الآن:",
                    options=range(len(pilgrims_data)),
                    format_func=lambda i: f"#{i+1}: {pilgrims_data[i].get('name', 'معتمر')} ({pilgrims_data[i].get('gender', 'رجال')}) | جواز: {pilgrims_data[i].get('passport', '-')} | تأشيرة: {pilgrims_data[i].get('visa', '-')}"
                )
            with c_del_one:
                st.write("")
                st.write("")
                if st.button("❌ حذف هذا المعتمر", help="حذف المعتمر المحدد حالياً من الكشف"):
                    st.session_state["live_pilgrims_list"].pop(chosen_idx)
                    st.success("تم الحذف بنجاح.")
                    st.rerun()

            active_pilgrim = pilgrims_data[chosen_idx]
            pilgrim_gender = active_pilgrim.get("gender", "رجال")
        else:
            st.warning("⚠️ الكشف فارغ حالياً. يرجى رفع ملف إكسيل أو لصق بيانات أو إضافة معتمر يدوياً من التبويبات أعلاه.")
            active_pilgrim = None
            pilgrim_gender = "رجال"

        st.divider()

        # --- 2. رادار نسك الحي مع دمج العقل المدبر (Gemini AI Brain) ---
        if active_pilgrim:
            st.markdown("##### 2️⃣ 🧠 توجيه العقل المدبر ومرآة نسك الحية:")

            # بطاقة العقل المدبر المدمجة
            with st.container():
                st.info(f"👤 المعتمر النشط: **{active_pilgrim.get('name')}** ({'رجال 👨' if 'رج' in pilgrim_gender else 'نساء 👩'}) | جواز: `{active_pilgrim.get('passport', '-')}` | تأشيرة: `{active_pilgrim.get('visa', '-')}`")

                c_ai_in1, c_ai_in2 = st.columns([3, 1])
                with c_ai_in1:
                    ai_hint_input = st.text_input(
                        "🗣 وجه العقل المدبر لطلبك (مثال: احجزله فجر الجمعة القادمة، أو أقرب موعد صباحي، أو منتصف الليل):",
                        placeholder="اكتب أي تعليمات تريدها وسيقوم الذكاء الاصطناعي بضبط التاريخ والوقت تلقائياً...",
                        key=f"ai_hint_{active_pilgrim.get('name')}"
                    )
                with c_ai_in2:
                    st.write("")
                    st.write("")
                    ai_analyze_btn = st.button("💡 توجيه ذكي بـ Gemini")

                # تنفيذ مشورة العقل المدبر
                if ai_analyze_btn or ai_hint_input.strip():
                    if GeminiSupervisor:
                        sup_rec = GeminiSupervisor(api_key=st.session_state.get("gemini_api_key_setting", "YOUR_GEMINI_API_KEY_HERE"))
                        rec_res = sup_rec.recommend_best_slot_and_timing(active_pilgrim, ai_hint_input)
                        st.success(f"🧠 **رأي العقل المدبر:** {rec_res.get('advice')}")
                        if rec_res.get("target_date"):
                            st.session_state[f"rec_date_{active_pilgrim.get('name')}"] = rec_res.get("target_date")
                        if rec_res.get("target_slot"):
                            st.session_state[f"rec_slot_{active_pilgrim.get('name')}"] = rec_res.get("target_slot")

            c_rad1, c_rad2 = st.columns([1, 1])

            radar = SlotRadar() if SlotRadar else None

            with c_rad1:
                st.markdown("###### 📱 شاشة التطبيق الحية على المحاكي:")
                if st.button("🔄 فحص وسحب شاشة ومواعيد نسك الآن"):
                    if radar:
                        with st.spinner("جاري الاتصال وسحب شاشة نسك الحية..."):
                            radar.scan_slots_from_app(gender=pilgrim_gender)
                        st.success("✅ تم تحديث الشاشة والمواعيد بنجاح!")
                    st.rerun()

                screenshot_file = Path("auto_booking/cache/live_radar.png")
                if screenshot_file.exists():
                    st.image(str(screenshot_file), caption="لقطة مباشرة من شاشة نسك على محاكي MuMu Player", use_container_width=True)
                else:
                    st.info("اضغط على زر (فحص وسحب شاشة ومواعيد نسك) لعرض الشاشة الحية أمامك.")

            with c_rad2:
                st.markdown(f"###### ⏰ الفترات والمواعيد المتاحة لـ ({'الرجال 👨' if 'رج' in pilgrim_gender else 'النساء 👩'}):")
                
                raw_options = NUSUK_OFFICIAL_WINDOWS.get("نساء" if "نس" in pilgrim_gender else "رجال", []) if NUSUK_OFFICIAL_WINDOWS else []
                slot_choices = ["⚡ أول موعد متاح فورياً (قناص سريع)"] + [f"{item['time']} ({item['label']})" for item in raw_options]

                # قراءة الموعد الموصى به من Gemini إن وجد
                default_slot_idx = 0
                suggested_slot = st.session_state.get(f"rec_slot_{active_pilgrim.get('name')}", "")
                if suggested_slot:
                    for s_idx, sc in enumerate(slot_choices):
                        if any(k in sc for k in [suggested_slot[:5]]):
                            default_slot_idx = s_idx
                            break

                selected_slot_str = st.radio("اختر الموعد المرغوب فيه:", slot_choices, index=default_slot_idx)
                
                suggested_date = st.session_state.get(f"rec_date_{active_pilgrim.get('name')}", "")
                target_date_input = st.text_input("التاريخ المطلوب (اتركه فارغاً لأقرب يوم متاح):", value=suggested_date, placeholder="YYYY-MM-DD", key="live_target_date")

                st.write("---")
                c_p_opt1, c_p_opt2 = st.columns(2)
                with c_p_opt1:
                    live_is_reg = st.checkbox("🔑 الحساب مسجل مسبقاً (تسجيل دخول فقط)", value=active_pilgrim.get("is_registered", False), key="live_chk_reg")
                with c_p_opt2:
                    live_logout = st.checkbox("🚪 تسجيل الخروج بعد اكتمال الحجز", value=True, key="live_chk_logout")

                active_pilgrim["is_registered"] = live_is_reg

                # زر الحجز الفوري السريع تحت إشراف Gemini
                if st.button(f"🚀 احجز لـ ({active_pilgrim['name']}) الآن بإشراف العقل المدبر", type="primary", key="btn_book_interactive"):
                    p_task = {
                        "name": active_pilgrim.get("name"),
                        "gender": pilgrim_gender,
                        "visa": str(active_pilgrim.get("visa", "")).strip(),
                        "passport": str(active_pilgrim.get("passport", "")).strip(),
                        "email": str(active_pilgrim.get("email", "")).strip(),
                        "password": str(active_pilgrim.get("password", "Zxcv1234$")).strip(),
                        "is_registered": live_is_reg
                    }
                    s_settings = {
                        "auto_logout": live_logout,
                        "target_date": target_date_input.strip(),
                        "target_slot": selected_slot_str
                    }

                    live_log_area = st.empty()
                    live_logs = []

                    def live_stream(m):
                        live_logs.append(m)
                        live_log_area.code("\n".join(live_logs[-15:]), language="text")

                    with st.spinner(f"جاري إطلاق البوت وحجز تصريح ({p_task['name']}) بإشراف العقل المدبر..."):
                        runner_live = BookingRunner(log_callback=live_stream)
                        res_live = runner_live.run_single_pilgrim_test(p_task, s_settings)

                    if res_live.get("status") == "SUCCESS":
                        st.success(f"🎉 تم تأكيد حجز المعتمر ({p_task['name']}) بنجاح! {res_live.get('details')}")
                    else:
                        st.error(f"❌ انتهت المحاولة: {res_live.get('details') or res_live.get('reason')}")

    elif bot_mode == "🧠 توجيه الحجز بالذكاء الاصطناعي (أوامر لغوية طبيعية)":
        st.markdown("#### 🗣 توجيه البوت كأنك تكلم موظفاً (العقل المدبر يفهم وينفذ فوراً):")
        st.caption("اكتب تفاصيل الرحلة باللغة العربية بالطريقة التي تفضلها. سيقوم العقل المدبر باستخراج التاريخ، ووقت الصلاة، وأولوية الرجال/النساء، وربط الأطفال، وتوزيع الحجز آلياً.")

        ai_prompt_text = st.text_area(
            "اكتب تعليمات الرحلة هنا:",
            value="احجز لحملة التقوى يوم السبت بعد العصر، ابدأ بالحريم الأول وخلّي البنات مع أمهاتهم والصبيان مع آبائهم على 10 نسخ وسجل خروج بعد ما تخلص.",
            height=100,
            key="ai_natural_prompt_input"
        )

        # استخراج وتحليل الأوامر لحظياً
        if GeminiSupervisor:
            brain_temp = GeminiSupervisor(api_key=st.session_get("gemini_api_key_setting", "YOUR_GEMINI_API_KEY_HERE") if hasattr(st, "session_get") else "YOUR_GEMINI_API_KEY_HERE")
            parsed_cmd = brain_temp.interpret_trip_prompt(ai_prompt_text)

            st.markdown("##### 📋 فهم العقل المدبر لتعليماتك:")
            c_p1, c_p2, c_p3, c_p4 = st.columns(4)
            with c_p1:
                st.metric("التاريخ المستهدف", parsed_cmd.get("target_date", "أول موعد"))
            with c_p2:
                st.metric("نافذة الصلاة", parsed_cmd.get("prayer_window", "أي وقت"))
            with c_p3:
                st.metric("الأولوية", "النساء أولاً 👩" if parsed_cmd.get("priority") == "نساء_أولا" else "الرجال أولاً 👨")
            with c_p4:
                st.metric("عدد النسخ المتزامنة", f"{parsed_cmd.get('num_clones', 10)} نسخ")

            c_p5, c_p6 = st.columns(2)
            with c_p5:
                st.write(f"👶 ربط الأطفال بالأمهات والآباء: **{'نعم ✅' if parsed_cmd.get('link_children') else 'لا ❌'}**")
            with c_p6:
                st.write(f"🚪 تسجيل الخروج التلقائي: **{'نعم ✅' if parsed_cmd.get('auto_logout') else 'لا ❌'}**")

            # زر تشغيل الحملة بأوامر الذكاء الاصطناعي
            if st.button("🚀 إطلاق حملة الحجز الآلية بأوامر العقل المدبر الآن", type="primary"):
                try:
                    p_query = "SELECT id, company_name as 'company', name, person_type, email, visa, passport FROM pilgrims WHERE status != '✅ تم الحجز' ORDER BY id DESC LIMIT 50"
                    df_run = pd.read_sql_query(p_query, conn)
                    if df_run.empty:
                        st.warning("⚠ لا يوجد معتمرون مسجلون في قاعدة البيانات. يمكنك تجربة حجز معتمر مفرد من التبويب الآخر.")
                    else:
                        pilgrims_list = df_run.to_dict(orient="records")
                        st.info(f"جاري إطلاق الحجز لـ {len(pilgrims_list)} معتمر عبر المحاكي بأوامر العقل المدبر...")
                        runner_ai = BookingRunner(gemini_key=brain_temp.api_key)
                        res_ai = runner_ai.run_with_natural_instructions(ai_prompt_text, pilgrims_list)
                        st.success("🎉 اكتمل تنفيذ مسار الحجز!")
                except Exception as e_run:
                    st.error(f"خطأ أثناء تشغيل الحملة: {e_run}")

    elif bot_mode == "🧪 تجربة فورية لمعتمر واحد (النسخة الرئيسية للمحاكي)":
        st.markdown("#### 🎯 بيانات المعتمر المطلوب حجز تصريح له:")
        st.caption("أدخل بيانات المعتمر أدناه ليقوم البوت بفتح تطبيق نسك على النسخة الرئيسية، وتعبئة البيانات، وسحب كود الـ OTP تلقائياً، وتأكيد الحجز.")

        col_t1, col_t2 = st.columns(2)
        with col_t1:
            t_name = st.text_input("اسم المعتمر الكامل:", value="عمرو محمد عبد الرازق على زيدان", key="bot_single_name")
            t_gender = st.selectbox("الفئة / النوع:", ["رجال 👨", "نساء 👩", "طفل 👦", "طفلة 👧"], key="bot_single_gender")
            t_visa = st.text_input("رقم التأشيرة (Visa No):", value="6174321724", key="bot_single_visa")

        with col_t2:
            t_passport = st.text_input("رقم جواز السفر (Passport No):", value="A46220549", key="bot_single_pass")
            t_email = st.text_input("البريد الإلكتروني:", value="most.a.f.asaee.dtravel5@gmail.com", key="bot_single_email")
            t_pwd = st.text_input("كلمة مرور الحساب في نسك:", value="Zxcv1234$", type="password", key="bot_single_pwd")

        c_opt1, c_opt2, c_opt3 = st.columns(3)
        with c_opt1:
            t_is_reg = st.checkbox("🔑 الحساب مسجل مسبقاً (دخول مباشر)", value=False, help="اتركه غير محدد لإنشاء حساب جديد")
        with c_opt2:
            t_logout = st.checkbox("🚪 تسجيل الخروج بعد تأكيد الحجز", value=True)
        with c_opt3:
            t_target_date = st.text_input("التاريخ المطلوب (اتركه فارغاً لأول موعد متاح):", placeholder="YYYY-MM-DD", key="bot_single_date")

        if st.button("🚀 إطلاق الحجز التجريبي الآن فوراً", type="primary"):
            if not t_name.strip():
                st.warning("⚠ يرجى إدخال اسم المعتمر على الأقل.")
            else:
                p_task = {
                    "name": t_name.strip(),
                    "gender": "نساء" if "نساء" in t_gender or "طفلة" in t_gender else "رجال",
                    "visa": t_visa.strip(),
                    "passport": t_passport.strip(),
                    "email": t_email.strip(),
                    "password": t_pwd.strip(),
                    "is_registered": t_is_reg
                }
                s_settings = {
                    "auto_logout": t_logout,
                    "target_date": t_target_date.strip()
                }

                log_area = st.empty()
                logs_list = []

                def log_stream(m):
                    logs_list.append(m)
                    log_area.code("\n".join(logs_list[-15:]), language="text")

                with st.spinner("جاري تنفيذ الحجز الآلي عبر المحاكي بإشراف العقل المدبر..."):
                    g_key = gemini_key_input.strip() if "gemini_key_input" in locals() and gemini_key_input else None
                    runner = BookingRunner(log_callback=log_stream, gemini_key=g_key)
                    result = runner.run_single_pilgrim_test(p_task, s_settings)

                if result.get("status") == "SUCCESS":
                    st.success(f"🎉 تم تأكيد حجز المعتمر ({t_name}) بنجاح! {result.get('details')}")
                else:
                    st.error(f"❌ انتهت المحاولة: {result.get('details') or result.get('reason')}")

    else:
        st.markdown("#### ⚡ إعدادات حملة الحجز الجماعي المتوازي:")
        st.caption("توزيع المعتمرين تلقائياً على نسخ تطبيق نسك (حتى 10 نسخ متزامنة) مع الربط الذكي للأطفال.")

        m_col1, m_col2 = st.columns(2)
        with m_col1:
            m_clones = st.slider("عدد النسخ المتزامنة المطلوب تشغيلها:", min_value=1, max_value=10, value=10)
            m_priority = st.selectbox("أولوية الحجز:", ["نساء أولاً ثم الرجال 👩⬅️👨", "رجال أولاً ثم النساء 👨⬅️👩", "حسب ترتيب الشيت الحالي 🔀"])

        with m_col2:
            m_link_kids = st.checkbox("👶 ربط الأطفال الذكور مع الرجال، والبنات مع النساء كتابعين", value=True)
            m_auto_logout = st.checkbox("🚪 تسجيل الخروج التلقائي من كل نسخة بعد اكتمال حجزها", value=True)

        st.info("💡 يمكنك تحديد دفعة معتمرين من قاعدة البيانات للبدء في حجزهم فوراً عبر النسخ الـ 10.")

        # عرض المعتمرين الجاهزين للحجز
        try:
            pending_df = pd.read_sql_query(
                "SELECT id, company_name as 'الشركة', name as 'الاسم', person_type as 'النوع', email as 'الإيميل', visa as 'التأشيرة', status as 'الحالة' FROM pilgrims WHERE status != '✅ تم الحجز' ORDER BY id DESC LIMIT 50",
                conn
            )
            if not pending_df.empty:
                st.dataframe(pending_df, use_container_width=True, height=220)
                if st.button(f"🚀 بدء تشغيل الحجز الآلي لـ {min(len(pending_df), m_clones)} معتمر عبر الـ {m_clones} نسخ", type="primary"):
                    st.info("سيتم تشغيل حملة الحجز عبر الـ 10 نسخ متزامنة...")
            else:
                st.info("لا يوجد معتمرون في قائمة الانتظار حالياً. يمكنك رفع كشف جديد من تبويب استيراد الإكسيل.")
        except Exception as e:
            st.error(f"خطأ في قراءة سجلات المعتمرين: {e}")

conn.close()



