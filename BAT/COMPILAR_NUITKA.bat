@echo off
setlocal enabledelayedexpansion

title Compilar con Nuitka
color 0A

echo ========================================
echo   COMPILANDO CON NUITKA
echo ========================================
echo.

cd /d "%~dp0..\..\source"

echo Instalando Nuitka...
pip install nuitka >nul 2>&1

echo Limpiando compilaciones anteriores...
if exist "build" rmdir /s /q "build" 2>nul
if exist "dist" rmdir /s /q "dist" 2>nul
if exist "MinecraftSSTool.dist" rmdir /s /q "MinecraftSSTool.dist" 2>nul
if exist "MinecraftSSTool.build" rmdir /s /q "MinecraftSSTool.build" 2>nul

echo.
echo Compilando con Nuitka (esto puede tardar varios minutos)...
python -m nuitka --onefile --windows-console-mode=force --include-module=tkinter --include-module=requests --include-module=psutil --include-module=flask --include-module=flask_cors --include-module=db_integration --include-module=ai_analyzer --include-module=astro_ss_techniques --include-module=silent_scanner_techniques --include-module=ui_style --include-data-file=config.json=config.json --output-dir=dist --output-filename=MinecraftSSTool.exe main.py

if exist "dist\MinecraftSSTool.exe" (
    echo.
    echo ========================================
    echo   COMPILACION EXITOSA
    echo ========================================
    echo.
    echo Archivo generado: dist\MinecraftSSTool.exe
    for %%A in ("dist\MinecraftSSTool.exe") do (
        set size=%%~zA
        set /a sizeMB=%%~zA/1024/1024
        echo Tamano: !size! bytes (~!sizeMB! MB)
    )
) else (
    echo.
    echo ERROR: No se genero el archivo
    echo Revisa los mensajes de error arriba
)

echo.
pause

