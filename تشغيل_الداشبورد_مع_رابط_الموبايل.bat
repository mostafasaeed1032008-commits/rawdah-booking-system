@echo off
chcp 65001 >nul
cd /d "%~dp0"
title منظومة الروضة الشريفة - تشغيل الداشبورد مع رابط الموبايل السحابي
set PYTHONIOENCODING=utf-8
set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"

"%PYTHON_EXE%" "%~dp0tunnel_launcher.py"

pause
