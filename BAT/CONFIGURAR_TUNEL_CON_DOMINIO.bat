@echo off
chcp 65001 >nul
echo ========================================
echo   CONFIGURAR TÚNEL CON DOMINIO PROPIO
echo   ASPERS Projects
echo ========================================
echo.

REM Ruta por defecto: C:\cloudflared\cloudflared.exe
set CLOUDFLARE_PATH=C:\cloudflared\cloudflared.exe
set TUNNEL_NAME=aspersprojects

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
echo   CONFIGURACIÓN DE DOMINIO
echo ========================================
echo.
echo Este script configurará Cloudflare Tunnel con tu dominio.
echo.
echo ⚠️  REQUISITOS:
echo    1. Debes tener un dominio agregado a Cloudflare
echo    2. Los nameservers deben estar configurados
echo    3. El dominio debe estar activo en Cloudflare
echo.
set /p DOMINIO="Ingresa tu dominio (ej: aspersprojects.tk): "

if "%DOMINIO%"=="" (
    echo.
    echo ❌ Debes ingresar un dominio
    pause
    exit /b 1
)

echo.
echo ========================================
echo   CONFIGURANDO TÚNEL
echo ========================================
echo.

echo [1/4] Iniciando aplicación Flask...
start "ASPERS Flask App" cmd /k "cd /d %~dp0 && python app.py"
timeout /t 3 /nobreak >nul

echo [2/4] Verificando/creando túnel "%TUNNEL_NAME%"...
%CLOUDFLARE_PATH% tunnel list | findstr /C:"%TUNNEL_NAME%" >nul 2>&1
if errorlevel 1 (
    echo Creando nuevo túnel...
    %CLOUDFLARE_PATH% tunnel create %TUNNEL_NAME%
    if errorlevel 1 (
        echo.
        echo ❌ Error al crear túnel. Verifica que hayas hecho login:
        echo    Ejecuta: HACER_LOGIN_CLOUDFLARE.bat
        echo.
        pause
        exit /b 1
    )
    echo ✅ Túnel creado
) else (
    echo ✅ Túnel ya existe
)

echo.
echo [3/4] Configurando ruta DNS para %DOMINIO%...
%CLOUDFLARE_PATH% tunnel route dns %TUNNEL_NAME% %DOMINIO%

if errorlevel 1 (
    echo.
    echo ⚠️  Error al configurar DNS. Esto puede ser porque:
    echo    1. El dominio no está en Cloudflare
    echo    2. Los nameservers no están configurados
    echo    3. El dominio aún no está activo
    echo.
    echo Continuando sin configuración DNS...
    echo El túnel funcionará pero necesitarás configurar DNS manualmente.
    echo.
) else (
    echo ✅ Ruta DNS configurada
)

echo.
echo [4/4] Iniciando túnel...
echo.
echo ========================================
echo   TÚNEL INICIADO
echo ========================================
echo.
echo ✅ El túnel está corriendo.
echo.
if not errorlevel 1 (
    echo 🌐 Tu aplicación estará disponible en:
    echo    https://%DOMINIO%
    echo.
) else (
    echo 🌐 Tu aplicación estará disponible en:
    echo    https://%TUNNEL_NAME%-xxxxx.trycloudflare.com
    echo.
    echo ⚠️  Para usar tu dominio, configura DNS manualmente:
    echo    1. Ve a Cloudflare Dashboard
    echo    2. Agrega registro CNAME:
    echo       Nombre: @ (o el subdominio que quieras)
    echo       Destino: %TUNNEL_NAME%-xxxxx.trycloudflare.com
    echo       Proxy: Activado (nube naranja)
    echo.
)

echo Presiona cualquier tecla para iniciar el túnel...
pause >nul

start "Cloudflare Tunnel - ASPERS Projects" cmd /k "%CLOUDFLARE_PATH% tunnel run %TUNNEL_NAME%"

echo.
echo ✅ Túnel iniciado. Revisa la ventana de Cloudflare.
echo.
pause

