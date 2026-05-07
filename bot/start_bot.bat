@echo off
REM ─────────────────────────────────────────────────────────────────
REM Argus Discord Bot — launcher para Windows
REM Doble-click sobre este archivo para arrancar el bot.
REM ─────────────────────────────────────────────────────────────────

setlocal
cd /d "%~dp0\.."

echo.
echo ============================================================
echo    Argus Discord Bot - Argus Projects
echo ============================================================
echo.

if not exist "bot\.env" (
    echo [ERROR] No se encontro bot\.env
    echo.
    echo Copia bot\.env.example como bot\.env y rellena tus tokens.
    echo.
    pause
    exit /b 1
)

echo Verificando dependencias...
python -m pip install --quiet --disable-pip-version-check -r bot\requirements.txt
if errorlevel 1 (
    echo [ERROR] Fallo instalando dependencias.
    pause
    exit /b 1
)

echo.
echo Arrancando bot...
echo (Ctrl+C para detener)
echo.

python -m bot

echo.
echo Bot detenido.
pause
