@echo off
title ArgusAdmin - Control Imperial
cd /d "%~dp0..\argus-admin"
if exist "dist\ArgusAdmin.exe" (
    start "" "dist\ArgusAdmin.exe"
    exit /b 0
)
pip install -q -r requirements.txt 2>nul
python run_argus_admin.py
if errorlevel 1 pause
