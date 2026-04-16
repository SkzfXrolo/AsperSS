"""
Módulo de conexión MySQL/PostgreSQL para reemplazar SQLite
Soporta múltiples hosts MySQL (PlanetScale, Railway, etc.) y PostgreSQL (Render, Supabase, Neon)
Detecta automáticamente qué base de datos usar según las variables de entorno
"""
import os
import sys
import threading
import time
from contextlib import contextmanager
from functools import wraps

# Detectar qué tipo de BD usar (PostgreSQL tiene prioridad)
USE_POSTGRESQL = bool(os.environ.get('DATABASE_URL') or os.environ.get('POSTGRES_HOST'))
USE_MYSQL = bool(os.environ.get('MYSQL_HOST') and not USE_POSTGRESQL)

# Debug: mostrar qué BD se detectó
if USE_POSTGRESQL:
    print(f"🔍 Detectado PostgreSQL: DATABASE_URL={'Sí' if os.environ.get('DATABASE_URL') else 'No'}, POSTGRES_HOST={'Sí' if os.environ.get('POSTGRES_HOST') else 'No'}")
elif USE_MYSQL:
    print(f"🔍 Detectado MySQL: MYSQL_HOST={os.environ.get('MYSQL_HOST')}")
else:
    print("🔍 No se detectó ninguna BD configurada")

# Variables globales para los módulos
psycopg2 = None
RealDictCursor = None
pymysql = None
DictCursor = None

if USE_POSTGRESQL:
    # Usar PostgreSQL
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        print("✅ Usando PostgreSQL")
    except ImportError as e:
        print(f"⚠️ psycopg2 no instalado: {e}")
        print("⚠️ Instala psycopg2-binary: pip install psycopg2-binary")
        print("⚠️ Deshabilitando PostgreSQL, intentando MySQL...")
        USE_POSTGRESQL = False
        psycopg2 = None
        RealDictCursor = None

if USE_MYSQL and not USE_POSTGRESQL:
    # Usar MySQL
    try:
        import pymysql
        from pymysql.cursors import DictCursor
        print("✅ Usando MySQL")
    except ImportError as e:
        print(f"⚠️ pymysql no instalado: {e}")
        USE_MYSQL = False
        pymysql = None
        DictCursor = None

# Configuración desde variables de entorno (solo si no es PostgreSQL)
MYSQL_HOST = os.environ.get('MYSQL_HOST')  # No usar 'localhost' por defecto
MYSQL_PORT = int(os.environ.get('MYSQL_PORT', 3306))
MYSQL_USER = os.environ.get('MYSQL_USER', 'root')
MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', '')
MYSQL_DATABASE = os.environ.get('MYSQL_DATABASE', 'scanner_db')
MYSQL_SSL_CA = os.environ.get('MYSQL_SSL_CA')  # Para PlanetScale y otros hosts con SSL

# Pool de conexiones thread-local
_local = threading.local()

def get_db_connection():
    """Obtiene una conexión MySQL/PostgreSQL thread-local (reutilizable)"""
    # Verificar nuevamente las variables de entorno (por si cambiaron)
    current_use_postgresql = bool(os.environ.get('DATABASE_URL') or os.environ.get('POSTGRES_HOST'))
    current_use_mysql = bool(os.environ.get('MYSQL_HOST') and not current_use_postgresql)
    
    if current_use_postgresql:
        # Usar PostgreSQL
        return _get_postgresql_connection()
    elif current_use_mysql:
        # Usar MySQL
        return _get_mysql_connection()
    else:
        raise Exception("No hay base de datos configurada. Configura DATABASE_URL o MYSQL_HOST")

