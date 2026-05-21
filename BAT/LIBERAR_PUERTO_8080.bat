@echo off
echo Liberando puerto 8080...
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":8080" ^| findstr "LISTENING"') do (
    echo Matando PID %%P
    taskkill /F /PID %%P
)
timeout /t 2 /nobreak >nul
netstat -ano | findstr ":8080" | findstr "LISTENING"
if errorlevel 1 (
    echo [OK] Puerto 8080 libre.
) else (
    echo [!] Sigue ocupado. Cierra Opera/navegador o reinicia PC.
)
pause
