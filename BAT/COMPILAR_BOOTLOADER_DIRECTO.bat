@echo off
echo Compilando bootloader de PyInstaller para Python 3.14...
echo.

python -c "import PyInstaller; import os; import subprocess; import sys; bootloader = os.path.join(PyInstaller.__path__[0], 'bootloader', 'Windows-64bit-intel'); print('Bootloader dir:', bootloader); os.chdir(bootloader); subprocess.run([sys.executable, 'waf', 'all'])"

echo.
echo Si la compilacion fue exitosa, ahora puedes compilar normalmente.
pause

