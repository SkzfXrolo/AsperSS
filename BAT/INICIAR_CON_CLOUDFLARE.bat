@echo off
chcp 65001 >nul
echo ========================================
echo   ASPERS Projects - Iniciar con Cloudflare Tunnel
echo ========================================
echo.

REM Cambiar esta ruta a donde tengas cloudflared.exe
REM Si cloudflared está en el PATH, puedes usar solo "cloudflared"
set CLOUDFLARE_PATH=cloudflared.exe

REM Ruta de la aplicación (directorio actual)
set APP_PATH=%~dp0

echo [1/2] Iniciando aplicación Flask...
start "ASPERS Flask App" cmd /k "cd /d %APP_PATH% && python app.py"

timeout /t 3 /nobreak >nul

echo [2/2] Iniciando túnel Cloudflare...
echo.
echo ========================================
echo   IMPORTANTE:
echo ========================================
echo La URL pública aparecerá en la ventana de Cloudflare
echo Es completamente gratis y sin límites
echo ========================================
echo.

start "Cloudflare Tunnel" cmd /k "%CLOUDFLARE_PATH% tunnel --url http://localhost:8080"

echo.
echo ========================================
echo   ¡Aplicación iniciada!
echo ========================================
echo.
echo La aplicación está corriendo en:
echo   - Local: http://localhost:8080
echo   - Público: Revisa la ventana de Cloudflare para la URL
echo.
echo Presiona cualquier tecla para cerrar esta ventana...
pause >nul

