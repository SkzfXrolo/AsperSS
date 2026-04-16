@echo off
chcp 65001 >nul
title ASPERS Projects - Iniciar API REST
color 0A

echo ========================================
echo   ASPERS PROJECTS - API REST SERVER
echo ========================================
echo.

:: Verificar que Python está instalado
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python no encontrado
    echo.
    echo Por favor instala Python 3.8 o superior
    echo.
    pause
    exit /b 1
)

:: Cambiar al directorio del proyecto
cd /d "%~dp0"

:: Verificar que existe el archivo de la API
if not exist "source\api_server.py" (
    echo ❌ No se encontró source\api_server.py
    echo.
    echo Asegúrate de estar en la carpeta del proyecto
    echo.
    pause
    exit /b 1
)

echo ✅ Iniciando API REST...
echo.
echo 📡 La API estará disponible en: http://localhost:5000
echo 🔑 La API Key se mostrará al iniciar
echo.
echo 💡 Para detener la API, presiona Ctrl+C
echo.

:: Iniciar la API
python source\api_server.py

pause

