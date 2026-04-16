@echo off
chcp 65001 >nul
echo ========================================
echo   CONFIGURAR TÚNEL PERMANENTE CLOUDFLARE
echo   ASPERS Projects - URL Permanente
echo ========================================
echo.

REM ============================================================
REM CONFIGURACIÓN
REM ============================================================

REM Ruta por defecto: C:\cloudflared\cloudflared.exe
REM Si cloudflared está en otra ubicación, cambia esta línea:
set CLOUDFLARE_PATH=C:\cloudflared\cloudflared.exe

set TUNNEL_NAME=aspersprojects
set APP_PATH=%~dp0

echo ========================================
echo   VERIFICANDO CLOUDFLARED...
echo ========================================
echo.

REM Verificar primero en la ruta por defecto (C:\cloudflared\)
if exist "%CLOUDFLARE_PATH%" (
    echo ✅ cloudflared encontrado en: %CLOUDFLARE_PATH%
    goto :found_cloudflared
)

REM Si no está ahí, buscar en otras ubicaciones comunes
echo 🔍 Buscando cloudflared en otras ubicaciones...

REM Buscar en PATH del sistema
where cloudflared.exe >nul 2>&1
if not errorlevel 1 (
    echo ✅ cloudflared encontrado en el PATH del sistema
    set CLOUDFLARE_PATH=cloudflared.exe
    goto :found_cloudflared
)

REM Buscar en Downloads
if exist "%USERPROFILE%\Downloads\cloudflared.exe" (
    set CLOUDFLARE_PATH=%USERPROFILE%\Downloads\cloudflared.exe
    echo ✅ cloudflared encontrado en: %USERPROFILE%\Downloads\
    goto :found_cloudflared
)

REM Buscar en la misma carpeta del script
if exist "%~dp0cloudflared.exe" (
    set CLOUDFLARE_PATH=%~dp0cloudflared.exe
    echo ✅ cloudflared encontrado en la misma carpeta del script
    goto :found_cloudflared
)

REM Si no se encuentra, mostrar ayuda
echo.
echo ❌ cloudflared.exe NO ENCONTRADO
echo.
echo ========================================
echo   OPCIONES PARA SOLUCIONAR:
echo ========================================
echo.
echo SOLUCIÓN RÁPIDA:
echo.
echo 1. Verifica que cloudflared.exe esté en: C:\cloudflared\cloudflared.exe
echo    Si está en otra ubicación, edita este script y cambia la línea:
echo    set CLOUDFLARE_PATH=C:\cloudflared\cloudflared.exe
echo.
echo 2. O descarga cloudflared desde:
echo    https://github.com/cloudflare/cloudflared/releases
echo    - Descarga: cloudflared-windows-amd64.exe
echo    - Renómbralo a: cloudflared.exe
echo    - Colócalo en: C:\cloudflared\
echo.
echo 3. O ejecuta el script: AGREGAR_CLOUDFLARE_AL_PATH.bat
echo    para agregar cloudflared al PATH de Windows automáticamente
echo.
echo ========================================
echo.
pause
exit /b 1

:found_cloudflared
echo.

echo [2/4] Iniciando aplicación Flask...
start "ASPERS Flask App" cmd /k "cd /d %APP_PATH% && python app.py"

timeout /t 3 /nobreak >nul

echo [3/4] Verificando/creando túnel permanente "%TUNNEL_NAME%"...
echo.
echo ⚠️  IMPORTANTE:
echo    - Si te pide login, CIERRA la ventana del navegador
echo    - Si ves una página de "nameservers", CIÉRRALA (no es necesaria)
echo    - No necesitas seleccionar ningún dominio
echo    - El túnel se creará con nombre "%TUNNEL_NAME%"
echo    - Esto creará una URL permanente tipo: https://%TUNNEL_NAME%-xxxxx.trycloudflare.com
echo    - NO necesitas configurar nameservers para que funcione
echo.

REM Verificar si el túnel ya existe
%CLOUDFLARE_PATH% tunnel list | findstr /C:"%TUNNEL_NAME%" >nul 2>&1
if not errorlevel 1 (
    echo ℹ️  El túnel "%TUNNEL_NAME%" ya existe. Usando túnel existente...
    echo.
    goto :tunnel_ready
)

