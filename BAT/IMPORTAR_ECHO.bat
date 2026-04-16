@echo off
chcp 65001 >nul
echo ========================================
echo   IMPORTADOR DE RESULTADOS ECHO
echo   ASPERS Projects
echo ========================================
echo.

cd /d "%~dp0"

echo Iniciando importador...
echo.

python importar_resultados_echo.py

echo.
echo Presiona cualquier tecla para cerrar...
pause >nul

