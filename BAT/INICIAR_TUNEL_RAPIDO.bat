@echo off
chcp 65001 >nul
echo ========================================
echo   TÚNEL RÁPIDO CLOUDFLARE
echo   ASPERS Projects - Sin Login Requerido
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

echo [2/2] Iniciando túnel rápido...
echo.
echo ⚠️  IMPORTANTE:
echo    - Este modo NO requiere login
echo    - La URL cambiará cada vez que reinicies
echo    - Pero funciona perfectamente para pruebas
echo.
echo 💡 ALTERNATIVA: Si quieres URL permanente con nombre fijo:
echo    Ejecuta CONFIGURAR_TUNEL_PERMANENTE.bat (requiere login)
echo.
echo 📋 La URL aparecerá en la ventana de Cloudflare
echo    Será algo como: https://xxxxx.trycloudflare.com
echo.
echo Presiona cualquier tecla para iniciar el túnel...
pause >nul

start "Cloudflare Tunnel - ASPERS Projects" cmd /k "%CLOUDFLARE_PATH% tunnel --url http://localhost:8080"

echo.
echo ========================================
echo   ✅ TÚNEL INICIADO
echo ========================================
echo.
echo ✅ El túnel está corriendo en una ventana separada.
echo.
echo 📋 Revisa la ventana "Cloudflare Tunnel - ASPERS Projects"
echo    para ver tu URL temporal.
echo.
echo 💡 Para URL permanente, necesitas hacer login primero.
echo    Ejecuta HACER_LOGIN_CLOUDFLARE.bat después de crear
echo    una cuenta gratuita en Cloudflare.
echo.
echo Para detener: Cierra la ventana de Cloudflare Tunnel
echo Para reiniciar: Ejecuta este script nuevamente
echo.
echo Presiona cualquier tecla para cerrar esta ventana...
pause >nul

