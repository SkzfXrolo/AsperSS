"""
Módulo de conexión PostgreSQL para reemplazar SQLite
Usa Render PostgreSQL (100% gratis) o cualquier host PostgreSQL
"""
import os
import threading
import time
from contextlib import contextmanager
from functools import wraps
import psycopg2
from psycopg2.extras import RealDictCursor

# Configuración desde variables de entorno
POSTGRES_HOST = os.environ.get('POSTGRES_HOST') or os.environ.get('DATABASE_URL', '').split('@')[1].split('/')[0].split(':')[0] if os.environ.get('DATABASE_URL') else None
POSTGRES_PORT = int(os.environ.get('POSTGRES_PORT', 5432))
POSTGRES_USER = os.environ.get('POSTGRES_USER') or os.environ.get('DATABASE_URL', '').split('://')[1].split(':')[0] if os.environ.get('DATABASE_URL') else None
POSTGRES_PASSWORD = os.environ.get('POSTGRES_PASSWORD') or os.environ.get('DATABASE_URL', '').split('@')[0].split(':')[1] if os.environ.get('DATABASE_URL') else None
POSTGRES_DATABASE = os.environ.get('POSTGRES_DATABASE') or os.environ.get('DATABASE_URL', '').split('/')[-1] if os.environ.get('DATABASE_URL') else None

# Si Render proporciona DATABASE_URL directamente, usarla
if os.environ.get('DATABASE_URL'):
    DATABASE_URL = os.environ.get('DATABASE_URL')
else:
    DATABASE_URL = None

# Pool de conexiones thread-local
_local = threading.local()

def get_db_connection():
    """Obtiene una conexión PostgreSQL thread-local (reutilizable)"""
    if not hasattr(_local, 'connection') or _local.connection.closed:
        try:
            if DATABASE_URL:
                # Usar connection string de Render
                _local.connection = psycopg2.connect(
                    DATABASE_URL,
                    cursor_factory=RealDictCursor,
                    connect_timeout=10
                )
            else:
                # Usar variables individuales
                _local.connection = psycopg2.connect(
                    host=POSTGRES_HOST,
                    port=POSTGRES_PORT,
                    user=POSTGRES_USER,
                    password=POSTGRES_PASSWORD,
                    database=POSTGRES_DATABASE,
                    cursor_factory=RealDictCursor,
                    connect_timeout=10
                )
            print(f"✅ Conexión PostgreSQL establecida: {POSTGRES_HOST or 'via DATABASE_URL'}:{POSTGRES_PORT}/{POSTGRES_DATABASE or 'via URL'}")
        except Exception as e:
            print(f"❌ Error conectando a PostgreSQL: {e}")
            raise
    
    return _local.connection

