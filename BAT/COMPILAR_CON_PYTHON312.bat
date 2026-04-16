@echo off
setlocal enabledelayedexpansion

title Compilar con Python 3.12
color 0A

echo ========================================
echo   COMPILAR CON PYTHON 3.12
echo ========================================
echo.

REM Buscar Python 3.12
set "PYTHON312="
if exist "C:\Python312\python.exe" set "PYTHON312=C:\Python312\python.exe"
if exist "C:\Program Files\Python312\python.exe" set "PYTHON312=C:\Program Files\Python312\python.exe"
if exist "C:\Program Files (x86)\Python312\python.exe" set "PYTHON312=C:\Program Files (x86)\Python312\python.exe"

if "!PYTHON312!"=="" (
    echo.
    echo ERROR: Python 3.12 no encontrado
    echo.
    echo Por favor instala Python 3.12 desde python.org
    echo O descarga version portable desde:
    echo https://www.python.org/downloads/release/python-3120/
    echo.
    pause
    exit /b 1
)

echo Python 3.12 encontrado: !PYTHON312!
echo.

cd /d "%~dp0..\..\source"

echo Instalando PyInstaller en Python 3.12...
!PYTHON312! -m pip install pyinstaller >nul 2>&1

echo Instalando dependencias...
!PYTHON312! -m pip install psutil requests flask flask-cors colorama >nul 2>&1

echo.
echo Compilando...
!PYTHON312! -m PyInstaller MinecraftSSTool.spec --clean --distpath "dist" --workpath "build" --noconfirm

if exist "dist\MinecraftSSTool.exe" (
    echo.
    echo ========================================
    echo   COMPILACION EXITOSA
    echo ========================================
    echo Archivo: dist\MinecraftSSTool.exe
    for %%A in ("dist\MinecraftSSTool.exe") do (
        set size=%%~zA
        set /a sizeMB=%%~zA/1024/1024
        echo Tamano: !size! bytes (~!sizeMB! MB)
    )
) else (
    echo ERROR en la compilacion
)

pause

