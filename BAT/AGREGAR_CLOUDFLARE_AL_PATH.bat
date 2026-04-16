@echo off
chcp 65001 >nul
echo ========================================
echo   AGREGAR CLOUDFLARE AL PATH DE WINDOWS
echo   ASPERS Projects
echo ========================================
echo.

echo Este script te ayudará a agregar cloudflared.exe al PATH de Windows
echo para que puedas usarlo desde cualquier lugar.
echo.
echo ========================================
echo   PASO 1: UBICACIÓN DE CLOUDFLARE
echo ========================================
echo.
echo ¿Dónde está cloudflared.exe?
echo.
echo 1. Si ya lo descargaste, escribe la ruta completa
echo    Ejemplo: C:\cloudflared\cloudflared.exe
echo.
echo 2. Si NO lo has descargado:
echo    - Ve a: https://github.com/cloudflare/cloudflared/releases
echo    - Descarga: cloudflared-windows-amd64.exe
echo    - Renómbralo a: cloudflared.exe
echo    - Colócalo en una carpeta (ej: C:\cloudflared\)
echo.
set /p CLOUDFLARE_FOLDER="Escribe la carpeta donde está cloudflared.exe (ej: C:\cloudflared): "

REM Limpiar comillas si las agregó el usuario
set CLOUDFLARE_FOLDER=%CLOUDFLARE_FOLDER:"=%

REM Verificar que existe
if not exist "%CLOUDFLARE_FOLDER%\cloudflared.exe" (
    echo.
    echo ❌ No se encontró cloudflared.exe en: %CLOUDFLARE_FOLDER%
    echo.
    echo Por favor verifica la ruta e intenta de nuevo.
    pause
    exit /b 1
)

echo.
echo ✅ cloudflared.exe encontrado en: %CLOUDFLARE_FOLDER%
echo.

echo ========================================
echo   PASO 2: AGREGAR AL PATH
echo ========================================
echo.
echo Se agregará la siguiente ruta al PATH del sistema:
echo %CLOUDFLARE_FOLDER%
echo.
set /p CONFIRM="¿Continuar? (S/N): "

if /i not "%CONFIRM%"=="S" (
    echo Operación cancelada.
    pause
    exit /b 0
)

echo.
echo Agregando al PATH...
echo.

REM Agregar al PATH del usuario (más seguro que PATH del sistema)
for /f "tokens=2*" %%A in ('reg query "HKCU\Environment" /v PATH 2^>nul') do set "USER_PATH=%%B"

if defined USER_PATH (
    REM Verificar si ya está en el PATH
    echo %USER_PATH% | findstr /C:"%CLOUDFLARE_FOLDER%" >nul
    if not errorlevel 1 (
        echo ℹ️  La carpeta ya está en el PATH del usuario.
    ) else (
        setx PATH "%USER_PATH%;%CLOUDFLARE_FOLDER%" >nul
        echo ✅ Agregado al PATH del usuario exitosamente.
    )
) else (
    setx PATH "%CLOUDFLARE_FOLDER%" >nul
    echo ✅ Agregado al PATH del usuario exitosamente.
)

echo.
echo ========================================
echo   ✅ CONFIGURACIÓN COMPLETADA
echo ========================================
echo.
echo cloudflared.exe ha sido agregado al PATH.
echo.
echo ⚠️  IMPORTANTE:
echo    - Cierra y vuelve a abrir cualquier terminal/CMD abierta
echo    - O reinicia tu computadora para que los cambios surtan efecto
echo.
echo Ahora puedes usar "cloudflared" desde cualquier lugar.
echo.
pause

