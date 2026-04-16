@echo off
chcp 65001 >nul
title ASPERS Projects - Sistema Completo

echo ========================================
echo   ASPERS PROJECTS - SISTEMA COMPLETO
echo ========================================
echo.
echo Este script iniciara:
echo   1. API REST (Puerto 5000)
echo   2. Aplicacion Web (Puerto 8080)
echo.
echo Presiona cualquier tecla para continuar...
pause >nul

echo.
echo [1/2] Iniciando API REST...
start "ASPERS API Server" cmd /k "cd /d %~dp0 && python source/api_server.py"
timeout /t 3 /nobreak >nul

echo [2/2] Iniciando Aplicacion Web...
start "ASPERS Web App" cmd /k "cd /d %~dp0 && python web_app/app.py"
timeout /t 2 /nobreak >nul

echo.
echo ========================================
echo   SISTEMA INICIADO CORRECTAMENTE
echo ========================================
echo.
echo API REST: http://localhost:5000
echo Web App:  http://localhost:8080
echo.
echo Panel Staff: http://localhost:8080/panel
echo.
echo Las ventanas de la API y Web App permaneceran abiertas.
echo Cierra esta ventana cuando quieras.
echo.
pause