def _get_postgresql_connection():
    """Obtiene conexión PostgreSQL"""
    if psycopg2 is None:
        raise ImportError("psycopg2 no está instalado. Instala con: pip install psycopg2-binary")
    
    if not hasattr(_local, 'connection') or _local.connection.closed:
        try:
            database_url = os.environ.get('DATABASE_URL')
            
            if database_url:
                # Intentar corregir automáticamente el hostname si falta el dominio
                corrected_url = _fix_postgresql_url(database_url)
                
                # Intentar conectar
                try:
                    _local.connection = psycopg2.connect(
                        corrected_url,
                        cursor_factory=RealDictCursor,
                        connect_timeout=10
                    )
                    print(f"✅ Conexión PostgreSQL establecida")
                except Exception as connect_error:
                    # Si falla, intentar con la URL original
                    if corrected_url != database_url:
                        print(f"⚠️ Falló con URL corregida, intentando URL original...")
                        try:
                            _local.connection = psycopg2.connect(
                                database_url,
                                cursor_factory=RealDictCursor,
                                connect_timeout=10
                            )
                            print(f"✅ Conexión PostgreSQL establecida (con URL original)")
                        except:
                            raise connect_error
                    else:
                        raise
            else:
                # Usar variables individuales
                POSTGRES_HOST = os.environ.get('POSTGRES_HOST')
                POSTGRES_PORT = int(os.environ.get('POSTGRES_PORT', 5432))
                POSTGRES_USER = os.environ.get('POSTGRES_USER')
                POSTGRES_PASSWORD = os.environ.get('POSTGRES_PASSWORD')
                POSTGRES_DATABASE = os.environ.get('POSTGRES_DATABASE')
                
                if not POSTGRES_HOST:
                    raise Exception("POSTGRES_HOST o DATABASE_URL debe estar configurado")
                
                # Intentar corregir el hostname si falta el dominio
                if '.' not in POSTGRES_HOST and POSTGRES_HOST != 'localhost':
                    # Intentar agregar el dominio común de Render
                    possible_domains = [
                        '.oregon-postgres.render.com',
                        '.virginia-postgres.render.com',
                        '.frankfurt-postgres.render.com',
                        '.singapore-postgres.render.com'
                    ]
                    
                    for domain in possible_domains:
                        try:
                            test_host = POSTGRES_HOST + domain
                            print(f"🔄 Intentando con hostname corregido: {test_host}")
                            _local.connection = psycopg2.connect(
                                host=test_host,
                                port=POSTGRES_PORT,
                                user=POSTGRES_USER,
                                password=POSTGRES_PASSWORD,
                                database=POSTGRES_DATABASE,
                                cursor_factory=RealDictCursor,
                                connect_timeout=10
                            )
                            print(f"✅ Conexión PostgreSQL establecida con hostname corregido")
                            return _local.connection
                        except:
                            continue
                    
                    # Si ninguna funciona, intentar con el hostname original
                    print(f"⚠️ No se pudo corregir automáticamente el hostname")
                
                _local.connection = psycopg2.connect(
                    host=POSTGRES_HOST,
                    port=POSTGRES_PORT,
                    user=POSTGRES_USER,
                    password=POSTGRES_PASSWORD,
                    database=POSTGRES_DATABASE,
                    cursor_factory=RealDictCursor,
                    connect_timeout=10
                )
                print(f"✅ Conexión PostgreSQL establecida")
        except Exception as e:
            error_msg = str(e)
            print(f"❌ Error conectando a PostgreSQL: {error_msg}")
            
            # Mensajes de ayuda específicos
            if "could not translate host name" in error_msg or "Name or service not known" in error_msg:
                print(f"\n🔧 SOLUCIÓN:")
                print(f"   1. Ve a tu servicio PostgreSQL en Render")
                print(f"   2. Ve a la pestaña 'Connections'")
                print(f"   3. Copia el 'Internal Database URL' COMPLETO")
                print(f"   4. Debe incluir el dominio completo, ejemplo:")
                print(f"      postgresql://user:pass@dpg-xxxxx-a.oregon-postgres.render.com:5432/db")
                print(f"   5. Actualiza DATABASE_URL en tu Web App con esa URL completa")
            else:
                print(f"💡 Verifica que DATABASE_URL tenga el formato correcto:")
                print(f"   postgresql://usuario:password@host-completo:5432/database")
            
            raise
    return _local.connection

def _fix_postgresql_url(url):
    """Normaliza el prefijo de la URL — psycopg2 requiere postgresql://, Render da postgres://"""
    if not url:
        return url
    # Solo normalizar el prefijo, nunca modificar el hostname (rompe hostnames internos de Render)
    return url.replace('postgres://', 'postgresql://', 1)

