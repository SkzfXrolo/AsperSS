"""
Script de uso único: promueve un usuario a admin directamente en la BD.
Uso: python fix_user_role.py <username> <nuevo_rol>
Roles válidos: helper, moderador, admin, owner

Ejemplo: python fix_user_role.py arefy_admin admin
"""
import os, sys, json

TARGET_USERNAME = sys.argv[1] if len(sys.argv) > 1 else 'arefy_admin'
NEW_ROLE        = sys.argv[2] if len(sys.argv) > 2 else 'admin'

VALID_ROLES = ['helper', 'moderador', 'admin', 'owner']
if NEW_ROLE not in VALID_ROLES:
    print(f"❌ Rol inválido '{NEW_ROLE}'. Válidos: {VALID_ROLES}")
    sys.exit(1)

# ── Conexión a la BD (PostgreSQL en Render, SQLite en local) ────────────────
DATABASE_URL = os.environ.get('DATABASE_URL', '').strip()

if DATABASE_URL:
    import psycopg2
    conn = psycopg2.connect(DATABASE_URL)
    ph   = '%s'
    print(f"✅ Conectado a PostgreSQL")
else:
    import sqlite3
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scanner_db.sqlite')
    conn = sqlite3.connect(db_path)
    ph   = '?'
    print(f"✅ Conectado a SQLite: {db_path}")

cur = conn.cursor()

# ── Leer usuario ────────────────────────────────────────────────────────────
cur.execute(f'SELECT id, username, roles FROM users WHERE username = {ph}', (TARGET_USERNAME,))
row = cur.fetchone()

if not row:
    print(f"❌ Usuario '{TARGET_USERNAME}' no encontrado en la BD")
    conn.close()
    sys.exit(1)

user_id, username, roles_raw = row
try:
    roles = json.loads(roles_raw) if roles_raw else []
except (TypeError, ValueError):
    roles = [roles_raw] if roles_raw else []

print(f"📋 Usuario encontrado: id={user_id}, username={username}")
print(f"   Roles actuales: {roles}")

# ── Calcular nuevos roles ───────────────────────────────────────────────────
# Quitar cualquier otro rol de staff de la jerarquía y poner el nuevo
new_roles = [r for r in roles if r not in ['helper', 'moderador', 'admin', 'owner']]
new_roles.append(NEW_ROLE)
# Asegurarse de que tenga 'admin' en roles si el nuevo rol es admin/owner
# para que is_admin() también lo reconozca
if NEW_ROLE in ('admin', 'owner') and 'admin' not in new_roles:
    new_roles.append('admin')

print(f"   Nuevos roles:    {new_roles}")

# ── Actualizar ──────────────────────────────────────────────────────────────
cur.execute(
    f'UPDATE users SET roles = {ph} WHERE id = {ph}',
    (json.dumps(new_roles), user_id)
)
conn.commit()
print(f"✅ Roles actualizados correctamente para '{username}'")
conn.close()
