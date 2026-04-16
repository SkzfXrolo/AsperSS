@echo off
chcp 65001 >nul
echo ========================================
echo   LOGIN CLOUDFLARE TUNNEL
echo   ASPERS Projects
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
echo   INICIANDO LOGIN
echo ========================================
echo.
echo ⚠️  IMPORTANTE:
echo    1. Se abrirá una ventana del navegador para autorizar
echo    2. Si ves una tabla VACÍA (sin dominios), es NORMAL
echo    3. SIMPLEMENTE CIERRA la ventana del navegador
echo    4. El login se completará automáticamente
echo    5. El certificado se guardará en: C:\Users\%USERNAME%\.cloudflared\
echo    6. Solo necesitas hacer esto UNA VEZ para tener dominio fijo
echo.
echo Presiona cualquier tecla para iniciar el login...
pause >nul

echo.
echo Iniciando login...
echo.

%CLOUDFLARE_PATH% tunnel login

if errorlevel 1 (
    echo.
    echo ⚠️  Login no completado (esto es normal si no tienes dominios)
    echo.
    echo 💡 SOLUCIÓN RÁPIDA:
    echo    Ejecuta INICIAR_TUNEL_RAPIDO.bat
    echo    Funciona sin login y sin necesidad de dominios.
    echo.
    echo Si quieres URL permanente, necesitas:
    echo   1. Crear cuenta en Cloudflare (gratis)
    echo   2. O usar el modo rápido que funciona perfectamente
    echo.
    pause
    exit /b 1
) else (
    echo.
    echo ========================================
    echo   ✅ LOGIN COMPLETADO
    echo ========================================
    echo.
    echo Ahora puedes ejecutar CONFIGURAR_TUNEL_PERMANENTE.bat
    echo para crear tu túnel permanente con URL fija.
    echo.
    echo ⚠️  NOTA: Si la tabla estaba vacía, el túnel permanente
    echo    puede no funcionar. En ese caso usa INICIAR_TUNEL_RAPIDO.bat
    echo.
    pause
)