@contextmanager
def get_db_cursor():
    """Context manager para operaciones de base de datos PostgreSQL"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()

def execute_query(query, params=None, fetch_one=False, fetch_all=False):
    """Ejecuta una consulta SQL y retorna resultados"""
    with get_db_cursor() as cursor:
        cursor.execute(query, params or ())
        if fetch_one:
            return cursor.fetchone()
        elif fetch_all:
            return cursor.fetchall()
        else:
            return cursor.rowcount

def init_postgresql_db():
    """Inicializa la base de datos PostgreSQL creando todas las tablas necesarias"""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if conn is None or conn.closed:
            raise Exception("No se pudo obtener conexión a PostgreSQL")
        cursor = conn.cursor()
    except Exception as e:
        print(f"❌ Error obteniendo conexión PostgreSQL: {e}")
        raise
    
    try:
        # Tabla de tokens de escaneo
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scan_tokens (
                id SERIAL PRIMARY KEY,
                token VARCHAR(255) UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                used_count INTEGER DEFAULT 0,
                max_uses INTEGER DEFAULT -1,
                is_active BOOLEAN DEFAULT TRUE,
                created_by VARCHAR(255),
                description TEXT
            )
        ''')
        
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_token ON scan_tokens(token)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_active ON scan_tokens(is_active, expires_at)')
        
        # Tabla de escaneos
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scans (
                id SERIAL PRIMARY KEY,
                token_id INTEGER,
                scan_token VARCHAR(255),
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                status VARCHAR(50) DEFAULT 'running',
                total_files_scanned INTEGER DEFAULT 0,
                issues_found INTEGER DEFAULT 0,
                scan_duration DECIMAL(10, 2),
                machine_id VARCHAR(255),
                machine_name VARCHAR(255),
                ip_address VARCHAR(45),
                country VARCHAR(100),
                minecraft_username VARCHAR(255),
                FOREIGN KEY (token_id) REFERENCES scan_tokens(id) ON DELETE SET NULL
            )
        ''')
        
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_token_id ON scans(token_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_scan_token ON scans(scan_token)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_status ON scans(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_started_at ON scans(started_at)')
        
        # Tabla de historial de bans
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ban_history (
                id SERIAL PRIMARY KEY,
                machine_id VARCHAR(255),
                minecraft_username VARCHAR(255),
                ip_address VARCHAR(45),
                ban_reason TEXT,
                hack_type VARCHAR(255),
                banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                scan_id INTEGER,
                FOREIGN KEY (scan_id) REFERENCES scans(id) ON DELETE SET NULL
            )
        ''')
        
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_machine_id ON ban_history(machine_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_username ON ban_history(minecraft_username)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_banned_at ON ban_history(banned_at)')
        
        # Tabla de resultados de escaneos
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scan_results (
                id SERIAL PRIMARY KEY,
                scan_id INTEGER,
                issue_type VARCHAR(255),
                issue_name VARCHAR(255),
                issue_path TEXT,
                issue_category VARCHAR(255),
                alert_level VARCHAR(50),
                confidence DECIMAL(5, 2),
                detected_patterns TEXT,
                obfuscation_detected BOOLEAN DEFAULT FALSE,
                file_hash VARCHAR(64),
                ai_analysis TEXT,
                ai_confidence DECIMAL(5, 2),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (scan_id) REFERENCES scans(id) ON DELETE CASCADE
            )
        ''')
        
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_scan_id ON scan_results(scan_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_issue_type ON scan_results(issue_type)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_alert_level ON scan_results(alert_level)')
        
        # Tabla de análisis de IA
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ai_analyses (
                id SERIAL PRIMARY KEY,
                scan_id INTEGER,
                result_id INTEGER,
                analysis_type VARCHAR(255),
                ai_model VARCHAR(255),
                analysis_result TEXT,
                confidence DECIMAL(5, 2),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (scan_id) REFERENCES scans(id) ON DELETE CASCADE,
                FOREIGN KEY (result_id) REFERENCES scan_results(id) ON DELETE CASCADE
            )
        ''')
        
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_scan_id ON ai_analyses(scan_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_result_id ON ai_analyses(result_id)')
        
        # Tabla de empresas
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS companies (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) UNIQUE NOT NULL,
                contact_email VARCHAR(255),
                contact_phone VARCHAR(50),
                subscription_type VARCHAR(50) DEFAULT 'enterprise',
                subscription_status VARCHAR(50) DEFAULT 'active',
                subscription_start_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                subscription_end_date TIMESTAMP,
                subscription_price DECIMAL(10, 2) DEFAULT 13.0,
                max_users INTEGER DEFAULT 8,
                max_admins INTEGER DEFAULT 3,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by INTEGER,
                is_active BOOLEAN DEFAULT TRUE,
                notes TEXT
            )
        ''')
        
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_name ON companies(name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_active ON companies(is_active)')
        
        # Crear empresa default "arefy" si no existe
        cursor.execute('SELECT COUNT(*) as count FROM companies WHERE name = %s', ('arefy',))
        result = cursor.fetchone()
        # RealDictCursor devuelve un diccionario
        count = result['count'] if result else 0
        if count == 0:
            cursor.execute('''
                INSERT INTO companies (name, subscription_type, subscription_status, subscription_price, max_users, max_admins, created_by, notes)
                VALUES (%s, 'enterprise', 'active', 13.0, 8, 3, NULL, 'Empresa default creada automáticamente')
            ''', ('arefy',))
            print("✅ Empresa default 'arefy' creada en PostgreSQL")
        
        # Tabla de usuarios
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(255) UNIQUE NOT NULL,
                email VARCHAR(255) UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                roles TEXT DEFAULT '["user"]',
                company_id INTEGER,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                created_by VARCHAR(255),
                FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE SET NULL
            )
        ''')
        
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_username ON users(username)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_email ON users(email)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_company_id ON users(company_id)')
        
        # Tabla de enlaces de descarga
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS download_links (
                id SERIAL PRIMARY KEY,
                token VARCHAR(255) UNIQUE NOT NULL,
                filename VARCHAR(255) NOT NULL,
                created_by INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                max_downloads INTEGER DEFAULT 1,
                download_count INTEGER DEFAULT 0,
                is_active BOOLEAN DEFAULT TRUE,
                description TEXT,
                FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_token ON download_links(token)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_active ON download_links(is_active, expires_at)')
        
        # Tabla de tokens de registro
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS registration_tokens (
                id SERIAL PRIMARY KEY,
                token VARCHAR(255) UNIQUE NOT NULL,
                company_id INTEGER,
                created_by INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                used_at TIMESTAMP,
                is_used BOOLEAN DEFAULT FALSE,
                used_by INTEGER,
                max_uses INTEGER DEFAULT 1,
                description TEXT,
                is_admin_token BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE SET NULL,
                FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (used_by) REFERENCES users(id) ON DELETE SET NULL
            )
        ''')
        
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_token ON registration_tokens(token)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_company_id ON registration_tokens(company_id)')
        
        # Tabla de versiones de aplicación
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS app_versions (
                id SERIAL PRIMARY KEY,
                version VARCHAR(50) UNIQUE NOT NULL,
                release_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                download_url TEXT,
                changelog TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                file_size BIGINT,
                file_hash VARCHAR(64),
                min_required_version VARCHAR(50)
            )
        ''')
        
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_version ON app_versions(version)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_active ON app_versions(is_active)')
        
        # Tabla de configuraciones
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS configurations (
                id SERIAL PRIMARY KEY,
                key VARCHAR(255) UNIQUE NOT NULL,
                value TEXT,
                description TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_key ON configurations(key)')
        
        # Tabla de estadísticas
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS statistics (
                id SERIAL PRIMARY KEY,
                date DATE DEFAULT CURRENT_DATE,
                total_scans INTEGER DEFAULT 0,
                total_issues_found INTEGER DEFAULT 0,
                unique_machines INTEGER DEFAULT 0,
                avg_scan_duration DECIMAL(10, 2)
            )
        ''')
        
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_date ON statistics(date)')
        
        # Tabla de feedback del staff
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS staff_feedback (
                id SERIAL PRIMARY KEY,
                result_id INTEGER NOT NULL,
                scan_id INTEGER,
                staff_verification VARCHAR(50) NOT NULL,
                staff_notes TEXT,
                verified_by VARCHAR(255),
                verified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                file_hash VARCHAR(64),
                issue_name VARCHAR(255),
                issue_path TEXT,
                extracted_patterns TEXT,
                extracted_features TEXT,
                FOREIGN KEY (result_id) REFERENCES scan_results(id) ON DELETE CASCADE,
                FOREIGN KEY (scan_id) REFERENCES scans(id) ON DELETE SET NULL
            )
        ''')
        
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_result_id ON staff_feedback(result_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_scan_id ON staff_feedback(scan_id)')
        
        # Tabla de patrones aprendidos
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS learned_patterns (
                id SERIAL PRIMARY KEY,
                pattern_type VARCHAR(255) NOT NULL,
                pattern_value TEXT NOT NULL,
                pattern_category VARCHAR(255),
                confidence DECIMAL(5, 2) DEFAULT 1.0,
                source_feedback_id INTEGER,
                learned_from_count INTEGER DEFAULT 1,
                first_learned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE,
                FOREIGN KEY (source_feedback_id) REFERENCES staff_feedback(id) ON DELETE SET NULL
            )
        ''')
        
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_pattern_type ON learned_patterns(pattern_type)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_active ON learned_patterns(is_active)')
        
        # Tabla de hashes aprendidos
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS learned_hashes (
                id SERIAL PRIMARY KEY,
                file_hash VARCHAR(64) UNIQUE NOT NULL,
                is_hack BOOLEAN NOT NULL,
                confirmed_count INTEGER DEFAULT 1,
                first_confirmed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_confirmed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                source_feedback_id INTEGER,
                FOREIGN KEY (source_feedback_id) REFERENCES staff_feedback(id) ON DELETE SET NULL
            )
        ''')
        
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_file_hash ON learned_hashes(file_hash)')
        
        # Tabla de versiones de modelo de IA
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ai_model_versions (
                id SERIAL PRIMARY KEY,
                version VARCHAR(50) UNIQUE NOT NULL,
                model_type VARCHAR(255),
                training_data_count INTEGER,
                accuracy DECIMAL(5, 2),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE,
                model_path TEXT
            )
        ''')
        
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_version ON ai_model_versions(version)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_active ON ai_model_versions(is_active)')
        
        conn.commit()
        print("✅ Base de datos PostgreSQL inicializada correctamente")
        
        # Crear empresa default "arefy" si no existe (ya se creó arriba, pero verificamos de nuevo)
        try:
            cursor.execute('SELECT COUNT(*) as count FROM companies WHERE name = %s', ('arefy',))
            result = cursor.fetchone()
            # RealDictCursor devuelve un diccionario
            count = result['count'] if result else 0
            if count == 0:
                cursor.execute('''
                    INSERT INTO companies (name, subscription_type, subscription_status, subscription_price, max_users, max_admins, notes)
                    VALUES (%s, 'enterprise', 'active', 13.0, 8, 3, 'Empresa default creada automáticamente')
                ''', ('arefy',))
                conn.commit()
                print("✅ Empresa default 'arefy' creada")
        except Exception as e:
            print(f"⚠️ Error creando empresa default 'arefy': {e}")
            # No es crítico, continuar

        # Crear usuario admin default "arefy_admin" si no existe
        try:
            cursor.execute('SELECT COUNT(*) as count FROM users WHERE username = %s', ('arefy_admin',))
            result = cursor.fetchone()
            count = result['count'] if result else 0
            if count == 0:
                cursor.execute('SELECT id FROM companies WHERE name = %s', ('arefy',))
                arefy_row = cursor.fetchone()
                if arefy_row:
                    import hashlib as _hashlib
                    _default_hash = _hashlib.sha256('arefy2024!'.encode()).hexdigest()
                    cursor.execute('''
                        INSERT INTO users (username, email, password_hash, roles, company_id, created_by)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    ''', ('arefy_admin', 'admin@arefy.com', _default_hash,
                          '["admin", "empresa", "administrador"]', arefy_row['id'], 'system'))
                    conn.commit()
                    print("✅ Usuario admin 'arefy_admin' creado (contraseña: arefy2024!)")
        except Exception as e:
            print(f"⚠️ Error creando usuario admin default: {e}")
            # No es crítico, continuar

    except Exception as e:
        if conn:
            conn.rollback()
        error_type = type(e).__name__
        error_msg = str(e)
        print(f"❌ Error inicializando base de datos PostgreSQL: {error_type}: {error_msg}")
        import traceback
        print("📋 Traceback completo:")
        traceback.print_exc()
        raise
    finally:
        if cursor:
            cursor.close()
        # NO cerrar la conexión aquí porque es thread-local y se reutiliza

# Cache en memoria (similar al sistema SQLite)
_cache = {}
_cache_timeout = {}
CACHE_TTL = 30  # 30 segundos TTL

def get_cached(key):
    """Obtiene un valor del caché si no ha expirado"""
    if key in _cache:
        if time.time() - _cache_timeout.get(key, 0) < CACHE_TTL:
            return _cache[key]
        else:
            del _cache[key]
            del _cache_timeout[key]
    return None

def set_cached(key, value):
    """Guarda un valor en el caché"""
    _cache[key] = value
    _cache_timeout[key] = time.time()

def clear_cache(pattern=None):
    """Limpia el caché (opcionalmente por patrón)"""
    if pattern:
        keys_to_delete = [k for k in _cache.keys() if pattern in k]
        for k in keys_to_delete:
            _cache.pop(k, None)
            _cache_timeout.pop(k, None)
    else:
        _cache.clear()
        _cache_timeout.clear()

