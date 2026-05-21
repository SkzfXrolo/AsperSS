@echo off
setlocal EnableExtensions
chcp 65001 >nul 2>&1
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
title Argus Panel Local
color 0B

REM Ir a la raiz del repo (carpeta padre de BAT\)
cd /d "%~dp0"
cd /d ".."
set "ROOT=%CD%"
set "WEB=%ROOT%\web_app"

echo ========================================
echo   ARGUS - Panel local (solo tu PC)
echo ========================================
echo.
echo ROOT: %ROOT%
echo WEB:  %WEB%
echo.

REM Liberar puerto 8080 si quedo un python zombie tras Ctrl+C
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":8080" ^| findstr "LISTENING"') do (
    echo [!] Puerto 8080 ocupado por PID %%P - cerrando...
    taskkill /F /PID %%P >nul 2>&1
)
timeout /t 2 /nobreak >nul

if not exist "%WEB%\.env.local" (
    echo [!] Falta: %WEB%\.env.local
    echo.
    if exist "%WEB%\.env.local.example" (
        copy /Y "%WEB%\.env.local.example" "%WEB%\.env.local" >nul
        echo [OK] Se creo .env.local desde el ejemplo.
        echo      Edita DATABASE_URL si hace falta y vuelve a ejecutar.
    ) else (
        echo 1. Crea web_app\.env.local
        echo 2. Pega DATABASE_URL de Render (aspers-db - External)
    )
    echo.
    pause
    exit /b 1
)

cd /d "%WEB%"

if not exist "%ROOT%\.venv\Scripts\python.exe" (
    echo Creando venv...
    cd /d "%ROOT%"
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] No se pudo crear venv. Instala Python 3.11+
        pause
        exit /b 1
    )
)

call "%ROOT%\.venv\Scripts\activate.bat"
pip install -q -r "%ROOT%\web_app\requirements.txt" 2>nul
pip install -q python-dotenv 2>nul

cd /d "%WEB%"

echo.
echo Panel: http://127.0.0.1:8080/panel
echo Login: misma cuenta que Render (misma BD)
echo.
python app.py

pause
endlocal
