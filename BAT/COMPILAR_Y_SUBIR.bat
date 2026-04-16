@echo off
chcp 65001 >nul
title Compilar y Subir a GitHub
color 0A

echo ========================================
echo   COMPILAR Y SUBIR A GITHUB
echo ========================================
echo.

:: Verificar que estamos en un repositorio Git
git status >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ No se detectó un repositorio Git
    echo.
    pause
    exit /b 1
)

echo ✅ Repositorio Git detectado
echo.

:: Paso 1: Compilar (opcional)
echo ========================================
echo   PASO 1: COMPILAR EJECUTABLE
echo ========================================
echo.
echo ¿Deseas compilar el ejecutable? (S/N)
set /p compilar="> "

if /i "%compilar%"=="S" (
    echo.
    echo 🔨 Compilando...
    echo.
    
    cd source
    pyinstaller MinecraftSSTool.spec --clean --noconfirm
    
    if %errorlevel% equ 0 (
        echo ✅ Compilación exitosa
        echo.
        echo 📦 Ejecutable generado en: source\dist\MinecraftSSTool.exe
        echo.
    ) else (
        echo ❌ Error en la compilación
        echo.
        echo 💡 Intenta compilar manualmente:
        echo    cd source
        echo    pyinstaller MinecraftSSTool.spec
        echo.
    )
    cd ..
    echo.
) else (
    echo ⏭️  Omitiendo compilación
    echo.
)

:: Paso 2: Agregar cambios del código fuente
echo ========================================
echo   PASO 2: AGREGAR CAMBIOS DEL CÓDIGO
echo ========================================
echo.

echo 📤 Agregando cambios del código fuente...
echo.

:: Agregar archivos modificados del código fuente
git add source/main.py
git add source/api_server.py
git add web_app/auth.py
git add web_app/app.py

:: Agregar otros archivos modificados si existen
git add source/*.py
git add web_app/*.py

echo.
echo 📋 Archivos modificados:
git status --short

echo.
echo 📝 ¿Deseas hacer commit y push? (S/N)
set /p continuar="> "

if /i not "%continuar%"=="S" (
    echo.
    echo ⏭️  Cancelado. Los archivos están agregados pero no commiteados.
    echo    Puedes hacer commit manualmente con:
    echo    git commit -m "Fix: Arreglar guardado de datos en BD y envío de formularios"
    echo    git push
    echo.
    pause
    exit /b 0
)

echo.
echo 📝 Haciendo commit...
echo.

git commit -m "Fix: Arreglar guardado de usuarios, tokens y resultados en BD

- Mejorar manejo de transacciones en auth.py y api_server.py
- Arreglar inicialización de db_integration en main.py
- Corregir guardado de config.json en ubicación persistente
- Mejorar envío de resultados del formulario a la página web
- Agregar verificaciones de persistencia después de commits"

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
        echo Los cambios han sido subidos a GitHub
        echo.
        echo 💡 Próximos pasos:
        echo    1. Verifica los cambios en GitHub
        echo    2. Si compilaste, puedes subir el .exe con: SUBIR_EXE_A_GITHUB.bat
        echo    3. En Render, los cambios se desplegarán automáticamente
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
    echo    git commit -m "Fix: Arreglar guardado de datos"
    echo    git push
    echo.
)

echo.
pause

