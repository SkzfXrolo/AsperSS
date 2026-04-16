"""
Script de verificación rápida para la aplicación
Ejecuta este script para verificar que todo esté correcto antes de desplegar
"""
import sys
import os

print("🔍 Verificando aplicación...\n")

# Verificar imports
print("1. Verificando imports...")
try:
    from flask import Flask
    print("   ✅ Flask importado correctamente")
except ImportError as e:
    print(f"   ❌ Error importando Flask: {e}")
    sys.exit(1)

try:
    from auth import init_auth_db
    print("   ✅ auth importado correctamente")
except ImportError as e:
    print(f"   ❌ Error importando auth: {e}")
    sys.exit(1)

# Verificar que app.py se puede importar
print("\n2. Verificando app.py...")
try:
    import app
    print("   ✅ app.py se puede importar correctamente")
except Exception as e:
    print(f"   ❌ Error importando app.py: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Verificar base de datos
print("\n3. Verificando base de datos...")
try:
    init_auth_db()
    print("   ✅ Base de datos inicializada correctamente")
except Exception as e:
    print(f"   ⚠️  Advertencia al inicializar base de datos: {e}")
    print("   (Esto puede ser normal si la BD ya existe)")

# Verificar archivos necesarios
print("\n4. Verificando archivos necesarios...")
archivos_necesarios = [
    'app.py',
    'auth.py',
    'Procfile',
    'requirements.txt',
    'gunicorn_config.py'
]

for archivo in archivos_necesarios:
    if os.path.exists(archivo):
        print(f"   ✅ {archivo} existe")
    else:
        print(f"   ❌ {archivo} NO existe")

print("\n✅ Verificación completada!")
print("\nSi todos los checks pasaron, la aplicación debería funcionar correctamente.")

