@echo off
cd /d "%~dp0..\..\source"
echo Directorio: %CD%
echo.
echo Probando compilacion directa...
python -m PyInstaller MinecraftSSTool.spec --clean --distpath "dist" --workpath "build" --noconfirm
echo.
echo Errorlevel: %errorlevel%
pause

