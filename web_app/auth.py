"""
Sistema de Autenticación para la Aplicación Web
Maneja usuarios, sesiones y tokens de registro
Migrado a MySQL para persistencia en Render
"""
import hashlib
import secrets
import datetime
import json
from functools import wraps
from flask import session, redirect, url_for, request, jsonify

import os
import sys

# Intentar usar MySQL/PostgreSQL primero, fallback a SQLite
USE_MYSQL = False
USE_POSTGRESQL = False

# Siempre importar sqlite3 como fallback
import sqlite3
DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scanner_db.sqlite')

try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    # Verificar si está usando PostgreSQL o MySQL ANTES de importar
    _db_url = os.environ.get('DATABASE_URL', '').strip()
    _pg_host = os.environ.get('POSTGRES_HOST', '').strip()
    _mysql_host = os.environ.get('MYSQL_HOST', '').strip()
    print(f"🔍 BD detection — DATABASE_URL={'sí ('+_db_url[:30]+'...)' if _db_url else 'NO'}, POSTGRES_HOST={'sí' if _pg_host else 'NO'}, MYSQL_HOST={'sí' if _mysql_host else 'NO'}")
    USE_POSTGRESQL = bool(_db_url or _pg_host)
    USE_MYSQL = bool(_mysql_host and not USE_POSTGRESQL)

    if USE_POSTGRESQL or USE_MYSQL:
        try:
            from db_mysql import (
                get_db_connection,
                get_db_cursor,
                init_mysql_db
            )
            if USE_POSTGRESQL:
                print("✅ Usando PostgreSQL para autenticación")
            elif USE_MYSQL:
                print("✅ Usando MySQL para autenticación")
        except ImportError as e:
            print(f"⚠️ Error importando db_mysql: {e}")
            print("⚠️ Usando SQLite como fallback")
            USE_POSTGRESQL = False
            USE_MYSQL = False
    else:
        print("⚠️ No hay BD configurada, usando SQLite como fallback")
        print("⚠️ Variables de entorno disponibles con 'DB' o 'PG':", [k for k in os.environ if 'DB' in k or 'PG' in k or 'SQL' in k])
        USE_POSTGRESQL = False
        USE_MYSQL = False
except Exception as e:
    print(f"⚠️ Error configurando BD: {e}")
    print("⚠️ Usando SQLite como fallback")
    USE_POSTGRESQL = False
    USE_MYSQL = False

