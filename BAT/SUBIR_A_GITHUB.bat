@echo off
chcp 65001 >nul
echo ========================================
echo   SUBIR PROYECTO A GITHUB
echo   ASPERS Projects
echo ========================================
echo.

REM Ir a la carpeta del proyecto
cd /d "%~dp0\.."

echo ✅ Carpeta del proyecto: %CD%
echo.

REM Configurar Git (si no está configurado)
echo [1/6] Configurando Git...
git config user.name "aspersink-svg" >nul 2>&1
git config user.email "aspersink-svg@users.noreply.github.com" >nul 2>&1
echo ✅ Git configurado
echo.

REM Inicializar repositorio (si no está inicializado)
echo [2/6] Inicializando repositorio...
if not exist ".git" (
    git init
    echo ✅ Repositorio inicializado
) else (
    echo ✅ Repositorio ya existe
)
echo.

REM Agregar todos los archivos
echo [3/6] Agregando archivos...
git add .
echo ✅ Archivos agregados
echo.

REM Hacer commit
echo [4/6] Haciendo commit...
git commit -m "Initial commit - ASPERS Projects" >nul 2>&1
if errorlevel 1 (
    echo ⚠️  No hay cambios para commitear (o ya está todo commiteado)
) else (
    echo ✅ Commit realizado
)
echo.

REM Configurar rama main
echo [5/6] Configurando rama main...
git branch -M main >nul 2>&1
echo ✅ Rama main configurada
echo.

REM Agregar remote (si no existe)
echo [6/6] Conectando con GitHub...
git remote remove origin >nul 2>&1
git remote add origin https://github.com/aspersink-svg/aspersprojectsSS.git
echo ✅ Remote configurado
echo.

REM Verificar si hay commits locales
git log --oneline >nul 2>&1
if errorlevel 1 (
    echo ⚠️  No hay commits locales. Creando commit...
    git add .
    git commit -m "Initial commit - ASPERS Projects"
    echo ✅ Commit creado
    echo.
)

REM Intentar pull primero (por si el repositorio remoto tiene contenido)
echo [7/7] Sincronizando con GitHub...
git pull origin main --allow-unrelated-histories --no-edit >nul 2>&1
if errorlevel 1 (
    echo ℹ️  No hay contenido remoto o ya está sincronizado
) else (
    echo ✅ Contenido remoto traído
)
echo.

REM Push
echo.
echo ========================================
echo   SUBIENDO A GITHUB...
echo ========================================
echo.
echo Esto puede tomar unos segundos...
echo.

git push -u origin main

if errorlevel 1 (
    echo.
    echo ⚠️  Error al subir. Posibles causas:
    echo    1. No tienes permisos (necesitas autenticarte en GitHub)
    echo    2. Problema de conexión
    echo.
    echo 💡 SOLUCIÓN MANUAL:
    echo    1. Ve a GitHub y crea un Personal Access Token
    echo    2. O ejecuta manualmente:
    echo       git pull origin main --allow-unrelated-histories
    echo       git push -u origin main
    echo.
    pause
    exit /b 1
) else (
    echo.
    echo ========================================
    echo   ✅ ¡CÓDIGO SUBIDO A GITHUB!
    echo ========================================
    echo.
    echo Tu código está en:
    echo https://github.com/aspersink-svg/aspersprojectsSS
    echo.
    echo Ahora puedes configurar Render.com:
    echo 1. Ve a Render.com
    echo 2. Click "New Web Service"
    echo 3. Conecta este repositorio
    echo 4. Root Directory: web_app
    echo 5. Start Command: gunicorn app:app --bind 0.0.0.0:$PORT
    echo.
    pause
)

