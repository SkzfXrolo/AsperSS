@echo off
setlocal enabledelayedexpansion

title Compilar con Captura de Errores
color 0E

cd /d "%~dp0..\..\source"

echo ========================================
echo   COMPILANDO Y CAPTURANDO ERRORES
echo ========================================
echo.
echo Directorio: %CD%
echo.

python -m PyInstaller MinecraftSSTool.spec --clean --distpath "dist" --workpath "build" --noconfirm > compilacion_log.txt 2>&1

echo.
echo ========================================
echo   RESULTADO DE LA COMPILACION
echo ========================================
echo.

if %errorlevel% equ 0 (
    echo COMPILACION EXITOSA
    if exist "dist\MinecraftSSTool.exe" (
        echo Archivo generado: dist\MinecraftSSTool.exe
    )
) else (
    echo ERROR EN LA COMPILACION
    echo.
    echo Ultimas 50 lineas del log:
    echo ========================================
    powershell -Command "Get-Content compilacion_log.txt -Tail 50"
    echo ========================================
    echo.
    echo Log completo guardado en: compilacion_log.txt
)

echo.
echo Presiona cualquier tecla para cerrar...
pause >nul

