@echo off
setlocal enabledelayedexpansion

title Compilar con cx_Freeze
color 0A

echo ========================================
echo   COMPILANDO CON CX_FREEZE
echo ========================================
echo.

cd /d "%~dp0..\..\source"

echo Instalando cx_Freeze...
pip install cx_Freeze >nul 2>&1

echo Limpiando compilaciones anteriores...
if exist "build" rmdir /s /q "build" 2>nul
if exist "dist" rmdir /s /q "dist" 2>nul

echo.
echo Compilando...
python setup_cxfreeze.py build

if exist "build\exe.win-amd64-3.14\MinecraftSSTool.exe" (
    echo.
    echo ========================================
    echo   COMPILACION EXITOSA
    echo ========================================
    echo.
    echo Archivo generado: build\exe.win-amd64-3.14\MinecraftSSTool.exe
    echo.
    echo Copiando a dist...
    if not exist "dist" mkdir "dist"
    copy "build\exe.win-amd64-3.14\MinecraftSSTool.exe" "dist\MinecraftSSTool.exe" >nul
    if exist "dist\MinecraftSSTool.exe" (
        echo Archivo copiado a: dist\MinecraftSSTool.exe
        for %%A in ("dist\MinecraftSSTool.exe") do (
            set size=%%~zA
            set /a sizeMB=%%~zA/1024/1024
            echo Tamano: !size! bytes (~!sizeMB! MB)
        )
    )
) else (
    echo.
    echo ERROR: No se genero el archivo
    echo Revisa los mensajes de error arriba
)

echo.
pause

