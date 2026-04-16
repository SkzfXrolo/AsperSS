@echo off
chcp 65001 >nul
title Subir carpetas build y dist a GitHub
color 0B

echo ========================================
echo   SUBIR CARPETAS BUILD Y DIST A GITHUB
echo ========================================
echo.

:: Verificar que estamos en un repositorio Git
git status >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ No estás en un repositorio Git
    echo.
    echo 💡 Asegúrate de estar en la carpeta del proyecto
    echo    y que el repositorio esté inicializado
    echo.
    pause
    exit /b 1
)

echo 📤 Agregando carpetas build y dist a Git...
echo.

:: Agregar todo el contenido de source/build/
if exist "source\build" (
    echo ✅ Agregando source/build/...
    git add -f source/build/
    git add -f source/build/*
    git add -f source/build/**/*
) else (
    echo ⚠️  source/build/ no existe localmente
)

:: Agregar todo el contenido de source/dist/
if exist "source\dist" (
    echo ✅ Agregando source/dist/...
    git add -f source/dist/
    git add -f source/dist/*
    git add -f source/dist/**/*
) else (
    echo ⚠️  source/dist/ no existe localmente
)

echo.
echo 📋 Verificando archivos agregados...
git status --short | findstr /i "build dist"

if %errorlevel% equ 0 (
    echo.
    echo ✅ Archivos agregados correctamente
    echo.
    echo 💡 Próximos pasos:
    echo    1. Abre GitHub Desktop
    echo    2. Verás los archivos de source/build/ y source/dist/ como nuevos
    echo    3. Haz commit con el mensaje: "Agregar carpetas build y dist"
    echo    4. Haz push para subirlos a GitHub
    echo.
) else (
    echo.
    echo ⚠️  No se encontraron archivos nuevos para agregar
    echo    Puede que ya estén en el repositorio o que las carpetas estén vacías
    echo.
)

echo.
pause