def _get_mysql_connection():
    """Obtiene conexión MySQL"""
    if pymysql is None:
        raise ImportError("pymysql no está instalado. Instala con: pip install pymysql")
    
    # Verificar que MYSQL_HOST esté configurado
    if not MYSQL_HOST:
        raise Exception("MYSQL_HOST no está configurado. Configura MYSQL_HOST o usa PostgreSQL con DATABASE_URL")
    
    if not hasattr(_local, 'connection') or not _local.connection.open:
        # Configurar SSL si es necesario (para PlanetScale, Railway, etc.)
        ssl_config = None
        if MYSQL_SSL_CA:
            ssl_config = {'ca': MYSQL_SSL_CA}
        elif MYSQL_HOST != 'localhost' and MYSQL_HOST != '127.0.0.1':
            # Para hosts remotos, usar SSL por defecto
            ssl_config = {}
        
        try:
            _local.connection = pymysql.connect(
                host=MYSQL_HOST,
                port=MYSQL_PORT,
                user=MYSQL_USER,
                password=MYSQL_PASSWORD,
                database=MYSQL_DATABASE,
                charset='utf8mb4',
                cursorclass=DictCursor,
                autocommit=False,
                ssl=ssl_config,
                connect_timeout=10,
                read_timeout=30,
                write_timeout=30
            )
            print(f"✅ Conexión MySQL establecida: {MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}")
        except Exception as e:
            print(f"❌ Error conectando a MySQL: {e}")
            raise
    
    return _local.connection

@contextmanager
def get_db_cursor():
    """Context manager para operaciones de base de datos MySQL/PostgreSQL"""
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

