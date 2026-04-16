@echo off
chcp 65001 >nul
echo ========================================
echo   ASPERS Projects - Iniciar con ngrok
echo ========================================
echo.

REM Cambiar esta ruta a donde tengas ngrok.exe
REM Si ngrok está en el PATH, puedes usar solo "ngrok"
set NGROK_PATH=ngrok.exe

REM Ruta de la aplicación (directorio actual)
set APP_PATH=%~dp0

echo [1/3] Iniciando aplicación Flask...
start "ASPERS Flask App" cmd /k "cd /d %APP_PATH% && python app.py"

timeout /t 3 /nobreak >nul

echo [2/3] Esperando que la aplicación inicie...
timeout /t 5 /nobreak >nul

echo [3/3] Iniciando túnel ngrok...
echo.
echo ========================================
echo   IMPORTANTE:
echo ========================================
echo 1. Si es la primera vez, necesitas configurar ngrok:
echo    ngrok config add-authtoken TU_TOKEN
echo.
echo 2. Obtén tu token en: https://dashboard.ngrok.com/get-started/your-authtoken
echo.
echo 3. La URL pública aparecerá en la ventana de ngrok
echo ========================================
echo.

start "ngrok Tunnel" cmd /k "%NGROK_PATH% http 8080"

echo.
echo ========================================
echo   ¡Aplicación iniciada!
echo ========================================
echo.
echo La aplicación está corriendo en:
echo   - Local: http://localhost:8080
echo   - Público: Revisa la ventana de ngrok para la URL
echo.
echo Presiona cualquier tecla para cerrar esta ventana...
pause >nul

