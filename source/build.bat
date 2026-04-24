@echo off
cd /d "%~dp0"
echo [BUILD] Compilando ArgusScanner con PyInstaller...
pyinstaller ArgusScanner.spec --clean --noconfirm
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Compilacion fallida.
    pause
    exit /b 1
)
echo [OK] Compilacion exitosa. Ejecutable en dist\ArgusScanner.exe
pause