REM Intentar crear el túnel
echo Creando nuevo túnel...
%CLOUDFLARE_PATH% tunnel create %TUNNEL_NAME% 2>&1 | findstr /V "ERR" >nul

if errorlevel 1 (
    echo.
    echo ⚠️  No se pudo crear túnel permanente.
    echo.
    echo 💡 Esto significa que necesitas hacer login primero.
    echo.
    echo 📋 PASOS PARA DOMINIO FIJO:
    echo    1. Crea cuenta en Cloudflare (gratis): https://dash.cloudflare.com/sign-up
    echo    2. Ejecuta: HACER_LOGIN_CLOUDFLARE.bat
    echo    3. Cuando se abra el navegador, CIERRA la ventana (aunque esté vacía)
    echo    4. Vuelve a ejecutar este script
    echo.
    echo ¿Quieres usar modo rápido ahora (URL cambiará cada vez)?
    echo [S] Sí, usar modo rápido  [N] No, hacer login primero
    choice /C SN /N /M "Tu elección: "
    if errorlevel 2 (
        echo.
        echo Ejecuta HACER_LOGIN_CLOUDFLARE.bat primero.
        echo Luego vuelve a ejecutar este script.
        pause
        exit /b 1
    )
    echo.
    echo Usando modo rápido (URL cambiará cada vez)...
    echo.
    set USE_QUICK_TUNNEL=1
    goto :quick_tunnel
) else (
    echo.
    echo ✅ Túnel "%TUNNEL_NAME%" creado exitosamente
    echo.
)

:tunnel_ready
echo.

echo.
echo [4/4] Iniciando túnel...
echo.

REM Verificar si debemos usar modo rápido o permanente
if defined USE_QUICK_TUNNEL (
    goto :quick_tunnel
)

REM Intentar iniciar túnel permanente
echo ========================================
echo   INICIANDO TÚNEL PERMANENTE
echo ========================================
echo.
echo El túnel "%TUNNEL_NAME%" se iniciará ahora.
echo.
echo 📋 La URL permanente aparecerá en la ventana que se abrirá.
echo    Será algo como: https://%TUNNEL_NAME%-xxxxx.trycloudflare.com
echo.
echo ⚠️  IMPORTANTE:
echo    - Esta URL será PERMANENTE (siempre la misma)
echo    - Cada vez que ejecutes este script, tendrás la misma URL
echo    - Para mantenerla activa, deja la ventana de Cloudflare abierta
echo.
echo Presiona cualquier tecla para iniciar el túnel...
pause >nul

start "Cloudflare Tunnel - ASPERS Projects" cmd /k "%CLOUDFLARE_PATH% tunnel run %TUNNEL_NAME%"
goto :tunnel_started

:quick_tunnel
echo ========================================
echo   MODO TÚNEL RÁPIDO
echo ========================================
echo.
echo ✅ Usando modo rápido (sin login requerido)
echo.
echo 📋 La URL aparecerá en la ventana de Cloudflare
echo    Será algo como: https://xxxxx.trycloudflare.com
echo.
echo ⚠️  NOTA: La URL cambiará cada vez que reinicies
echo    Pero funciona perfectamente para empezar.
echo.
echo 💡 Para URL permanente más adelante:
echo   1. Crea cuenta en Cloudflare (gratis)
echo   2. Ejecuta: HACER_LOGIN_CLOUDFLARE.bat
echo   3. Vuelve a ejecutar este script
echo.
echo Presiona cualquier tecla para iniciar túnel rápido...
pause >nul

start "Cloudflare Tunnel - ASPERS Projects" cmd /k "%CLOUDFLARE_PATH% tunnel --url http://localhost:8080"
goto :tunnel_started

:tunnel_started

echo.
echo ========================================
echo   ✅ TÚNEL INICIADO
echo ========================================
echo.
echo ✅ El túnel está corriendo en una ventana separada.
echo.
echo 📋 Revisa la ventana "Cloudflare Tunnel - ASPERS Projects"
echo    para ver tu URL permanente.
echo.
echo 💡 La URL será siempre la misma cada vez que ejecutes este script.
echo.
echo Para detener: Cierra la ventana de Cloudflare Tunnel
echo Para reiniciar: Ejecuta este script nuevamente
echo.
echo Presiona cualquier tecla para cerrar esta ventana...
pause >nul

