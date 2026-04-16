"""
Script para crear el usuario administrador de la empresa 'arefy'
Ejecutar: python create_arefy_admin.py
"""
import sqlite3
import hashlib
import json
import os
import sys

# Agregar el directorio actual al path para importar auth
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Usar la misma base de datos que auth.py
try:
    from auth import DATABASE
except:
    DATABASE = 'auth.db'

def create_arefy_admin():
    """Crea el usuario administrador para la empresa arefy"""
    # Primero inicializar la base de datos
    try:
        from auth import init_auth_db
        print("🔧 Inicializando base de datos...")
        init_auth_db()
        print("✅ Base de datos inicializada\n")
    except Exception as e:
        print(f"⚠️ Error al inicializar BD (puede que ya exista): {str(e)}\n")
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    try:
        # Buscar la empresa arefy
        cursor.execute('SELECT id FROM companies WHERE name = ?', ('arefy',))
        company = cursor.fetchone()
        
        if not company:
            print("❌ Empresa 'arefy' no encontrada. Creándola...")
            cursor.execute('''
                INSERT INTO companies (name, subscription_type, subscription_status, subscription_price, max_users, max_admins, notes)
                VALUES (?, 'enterprise', 'active', 13.0, 8, 3, 'Empresa default')
            ''', ('arefy',))
            company_id = cursor.lastrowid
            conn.commit()
            print(f"✅ Empresa 'arefy' creada con ID: {company_id}")
        else:
            company_id = company[0]
            print(f"✅ Empresa 'arefy' encontrada con ID: {company_id}")
        
        # Verificar si el usuario admin ya existe
        cursor.execute('SELECT id FROM users WHERE username = ?', ('arefy_admin',))
        existing_user = cursor.fetchone()
        
        if existing_user:
            print("⚠️ Usuario 'arefy_admin' ya existe. Actualizando contraseña...")
            user_id = existing_user[0]
            
            # Contraseña: arefy2024!
            password_hash = hashlib.sha256('arefy2024!'.encode()).hexdigest()
            
            cursor.execute('''
                UPDATE users 
                SET password_hash = ?, 
                    roles = ?,
                    company_id = ?,
                    is_active = 1
                WHERE id = ?
            ''', (password_hash, json.dumps(['empresa', 'administrador']), company_id, user_id))
            
            conn.commit()
            print("✅ Usuario 'arefy_admin' actualizado")
        else:
            # Crear nuevo usuario admin
            password_hash = hashlib.sha256('arefy2024!'.encode()).hexdigest()
            
            cursor.execute('''
                INSERT INTO users (username, password_hash, email, roles, company_id, is_active, created_by)
                VALUES (?, ?, ?, ?, ?, 1, 'system')
            ''', (
                'arefy_admin',
                password_hash,
                'admin@arefy.com',
                json.dumps(['empresa', 'administrador']),
                company_id
            ))
            
            conn.commit()
            print("✅ Usuario 'arefy_admin' creado")
        
        print("\n" + "="*60)
        print("📋 CREDENCIALES DE ACCESO PARA EMPRESA AREFY")
        print("="*60)
        print("Usuario: arefy_admin")
        print("Contraseña: arefy2024!")
        print("Empresa: arefy")
        print("Roles: empresa, administrador")
        print("="*60)
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        conn.close()
        return False

if __name__ == '__main__':
    print("🚀 Creando usuario administrador para empresa 'arefy'...\n")
    create_arefy_admin()

