@echo off
chcp 65001 >nul
title Reorganizar Repositorio - Mover a Raíz
color 0B

echo ========================================
echo   REORGANIZAR REPOSITORIO
echo   Mover archivos de "Aplicación de SS" a la raíz
echo ========================================
echo.

:: Verificar que estamos en el directorio correcto
if not exist "Aplicación de SS" (
    echo ❌ No se encontró la carpeta "Aplicación de SS"
    echo.
    echo 💡 Asegúrate de estar en: C:\Users\robin\Desktop\Tareas
    echo    Y que el repositorio esté ahí
    echo.
    pause
    exit /b 1
)

echo ✅ Carpeta "Aplicación de SS" encontrada
echo.

:: Verificar que es un repositorio Git
git status >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ No es un repositorio Git
    echo.
    echo 💡 Asegúrate de estar en la carpeta del repositorio
    echo.
    pause
    exit /b 1
)

echo ✅ Repositorio Git detectado
echo.
echo ⚠️  ADVERTENCIA: Esto moverá todos los archivos
echo    de "Aplicación de SS" a la raíz del repositorio
echo.
echo Presiona cualquier tecla para continuar o Ctrl+C para cancelar...
pause >nul

echo.
echo 📤 Moviendo archivos...
echo.

:: Mover archivos uno por uno usando PowerShell
powershell -Command "Get-ChildItem -Path 'Aplicación de SS' -File | ForEach-Object { git mv $_.FullName . }"

:: Mover carpetas
powershell -Command "Get-ChildItem -Path 'Aplicación de SS' -Directory | ForEach-Object { git mv $_.FullName . }"

echo.
echo 📋 Verificando cambios...
echo.
git status --short

echo.
echo ✅ Archivos movidos
echo.
echo 💡 Próximos pasos:
echo    1. Revisa los cambios arriba
echo    2. Si todo se ve bien, ejecuta:
echo       git commit -m "Reorganizar: mover archivos a la raíz"
echo       git push
echo.

pause