def init_mysql_db():
    """Inicializa la base de datos MySQL/PostgreSQL creando todas las tablas necesarias"""
    if USE_POSTGRESQL:
        # Usar módulo PostgreSQL
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from db_postgresql import init_postgresql_db
            return init_postgresql_db()
        except ImportError:
            print("⚠️ db_postgresql no disponible, usando MySQL...")
            pass
    
    # Usar MySQL
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Tabla de tokens de escaneo
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scan_tokens (
                id INT AUTO_INCREMENT PRIMARY KEY,
                token VARCHAR(255) UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NULL,
                used_count INT DEFAULT 0,
                max_uses INT DEFAULT -1,
                is_active BOOLEAN DEFAULT 1,
                created_by VARCHAR(255),
                description TEXT,
                INDEX idx_token (token),
                INDEX idx_active (is_active, expires_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ''')
        
        # Tabla de escaneos
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scans (
                id INT AUTO_INCREMENT PRIMARY KEY,
                token_id INT,
                scan_token VARCHAR(255),
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP NULL,
                status VARCHAR(50) DEFAULT 'running',
                total_files_scanned INT DEFAULT 0,
                issues_found INT DEFAULT 0,
                scan_duration DECIMAL(10, 2),
                machine_id VARCHAR(255),
                machine_name VARCHAR(255),
                ip_address VARCHAR(45),
                country VARCHAR(100),
                minecraft_username VARCHAR(255),
                FOREIGN KEY (token_id) REFERENCES scan_tokens(id) ON DELETE SET NULL,
                INDEX idx_token_id (token_id),
                INDEX idx_scan_token (scan_token),
                INDEX idx_status (status),
                INDEX idx_started_at (started_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ''')
        
        # Tabla de historial de bans
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ban_history (
                id INT AUTO_INCREMENT PRIMARY KEY,
                machine_id VARCHAR(255),
                minecraft_username VARCHAR(255),
                ip_address VARCHAR(45),
                ban_reason TEXT,
                hack_type VARCHAR(255),
                banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                scan_id INT,
                FOREIGN KEY (scan_id) REFERENCES scans(id) ON DELETE SET NULL,
                INDEX idx_machine_id (machine_id),
                INDEX idx_username (minecraft_username),
                INDEX idx_banned_at (banned_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ''')
        
        # Tabla de resultados de escaneos
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scan_results (
                id INT AUTO_INCREMENT PRIMARY KEY,
                scan_id INT,
                issue_type VARCHAR(255),
                issue_name VARCHAR(255),
                issue_path TEXT,
                issue_category VARCHAR(255),
                alert_level VARCHAR(50),
                confidence DECIMAL(5, 2),
                detected_patterns TEXT,
                obfuscation_detected BOOLEAN DEFAULT 0,
                file_hash VARCHAR(64),
                ai_analysis TEXT,
                ai_confidence DECIMAL(5, 2),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (scan_id) REFERENCES scans(id) ON DELETE CASCADE,
                INDEX idx_scan_id (scan_id),
                INDEX idx_issue_type (issue_type),
                INDEX idx_alert_level (alert_level)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ''')
        
        # Tabla de análisis de IA
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ai_analyses (
                id INT AUTO_INCREMENT PRIMARY KEY,
                scan_id INT,
                result_id INT,
                analysis_type VARCHAR(255),
                ai_model VARCHAR(255),
                analysis_result TEXT,
                confidence DECIMAL(5, 2),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (scan_id) REFERENCES scans(id) ON DELETE CASCADE,
                FOREIGN KEY (result_id) REFERENCES scan_results(id) ON DELETE CASCADE,
                INDEX idx_scan_id (scan_id),
                INDEX idx_result_id (result_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ''')
        
        # Tabla de empresas
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS companies (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) UNIQUE NOT NULL,
                contact_email VARCHAR(255),
                contact_phone VARCHAR(50),
                subscription_type VARCHAR(50) DEFAULT 'enterprise',
                subscription_status VARCHAR(50) DEFAULT 'active',
                subscription_start_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                subscription_end_date TIMESTAMP NULL,
                subscription_price DECIMAL(10, 2) DEFAULT 13.0,
                max_users INT DEFAULT 8,
                max_admins INT DEFAULT 3,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by INT,
                is_active BOOLEAN DEFAULT 1,
                notes TEXT,
                INDEX idx_name (name),
                INDEX idx_active (is_active)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ''')
        
        # Tabla de usuarios
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(255) UNIQUE NOT NULL,
                email VARCHAR(255) UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                roles TEXT DEFAULT '["user"]',
                company_id INT,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP NULL,
                created_by VARCHAR(255),
                FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE SET NULL,
                INDEX idx_username (username),
                INDEX idx_email (email),
                INDEX idx_company_id (company_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ''')
        
        # Tabla de enlaces de descarga
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS download_links (
                id INT AUTO_INCREMENT PRIMARY KEY,
                token VARCHAR(255) UNIQUE NOT NULL,
                filename VARCHAR(255) NOT NULL,
                created_by INT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NULL,
                max_downloads INT DEFAULT 1,
                download_count INT DEFAULT 0,
                is_active BOOLEAN DEFAULT 1,
                description TEXT,
                FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE CASCADE,
                INDEX idx_token (token),
                INDEX idx_active (is_active, expires_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ''')
        
        # Tabla de tokens de registro
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS registration_tokens (
                id INT AUTO_INCREMENT PRIMARY KEY,
                token VARCHAR(255) UNIQUE NOT NULL,
                company_id INT,
                created_by INT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NULL,
                used_at TIMESTAMP NULL,
                is_used BOOLEAN DEFAULT 0,
                used_by INT,
                max_uses INT DEFAULT 1,
                description TEXT,
                is_admin_token BOOLEAN DEFAULT 0,
                FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE SET NULL,
                FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (used_by) REFERENCES users(id) ON DELETE SET NULL,
                INDEX idx_token (token),
                INDEX idx_company_id (company_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ''')
        
        # Tabla de versiones de aplicación
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS app_versions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                version VARCHAR(50) UNIQUE NOT NULL,
                release_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                download_url TEXT,
                changelog TEXT,
                is_active BOOLEAN DEFAULT 1,
                file_size BIGINT,
                file_hash VARCHAR(64),
                min_required_version VARCHAR(50),
                INDEX idx_version (version),
                INDEX idx_active (is_active)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ''')
        
        # Tabla de configuraciones
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS configurations (
                id INT AUTO_INCREMENT PRIMARY KEY,
                `key` VARCHAR(255) UNIQUE NOT NULL,
                value TEXT,
                description TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_key (`key`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ''')
        
        # Tabla de estadísticas
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS statistics (
                id INT AUTO_INCREMENT PRIMARY KEY,
                date DATE DEFAULT (CURRENT_DATE),
                total_scans INT DEFAULT 0,
                total_issues_found INT DEFAULT 0,
                unique_machines INT DEFAULT 0,
                avg_scan_duration DECIMAL(10, 2),
                INDEX idx_date (date)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ''')
        
        # Tabla de feedback del staff
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS staff_feedback (
                id INT AUTO_INCREMENT PRIMARY KEY,
                result_id INT NOT NULL,
                scan_id INT,
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
                FOREIGN KEY (scan_id) REFERENCES scans(id) ON DELETE SET NULL,
                INDEX idx_result_id (result_id),
                INDEX idx_scan_id (scan_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ''')
        
        # Tabla de patrones aprendidos
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS learned_patterns (
                id INT AUTO_INCREMENT PRIMARY KEY,
                pattern_type VARCHAR(255) NOT NULL,
                pattern_value TEXT NOT NULL,
                pattern_category VARCHAR(255),
                confidence DECIMAL(5, 2) DEFAULT 1.0,
                source_feedback_id INT,
                learned_from_count INT DEFAULT 1,
                first_learned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1,
                FOREIGN KEY (source_feedback_id) REFERENCES staff_feedback(id) ON DELETE SET NULL,
                INDEX idx_pattern_type (pattern_type),
                INDEX idx_active (is_active)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ''')
        
        # Tabla de hashes aprendidos
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS learned_hashes (
                id INT AUTO_INCREMENT PRIMARY KEY,
                file_hash VARCHAR(64) UNIQUE NOT NULL,
                is_hack BOOLEAN NOT NULL,
                confirmed_count INT DEFAULT 1,
                first_confirmed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_confirmed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                source_feedback_id INT,
                FOREIGN KEY (source_feedback_id) REFERENCES staff_feedback(id) ON DELETE SET NULL,
                INDEX idx_file_hash (file_hash)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ''')
        
        # Tabla de versiones de modelo de IA
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ai_model_versions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                version VARCHAR(50) UNIQUE NOT NULL,
                model_type VARCHAR(255),
                training_data_count INT,
                accuracy DECIMAL(5, 2),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1,
                model_path TEXT,
                INDEX idx_version (version),
                INDEX idx_active (is_active)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ''')
        
        conn.commit()
        print("✅ Base de datos MySQL inicializada correctamente")
        
        # Crear empresa default "arefy" si no existe
        cursor.execute('SELECT COUNT(*) as count FROM companies WHERE name = %s', ('arefy',))
        if cursor.fetchone()['count'] == 0:
            cursor.execute('''
                INSERT INTO companies (name, subscription_type, subscription_status, subscription_price, max_users, max_admins, notes)
                VALUES (%s, 'enterprise', 'active', 13.0, 8, 3, 'Empresa default creada automáticamente')
            ''', ('arefy',))
            conn.commit()
            print("✅ Empresa default 'arefy' creada")

        # Crear usuario admin default "arefy_admin" si no existe
        cursor.execute('SELECT COUNT(*) as count FROM users WHERE username = %s', ('arefy_admin',))
        if cursor.fetchone()['count'] == 0:
            cursor.execute('SELECT id FROM companies WHERE name = %s', ('arefy',))
            arefy_row = cursor.fetchone()
            if arefy_row:
                import hashlib as _hashlib
                _default_hash = _hashlib.sha256('arefy2024!'.encode()).hexdigest()
                cursor.execute('''
                    INSERT INTO users (username, email, password_hash, roles, company_id, created_by)
                    VALUES (%s, %s, %s, %s, %s, %s)
                ''', ('arefy_admin', 'admin@arefy.com', _default_hash,
                      '["empresa", "administrador"]', arefy_row['id'], 'system'))
                conn.commit()
                print("✅ Usuario admin 'arefy_admin' creado en PostgreSQL/MySQL (contraseña: arefy2024!)")
        
    except Exception as e:
        conn.rollback()
        error_type = type(e).__name__
        error_msg = str(e)
        print(f"❌ Error inicializando base de datos MySQL: {error_type}: {error_msg}")
        import traceback
        print("📋 Traceback completo:")
        traceback.print_exc()
        raise
    finally:
        cursor.close()

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

