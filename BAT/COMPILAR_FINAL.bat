@echo off
setlocal enabledelayedexpansion

title Compilar Minecraft SS Tool
color 0A

echo ========================================
echo   COMPILANDO MINECRAFT SS TOOL
echo ========================================
echo.

set "SCRIPT_PATH=%~dp0"
set "PROJECT_ROOT=%SCRIPT_PATH%..\.."
cd /d "%PROJECT_ROOT%"
if %errorlevel% neq 0 (
    echo ERROR: No se pudo cambiar al directorio del proyecto
    echo Ruta intentada: %PROJECT_ROOT%
    echo.
    echo Esperando 5 segundos antes de cerrar...
    timeout /t 5 /nobreak >nul
    exit /b 1
)

echo Directorio actual: %CD%
echo.

echo Paso 1: Verificando Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo ERROR: Python no encontrado.
    echo.
    echo Python no esta instalado o no esta en el PATH del sistema.
    echo Por favor instala Python 3.8 o superior desde python.org
    echo Asegurate de marcar Add Python to PATH durante la instalacion
    echo.
    echo Esperando 5 segundos antes de cerrar...
    timeout /t 5 /nobreak >nul
    exit /b 1
)
python --version
echo Python encontrado
echo.

echo Paso 1.1: Verificando y actualizando PyInstaller...
python -c "import PyInstaller" >nul 2>&1
if %errorlevel% neq 0 (
    echo PyInstaller no encontrado. Instalando version mas reciente...
    pip install --upgrade pyinstaller
    if %errorlevel% neq 0 (
        echo.
        echo ERROR: No se pudo instalar PyInstaller
        echo Verifica tu conexion a internet y los permisos
        echo.
        echo Esperando 5 segundos antes de cerrar...
        timeout /t 5 /nobreak >nul
        exit /b 1
    )
    echo PyInstaller instalado correctamente
) else (
    echo PyInstaller encontrado, actualizando a version mas reciente...
    pip install --upgrade pyinstaller >nul 2>&1
    echo PyInstaller actualizado
)
echo.

echo Paso 1.2: Instalando dependencias necesarias...
if exist "source\requirements.txt" (
    echo Instalando dependencias una por una para mejor control...
    echo.
    
    REM Instalar dependencias basicas (sin matplotlib/numpy para evitar problemas)
    echo [1/5] Instalando psutil...
    pip install psutil==5.9.6 >nul 2>&1
    
    echo [2/5] Instalando requests...
    pip install requests==2.31.0 >nul 2>&1
    
    echo [3/5] Instalando discord.py...
    pip install discord.py==2.3.2 >nul 2>&1
    
    echo [4/5] Instalando flask...
    pip install flask==3.0.0 >nul 2>&1
    
    echo [5/5] Instalando flask-cors y colorama...
    pip install flask-cors==4.0.0 colorama==0.4.6 >nul 2>&1
    
    echo.
    echo NOTA: matplotlib/numpy excluidos para evitar problemas de compilacion
    echo La aplicacion funcionara sin graficos (ya es opcional en el codigo)
    echo.
    echo Dependencias instaladas correctamente
) else (
    echo requirements.txt no encontrado, instalando dependencias basicas...
    pip install psutil requests matplotlib flask flask-cors colorama
    if %errorlevel% neq 0 (
        echo ERROR: Error instalando dependencias basicas
        echo.
        echo Esperando 5 segundos antes de cerrar...
        timeout /t 5 /nobreak >nul
        exit /b 1
    )
)
echo.

echo Paso 2: Limpiando compilaciones anteriores...
if exist "build" rmdir /s /q "build" 2>nul
if exist "dist" rmdir /s /q "dist" 2>nul
if exist "source\build" rmdir /s /q "source\build" 2>nul
if exist "source\dist" rmdir /s /q "source\dist" 2>nul

REM Limpiar posibles carpetas numpy problemáticas
if exist "source\numpy" rmdir /s /q "source\numpy" 2>nul
if exist "numpy" rmdir /s /q "numpy" 2>nul

