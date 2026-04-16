from cx_Freeze import setup, Executable
import sys
import os

# Incluir archivos de datos
include_files = []
if os.path.exists('config.json'):
    include_files.append('config.json')

# Opciones de build
build_exe_options = {
    "packages": [
        "tkinter", "requests", "psutil", "flask", "flask_cors",
        "json", "hashlib", "secrets", "datetime", "threading", 
        "time", "colorama", "sqlite3", "subprocess", "os", "sys",
        "traceback", "concurrent.futures", "ctypes", "webbrowser",
        "base64", "io", "socket", "winreg", "re", "collections"
    ],
    "includes": [
        "db_integration", "ai_analyzer", "astro_ss_techniques", 
        "silent_scanner_techniques", "ui_style"
    ],
    "excludes": ["matplotlib", "numpy", "scipy", "pandas", "PIL", "Pillow"],
    "include_files": include_files,
    "optimize": 2
}

# Configuración del ejecutable
exe = Executable(
    script="main.py",
    base=None,  # None = console, "Win32GUI" = sin consola
    target_name="MinecraftSSTool.exe",
    icon=None
)

setup(
    name="MinecraftSSTool",
    version="1.0",
    description="Aspers Projects - Security Scanner",
    options={"build_exe": build_exe_options},
    executables=[exe]
)

