@echo off
chcp 65001 >nul
title Subir carpeta source/ a GitHub - URGENTE
color 0C

echo ========================================
echo   SUBIR CARPETA SOURCE/ A GITHUB
echo   (NECESARIO PARA RENDER)
echo ========================================
echo.

:: Verificar que estamos en un repositorio Git
git status >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ No se detectó un repositorio Git en esta carpeta
    echo.
    echo 💡 Si usas GitHub Desktop:
    echo    1. Abre GitHub Desktop
    echo    2. Ve a Repository → Open in Command Prompt
    echo    3. Ejecuta este script desde ahí
    echo.
    pause
    exit /b 1
)

echo ✅ Repositorio Git detectado
echo.

:: Verificar que source/ existe
if not exist "source" (
    echo ❌ No se encontró la carpeta source/
    echo.
    pause
    exit /b 1
)

echo ✅ Carpeta source/ encontrada
echo.

:: Verificar archivos críticos
if not exist "source\api_server.py" (
    echo ⚠️  Advertencia: source\api_server.py no encontrado
)

if not exist "source\Procfile" (
    echo ⚠️  Advertencia: source\Procfile no encontrado
)

if not exist "source\requirements.txt" (
    echo ⚠️  Advertencia: source\requirements.txt no encontrado
)

if not exist "source\gunicorn_config.py" (
    echo ⚠️  Advertencia: source\gunicorn_config.py no encontrado
)

echo.
echo 📤 Agregando carpeta source/ completa a Git...
echo.

:: Agregar todos los archivos de source/
git add source/
git add source/*
git add source/**/*

:: Agregar archivos críticos específicamente
git add -f source/api_server.py
git add -f source/Procfile
git add -f source/requirements.txt
git add -f source/gunicorn_config.py

echo.
echo 📋 Verificando archivos agregados...
echo.
git status --short | findstr /i "source"

echo.
echo ✅ Archivos agregados
echo.
echo 📝 Haciendo commit...
echo.

git commit -m "Agregar carpeta source/ con archivos de API para Render"

if %errorlevel% equ 0 (
    echo ✅ Commit realizado
    echo.
    echo 📤 Subiendo a GitHub...
    echo.
    git push
    
    if %errorlevel% equ 0 (
        echo.
        echo ✅✅✅ ¡ÉXITO! ✅✅✅
        echo.
        echo La carpeta source/ ha sido subida a GitHub
        echo.
        echo 💡 Próximos pasos:
        echo    1. Espera 1-2 minutos
        echo    2. Ve a: https://github.com/aspersink-svg/aspersprojectsSS/tree/main/source
        echo    3. Verifica que la carpeta source/ esté visible
        echo    4. En Render, haz clic en "Manual Deploy" → "Deploy latest commit"
        echo.
    ) else (
        echo.
        echo ❌ Error al hacer push
        echo.
        echo 💡 Intenta manualmente:
        echo    git push
        echo.
    )
) else (
    echo.
    echo ❌ Error al hacer commit
    echo.
    echo 💡 Puede que no haya cambios nuevos
    echo    O ejecuta manualmente:
    echo    git commit -m "Agregar carpeta source/"
    echo    git push
    echo.
)

echo.
pause

