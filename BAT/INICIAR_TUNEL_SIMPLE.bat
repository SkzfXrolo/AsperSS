@echo off
chcp 65001 >nul
echo ========================================
echo   TÚNEL CLOUDFLARE SIMPLE
echo   ASPERS Projects - Sin Configuración
echo ========================================
echo.

REM Ruta por defecto: C:\cloudflared\cloudflared.exe
set CLOUDFLARE_PATH=C:\cloudflared\cloudflared.exe

REM Verificar si cloudflared existe
if not exist "%CLOUDFLARE_PATH%" (
    echo ❌ cloudflared.exe no encontrado en: %CLOUDFLARE_PATH%
    echo.
    echo Verifica que cloudflared.exe esté en C:\cloudflared\
    echo.
    pause
    exit /b 1
)

echo ✅ cloudflared encontrado
echo.

echo ========================================
echo   INICIANDO APLICACIÓN Y TÚNEL
echo ========================================
echo.

echo [1/2] Iniciando aplicación Flask...
start "ASPERS Flask App" cmd /k "cd /d %~dp0 && python app.py"

timeout /t 3 /nobreak >nul

echo [2/2] Iniciando túnel...
echo.
echo ✅ Modo simple activado
echo    No requiere login ni configuración
echo.
echo 📋 La URL aparecerá en la ventana de Cloudflare
echo    Será algo como: https://xxxxx.trycloudflare.com
echo.
echo Presiona cualquier tecla para iniciar...
pause >nul

start "Cloudflare Tunnel - ASPERS Projects" cmd /k "%CLOUDFLARE_PATH% tunnel --url http://localhost:8080"

echo.
echo ========================================
echo   ✅ TÚNEL INICIADO
echo ========================================
echo.
echo ✅ Revisa la ventana "Cloudflare Tunnel - ASPERS Projects"
echo    para ver tu URL pública.
echo.
echo 💡 Esta URL funciona inmediatamente y es pública.
echo    Compártela con quien quieras.
echo.
echo Para detener: Cierra la ventana de Cloudflare Tunnel
echo.
pause

