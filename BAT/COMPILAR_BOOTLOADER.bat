@echo off
echo ========================================
echo   COMPILANDO BOOTLOADER PARA PYTHON 3.14
echo ========================================
echo.
echo Esto puede tardar varios minutos...
echo.

cd /d "%~dp0..\.."

python -m PyInstaller.utils.build bootloader

if %errorlevel% equ 0 (
    echo.
    echo Bootloader compilado exitosamente!
    echo Ahora puedes compilar la aplicacion normalmente.
) else (
    echo.
    echo ERROR: No se pudo compilar el bootloader
    echo.
    echo Necesitas Visual Studio Build Tools o un compilador C++
    echo.
    echo Alternativa: Usar Python 3.11 o 3.12 que ya tienen bootloader
)

echo.
pause