def init_auth_db():
    """Inicializa las tablas de autenticación en la base de datos"""
    # Si está usando MySQL/PostgreSQL, usar ese módulo
    if USE_MYSQL or USE_POSTGRESQL:
        try:
            init_mysql_db()
            print("✅ Base de datos MySQL/PostgreSQL inicializada para autenticación")
            
            # Crear empresa default "arefy" si no existe (solo en PostgreSQL/MySQL)
            try:
                with get_db_cursor() as cursor:
                    cursor.execute('SELECT COUNT(*) as count FROM companies WHERE name = %s', ('arefy',))
                    result = cursor.fetchone()
                    # PostgreSQL (RealDictCursor) y MySQL (DictCursor) devuelven diccionarios
                    count = result['count'] if result else 0
                    if count == 0:
                        cursor.execute('''
                            INSERT INTO companies (name, subscription_type, subscription_status, subscription_price, max_users, max_admins, created_by, notes)
                            VALUES (%s, 'enterprise', 'active', 13.0, 8, 3, NULL, 'Empresa default creada automáticamente')
                        ''', ('arefy',))
                        print("✅ Empresa default 'arefy' creada en PostgreSQL/MySQL")
            except Exception as e:
                print(f"⚠️ Error creando empresa default: {e}")
                import traceback
                traceback.print_exc()
            
            return
        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)
            print(f"❌ Error inicializando MySQL/PostgreSQL: {error_type}: {error_msg}")
            print("❌ NO se usará SQLite como fallback para evitar pérdida de datos en deploys")
            print("❌ Verifica la configuración de DATABASE_URL")
            import traceback
            print("📋 Traceback completo:")
            traceback.print_exc()
            raise  # NO hacer fallback a SQLite, lanzar el error
    
    # Fallback a SQLite SOLO si NO hay PostgreSQL/MySQL configurado
    # (solo para desarrollo local)
    if not USE_MYSQL and not USE_POSTGRESQL:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
    
    # Tabla de empresas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            contact_email TEXT,
            contact_phone TEXT,
            subscription_type TEXT DEFAULT 'enterprise',  -- 'individual' o 'enterprise'
            subscription_status TEXT DEFAULT 'active',
            subscription_start_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            subscription_end_date TIMESTAMP,
            subscription_price REAL DEFAULT 13.0,  -- Precio en USD
            max_users INTEGER DEFAULT 8,
            max_admins INTEGER DEFAULT 3,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by INTEGER,
            is_active BOOLEAN DEFAULT 1,
            notes TEXT,
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    ''')
    
    # Migración: Agregar columnas nuevas si no existen
    try:
        cursor.execute('ALTER TABLE companies ADD COLUMN subscription_type TEXT DEFAULT \'enterprise\'')
    except sqlite3.OperationalError:
        pass
    
    try:
        cursor.execute('ALTER TABLE companies ADD COLUMN subscription_price REAL DEFAULT 13.0')
    except sqlite3.OperationalError:
        pass
    
    # Crear empresa default "arefy" si no existe
    cursor.execute('SELECT COUNT(*) FROM companies WHERE name = ?', ('arefy',))
    if cursor.fetchone()[0] == 0:
        cursor.execute('''
            INSERT INTO companies (name, subscription_type, subscription_status, subscription_price, max_users, max_admins, created_by, notes)
            VALUES (?, 'enterprise', 'active', 13.0, 8, 3, NULL, 'Empresa default creada automáticamente')
        ''', ('arefy',))
        print("✅ Empresa default 'arefy' creada")
    
    # Tabla de usuarios (modificada para soportar empresas y múltiples roles)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE,
            password_hash TEXT NOT NULL,
            roles TEXT DEFAULT '["user"]',  -- JSON array de roles: ["empresa", "staff"] o ["empresa", "administrador"]
            company_id INTEGER,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP,
            created_by TEXT,
            FOREIGN KEY (company_id) REFERENCES companies(id)
        )
    ''')
    
    # Migración: Agregar columnas nuevas si no existen (para bases de datos existentes)
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN roles TEXT DEFAULT \'["user"]\'')
    except sqlite3.OperationalError:
        pass  # La columna ya existe
    
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN company_id INTEGER')
    except sqlite3.OperationalError:
        pass  # La columna ya existe
    
    # Migración: Si la columna 'role' existe pero 'roles' no, migrar datos
    try:
        cursor.execute('SELECT role FROM users LIMIT 1')
        # Si existe 'role', migrar a 'roles'
        cursor.execute('UPDATE users SET roles = json_array(role) WHERE roles IS NULL OR roles = \'["user"]\' AND role IS NOT NULL')
    except sqlite3.OperationalError:
        pass  # La columna 'role' no existe, todo bien
    
    # Tabla de enlaces de descarga temporales (similar a Ocean)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS download_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT UNIQUE NOT NULL,
            filename TEXT NOT NULL,
            created_by INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            max_downloads INTEGER DEFAULT 1,
            download_count INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT 1,
            description TEXT,
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    ''')
    
    # Índice para búsquedas rápidas por token
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_download_links_token ON download_links(token)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_download_links_active ON download_links(is_active, expires_at)')
    
    # Índices para mejor rendimiento (solo después de asegurar que las columnas existen)
    try:
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_company ON users(company_id)')
    except sqlite3.OperationalError:
        pass  # Puede fallar si la columna no existe aún
    
    try:
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)')
    except sqlite3.OperationalError:
        pass
    
    # Tabla de tokens de registro (modificada para vincularse a empresas)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS registration_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT UNIQUE NOT NULL,
            company_id INTEGER,
            created_by INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            used_at TIMESTAMP,
            is_used BOOLEAN DEFAULT 0,
            used_by INTEGER,
            max_uses INTEGER DEFAULT 1,
            description TEXT,
            is_admin_token BOOLEAN DEFAULT 0,  -- Si es True, crea un admin de empresa
            FOREIGN KEY (company_id) REFERENCES companies(id),
            FOREIGN KEY (created_by) REFERENCES users(id),
            FOREIGN KEY (used_by) REFERENCES users(id)
        )
    ''')
    
    # Migración: Agregar columnas nuevas si no existen
    try:
        cursor.execute('ALTER TABLE registration_tokens ADD COLUMN company_id INTEGER')
    except sqlite3.OperationalError:
        pass
    
    try:
        cursor.execute('ALTER TABLE registration_tokens ADD COLUMN is_admin_token BOOLEAN DEFAULT 0')
    except sqlite3.OperationalError:
        pass
    
    # Migración: Cambiar created_by de TEXT a INTEGER si es necesario
    try:
        # Verificar si created_by es TEXT
        cursor.execute('PRAGMA table_info(registration_tokens)')
        columns = cursor.fetchall()
        created_by_type = None
        for col in columns:
            if col[1] == 'created_by':
                created_by_type = col[2]
                break
        
        # Si es TEXT, necesitamos migrar (esto es complejo, mejor dejarlo como está por ahora)
        # Solo creamos los índices si las columnas existen
    except:
        pass
    
    # Índices para mejor rendimiento
    try:
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_tokens_company ON registration_tokens(company_id)')
    except sqlite3.OperationalError:
        pass
    
    try:
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_tokens_token ON registration_tokens(token)')
    except sqlite3.OperationalError:
        pass
    
    # Crear usuario administrador por defecto si no existe
    try:
        # Verificar si existe algún admin (compatibilidad con esquema antiguo y nuevo)
        # Primero verificar qué columnas existen
        cursor.execute("PRAGMA table_info(users)")
        columns = [col[1] for col in cursor.fetchall()]
        has_role_column = 'role' in columns
        has_roles_column = 'roles' in columns
        
        if has_roles_column:
            # Usar esquema nuevo con roles
            cursor.execute('SELECT COUNT(*) FROM users WHERE roles LIKE "%admin%"')
        elif has_role_column:
            # Usar esquema antiguo con role
            cursor.execute('SELECT COUNT(*) FROM users WHERE role = "admin"')
        else:
            # No hay ninguna columna, crear admin con roles
            cursor.execute('SELECT COUNT(*) FROM users')
        
        admin_count = cursor.fetchone()[0]
        
        if admin_count == 0:
            # Crear admin por defecto: admin / admin123 (cambiar en producción!)
            default_password_hash = hash_password('admin123')
            # Intentar con el esquema nuevo primero (roles)
            if has_roles_column:
                try:
                    cursor.execute('''
                        INSERT INTO users (username, password_hash, roles, created_by)
                        VALUES (?, ?, ?, ?)
                    ''', ('admin', default_password_hash, '["admin"]', 'system'))
                    print("✅ Usuario administrador creado: admin / admin123")
                except sqlite3.OperationalError as e:
                    print(f"⚠️ Error creando admin con roles: {e}")
            elif has_role_column:
                # Intentar con esquema antiguo (role)
                try:
                    cursor.execute('''
                        INSERT INTO users (username, password_hash, role, created_by)
                        VALUES (?, ?, ?, ?)
                    ''', ('admin', default_password_hash, 'admin', 'system'))
                    print("✅ Usuario administrador creado: admin / admin123")
                except sqlite3.OperationalError as e:
                    print(f"⚠️ Error creando admin con role: {e}")
            print("⚠️ IMPORTANTE: Cambia la contraseña del admin en producción!")
    except Exception as e:
        print(f"⚠️ Error verificando/creando admin: {e}")
        import traceback
        traceback.print_exc()
    
    conn.commit()
    conn.close()

    # Inicializar también las tablas del scanner en la misma BD
    _init_scanner_tables_sqlite()
    print("✅ Base de datos de autenticación inicializada correctamente")

