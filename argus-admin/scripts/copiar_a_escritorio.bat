@echo off
REM Copia ArgusAdmin.exe al escritorio y borra versiones viejas ArgusAdmin*.exe
setlocal
set "ROOT=%~dp0.."
set "SRC=%ROOT%\dist\ArgusAdmin.exe"
if not exist "%SRC%" (
    echo [ERROR] No existe dist\ArgusAdmin.exe — compilá antes: pyinstaller ArgusAdmin.spec
    exit /b 1
)

set "DESKTOP=%USERPROFILE%\OneDrive\Desktop"
if not exist "%DESKTOP%" set "DESKTOP=%USERPROFILE%\Desktop"
if not exist "%DESKTOP%" set "DESKTOP=%USERPROFILE%\OneDrive\Escritorio"
if not exist "%DESKTOP%" (
    echo [ERROR] No se encontró el escritorio.
    exit /b 1
)

for /f "delims=" %%V in ('python -c "from argus_admin import ADMIN_VERSION; print(ADMIN_VERSION)" 2^>nul') do set "VER=%%V"
if not defined VER set "VER=latest"
set "DEST=%DESKTOP%\ArgusAdmin-v%VER%.exe"

echo Borrando ArgusAdmin*.exe en escritorio...
del /q "%DESKTOP%\ArgusAdmin*.exe" 2>nul

echo Copiando a %DEST%
copy /y "%SRC%" "%DEST%" >nul
if errorlevel 1 (
    echo [ERROR] No se pudo copiar.
    exit /b 1
)
echo Listo: %DEST%
endlocal
