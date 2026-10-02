# -*- coding: utf-8 -*-
"""
منظومة حجز الروضة الشريفة - محرك التزامن السحابي المزدوج 24/7 (Neon PostgreSQL / SQLite)
يربط الداشبورد على السيرفر السحابي واللاب توب بنفس قاعدة البيانات الموحدة الحية.
"""

import os
import re
import sqlite3
import warnings
from pathlib import Path
from typing import Optional, Any, Dict, List
import pandas as pd

# كتم تحذير pandas بشأن كائنات DBAPI2 المخصصة
warnings.filterwarnings("ignore", category=UserWarning, module="pandas")

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
LOCAL_DB_PATH = PROJECT_ROOT / "database" / "rawdah_central.db"
LOCAL_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# الرابط الافتراضي لقاعدة البيانات السحابية (Neon)
DEFAULT_CLOUD_DB_URL = "postgresql://neondb_owner:npg_Ut7XGTKxmfk8@ep-old-fog-b5dfx0ja-pooler.c-7.us-east-2.aws.neon.tech/neondb?sslmode=require"

def get_database_url() -> str:
    """الحصول على رابط قاعدة البيانات السحابية"""
    # 1. من Streamlit secrets
    try:
        import streamlit as st
        url = st.secrets.get("DATABASE_URL", "")
        if url:
            return url.strip()
    except Exception:
        pass

    # 2. من متغيرات البيئة
    url = os.environ.get("DATABASE_URL", "").strip()
    if url:
        return url

    # 3. من ملف .env
    env_file = PROJECT_ROOT / ".env"
    if env_file.exists():
        try:
            with open(env_file, encoding="utf-8") as f:
                for line in f:
                    if line.startswith("DATABASE_URL="):
                        return line.split("=", 1)[1].strip().strip('"').strip("'")
        except Exception:
            pass

    # 4. الرابط الافتراضي المدمج
    return DEFAULT_CLOUD_DB_URL

class PostgresWrapper:
    """مغلف اتصال PostgreSQL يوفر نفس واجهة SQLite تماماً مع دعم pandas"""
    def __init__(self, db_url: str):
        import psycopg2
        from psycopg2.extras import RealDictCursor
        from sqlalchemy import create_engine

        self.db_url = db_url
        if db_url.startswith("postgresql://"):
            self.sqlalchemy_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)
        elif db_url.startswith("postgres://"):
            self.sqlalchemy_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)
        else:
            self.sqlalchemy_url = db_url

        self.engine = create_engine(self.sqlalchemy_url, pool_pre_ping=True)
        self.raw_conn = psycopg2.connect(self.db_url, cursor_factory=RealDictCursor)
        self.raw_conn.autocommit = True

    def execute(self, sql: str, params: Any = None):
        """تنفيذ استعلام SQL مع تحويل صيغ SQLite إلى PostgreSQL تلقائياً"""
        clean_sql = sql.replace("?", "%s")

        # معالجة INSERT OR IGNORE الخاصة بـ SQLite
        if "INSERT OR IGNORE INTO companies" in clean_sql:
            clean_sql = clean_sql.replace("INSERT OR IGNORE INTO companies", "INSERT INTO companies")
            if "ON CONFLICT" not in clean_sql:
                clean_sql += " ON CONFLICT (name) DO NOTHING"

        cur = self.raw_conn.cursor()
        if params is not None:
            cur.execute(clean_sql, params)
        else:
            cur.execute(clean_sql)
        return cur

    def commit(self):
        try:
            self.raw_conn.commit()
        except Exception:
            pass

    def close(self):
        try:
            self.raw_conn.close()
        except Exception:
            pass

    def cursor(self):
        return self.raw_conn.cursor()

def get_db_connection():
    """
    الاتصال الذكي الموحد:
    يتصل بسيرفر Neon السحابي ليحقق التزامن المزدوج 24/7.
    في حال انقطاع النت تماماً، يعود تلقائياً لـ SQLite المحلي.
    """
    url = get_database_url()
    if url:
        try:
            pg = PostgresWrapper(url)
            # فحص خفيف للاتصال
            cur = pg.execute("SELECT 1")
            cur.fetchone()
            return pg
        except Exception as e:
            print(f"[db_sync] تعذر الاتصال بالسحابة ({e})، جاري التبديل لـ SQLite المحلي...")

    # البديل المحلي
    conn = sqlite3.connect(str(LOCAL_DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn
