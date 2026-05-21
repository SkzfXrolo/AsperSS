@echo off
title Compilar Argus + ArgusAdmin
set ROOT=%~dp0..
echo.
echo [1/2] Argus Assistant...
cd /d "%ROOT%\argus-assistant"
pip install -q pyinstaller pillow pystray requests
if not exist assets\argus.ico python scripts\build_icon.py
python -m PyInstaller --noconfirm Argus.spec
echo.
echo [2/2] ArgusAdmin...
cd /d "%ROOT%\argus-admin"
pip install -q pyinstaller pillow numpy requests sounddevice
python scripts\build_icon.py
python -m PyInstaller --noconfirm ArgusAdmin.spec
call scripts\copiar_a_escritorio.bat
echo.
echo Listo:
dir "%ROOT%\argus-assistant\dist\Argus.exe"
dir "%ROOT%\argus-admin\dist\ArgusAdmin.exe"
pause
