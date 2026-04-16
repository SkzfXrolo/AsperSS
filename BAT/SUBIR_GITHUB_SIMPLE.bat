@echo off
chcp 65001 >nul
echo ========================================
echo   SUBIR A GITHUB - VERSION SIMPLE
echo ========================================
echo.

REM Ir a la carpeta del proyecto (usando ruta relativa)
cd /d "%~dp0\.."

echo Carpeta actual: %CD%
echo.

REM Verificar que estamos en el lugar correcto
if not exist "web_app" (
    echo ERROR: No se encuentra la carpeta web_app
    echo Asegurate de ejecutar este script desde la carpeta web_app
    pause
    exit /b 1
)

echo [1] Configurando Git...
git config user.name "aspersink-svg" 2>nul
git config user.email "aspersink-svg@users.noreply.github.com" 2>nul
echo OK
echo.

echo [2] Inicializando repositorio...
if not exist ".git" (
    git init
)
echo OK
echo.

echo [3] Agregando archivos...
git add .
echo OK
echo.

echo [4] Creando commit...
git commit -m "Initial commit - ASPERS Projects" 2>nul
if errorlevel 1 (
    echo No hay cambios nuevos para commitear
) else (
    echo OK
)
echo.

echo [5] Configurando rama main...
git branch -M main 2>nul
echo OK
echo.

echo [6] Configurando remote...
git remote remove origin 2>nul
git remote add origin https://github.com/aspersink-svg/aspersprojectsSS.git
echo OK
echo.

echo [7] Traer contenido remoto...
git fetch origin 2>nul
git pull origin main --allow-unrelated-histories --no-edit 2>nul
if errorlevel 1 (
    echo No hay contenido remoto o ya esta sincronizado
) else (
    echo OK - Contenido remoto fusionado
)
echo.

echo [8] Subiendo a GitHub...
echo.
echo Si te pide usuario/contraseña:
echo - Username: aspersink-svg
echo - Password: Tu Personal Access Token (no tu contraseña)
echo.
echo Si no tienes token, ve a: https://github.com/settings/tokens
echo.
pause

git push -u origin main

if errorlevel 1 (
    echo.
    echo ========================================
    echo   ERROR AL SUBIR
    echo ========================================
    echo.
    echo Posibles causas:
    echo 1. Necesitas autenticarte (crea un token en GitHub)
    echo 2. Problema de conexion
    echo.
    echo Ve a: https://github.com/settings/tokens
    echo Crea un token y vuelve a ejecutar este script
    echo.
    pause
    exit /b 1
) else (
    echo.
    echo ========================================
    echo   EXITO! CODIGO SUBIDO A GITHUB
    echo ========================================
    echo.
    echo Tu codigo esta en:
    echo https://github.com/aspersink-svg/aspersprojectsSS
    echo.
    echo Ahora puedes configurar Render.com:
    echo 1. Ve a Render.com
    echo 2. Click "New Web Service"
    echo 3. Conecta el repositorio: aspersink-svg/aspersprojectsSS
    echo 4. Root Directory: web_app
    echo 5. Start Command: gunicorn app:app --bind 0.0.0.0:$PORT
    echo.
    pause
)

