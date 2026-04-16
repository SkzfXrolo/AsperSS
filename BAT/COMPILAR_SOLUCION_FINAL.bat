@echo off
setlocal enabledelayedexpansion

title Solucion Final - Compilar EXE
color 0A

echo ========================================
echo   SOLUCION FINAL - COMPILAR EXE
echo ========================================
echo.
echo Opcion 1: Usar bootloader de Python 3.13 (si existe)
echo Opcion 2: Compilar bootloader manualmente
echo Opcion 3: Usar Python 3.11/3.12 portable
echo.

cd /d "%~dp0..\..\source"

REM Intentar copiar bootloader de Python 3.13 si existe
set "PYTHON313=C:\Python313"
if exist "%PYTHON313%\python.exe" (
    echo Encontrado Python 3.13, intentando usar su bootloader...
    set "BOOTLOADER_SRC=%PYTHON313%\Lib\site-packages\PyInstaller\bootloader\Windows-64bit-intel"
    set "BOOTLOADER_DST=%APPDATA%\Python\Python314\site-packages\PyInstaller\bootloader\Windows-64bit-intel"
    if exist "!BOOTLOADER_SRC!" (
        if not exist "!BOOTLOADER_DST!" mkdir "!BOOTLOADER_DST!"
        xcopy /Y /E "!BOOTLOADER_SRC!\*" "!BOOTLOADER_DST!\" >nul 2>&1
        echo Bootloader copiado, intentando compilar...
    )
)

REM Intentar compilar
echo.
echo Compilando con PyInstaller...
python -m PyInstaller MinecraftSSTool.spec --clean --distpath "dist" --workpath "build" --noconfirm

if exist "dist\MinecraftSSTool.exe" (
    echo.
    echo ========================================
    echo   COMPILACION EXITOSA
    echo ========================================
    echo Archivo: dist\MinecraftSSTool.exe
) else (
    echo.
    echo ========================================
    echo   ERROR: NO SE PUDO COMPILAR
    echo ========================================
    echo.
    echo SOLUCION RAPIDA:
    echo 1. Descarga Python 3.12 desde python.org
    echo 2. Instalalo en C:\Python312
    echo 3. Ejecuta: C:\Python312\python.exe -m pip install pyinstaller
    echo 4. Ejecuta: C:\Python312\python.exe -m PyInstaller source\MinecraftSSTool.spec
    echo.
)

pause