def _init_scanner_tables_sqlite():
    """Crea las tablas del scanner (scan_tokens, scans, etc.) en la misma BD SQLite que auth"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('PRAGMA journal_mode=WAL')

    cursor.execute('''CREATE TABLE IF NOT EXISTS scan_tokens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        token TEXT UNIQUE NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        expires_at TIMESTAMP,
        used_count INTEGER DEFAULT 0,
        max_uses INTEGER DEFAULT -1,
        is_active BOOLEAN DEFAULT 1,
        created_by TEXT,
        description TEXT
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS scans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        token_id INTEGER,
        scan_token TEXT,
        started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        completed_at TIMESTAMP,
        status TEXT DEFAULT 'running',
        total_files_scanned INTEGER DEFAULT 0,
        issues_found INTEGER DEFAULT 0,
        scan_duration REAL,
        machine_id TEXT,
        machine_name TEXT,
        ip_address TEXT,
        country TEXT,
        minecraft_username TEXT,
        FOREIGN KEY (token_id) REFERENCES scan_tokens(id)
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS scan_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        scan_id INTEGER,
        issue_type TEXT,
        issue_name TEXT,
        issue_path TEXT,
        issue_category TEXT,
        alert_level TEXT,
        confidence REAL,
        detected_patterns TEXT,
        obfuscation_detected BOOLEAN,
        file_hash TEXT,
        ai_analysis TEXT,
        ai_confidence REAL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (scan_id) REFERENCES scans(id)
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS ban_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        machine_id TEXT,
        minecraft_username TEXT,
        ip_address TEXT,
        ban_reason TEXT,
        hack_type TEXT,
        banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        scan_id INTEGER,
        FOREIGN KEY (scan_id) REFERENCES scans(id)
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS staff_feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        result_id INTEGER NOT NULL,
        scan_id INTEGER,
        staff_verification TEXT NOT NULL,
        staff_notes TEXT,
        verified_by TEXT,
        verified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        file_hash TEXT,
        issue_name TEXT,
        issue_path TEXT,
        extracted_patterns TEXT,
        extracted_features TEXT,
        FOREIGN KEY (result_id) REFERENCES scan_results(id),
        FOREIGN KEY (scan_id) REFERENCES scans(id)
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS learned_patterns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pattern_type TEXT NOT NULL,
        pattern_value TEXT NOT NULL,
        pattern_category TEXT,
        confidence REAL DEFAULT 1.0,
        source_feedback_id INTEGER,
        learned_from_count INTEGER DEFAULT 1,
        first_learned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_active BOOLEAN DEFAULT 1,
        FOREIGN KEY (source_feedback_id) REFERENCES staff_feedback(id)
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS learned_hashes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_hash TEXT UNIQUE NOT NULL,
        is_hack BOOLEAN NOT NULL,
        confirmed_count INTEGER DEFAULT 1,
        first_confirmed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_confirmed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        source_feedback_id INTEGER,
        FOREIGN KEY (source_feedback_id) REFERENCES staff_feedback(id)
    )''')

    # Índices
    for idx_sql in [
        'CREATE INDEX IF NOT EXISTS idx_scan_tokens_active ON scan_tokens(is_active, expires_at)',
        'CREATE INDEX IF NOT EXISTS idx_scans_started ON scans(started_at DESC)',
        'CREATE INDEX IF NOT EXISTS idx_scans_token ON scans(scan_token)',
        'CREATE INDEX IF NOT EXISTS idx_results_scan ON scan_results(scan_id)',
        'CREATE INDEX IF NOT EXISTS idx_results_level ON scan_results(alert_level)',
    ]:
        try:
            cursor.execute(idx_sql)
        except sqlite3.OperationalError:
            pass

    conn.commit()
    conn.close()
    print("✅ Tablas del scanner inicializadas en BD local")

def hash_password(password):
    """Genera hash PBKDF2-SHA256 con salt aleatorio (resistente a rainbow tables)"""
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 260000)
    return f"pbkdf2:sha256:260000:{salt}:{dk.hex()}"

def verify_password(password, password_hash):
    """Verifica contraseña — compatible con hashes SHA256 antiguos y PBKDF2 nuevos"""
    if not password_hash:
        return False
    if password_hash.startswith('pbkdf2:'):
        parts = password_hash.split(':')
        if len(parts) == 5:
            _, algo, iterations, salt, stored = parts
            dk = hashlib.pbkdf2_hmac(algo, password.encode('utf-8'), salt.encode('utf-8'), int(iterations))
            return secrets.compare_digest(dk.hex(), stored)
    # Fallback para hashes SHA256 sin salt (datos existentes)
    return secrets.compare_digest(
        hashlib.sha256(password.encode()).hexdigest(),
        password_hash
    )

def create_user(username, password, email=None, roles=None, company_id=None, created_by=None):
    """Crea un nuevo usuario con soporte para múltiples roles y empresas (PostgreSQL/MySQL/SQLite)"""
    import json

    print(f"\n{'='*60}")
    print(f"👤 ===== CREANDO USUARIO ======")
    print(f"👤 Username: {username}")
    print(f"👤 Email: {email}")
    print(f"👤 Roles: {roles}")
    print(f"👤 Company ID: {company_id}")
    print(f"👤 Created by: {created_by}")
    print(f"{'='*60}\n")

    # Normalizar roles
    if roles is None:
        roles = ['user']
    elif isinstance(roles, str):
        try:
            roles = json.loads(roles)
        except Exception:
            roles = [roles]
    elif not isinstance(roles, list):
        roles = [roles]

    roles_json = json.dumps(roles)
    password_hash = hash_password(password)

    try:
        if USE_POSTGRESQL or USE_MYSQL:
            # --- Ruta PostgreSQL / MySQL ---
            with get_db_cursor() as cursor:
                # Validar límites de empresa
                if company_id:
                    cursor.execute(
                        'SELECT COUNT(*) as cnt FROM users WHERE company_id = %s AND is_active = 1',
                        (company_id,)
                    )
                    current_users = cursor.fetchone()['cnt']
                    cursor.execute('SELECT max_users, max_admins FROM companies WHERE id = %s', (company_id,))
                    company_data = cursor.fetchone()
                    if company_data:
                        if current_users >= company_data['max_users']:
                            return {'success': False, 'error': f'La empresa ha alcanzado el límite de {company_data["max_users"]} usuarios'}
                        if 'administrador' in roles:
                            cursor.execute(
                                "SELECT COUNT(*) as cnt FROM users WHERE company_id = %s AND is_active = 1 AND roles LIKE %s",
                                (company_id, '%administrador%')
                            )
                            current_admins = cursor.fetchone()['cnt']
                            if current_admins >= company_data['max_admins']:
                                return {'success': False, 'error': f'La empresa ha alcanzado el límite de {company_data["max_admins"]} administradores'}

                cursor.execute('''
                    INSERT INTO users (username, email, password_hash, roles, company_id, created_by)
                    VALUES (%s, %s, %s, %s, %s, %s)
                ''', (username, email, password_hash, roles_json, company_id, created_by))

                # PostgreSQL RETURNING o lastrowid según el driver
                try:
                    user_id = cursor.fetchone()['id'] if cursor.rowcount else None
                except Exception:
                    pass
                user_id = getattr(cursor, 'lastrowid', None)

            print(f"✅ ===== USUARIO CREADO EN PostgreSQL/MySQL ======\n")
            return {'success': True, 'user_id': user_id}

        else:
            # --- Ruta SQLite (desarrollo local) ---
            conn = sqlite3.connect(DATABASE, timeout=10.0)
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('PRAGMA synchronous=NORMAL')
            conn.execute('PRAGMA busy_timeout=5000')
            cursor = conn.cursor()

            if company_id:
                cursor.execute('SELECT COUNT(*) FROM users WHERE company_id = ? AND is_active = 1', (company_id,))
                current_users = cursor.fetchone()[0]
                cursor.execute('SELECT max_users, max_admins FROM companies WHERE id = ?', (company_id,))
                company_data = cursor.fetchone()
                if company_data:
                    max_users, max_admins = company_data
                    if current_users >= max_users:
                        conn.close()
                        return {'success': False, 'error': f'La empresa ha alcanzado el límite de {max_users} usuarios'}
                    if 'administrador' in roles:
                        cursor.execute(
                            'SELECT COUNT(*) FROM users WHERE company_id = ? AND is_active = 1 AND roles LIKE "%administrador%"',
                            (company_id,)
                        )
                        if cursor.fetchone()[0] >= max_admins:
                            conn.close()
                            return {'success': False, 'error': f'La empresa ha alcanzado el límite de {max_admins} administradores'}

            cursor.execute('''
                INSERT INTO users (username, email, password_hash, roles, company_id, created_by)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (username, email, password_hash, roles_json, company_id, created_by))

            user_id = cursor.lastrowid
            conn.commit()

            # Verificar persistencia
            cursor.execute('SELECT id FROM users WHERE id = ?', (user_id,))
            if not cursor.fetchone():
                conn.close()
                return {'success': False, 'error': 'Error al guardar usuario en la base de datos'}

            conn.close()
            print(f"✅ ===== USUARIO CREADO EN SQLite ======\n")
            return {'success': True, 'user_id': user_id}

    except Exception as e:
        import traceback
        err_str = str(e).lower()
        if 'unique' in err_str or 'duplicate' in err_str or '1062' in err_str:
            print(f"❌ ERROR: Usuario o email ya existe: {e}")
            return {'success': False, 'error': 'Usuario o email ya existe'}
        print(f"❌ ERROR inesperado al crear usuario: {e}")
        print(traceback.format_exc())
        print(f"{'='*60}\n")
        return {'success': False, 'error': str(e)}

def authenticate_user(username, password):
    """Autentica un usuario con soporte para múltiples roles (PostgreSQL/MySQL/SQLite)"""
    import json

    username = (username or '').strip()
    if not username:
        return {'success': False, 'error': 'Usuario no puede estar vacío'}

    try:
        if USE_POSTGRESQL or USE_MYSQL:
            # --- Ruta PostgreSQL / MySQL ---
            with get_db_cursor() as cursor:
                cursor.execute('''
                    SELECT id, username, email, password_hash, roles, is_active, company_id
                    FROM users WHERE username = %s OR email = %s
                ''', (username, username))
                user = cursor.fetchone()

                if not user:
                    cursor.execute('''
                        SELECT id, username, email, password_hash, roles, is_active, company_id
                        FROM users
                        WHERE LOWER(username) = LOWER(%s) OR LOWER(email) = LOWER(%s)
                    ''', (username, username))
                    user = cursor.fetchone()

                if not user:
                    return {'success': False, 'error': 'Usuario no encontrado'}

                user_id      = user['id']
                db_username  = user['username']
                email        = user['email']
                password_hash = user['password_hash']
                roles_json   = user['roles']
                is_active    = user['is_active']
                company_id   = user['company_id']

                if not is_active:
                    return {'success': False, 'error': 'Usuario desactivado'}

                if not verify_password(password, password_hash):
                    return {'success': False, 'error': 'Contraseña incorrecta'}

                try:
                    roles = json.loads(roles_json) if roles_json else ['user']
                except Exception:
                    roles = [roles_json] if roles_json else ['user']

                cursor.execute(
                    'UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = %s', (user_id,)
                )

        else:
            # --- Ruta SQLite (desarrollo local) ---
            conn = sqlite3.connect(DATABASE)
            cursor = conn.cursor()

            cursor.execute('''
                SELECT id, username, email, password_hash, roles, is_active, company_id
                FROM users WHERE username = ? OR email = ?
            ''', (username, username))
            user = cursor.fetchone()

            if not user:
                cursor.execute('''
                    SELECT id, username, email, password_hash, roles, is_active, company_id
                    FROM users WHERE LOWER(username) = LOWER(?) OR LOWER(email) = LOWER(?)
                ''', (username, username))
                user = cursor.fetchone()

            if not user:
                conn.close()
                return {'success': False, 'error': 'Usuario no encontrado'}

            user_id, db_username, email, password_hash, roles_json, is_active, company_id = user

            if not is_active:
                conn.close()
                return {'success': False, 'error': 'Usuario desactivado'}

            if not verify_password(password, password_hash):
                conn.close()
                return {'success': False, 'error': 'Contraseña incorrecta'}

            try:
                roles = json.loads(roles_json) if roles_json else ['user']
            except Exception:
                roles = [roles_json] if roles_json else ['user']

            cursor.execute('UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?', (user_id,))
            conn.commit()
            conn.close()

        return {
            'success': True,
            'user': {
                'id': user_id,
                'username': db_username,
                'email': email,
                'roles': roles,
                'company_id': company_id
            }
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}

def create_registration_token(created_by, company_id=None, expires_hours=24, description=None, is_admin_token=False):
    """Crea un token de registro de un solo uso, opcionalmente vinculado a una empresa - OPTIMIZADO"""
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        # Si es token de empresa, validar límites en UNA SOLA consulta optimizada
        if company_id:
            # Consulta única que obtiene toda la información necesaria
            cursor.execute('''
                SELECT 
                    c.max_users,
                    c.max_admins,
                    (SELECT COUNT(*) FROM users WHERE company_id = ? AND is_active = 1) as current_users,
                    (SELECT COUNT(*) FROM users WHERE company_id = ? AND is_active = 1 AND roles LIKE "%administrador%") as current_admins
                FROM companies c
                WHERE c.id = ?
            ''', (company_id, company_id, company_id))
            
            company_data = cursor.fetchone()
            if company_data:
                max_users, max_admins, current_users, current_admins = company_data
                
                # Validar límite de usuarios
                if current_users >= max_users:
                    conn.close()
                    return {'success': False, 'error': f'La empresa ha alcanzado el límite de {max_users} usuarios'}
                
                # Si es token de admin, validar límite de admins
                if is_admin_token and current_admins >= max_admins:
                    conn.close()
                    return {'success': False, 'error': f'La empresa ha alcanzado el límite de {max_admins} administradores'}
        
        # Generar token y crear registro en una sola operación
        token = secrets.token_urlsafe(32)
        expires_at = datetime.datetime.now() + datetime.timedelta(hours=expires_hours)
        
        cursor.execute('''
            INSERT INTO registration_tokens 
            (token, company_id, created_by, expires_at, description, is_admin_token)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (token, company_id, created_by, expires_at, description, is_admin_token))
        
        token_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return {'success': True, 'token': token, 'token_id': token_id, 'expires_at': expires_at}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def verify_registration_token(token):
    """Verifica y marca como usado un token de registro, retorna información de empresa y tipo"""
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, company_id, created_by, expires_at, is_used, used_at, is_admin_token
            FROM registration_tokens
            WHERE token = ?
        ''', (token,))
        
        token_data = cursor.fetchone()
        
        if not token_data:
            conn.close()
            return {'success': False, 'error': 'Token inválido'}
        
        token_id, company_id, created_by, expires_at_str, is_used, used_at, is_admin_token = token_data
        
        # Convertir is_admin_token a booleano correctamente
        if isinstance(is_admin_token, int):
            is_admin_token_bool = bool(is_admin_token)
        elif isinstance(is_admin_token, str):
            is_admin_token_bool = is_admin_token.lower() in ('true', '1', 'yes')
        else:
            is_admin_token_bool = bool(is_admin_token)
        
        if is_used:
            conn.close()
            return {'success': False, 'error': 'Token ya utilizado'}
        
        # Verificar expiración
        if expires_at_str:
            expires_at = datetime.datetime.fromisoformat(expires_at_str)
            if datetime.datetime.now() > expires_at:
                conn.close()
                return {'success': False, 'error': 'Token expirado'}
        
        # Marcar como usado
        cursor.execute('''
            UPDATE registration_tokens
            SET is_used = 1, used_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (token_id,))
        
        conn.commit()
        conn.close()
        
        return {
            'success': True,
            'created_by': created_by,
            'company_id': company_id,
            'is_admin_token': is_admin_token_bool
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}

def get_user_by_id(user_id):
    """Obtiene un usuario por ID con soporte para múltiples roles"""
    import json
    
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, username, email, roles, is_active, created_at, last_login, company_id
            FROM users
            WHERE id = ?
        ''', (user_id,))
        
        user = cursor.fetchone()
        conn.close()
        
        if user:
            # Parsear roles JSON
            try:
                roles = json.loads(user[3]) if user[3] else ['user']
            except:
                roles = [user[3]] if user[3] else ['user']
            
            return {
                'id': user[0],
                'username': user[1],
                'email': user[2],
                'roles': roles,
                'is_active': bool(user[4]),
                'created_at': user[5],
                'last_login': user[6],
                'company_id': user[7]
            }
        return None
    except Exception as e:
        return None

def has_role(user, role):
    """Verifica si un usuario tiene un rol específico"""
    if isinstance(user, dict):
        roles = user.get('roles', [])
    elif isinstance(user, list):
        roles = user
    else:
        return False
    
    return role in roles

def is_admin(user):
    """Verifica si un usuario es administrador (admin o administrador)"""
    if isinstance(user, dict):
        roles = user.get('roles', [])
    elif isinstance(user, list):
        roles = user
    else:
        return False
    
    return 'admin' in roles or 'administrador' in roles

def is_company_admin(user):
    """Verifica si un usuario es administrador de empresa"""
    if isinstance(user, dict):
        roles = user.get('roles', [])
    else:
        return False
    
    return 'empresa' in roles and 'administrador' in roles

def is_company_user(user):
    """Verifica si un usuario pertenece a una empresa"""
    if isinstance(user, dict):
        return user.get('company_id') is not None
    return False

def list_registration_tokens(include_used=False, company_id=None):
    """Lista tokens de registro, opcionalmente filtrados por empresa"""
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        if company_id:
            if include_used:
                cursor.execute('''
                    SELECT id, token, company_id, created_by, created_at, expires_at, 
                           is_used, used_at, used_by, description, is_admin_token
                    FROM registration_tokens
                    WHERE company_id = ?
                    ORDER BY created_at DESC
                ''', (company_id,))
            else:
                cursor.execute('''
                    SELECT id, token, company_id, created_by, created_at, expires_at, 
                           is_used, used_at, used_by, description, is_admin_token
                    FROM registration_tokens
                    WHERE is_used = 0 AND company_id = ?
                    ORDER BY created_at DESC
                ''', (company_id,))
        else:
            if include_used:
                cursor.execute('''
                    SELECT id, token, company_id, created_by, created_at, expires_at, 
                           is_used, used_at, used_by, description, is_admin_token
                    FROM registration_tokens
                    ORDER BY created_at DESC
                ''')
            else:
                cursor.execute('''
                    SELECT id, token, company_id, created_by, created_at, expires_at, 
                           is_used, used_at, used_by, description, is_admin_token
                    FROM registration_tokens
                    WHERE is_used = 0
                    ORDER BY created_at DESC
                ''')
        
        tokens = []
        for row in cursor.fetchall():
            tokens.append({
                'id': row[0],
                'token': row[1],
                'company_id': row[2],
                'created_by': row[3],
                'created_at': row[4],
                'expires_at': row[5],
                'is_used': bool(row[6]),
                'used_at': row[7],
                'used_by': row[8],
                'description': row[9],
                'is_admin_token': bool(row[10])
            })
        
        conn.close()
        return tokens
    except Exception as e:
        return []

def list_users(company_id=None):
    """Lista todos los usuarios, opcionalmente filtrados por empresa (PostgreSQL/MySQL/SQLite)"""
    import json

    try:
        if USE_POSTGRESQL or USE_MYSQL:
            with get_db_cursor() as cursor:
                if company_id:
                    cursor.execute('''
                        SELECT id, username, email, roles, is_active, created_at, last_login, company_id
                        FROM users WHERE company_id = %s ORDER BY created_at DESC
                    ''', (company_id,))
                else:
                    cursor.execute('''
                        SELECT id, username, email, roles, is_active, created_at, last_login, company_id
                        FROM users ORDER BY created_at DESC
                    ''')
                rows = cursor.fetchall()

            users = []
            for row in rows:
                try:
                    roles = json.loads(row['roles']) if row['roles'] else ['user']
                except Exception:
                    roles = [row['roles']] if row['roles'] else ['user']
                users.append({
                    'id': row['id'],
                    'username': row['username'],
                    'email': row['email'],
                    'roles': roles,
                    'is_active': bool(row['is_active']),
                    'created_at': str(row['created_at']),
                    'last_login': str(row['last_login']) if row['last_login'] else None,
                    'company_id': row['company_id']
                })
            return users

        else:
            conn = sqlite3.connect(DATABASE)
            cursor = conn.cursor()
            if company_id:
                cursor.execute('''
                    SELECT id, username, email, roles, is_active, created_at, last_login, company_id
                    FROM users WHERE company_id = ? ORDER BY created_at DESC
                ''', (company_id,))
            else:
                cursor.execute('''
                    SELECT id, username, email, roles, is_active, created_at, last_login, company_id
                    FROM users ORDER BY created_at DESC
                ''')
            rows = cursor.fetchall()
            conn.close()

            users = []
            for row in rows:
                try:
                    roles = json.loads(row[3]) if row[3] else ['user']
                except Exception:
                    roles = [row[3]] if row[3] else ['user']
                users.append({
                    'id': row[0], 'username': row[1], 'email': row[2],
                    'roles': roles, 'is_active': bool(row[4]),
                    'created_at': row[5], 'last_login': row[6], 'company_id': row[7]
                })
            return users

    except Exception as e:
        import traceback
        print(f"❌ ERROR al listar usuarios: {e}")
        print(traceback.format_exc())
        return []

# ============================================================
# FUNCIONES DE GESTIÓN DE EMPRESAS
# ============================================================

def create_company(name, contact_email=None, contact_phone=None, subscription_type='enterprise', 
                   subscription_status='active', subscription_price=13.0, max_users=8, max_admins=3, 
                   created_by=None, notes=None):
    """Crea una nueva empresa"""
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO companies 
            (name, contact_email, contact_phone, subscription_type, subscription_status, 
             subscription_price, max_users, max_admins, created_by, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (name, contact_email, contact_phone, subscription_type, subscription_status,
              subscription_price, max_users, max_admins, created_by, notes))
        
        company_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return {'success': True, 'company_id': company_id}
    except sqlite3.IntegrityError:
        return {'success': False, 'error': 'Empresa con ese nombre ya existe'}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def get_company_by_id(company_id):
    """Obtiene una empresa por ID"""
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, name, contact_email, contact_phone, subscription_type, subscription_status,
                   subscription_start_date, subscription_end_date, subscription_price,
                   max_users, max_admins, created_at, created_by, is_active, notes
            FROM companies
            WHERE id = ?
        ''', (company_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            # Contar usuarios actuales
            conn = sqlite3.connect(DATABASE)
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM users WHERE company_id = ? AND is_active = 1', (company_id,))
            current_users = cursor.fetchone()[0]
            
            cursor.execute('''
                SELECT COUNT(*) FROM users 
                WHERE company_id = ? AND is_active = 1 
                AND roles LIKE "%administrador%"
            ''', (company_id,))
            current_admins = cursor.fetchone()[0]
            conn.close()
            
            return {
                'id': row[0],
                'name': row[1],
                'contact_email': row[2],
                'contact_phone': row[3],
                'subscription_type': row[4] or 'enterprise',
                'subscription_status': row[5],
                'subscription_start_date': row[6],
                'subscription_end_date': row[7],
                'subscription_price': row[8] or 13.0,
                'max_users': row[9],
                'max_admins': row[10],
                'created_at': row[11],
                'created_by': row[12],
                'is_active': bool(row[13]),
                'notes': row[14],
                'current_users': current_users,
                'current_admins': current_admins
            }
        return None
    except Exception as e:
        return None

def list_companies():
    """Lista todas las empresas"""
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, name, contact_email, subscription_type, subscription_status, 
                   subscription_start_date, subscription_end_date, subscription_price,
                   max_users, max_admins, created_at, is_active
            FROM companies
            ORDER BY created_at DESC
        ''')
        
        companies = []
        for row in cursor.fetchall():
            company_id = row[0]
            
            # Contar usuarios actuales
            cursor.execute('SELECT COUNT(*) FROM users WHERE company_id = ? AND is_active = 1', (company_id,))
            current_users = cursor.fetchone()[0]
            
            cursor.execute('''
                SELECT COUNT(*) FROM users 
                WHERE company_id = ? AND is_active = 1 
                AND roles LIKE "%administrador%"
            ''', (company_id,))
            current_admins = cursor.fetchone()[0]
            
            companies.append({
                'id': company_id,
                'name': row[1],
                'contact_email': row[2],
                'subscription_type': row[3] or 'enterprise',
                'subscription_status': row[4],
                'subscription_start_date': row[5],
                'subscription_end_date': row[6],
                'subscription_price': row[7] or 13.0,
                'max_users': row[8],
                'max_admins': row[9],
                'created_at': row[10],
                'is_active': bool(row[11]),
                'current_users': current_users,
                'current_admins': current_admins
            })
        
        conn.close()
        return companies
    except Exception as e:
        return []

def update_company(company_id, name=None, contact_email=None, contact_phone=None,
                   subscription_type=None, subscription_status=None, subscription_price=None,
                   subscription_end_date=None, max_users=None, max_admins=None, is_active=None, notes=None):
    """Actualiza una empresa"""
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        updates = []
        params = []
        
        if name is not None:
            updates.append('name = ?')
            params.append(name)
        if contact_email is not None:
            updates.append('contact_email = ?')
            params.append(contact_email)
        if contact_phone is not None:
            updates.append('contact_phone = ?')
            params.append(contact_phone)
        if subscription_type is not None:
            updates.append('subscription_type = ?')
            params.append(subscription_type)
        if subscription_status is not None:
            updates.append('subscription_status = ?')
            params.append(subscription_status)
        if subscription_price is not None:
            updates.append('subscription_price = ?')
            params.append(subscription_price)
        if subscription_end_date is not None:
            updates.append('subscription_end_date = ?')
            params.append(subscription_end_date)
        if max_users is not None:
            updates.append('max_users = ?')
            params.append(max_users)
        if max_admins is not None:
            updates.append('max_admins = ?')
            params.append(max_admins)
        if is_active is not None:
            updates.append('is_active = ?')
            params.append(is_active)
        if notes is not None:
            updates.append('notes = ?')
            params.append(notes)
        
        if not updates:
            conn.close()
            return {'success': False, 'error': 'No hay campos para actualizar'}
        
        params.append(company_id)
        cursor.execute(f'''
            UPDATE companies SET {', '.join(updates)} WHERE id = ?
        ''', params)
        
        conn.commit()
        conn.close()
        
        return {'success': True}
    except Exception as e:
        return {'success': False, 'error': str(e)}

# Decoradores para Flask
def login_required(f):
    """Decorador para requerir login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Verificar si es una petición AJAX/JSON (múltiples formas de detectarlo)
        is_ajax = (request.is_json or 
                  request.headers.get('Content-Type', '').startswith('application/json') or
                  request.headers.get('Accept', '').startswith('application/json') or
                  request.headers.get('X-Requested-With') == 'XMLHttpRequest')
        
        if 'user_id' not in session:
            if is_ajax:
                return jsonify({'error': 'No autenticado'}), 401
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorador para requerir rol de administrador (super admin)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Verificar si es una petición AJAX/JSON (múltiples formas de detectarlo)
        is_ajax = (request.is_json or 
                  request.headers.get('Content-Type', '').startswith('application/json') or
                  request.headers.get('Accept', '').startswith('application/json') or
                  request.headers.get('X-Requested-With') == 'XMLHttpRequest')
        
        if 'user_id' not in session:
            if is_ajax:
                return jsonify({'error': 'No autenticado'}), 401
            return redirect(url_for('login'))
        
        user = get_user_by_id(session['user_id'])
        if not user or not is_admin(user):
            if is_ajax:
                return jsonify({'error': 'Acceso denegado. Se requiere rol de administrador.'}), 403
            return redirect(url_for('panel'))
        
        return f(*args, **kwargs)
    return decorated_function

