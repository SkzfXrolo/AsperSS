@echo off
chcp 65001 >nul
title Subir .exe a GitHub
color 0B

echo ========================================
echo   SUBIR MINECRAFTSSTOOL.EXE A GITHUB
echo ========================================
echo.

:: Verificar que el .exe existe
if not exist "source\dist\MinecraftSSTool.exe" (
    echo ❌ No se encontró source\dist\MinecraftSSTool.exe
    echo.
    echo 💡 Primero debes compilar el proyecto
    echo.
    pause
    exit /b 1
)

echo ✅ Ejecutable encontrado en: source\dist\MinecraftSSTool.exe
echo.

:: Verificar que estamos en un repositorio Git
git status >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ No estás en un repositorio Git
    echo.
    echo 💡 Asegúrate de estar en la carpeta del proyecto
    echo.
    pause
    exit /b 1
)

echo 📤 Agregando el ejecutable a Git...
echo.

:: Forzar agregar el .exe (ignorando .gitignore temporalmente)
git add -f source/dist/MinecraftSSTool.exe

if %errorlevel% equ 0 (
    echo ✅ Archivo agregado correctamente
    echo.
    echo 📝 El archivo está listo para commit
    echo.
    echo 💡 Próximos pasos:
    echo    1. Abre GitHub Desktop
    echo    2. Verás el archivo source/dist/MinecraftSSTool.exe como nuevo
    echo    3. Haz commit con el mensaje: "Agregar ejecutable compilado"
    echo    4. Haz push para subirlo a GitHub
    echo.
) else (
    echo ❌ Error al agregar el archivo
    echo.
    echo 💡 Intenta manualmente:
    echo    git add -f source/dist/MinecraftSSTool.exe
    echo.
)

echo.
pause