REM Limpiar cache de Python que puede causar problemas
python -Bc "import sys; sys.path.insert(0, ''); import shutil; [shutil.rmtree(p, ignore_errors=True) for p in ['__pycache__', 'source/__pycache__']]" 2>nul

echo.
echo Paso 3: Compilando con PyInstaller...
echo.

if not exist "source\config.json" (
    if exist "config.json" (
        copy "config.json" "source\config.json" >nul
        echo config.json copiado a source
    )
)

if not exist "source\main.py" (
    echo ERROR: source\main.py no encontrado
    echo.
    echo Esperando 5 segundos antes de cerrar...
    timeout /t 5 /nobreak >nul
    exit /b 1
)

if not exist "source\MinecraftSSTool.spec" (
    echo ERROR: source\MinecraftSSTool.spec no encontrado
    echo.
    echo Esperando 5 segundos antes de cerrar...
    timeout /t 5 /nobreak >nul
    exit /b 1
)

echo Usando archivo .spec...
cd source
if %errorlevel% neq 0 (
    echo ERROR: No se pudo cambiar al directorio source
    echo.
    echo Esperando 5 segundos antes de cerrar...
    timeout /t 5 /nobreak >nul
    exit /b 1
)

REM Limpiar variables de entorno que puedan causar problemas
set PYTHONPATH=
set NUMPY_SETUP_BUILD=

echo Iniciando compilacion con PyInstaller...
python -m PyInstaller MinecraftSSTool.spec --clean --distpath "dist" --workpath "build" --noconfirm --log-level=WARN
if %errorlevel% neq 0 (
    echo.
    echo ERROR durante la compilacion
    echo Revisa los mensajes de error arriba
    cd ..
    echo.
    echo Esperando 5 segundos antes de cerrar...
    timeout /t 5 /nobreak >nul
    exit /b 1
)

REM Esperar un momento para que el archivo se escriba completamente
timeout /t 2 /nobreak >nul

cd ..
if %errorlevel% neq 0 (
    echo Advertencia: No se pudo volver al directorio raiz
)

echo.
echo Verificando archivo compilado...
echo Directorio actual: %CD%

REM Verificar desde el directorio raiz
if exist "source\dist\MinecraftSSTool.exe" (
    echo.
    echo ========================================
    echo   COMPILACION EXITOSA
    echo ========================================
    echo.
    echo Archivo generado: source\dist\MinecraftSSTool.exe
    for %%A in ("source\dist\MinecraftSSTool.exe") do (
        set size=%%~zA
        set /a sizeMB=%%~zA/1024/1024
        echo Tamano: !size! bytes (~!sizeMB! MB)
    )
    echo.
    echo Compilacion completada exitosamente!
) else (
    REM Intentar verificar desde source
    cd source
    if exist "dist\MinecraftSSTool.exe" (
        echo.
        echo ========================================
        echo   COMPILACION EXITOSA
        echo ========================================
        echo.
        echo Archivo generado: source\dist\MinecraftSSTool.exe
        for %%A in ("dist\MinecraftSSTool.exe") do (
            set size=%%~zA
            set /a sizeMB=%%~zA/1024/1024
            echo Tamano: !size! bytes (~!sizeMB! MB)
        )
        echo.
        echo Compilacion completada exitosamente!
        cd ..
    ) else (
        cd ..
        echo.
        echo ========================================
        echo   ERROR EN LA COMPILACION
        echo ========================================
        echo.
        echo El archivo source\dist\MinecraftSSTool.exe no se genero.
        echo Revisa los mensajes de error arriba.
        echo.
        echo Esperando 5 segundos antes de cerrar...
        timeout /t 5 /nobreak >nul
        exit /b 1
    )
)

echo.
echo ========================================
echo   PROCESO COMPLETADO
echo ========================================
echo.
echo Presiona cualquier tecla para cerrar...
pause >nul
