@echo off
chcp 65001 >nul
title Verificar y Agregar source/ a GitHub
color 0B

echo ========================================
echo   VERIFICAR Y AGREGAR SOURCE/ A GITHUB
echo ========================================
echo.

echo 📋 Verificando estado de Git...
echo.
git status

echo.
echo.
echo 📋 Verificando si source/ está rastreado por Git...
echo.
git ls-files source/ | findstr /i "source" >nul
if %errorlevel% equ 0 (
    echo ✅ La carpeta source/ YA está en Git
    echo.
    echo Verificando archivos específicos...
    git ls-files source/ | findstr /i "api_server Procfile requirements gunicorn"
    echo.
    echo Si ves los archivos arriba, source/ ya está en GitHub
    echo.
) else (
    echo ❌ La carpeta source/ NO está rastreada
    echo.
    echo Agregando archivos críticos...
    echo.
    git add -f source/api_server.py
    git add -f source/Procfile
    git add -f source/requirements.txt
    git add -f source/gunicorn_config.py
    git add -f source/
    git add -f source/*
    
    echo.
    echo Verificando qué se agregó...
    git status --short | findstr /i "source"
    echo.
)

echo.
echo 💡 Si source/ ya está en GitHub:
echo    Ve a: https://github.com/aspersink-svg/aspersprojectsSS/tree/main/source
echo    Debe aparecer la carpeta con los archivos
echo.
echo 💡 Si NO está en GitHub:
echo    Ejecuta estos comandos:
echo    git add -f source/
echo    git commit -m "Agregar carpeta source/"
echo    git push
echo.

pause

