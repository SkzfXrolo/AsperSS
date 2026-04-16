@echo off
setlocal enabledelayedexpansion

title Descargar Python 3.12 y Compilar
color 0E

echo ========================================
echo   SOLUCION AUTOMATICA
echo ========================================
echo.
echo Esto descargara Python 3.12 portable y compilara el .exe
echo.

set "PYTHON312_PORTABLE=%TEMP%\Python312_Portable"
set "PYTHON312_EXE=%PYTHON312_PORTABLE%\python.exe"

REM Verificar si ya existe
if exist "!PYTHON312_EXE!" (
    echo Python 3.12 portable ya existe, usandolo...
    goto :compilar
)

echo Descargando Python 3.12 portable...
echo Esto puede tardar unos minutos...
echo.

REM Crear directorio temporal
if not exist "!PYTHON312_PORTABLE!" mkdir "!PYTHON312_PORTABLE!"

REM Descargar Python 3.12 embeddable
powershell -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.12.0/python-3.12.0-embed-amd64.zip' -OutFile '%TEMP%\python312.zip'"

if not exist "%TEMP%\python312.zip" (
    echo ERROR: No se pudo descargar Python 3.12
    echo.
    echo SOLUCION MANUAL:
    echo 1. Descarga manualmente desde: https://www.python.org/downloads/release/python-3120/
    echo 2. Busca "Windows embeddable package (64-bit)"
    echo 3. Extrae en: %PYTHON312_PORTABLE%
    echo 4. Ejecuta este script de nuevo
    pause
    exit /b 1
)

echo Extrayendo...
powershell -Command "Expand-Archive -Path '%TEMP%\python312.zip' -DestinationPath '!PYTHON312_PORTABLE!' -Force"

REM Habilitar pip
echo python312._pth > "!PYTHON312_PORTABLE!\python312._pth.bak"
echo python312.zip > "!PYTHON312_PORTABLE!\python312._pth"
echo. >> "!PYTHON312_PORTABLE!\python312._pth"
echo import site >> "!PYTHON312_PORTABLE!\python312._pth"

:compilar
echo.
echo Instalando PyInstaller...
"!PYTHON312_EXE!" -m pip install pyinstaller --quiet

echo Instalando dependencias...
"!PYTHON312_EXE!" -m pip install psutil requests flask flask-cors colorama --quiet

cd /d "%~dp0..\..\source"

echo.
echo Compilando...
"!PYTHON312_EXE!" -m PyInstaller MinecraftSSTool.spec --clean --distpath "dist" --workpath "build" --noconfirm

if exist "dist\MinecraftSSTool.exe" (
    echo.
    echo ========================================
    echo   COMPILACION EXITOSA
    echo ========================================
    echo Archivo: dist\MinecraftSSTool.exe
) else (
    echo ERROR en la compilacion
)

pause

