"""
Script de prueba para verificar el login de arefy_admin
"""
from auth import authenticate_user, DATABASE
import sqlite3
import os

print("="*60)
print("PRUEBA DE LOGIN - arefy_admin")
print("="*60)
print(f"Base de datos: {DATABASE}")
print(f"Base de datos existe: {os.path.exists(DATABASE)}")
print()

# Verificar usuario en BD
conn = sqlite3.connect(DATABASE)
cursor = conn.cursor()
cursor.execute('SELECT id, username, email, is_active, company_id FROM users WHERE username = ?', ('arefy_admin',))
user = cursor.fetchone()
if user:
    print(f"✅ Usuario encontrado en BD:")
    print(f"   ID: {user[0]}")
    print(f"   Username: {user[1]}")
    print(f"   Email: {user[2]}")
    print(f"   Activo: {user[3]}")
    print(f"   Empresa ID: {user[4]}")
else:
    print("❌ Usuario NO encontrado en BD")
    
    # Listar todos los usuarios
    cursor.execute('SELECT username FROM users')
    all_users = cursor.fetchall()
    print(f"\nUsuarios disponibles: {[u[0] for u in all_users]}")
conn.close()

print()
print("="*60)
print("PRUEBA DE AUTENTICACIÓN")
print("="*60)

# Probar autenticación
test_cases = [
    ('arefy_admin', 'arefy2024!'),
    ('arefy_admin ', 'arefy2024!'),  # Con espacio
    (' arefy_admin', 'arefy2024!'),  # Con espacio al inicio
    ('AREFY_ADMIN', 'arefy2024!'),  # Mayúsculas
]

for username, password in test_cases:
    print(f"\nProbando: '{username}' / '{password}'")
    result = authenticate_user(username, password)
    if result['success']:
        print(f"✅ ÉXITO - Usuario: {result['user']['username']}")
        print(f"   Roles: {result['user']['roles']}")
        print(f"   Empresa ID: {result['user'].get('company_id')}")
    else:
        print(f"❌ FALLO - Error: {result['error']}")

print()
print("="*60)