def company_admin_required(f):
    """Decorador para requerir rol de administrador de empresa"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.is_json:
                return jsonify({'error': 'No autenticado'}), 401
            return redirect(url_for('login'))
        
        user = get_user_by_id(session['user_id'])
        if not user:
            if request.is_json:
                return jsonify({'error': 'Usuario no encontrado'}), 404
            return redirect(url_for('login'))
        
        # Permitir tanto super admin como admin de empresa
        if not (is_admin(user) or is_company_admin(user)):
            if request.is_json:
                return jsonify({'error': 'Acceso denegado. Se requiere rol de administrador de empresa.'}), 403
            return redirect(url_for('panel'))
        
        return f(*args, **kwargs)
    return decorated_function

def company_user_required(f):
    """Decorador para requerir que el usuario pertenezca a una empresa"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.is_json:
                return jsonify({'error': 'No autenticado'}), 401
            return redirect(url_for('login'))
        
        user = get_user_by_id(session['user_id'])
        if not user:
            if request.is_json:
                return jsonify({'error': 'Usuario no encontrado'}), 404
            return redirect(url_for('login'))
        
        # Permitir super admin o usuarios de empresa
        if not (is_admin(user) or is_company_user(user)):
            if request.is_json:
                return jsonify({'error': 'Acceso denegado. Se requiere pertenecer a una empresa.'}), 403
            return redirect(url_for('panel'))
        
        return f(*args, **kwargs)
    return decorated_function

