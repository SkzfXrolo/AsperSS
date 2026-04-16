"""
API REST OPTIMIZADA para Aspers Projects Security Scanner
Optimizaciones: conexión pooling, índices, caché, consultas optimizadas
Migrado a MySQL para persistencia en Render
"""
from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import hashlib
import secrets
import datetime
from functools import wraps
import os
import time

# Importar módulo MySQL
try:
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from db_mysql import (
        get_db_connection, 
        get_db_cursor, 
        init_mysql_db,
        get_cached,
        set_cached,
        clear_cache
    )
    USE_MYSQL = True
    print("✅ Usando MySQL para persistencia de datos")
except ImportError as e:
    print(f"⚠️ Error importando MySQL, intentando SQLite como fallback: {e}")
    USE_MYSQL = False
    import sqlite3
    from contextlib import contextmanager
    import threading
    
    # Fallback a SQLite
    DATABASE = 'scanner_db.sqlite'
    _local = threading.local()
    
    def get_db():
        if not hasattr(_local, 'connection'):
            _local.connection = sqlite3.connect(DATABASE, check_same_thread=False, timeout=5.0)
            _local.connection.execute('PRAGMA journal_mode=WAL')
            _local.connection.execute('PRAGMA synchronous=NORMAL')
            _local.connection.row_factory = sqlite3.Row
        return _local.connection
    
    @contextmanager
    def get_db_cursor():
        conn = get_db()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    
    _cache = {}
    _cache_timeout = {}
    CACHE_TTL = 30
    
    def get_cached(key):
        if key in _cache:
            if time.time() - _cache_timeout.get(key, 0) < CACHE_TTL:
                return _cache[key]
            else:
                del _cache[key]
                del _cache_timeout[key]
        return None
    
    def set_cached(key, value):
        _cache[key] = value
        _cache_timeout[key] = time.time()
    
    def clear_cache(pattern=None):
        if pattern:
            keys_to_delete = [k for k in _cache.keys() if pattern in k]
            for k in keys_to_delete:
                _cache.pop(k, None)
                _cache_timeout.pop(k, None)
        else:
            _cache.clear()
            _cache_timeout.clear()

app = Flask(__name__)
CORS(app)

# Configuración
API_SECRET_KEY = os.environ.get('API_SECRET_KEY', secrets.token_hex(32))

# ============================================================
# UTILIDADES DE BASE DE DATOS
# ============================================================

def init_db():
    """Inicializa la base de datos con todas las tablas e índices optimizados"""
    if USE_MYSQL:
        # Usar MySQL/PostgreSQL
        try:
            init_mysql_db()
            print("✅ Base de datos MySQL/PostgreSQL inicializada")
            return
        except Exception as e:
            print(f"❌ Error inicializando MySQL/PostgreSQL: {e}")
            print("❌ NO se usará SQLite como fallback para evitar pérdida de datos en deploys")
            print("❌ Verifica la configuración de DATABASE_URL o MYSQL_HOST")
            raise  # NO hacer fallback a SQLite, lanzar el error
    
    # Fallback a SQLite SOLO si NO hay MySQL/PostgreSQL configurado
    # (solo para desarrollo local)
    if not USE_MYSQL:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        # Configurar optimizaciones de SQLite
        cursor.execute('PRAGMA journal_mode=WAL')
        cursor.execute('PRAGMA synchronous=NORMAL')
        cursor.execute('PRAGMA cache_size=-64000')
        cursor.execute('PRAGMA temp_store=MEMORY')
        cursor.execute('PRAGMA mmap_size=268435456')
        cursor.execute('PRAGMA busy_timeout=5000')
    
    # Tabla de tokens de escaneo
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scan_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            used_count INTEGER DEFAULT 0,
            max_uses INTEGER DEFAULT -1,
            is_active BOOLEAN DEFAULT 1,
            created_by TEXT,
            description TEXT
        )
    ''')
    
    # Tabla de escaneos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scans (
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
        )
    ''')
    
    # Tabla de historial de bans
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ban_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            machine_id TEXT,
            minecraft_username TEXT,
            ip_address TEXT,
            ban_reason TEXT,
            hack_type TEXT,
            banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            scan_id INTEGER,
            FOREIGN KEY (scan_id) REFERENCES scans(id)
        )
    ''')
    
    # Tabla de resultados de escaneos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scan_results (
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
        )
    ''')
    
    # Tabla de análisis de IA
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ai_analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_id INTEGER,
            result_id INTEGER,
            analysis_type TEXT,
            ai_model TEXT,
            analysis_result TEXT,
            confidence REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (scan_id) REFERENCES scans(id),
            FOREIGN KEY (result_id) REFERENCES scan_results(id)
        )
    ''')
    
    # Tabla de actualizaciones de aplicación
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS app_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version TEXT UNIQUE NOT NULL,
            release_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            download_url TEXT,
            changelog TEXT,
            is_active BOOLEAN DEFAULT 1,
            file_size INTEGER,
            file_hash TEXT,
            min_required_version TEXT
        )
    ''')
    
    # Tabla de configuraciones
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS configurations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE NOT NULL,
            value TEXT,
            description TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Tabla de estadísticas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS statistics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date DATE DEFAULT CURRENT_DATE,
            total_scans INTEGER DEFAULT 0,
            total_issues_found INTEGER DEFAULT 0,
            unique_machines INTEGER DEFAULT 0,
            avg_scan_duration REAL
        )
    ''')
    
    # Tabla de feedback del staff (SISTEMA DE APRENDIZAJE)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS staff_feedback (
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
        )
    ''')
    
    # Tabla de patrones aprendidos (PATRONES APRENDIDOS POR IA)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS learned_patterns (
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
        )
    ''')
    
    # Migración: Agregar columna is_active si no existe
    try:
        cursor.execute('ALTER TABLE learned_patterns ADD COLUMN is_active BOOLEAN DEFAULT 1')
    except sqlite3.OperationalError:
        pass  # La columna ya existe
    
    # Tabla de hashes aprendidos (HASHES DE HACKS CONFIRMADOS)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS learned_hashes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_hash TEXT UNIQUE NOT NULL,
            is_hack BOOLEAN NOT NULL,
            confirmed_count INTEGER DEFAULT 1,
            first_confirmed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_confirmed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            source_feedback_id INTEGER,
            FOREIGN KEY (source_feedback_id) REFERENCES staff_feedback(id)
        )
    ''')
    
    # Tabla de versiones de modelo de IA (CONTROL DE VERSIONES DEL MODELO)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ai_model_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version TEXT UNIQUE NOT NULL,
            patterns_count INTEGER DEFAULT 0,
            hashes_count INTEGER DEFAULT 0,
            feedback_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT 1,
            model_file_path TEXT,
            changelog TEXT
        )
    ''')
    
    # Crear índices optimizados para consultas rápidas
    print("🔧 Creando índices optimizados...")
    
    # Índices para tokens
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tokens_active ON scan_tokens(is_active, expires_at)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tokens_token ON scan_tokens(token)')
    
    # Índices para escaneos (CRÍTICOS para rendimiento)
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_scans_started ON scans(started_at DESC)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_scans_status ON scans(status)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_scans_token ON scans(scan_token)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_scans_machine ON scans(machine_id)')
    
    # Índices para resultados (MUY IMPORTANTES)
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_results_scan_id ON scan_results(scan_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_results_alert_level ON scan_results(alert_level)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_results_hash ON scan_results(file_hash)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_results_created ON scan_results(created_at DESC)')
    
    # Índices para análisis de IA
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_ai_scan_id ON ai_analyses(scan_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_ai_result_id ON ai_analyses(result_id)')
    
    # Índices para feedback
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_feedback_result_id ON staff_feedback(result_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_feedback_scan_id ON staff_feedback(scan_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_feedback_hash ON staff_feedback(file_hash)')
    
    # Índices para patrones aprendidos
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_patterns_active ON learned_patterns(is_active)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_patterns_value ON learned_patterns(pattern_value)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_patterns_type ON learned_patterns(pattern_type)')
    
    # Índices para hashes aprendidos
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_hashes_hash ON learned_hashes(file_hash)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_hashes_hack ON learned_hashes(is_hack)')
    
    # Índices para versiones
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_versions_active ON app_versions(is_active, release_date DESC)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_model_versions_active ON ai_model_versions(is_active, created_at DESC)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_config_key ON configurations(key)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_stats_date ON statistics(date DESC)')
    
    # Migración: Agregar nuevas columnas si no existen
    try:
        cursor.execute('PRAGMA table_info(scans)')
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'country' not in columns:
            cursor.execute('ALTER TABLE scans ADD COLUMN country TEXT')
            print("✅ Columna 'country' agregada a tabla scans")
        
        if 'minecraft_username' not in columns:
            cursor.execute('ALTER TABLE scans ADD COLUMN minecraft_username TEXT')
            print("✅ Columna 'minecraft_username' agregada a tabla scans")
    except Exception as e:
        print(f"⚠️ Error en migración: {e}")
    
    # Crear índices para ban_history
    try:
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_ban_machine ON ban_history(machine_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_ban_username ON ban_history(minecraft_username)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_ban_ip ON ban_history(ip_address)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_ban_date ON ban_history(banned_at DESC)')
    except Exception as e:
        print(f"⚠️ Error creando índices de ban_history: {e}")
    
        conn.commit()
        conn.close()
        print("✅ Base de datos SQLite inicializada con índices optimizados")

# Inicializar base de datos inmediatamente al cargar el módulo
# Esto asegura que las tablas existan siempre, sin importar cómo se ejecute la app
# (funciona tanto con ejecución directa como con gunicorn)
try:
    init_db()
    print("✅ Base de datos inicializada al cargar el módulo")
except Exception as e:
    print(f"⚠️ Error inicializando base de datos al cargar módulo: {e}")
    import traceback
    traceback.print_exc()

# ============================================================
# UTILIDADES DE AUTENTICACIÓN
# ============================================================

def require_api_key(f):
    """Decorador para requerir API key en endpoints protegidos"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # En desarrollo, permitir sin API key si no se proporciona
        api_key = request.headers.get('X-API-Key') or request.args.get('api_key')
        if api_key and api_key != API_SECRET_KEY:
            return jsonify({'error': 'API key inválida'}), 401
        # Si no se proporciona API key, permitir en desarrollo (modo permisivo)
        return f(*args, **kwargs)
    return decorated_function

def _get_result_value(result, key_or_index):
    """Helper para obtener valores de resultados (compatible SQLite/MySQL)"""
    if USE_MYSQL:
        # MySQL con DictCursor retorna diccionarios
        return result.get(key_or_index) if isinstance(result, dict) else result[key_or_index]
    else:
        # SQLite retorna tuplas o Row objects
        if isinstance(result, sqlite3.Row):
            return result[key_or_index]
        elif isinstance(key_or_index, int):
            return result[key_or_index]
        else:
            # Intentar como índice numérico
            return result[0]

def validate_scan_token(token):
    """Valida un token de escaneo - OPTIMIZADO CON CACHÉ"""
    # Verificar caché primero
    cache_key = f'token_{hashlib.md5(token.encode()).hexdigest()}'
    cached = get_cached(cache_key)
    if cached:
        print(f"🔍 Token encontrado en caché: {cached.get('error', 'válido')}")
        return cached['token_id'], cached.get('error')
    
    try:
        print(f"🔍 Buscando token en BD: {token[:20]}...")
        with get_db_cursor() as cursor:
            # Usar %s para MySQL, ? para SQLite
            placeholder = '%s' if USE_MYSQL else '?'
            cursor.execute(f'''
                SELECT id, expires_at, used_count, max_uses, is_active
                FROM scan_tokens
                WHERE token = {placeholder}
            ''', (token,))
            
            result = cursor.fetchone()
            
            if not result:
                # Verificar si el token existe con diferentes formatos (por si hay espacios)
                cursor.execute('SELECT COUNT(*) as count FROM scan_tokens')
                total_result = cursor.fetchone()
                total_tokens = _get_result_value(total_result, 'count') if USE_MYSQL else total_result[0]
                print(f"⚠️ Token no encontrado. Total de tokens en BD: {total_tokens}")
                print(f"⚠️ Token buscado (primeros 30 chars): {token[:30]}")
                
                # Listar algunos tokens para debug (solo primeros caracteres)
                cursor.execute('SELECT token FROM scan_tokens ORDER BY created_at DESC LIMIT 5')
                sample_tokens = cursor.fetchall()
                if sample_tokens:
                    print(f"📋 Tokens recientes en BD:")
                    for t in sample_tokens:
                        token_val = _get_result_value(t, 'token') if USE_MYSQL else t[0]
                        print(f"   - {token_val[:30]}...")
                
                result_data = {'token_id': None, 'error': 'Token no encontrado'}
                set_cached(cache_key, result_data)
                return None, "Token no encontrado"
            
            # Extraer valores según el tipo de BD
            if USE_MYSQL:
                token_id = result.get('id')
                expires_at = result.get('expires_at')
                used_count = result.get('used_count', 0)
                max_uses = result.get('max_uses', -1)
                is_active = result.get('is_active', 1)
            else:
                token_id = result[0]
                expires_at = result[1]
                used_count = result[2] if len(result) > 2 else 0
                max_uses = result[3] if len(result) > 3 else -1
                is_active = result[4] if len(result) > 4 else 1
            
            if not is_active:
                result_data = {'token_id': None, 'error': 'Token desactivado'}
                set_cached(cache_key, result_data)
                return None, "Token desactivado"
            
            if expires_at:
                if isinstance(expires_at, str):
                    expires = datetime.datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                else:
                    expires = expires_at
                if datetime.datetime.now() > expires:
                    result_data = {'token_id': None, 'error': 'Token expirado'}
                    set_cached(cache_key, result_data)
                    return None, "Token expirado"
            
            if max_uses > 0 and used_count >= max_uses:
                result_data = {'token_id': None, 'error': 'Token ha alcanzado el límite de usos'}
                set_cached(cache_key, result_data)
                return None, "Token ha alcanzado el límite de usos"
            
            result_data = {'token_id': token_id, 'error': None}
            set_cached(cache_key, result_data)
            print(f"✅ Token válido encontrado: ID={token_id}, activo={is_active}, usado={used_count}/{max_uses if max_uses > 0 else '∞'}")
            return token_id, None
    except Exception as e:
        print(f"❌ Error validando token: {str(e)}")
        import traceback
        traceback.print_exc()
        return None, f"Error validando token: {str(e)}"

# ============================================================
# HEALTH CHECK Y ENDPOINTS BÁSICOS
# ============================================================

@app.route('/')
def root():
    """Endpoint raíz - verifica que la API funciona"""
    return jsonify({
        'status': 'ok',
        'service': 'aspers-api',
        'version': '1.0',
        'message': 'API is running',
        'endpoints': [
            '/health',
            '/api/statistics',
            '/api/scans'
        ]
    }), 200

@app.route('/health')
@app.route('/healthz')
def health_check():
    """Health check para Render"""
    return jsonify({
        'status': 'ok',
        'service': 'aspers-api',
        'timestamp': datetime.datetime.now().isoformat()
    }), 200

@app.route('/api/statistics', methods=['GET'])
def get_statistics():
    """Obtiene estadísticas del sistema - OPTIMIZADO CON CACHÉ Y QUERY ÚNICA"""
    # Verificar caché primero (30 segundos TTL)
    cache_key = 'statistics'
    cached = get_cached(cache_key)
    if cached:
        return jsonify(cached), 200
    
    try:
        # Obtener todas las estadísticas en una sola transacción
        with get_db_cursor() as cursor:
            # Inicializar valores por defecto
            stats = {
                'total_scans': 0,
                'active_scans': 0,
                'unique_machines': 0,
                'severe_detections': 0,
                'total_results': 0,
                'active_tokens': 0,
                'total_bans': 0
            }
            
            # Consulta optimizada: obtener múltiples conteos en una sola query usando subconsultas
            # Esto es MUCHO más rápido que hacer 7 consultas separadas
            try:
                cursor.execute('''
                    SELECT 
                        (SELECT COUNT(*) FROM scans) as total_scans,
                        (SELECT COUNT(*) FROM scans WHERE status = "running") as active_scans,
                        (SELECT COUNT(DISTINCT machine_id) FROM scans WHERE machine_id IS NOT NULL AND machine_id != "") as unique_machines,
                        (SELECT COUNT(*) FROM scan_results WHERE alert_level = "CRITICAL") as severe_detections,
                        (SELECT COUNT(*) FROM scan_results) as total_results,
                        (SELECT COUNT(*) FROM scan_tokens WHERE is_active = 1) as active_tokens,
                        (SELECT COUNT(*) FROM ban_history) as total_bans
                ''')
                row = cursor.fetchone()
                if row:
                    stats['total_scans'] = row[0] or 0
                    stats['active_scans'] = row[1] or 0
                    stats['unique_machines'] = row[2] or 0
                    stats['severe_detections'] = row[3] or 0
                    stats['total_results'] = row[4] or 0
                    stats['active_tokens'] = row[5] or 0
                    stats['total_bans'] = row[6] or 0
            except sqlite3.OperationalError as e:
                # Si alguna tabla no existe, intentar consultas individuales como fallback
                try:
                    cursor.execute('SELECT COUNT(*) FROM scans')
                    stats['total_scans'] = cursor.fetchone()[0] or 0
                except sqlite3.OperationalError:
                    pass
                
                try:
                    cursor.execute('SELECT COUNT(*) FROM scans WHERE status = "running"')
                    stats['active_scans'] = cursor.fetchone()[0] or 0
                except sqlite3.OperationalError:
                    pass
                
                try:
                    cursor.execute('SELECT COUNT(DISTINCT machine_id) FROM scans WHERE machine_id IS NOT NULL AND machine_id != ""')
                    stats['unique_machines'] = cursor.fetchone()[0] or 0
                except sqlite3.OperationalError:
                    pass
                
                try:
                    cursor.execute('SELECT COUNT(*) FROM scan_results WHERE alert_level = "CRITICAL"')
                    stats['severe_detections'] = cursor.fetchone()[0] or 0
                except sqlite3.OperationalError:
                    pass
                
                try:
                    cursor.execute('SELECT COUNT(*) FROM scan_results')
                    stats['total_results'] = cursor.fetchone()[0] or 0
                except sqlite3.OperationalError:
                    pass
                
                try:
                    cursor.execute('SELECT COUNT(*) FROM scan_tokens WHERE is_active = 1')
                    stats['active_tokens'] = cursor.fetchone()[0] or 0
                except sqlite3.OperationalError:
                    pass
                
                try:
                    cursor.execute('SELECT COUNT(*) FROM ban_history')
                    stats['total_bans'] = cursor.fetchone()[0] or 0
                except sqlite3.OperationalError:
                    pass
        
        # Agregar timestamp
        stats['timestamp'] = datetime.datetime.now().isoformat()
        
        # Guardar en caché
        set_cached(cache_key, stats)
        
        return jsonify(stats), 200
    except Exception as e:
        return jsonify({
            'error': str(e),
            'status': 'error'
        }), 500

# ============================================================
# ENDPOINTS DE TOKENS
# ============================================================

@app.route('/api/debug/tokens', methods=['GET'])
def debug_list_tokens():
    """Endpoint de debug para listar tokens (sin autenticación, solo para diagnóstico)"""
    try:
        with get_db_cursor() as cursor:
            cursor.execute('SELECT COUNT(*) FROM scan_tokens')
            total = cursor.fetchone()[0]
            
            cursor.execute('''
                SELECT id, token, created_at, is_active, created_by
                FROM scan_tokens
                ORDER BY created_at DESC
                LIMIT 10
            ''')
            
            tokens = []
            for row in cursor.fetchall():
                tokens.append({
                    'id': row[0],
                    'token_preview': row[1][:30] + '...' if len(row[1]) > 30 else row[1],
                    'created_at': row[2],
                    'is_active': bool(row[3]),
                    'created_by': row[4]
                })
            
            return jsonify({
                'total_tokens': total,
                'recent_tokens': tokens
            }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/validate-token', methods=['POST'])
def validate_token_endpoint():
    """Endpoint público para validar tokens de escaneo (usado por el cliente)"""
    try:
        data = request.json or {}
        token = data.get('token', '').strip()
        
        if not token:
            print("❌ Validación: Token no proporcionado")
            return jsonify({'valid': False, 'error': 'Token no proporcionado'}), 400
        
        print(f"🔍 Validando token recibido: {token[:30]}... (longitud: {len(token)})")
        
        token_id, error = validate_scan_token(token)
        
        if error:
            print(f"❌ Token inválido: {error}")
            return jsonify({'valid': False, 'error': error}), 200
        
        print(f"✅ Token válido: ID={token_id}")
        return jsonify({
            'valid': True,
            'token_id': token_id,
            'message': 'Token válido'
        }), 200
    except Exception as e:
        print(f"❌ Error en validate_token_endpoint: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'valid': False, 'error': f'Error validando token: {str(e)}'}), 500

@app.route('/api/tokens', methods=['POST'])
def create_scan_token():
    """Crea un nuevo token de escaneo - SIN REQUIRE_API_KEY para permitir creación desde web app"""
    try:
        print(f"📥 ===== RECIBIENDO PETICIÓN PARA CREAR TOKEN =====")
        print(f"📥 Headers recibidos: {dict(request.headers)}")
        print(f"📥 Método: {request.method}")
        print(f"📥 Content-Type: {request.content_type}")
        
        data = request.json or {}
        if not data:
            print(f"⚠️ No se recibieron datos JSON, intentando leer como form data...")
            data = request.form.to_dict() or {}
        
        print(f"📥 Datos recibidos: {data}")
        print(f"📥 expires_days={data.get('expires_days')}, max_uses={data.get('max_uses')}, created_by={data.get('created_by')}")
        
        # Generar token único
        token = secrets.token_urlsafe(32)
        
        # Configuración del token
        expires_days = data.get('expires_days', 30)
        max_uses = data.get('max_uses', -1)  # -1 = ilimitado
        description = data.get('description', '')
        created_by = data.get('created_by', 'web_app')
        
        expires_at = None
        if expires_days > 0:
            expires_at = (datetime.datetime.now() + datetime.timedelta(days=expires_days)).isoformat()
        
        print(f"🔑 Token generado: {token[:30]}... (longitud: {len(token)})")
        
        try:
            with get_db_cursor() as cursor:
                # Verificar que la tabla existe
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='scan_tokens'")
                table_exists = cursor.fetchone()
                if not table_exists:
                    print("⚠️ Tabla scan_tokens no existe, inicializando BD...")
                    init_db()
                
                cursor.execute('''
                    INSERT INTO scan_tokens (token, expires_at, max_uses, description, created_by)
                    VALUES (?, ?, ?, ?, ?)
                ''', (token, expires_at, max_uses, description, created_by))
                
                token_id = cursor.lastrowid
                print(f"✅ Token insertado con ID: {token_id}, created_by='{created_by}'")
                
                # Verificar inmediatamente que se guardó correctamente
                placeholder = '%s' if USE_MYSQL else '?'
                cursor.execute(f'SELECT token, created_by, created_at FROM scan_tokens WHERE id = {placeholder}', (token_id,))
                verification = cursor.fetchone()
                if verification:
                    created_by_val = verification.get('created_by') if USE_MYSQL else verification[1]
                    created_at_val = verification.get('created_at') if USE_MYSQL else verification[2]
                    print(f"✅ Verificación: Token guardado correctamente - created_by='{created_by_val}', created_at={created_at_val}")
                else:
                    print(f"❌ ERROR: Token no encontrado después de insertar!")
                
                # Limpiar caché de tokens para asegurar que se vean los nuevos tokens
                clear_cache('tokens')
                clear_cache('token_')
                print(f"🗑️ Caché de tokens limpiado")
                
                # El commit se hace automáticamente por el context manager
                # Pero verificamos inmediatamente después
                cursor.execute(f'SELECT token, created_at FROM scan_tokens WHERE id = {placeholder}', (token_id,))
                saved_token = cursor.fetchone()
                if saved_token:
                    token_val = saved_token.get('token') if USE_MYSQL else saved_token[0]
                    created_at_val = saved_token.get('created_at') if USE_MYSQL else saved_token[1]
                    print(f"✅ Token guardado correctamente en BD: ID={token_id}, Token guardado={token_val[:30]}..., Creado={created_at_val}")
                else:
                    print(f"❌ ERROR: Token no se encontró después de guardar!")
                    return jsonify({'error': 'Error al guardar token en la base de datos'}), 500
                
                # Contar total de tokens
                cursor.execute('SELECT COUNT(*) as count FROM scan_tokens')
                total_result = cursor.fetchone()
                total_tokens = total_result.get('count') if USE_MYSQL else total_result[0]
                print(f"📊 Total de tokens en BD: {total_tokens}")
                
                # Verificar persistencia con una nueva consulta
                cursor.execute(f'SELECT COUNT(*) as count FROM scan_tokens WHERE id = {placeholder}', (token_id,))
                token_result = cursor.fetchone()
                token_exists = token_result.get('count') if USE_MYSQL else token_result[0]
                if token_exists == 0:
                    print(f"❌ ERROR CRÍTICO: Token no persistido después del commit!")
                    return jsonify({'error': 'Error al persistir token en la base de datos'}), 500
                
                # Limpiar caché relacionado (importante para que la validación funcione)
                clear_cache('tokens')
                clear_cache('token_')
                print(f"🧹 Caché limpiado")
                
                print(f"✅ Token creado exitosamente: ID={token_id}, Token={token[:30]}..., Creado por={created_by}")
                
                return jsonify({
                    'success': True,
                    'token': token,
                    'token_id': token_id,
                    'expires_at': expires_at,
                    'max_uses': max_uses
                }), 201
        except Exception as e:
            print(f"❌ Error en transacción de creación de token: {str(e)}")
            import traceback
            traceback.print_exc()
            raise
    except Exception as e:
        print(f"❌ Error creando token: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/tokens', methods=['GET'])
@require_api_key
def list_tokens():
    """Lista todos los tokens de escaneo - OPTIMIZADO"""
    # NO usar caché para asegurar que siempre se obtengan los tokens más recientes
    # cache_key = 'tokens_list'
    # cached = get_cached(cache_key)
    # if cached:
    #     return jsonify(cached)
    
    try:
        with get_db_cursor() as cursor:
            # Verificar que la tabla existe
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='scan_tokens'")
            table_exists = cursor.fetchone()
            if not table_exists:
                print("⚠️ Tabla scan_tokens no existe, inicializando BD...")
                init_db()
            
            cursor.execute('''
                SELECT id, token, created_at, expires_at, used_count, max_uses, 
                       is_active, created_by, description
                FROM scan_tokens
                ORDER BY created_at DESC
                LIMIT 100
            ''')
            
            tokens = []
            for row in cursor.fetchall():
                tokens.append({
                    'id': row[0],
                    'token': row[1],
                    'created_at': row[2],
                    'expires_at': row[3],
                    'used_count': row[4],
                    'max_uses': row[5],
                    'is_active': bool(row[6]),
                    'created_by': row[7],
                    'description': row[8]
                })
            
            print(f"📋 Listando tokens: {len(tokens)} tokens encontrados")
            if tokens:
                print(f"📋 Primer token: ID={tokens[0].get('id')}, created_by={tokens[0].get('created_by')}")
            result = {'tokens': tokens, 'count': len(tokens)}
            # NO cachear para asegurar datos frescos
            # set_cached(cache_key, result)
            return jsonify(result)
    except Exception as e:
        print(f"❌ Error listando tokens: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/tokens/<int:token_id>', methods=['DELETE'])
@require_api_key
def delete_token(token_id):
    """Elimina permanentemente un token - OPTIMIZADO"""
    try:
        with get_db_cursor() as cursor:
            cursor.execute('SELECT token FROM scan_tokens WHERE id = ?', (token_id,))
            if not cursor.fetchone():
                return jsonify({'success': False, 'error': 'Token no encontrado'}), 404
            
            cursor.execute('DELETE FROM scan_tokens WHERE id = ?', (token_id,))
            clear_cache('tokens')
            clear_cache('token_')
            
            return jsonify({'success': True, 'message': 'Token eliminado permanentemente'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================================
# ENDPOINTS DE ESCANEOS
# ============================================================

@app.route('/api/scans', methods=['POST'])
def start_scan():
    """Inicia un nuevo escaneo"""
    data = request.json
    scan_token = data.get('token')
    machine_id = data.get('machine_id', '')
    machine_name = data.get('machine_name', '')
    ip_address = data.get('ip_address') or request.remote_addr
    country = data.get('country', '')
    minecraft_username = data.get('minecraft_username', '')
    
    # Validar token
    token_id, error = validate_scan_token(scan_token)
    if error:
        return jsonify({'error': error}), 401
    
    # Buscar historial de bans previos
    previous_bans = []
    if machine_id or minecraft_username or ip_address:
        try:
            with get_db_cursor() as cursor:
                ban_conditions = []
                ban_params = []
                
                if machine_id:
                    ban_conditions.append('machine_id = ?')
                    ban_params.append(machine_id)
                if minecraft_username:
                    ban_conditions.append('minecraft_username = ?')
                    ban_params.append(minecraft_username)
                if ip_address:
                    ban_conditions.append('ip_address = ?')
                    ban_params.append(ip_address)
                
                if ban_conditions:
                    query = f'''
                        SELECT ban_reason, hack_type, banned_at, scan_id
                        FROM ban_history
                        WHERE {' OR '.join(ban_conditions)}
                        ORDER BY banned_at DESC
                        LIMIT 10
                    '''
                    cursor.execute(query, ban_params)
                    previous_bans = [
                        {
                            'reason': row[0],
                            'hack_type': row[1],
                            'banned_at': row[2],
                            'scan_id': row[3]
                        }
                        for row in cursor.fetchall()
                    ]
        except Exception as e:
            print(f"Error buscando bans previos: {e}")
    
    # Incrementar contador de usos y desactivar si alcanzó el límite - OPTIMIZADO
    try:
        with get_db_cursor() as cursor:
            # Actualizar contador de usos del token
            cursor.execute('''
                UPDATE scan_tokens 
                SET used_count = used_count + 1,
                    is_active = CASE 
                        WHEN max_uses > 0 AND (used_count + 1) >= max_uses THEN 0
                        ELSE is_active
                    END
                WHERE id = ?
            ''', (token_id,))
            
            # Verificar que el token se actualizó correctamente
            cursor.execute('SELECT used_count, is_active FROM scan_tokens WHERE id = ?', (token_id,))
            token_update = cursor.fetchone()
            if token_update:
                print(f"✅ Token actualizado: used_count={token_update[0]}, is_active={token_update[1]}")
            else:
                print(f"⚠️ ADVERTENCIA: No se pudo verificar actualización del token")
            
            # Crear registro de escaneo
            cursor.execute('''
                INSERT INTO scans (token_id, scan_token, status, machine_id, machine_name, ip_address, country, minecraft_username)
                VALUES (?, ?, 'running', ?, ?, ?, ?, ?)
            ''', (token_id, scan_token, machine_id, machine_name, ip_address, country, minecraft_username))
            
            scan_id = cursor.lastrowid
            print(f"✅ Escaneo creado con ID: {scan_id}")
            
            # Verificar que el escaneo se guardó correctamente
            cursor.execute('SELECT id, status FROM scans WHERE id = ?', (scan_id,))
            scan_check = cursor.fetchone()
            if scan_check:
                print(f"✅ Escaneo verificado: ID={scan_check[0]}, Status={scan_check[1]}")
            else:
                print(f"❌ ERROR: Escaneo no encontrado después de crear!")
            
            # Limpiar caché relacionado
            clear_cache('token_')
            clear_cache('statistics')
    except Exception as e:
        return jsonify({'error': f'Error iniciando escaneo: {str(e)}'}), 500
    
    return jsonify({
        'success': True,
        'scan_id': scan_id,
        'status': 'running',
        'message': 'Escaneo iniciado'
    }), 201

@app.route('/api/scans/<int:scan_id>/results', methods=['POST'])
def submit_scan_results(scan_id):
    """Recibe y almacena los resultados - OPTIMIZADO CON BATCH INSERT"""
    print(f"\n{'='*60}")
    print(f"📥 ===== RECIBIENDO RESULTADOS DE ESCANEO ======")
    print(f"📥 Scan ID: {scan_id}")
    print(f"📥 IP del cliente: {request.remote_addr}")
    print(f"📥 User-Agent: {request.headers.get('User-Agent', 'N/A')}")
    print(f"{'='*60}\n")
    
    data = request.json
    if not data:
        print(f"❌ ERROR: No se recibieron datos JSON")
        return jsonify({'error': 'No se recibieron datos'}), 400
    
    print(f"📥 Datos recibidos:")
    print(f"   - Status: {data.get('status', 'N/A')}")
    print(f"   - Total archivos escaneados: {data.get('total_files_scanned', 0)}")
    print(f"   - Issues encontrados: {data.get('issues_found', 0)}")
    print(f"   - Duración: {data.get('scan_duration', 0)}s")
    print(f"   - Cantidad de resultados: {len(data.get('results', []))}")
    
    try:
        with get_db_cursor() as cursor:
            # Verificar que el escaneo existe
            cursor.execute('SELECT id, status FROM scans WHERE id = ?', (scan_id,))
            scan_row = cursor.fetchone()
            if not scan_row:
                print(f"❌ ERROR: Scan ID {scan_id} no existe en la BD")
                return jsonify({'error': f'Escaneo {scan_id} no encontrado'}), 404
            
            print(f"✅ Scan encontrado en BD - Status actual: {scan_row[1]}")
            
            # Actualizar estado del escaneo
            cursor.execute('''
                UPDATE scans 
                SET status = ?, completed_at = CURRENT_TIMESTAMP, 
                    total_files_scanned = ?, issues_found = ?, scan_duration = ?
                WHERE id = ?
            ''', (
                data.get('status', 'completed'),
                data.get('total_files_scanned', 0),
                data.get('issues_found', 0),
                data.get('scan_duration', 0),
                scan_id
            ))
            print(f"✅ Estado del escaneo actualizado")
            
            # Insertar resultados en batch (mucho más rápido)
            results = data.get('results', [])
            if results:
                print(f"📥 Preparando {len(results)} resultados para insertar...")
                # Preparar datos para batch insert
                batch_data = []
                for idx, result in enumerate(results):
                    # Mapear campos: el scanner envía 'tipo', 'nombre', 'ruta', 'archivo', etc.
                    # La BD espera: issue_type, issue_name, issue_path, etc.
                    issue_type = result.get('tipo', '')
                    issue_name = result.get('nombre', '') or result.get('archivo', '')
                    issue_path = result.get('ruta', '')
                    issue_category = result.get('categoria', '')
                    alert_level = result.get('alerta', '')
                    
                    batch_data.append((
                        scan_id,
                        issue_type,
                        issue_name,
                        issue_path,
                        issue_category,
                        alert_level,
                        result.get('confidence', 0),
                        json.dumps(result.get('detected_patterns', [])),
                        result.get('obfuscation', False),
                        result.get('file_hash', ''),
                        result.get('ai_analysis', ''),
                        result.get('ai_confidence', 0)
                    ))
                    if idx < 3:  # Mostrar primeros 3 resultados como ejemplo
                        print(f"   Resultado {idx+1}: {result.get('nombre', 'N/A')} - {result.get('tipo', 'N/A')}")
                
                # Batch insert (mucho más rápido que inserts individuales)
                cursor.executemany('''
                    INSERT INTO scan_results (
                        scan_id, issue_type, issue_name, issue_path, issue_category,
                        alert_level, confidence, detected_patterns, obfuscation_detected,
                        file_hash, ai_analysis, ai_confidence
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', batch_data)
                
                print(f"✅ Batch insert completado para {len(results)} resultados")
                
                # El commit se hace automáticamente por el context manager
                # Verificar cuántos resultados se insertaron DESPUÉS del commit
                cursor.execute('SELECT COUNT(*) FROM scan_results WHERE scan_id = ?', (scan_id,))
                total_inserted = cursor.fetchone()[0]
                print(f"✅ Verificación después del commit: {total_inserted} resultados en BD para este scan")
                
                if total_inserted < len(results):
                    print(f"⚠️ ADVERTENCIA: Se insertaron {len(results)} resultados pero solo {total_inserted} están en BD")
                else:
                    print(f"✅ Todos los resultados fueron insertados correctamente")
            else:
                print(f"⚠️ No hay resultados para insertar (lista vacía)")
            
            # Limpiar caché relacionado
            clear_cache('statistics')
            clear_cache(f'scan_{scan_id}')
            clear_cache('scans_list')
            print(f"✅ Caché limpiado")
        
        print(f"✅ ===== RESULTADOS ALMACENADOS EXITOSAMENTE ======\n")
        return jsonify({'success': True, 'message': 'Resultados almacenados'})
    except Exception as e:
        import traceback
        print(f"\n❌ ===== ERROR ALMACENANDO RESULTADOS ======")
        print(f"❌ Error: {str(e)}")
        print(f"❌ Traceback:")
        print(traceback.format_exc())
        print(f"{'='*60}\n")
        return jsonify({'error': f'Error almacenando resultados: {str(e)}'}), 500

@app.route('/api/scans/<int:scan_id>', methods=['GET'])
def get_scan(scan_id):
    """Obtiene información de un escaneo - OPTIMIZADO CON CACHÉ"""
    cache_key = f'scan_{scan_id}'
    cached = get_cached(cache_key)
    if cached:
        return jsonify(cached)
    
    try:
        with get_db_cursor() as cursor:
            cursor.execute('''
                SELECT id, token_id, scan_token, started_at, completed_at, status,
                       total_files_scanned, issues_found, scan_duration, machine_id, machine_name,
                       ip_address, country, minecraft_username
                FROM scans
                WHERE id = ?
            ''', (scan_id,))
            
            row = cursor.fetchone()
            if not row:
                return jsonify({'error': 'Escaneo no encontrado'}), 404
            
            scan = {
                'id': row[0],
                'token_id': row[1],
                'scan_token': row[2],
                'started_at': row[3],
                'completed_at': row[4],
                'status': row[5],
                'total_files_scanned': row[6],
                'issues_found': row[7],
                'scan_duration': row[8],
                'machine_id': row[9],
                'machine_name': row[10],
                'ip_address': row[11] if len(row) > 11 else None,
                'country': row[12] if len(row) > 12 else None,
                'minecraft_username': row[13] if len(row) > 13 else None
            }
            
            # Buscar historial de bans para este usuario
            ban_history = []
            if scan.get('machine_id') or scan.get('minecraft_username') or scan.get('ip_address'):
                cursor.execute('''
                    SELECT ban_reason, hack_type, banned_at, scan_id
                    FROM ban_history
                    WHERE (machine_id = ? OR minecraft_username = ? OR ip_address = ?)
                    ORDER BY banned_at DESC
                    LIMIT 10
                ''', (scan.get('machine_id', ''), scan.get('minecraft_username', ''), scan.get('ip_address', '')))
                
                ban_history = [
                    {
                        'reason': row[0],
                        'hack_type': row[1],
                        'banned_at': row[2],
                        'scan_id': row[3]
                    }
                    for row in cursor.fetchall()
                ]
            
            scan['ban_history'] = ban_history
            
            # Obtener resultados con estadísticas de severidad
            cursor.execute('''
                SELECT id, issue_type, issue_name, issue_path, issue_category,
                       alert_level, confidence, detected_patterns, obfuscation_detected,
                       file_hash, ai_analysis, ai_confidence
                FROM scan_results
                WHERE scan_id = ?
            ''', (scan_id,))
            
            results = []
            critical_count = 0
            suspicious_count = 0
            low_count = 0
            
            for r in cursor.fetchall():
                alert_level = r[5] or 'NORMAL'
                if alert_level == 'CRITICAL':
                    critical_count += 1
                elif alert_level in ['SOSPECHOSO', 'HACKS']:
                    suspicious_count += 1
                elif alert_level == 'POCO_SOSPECHOSO':
                    low_count += 1
                
                results.append({
                    'id': r[0],
                    'issue_type': r[1],
                    'issue_name': r[2],
                    'issue_path': r[3],
                    'issue_category': r[4],
                    'alert_level': r[5],
                    'confidence': r[6],
                    'detected_patterns': json.loads(r[7]) if r[7] else [],
                    'obfuscation_detected': bool(r[8]),
                    'file_hash': r[9],
                    'ai_analysis': r[10],
                    'ai_confidence': r[11]
                })
            
            scan['results'] = results
            
            # Calcular resumen de severidad para preview
            total_issues = len(results)
            if critical_count > 0:
                scan['severity_summary'] = 'CRITICO'
                scan['severity_badge'] = 'danger'
            elif suspicious_count > 0:
                scan['severity_summary'] = 'SOSPECHOSO'
                scan['severity_badge'] = 'warning'
            elif low_count > 0:
                scan['severity_summary'] = 'POCO_SOSPECHOSO'
                scan['severity_badge'] = 'info'
            elif total_issues == 0:
                scan['severity_summary'] = 'LIMPIO'
                scan['severity_badge'] = 'success'
            else:
                scan['severity_summary'] = 'NORMAL'
                scan['severity_badge'] = 'secondary'
            
            scan['severity_stats'] = {
                'critical': critical_count,
                'suspicious': suspicious_count,
                'low': low_count,
                'total': total_issues
            }
            
            # Verificar feedback en batch (más eficiente)
            if results:
                result_ids = [r['id'] for r in results]
                placeholders = ','.join(['?'] * len(result_ids))
                cursor.execute(f'''
                    SELECT result_id, staff_verification FROM staff_feedback
                    WHERE result_id IN ({placeholders})
                    ORDER BY verified_at DESC
                ''', result_ids)
                
                feedback_map = {}
                for row in cursor.fetchall():
                    if row[0] not in feedback_map:  # Solo el más reciente
                        feedback_map[row[0]] = row[1]
                
                for result in results:
                    result['feedback_status'] = feedback_map.get(result['id'])
            
            set_cached(cache_key, scan)
            return jsonify(scan)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/scans/<int:scan_id>/report-html', methods=['GET'])
def generate_scan_report_html(scan_id):
    """Genera un reporte HTML descargable para un escaneo específico"""
    import sqlite3
    from datetime import datetime
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    # Obtener información del escaneo
    cursor.execute('''
        SELECT id, started_at, completed_at, status,
               total_files_scanned, issues_found, scan_duration, machine_id, machine_name
        FROM scans
        WHERE id = ?
    ''', (scan_id,))
    
    row = cursor.fetchone()
    if not row:
        conn.close()
        return jsonify({'error': 'Escaneo no encontrado'}), 404
    
    scan = {
        'id': row[0],
        'started_at': row[1],
        'completed_at': row[2],
        'status': row[3],
        'total_files_scanned': row[4],
        'issues_found': row[5],
        'scan_duration': row[6],
        'machine_id': row[7],
        'machine_name': row[8]
    }
    
    # Obtener resultados con feedback
    cursor.execute('''
        SELECT sr.id, sr.issue_type, sr.issue_name, sr.issue_path, sr.issue_category,
               sr.alert_level, sr.confidence, sr.detected_patterns, sr.obfuscation_detected,
               sr.file_hash, sr.ai_analysis, sr.ai_confidence,
               sf.staff_verification, sf.staff_notes, sf.verified_at
        FROM scan_results sr
        LEFT JOIN staff_feedback sf ON sr.id = sf.result_id
        WHERE sr.scan_id = ?
        ORDER BY 
            CASE sr.alert_level
                WHEN 'CRITICAL' THEN 1
                WHEN 'SOSPECHOSO' THEN 2
                WHEN 'POCO_SOSPECHOSO' THEN 3
                ELSE 4
            END,
            sr.confidence DESC
    ''', (scan_id,))
    
    results = []
    for r in cursor.fetchall():
        results.append({
            'id': r[0],
            'issue_type': r[1],
            'issue_name': r[2],
            'issue_path': r[3],
            'issue_category': r[4],
            'alert_level': r[5],
            'confidence': r[6],
            'detected_patterns': json.loads(r[7]) if r[7] else [],
            'obfuscation_detected': bool(r[8]),
            'file_hash': r[9],
            'ai_analysis': r[10],
            'ai_confidence': r[11],
            'feedback': r[12],
            'feedback_notes': r[13],
            'feedback_date': r[14]
        })
    
    conn.close()
    
    # Generar HTML
    html = f'''<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ASPERS Projects - Reporte de Escaneo #{scan_id}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: #0a0e27;
            color: #f0f6fc;
            line-height: 1.6;
            padding: 2rem;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: #161b22;
            border-radius: 12px;
            padding: 2rem;
            border: 1px solid #30363d;
        }}
        .header {{
            border-bottom: 2px solid #1f6feb;
            padding-bottom: 1.5rem;
            margin-bottom: 2rem;
        }}
        .header h1 {{
            color: #1f6feb;
            font-size: 2rem;
            margin-bottom: 0.5rem;
        }}
        .header p {{
            color: #8b949e;
            font-size: 0.9rem;
        }}
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }}
        .summary-card {{
            background: #0d1117;
            padding: 1.5rem;
            border-radius: 8px;
            border: 1px solid #30363d;
        }}
        .summary-card h3 {{
            color: #8b949e;
            font-size: 0.875rem;
            margin-bottom: 0.5rem;
        }}
        .summary-card .value {{
            color: #1f6feb;
            font-size: 1.5rem;
            font-weight: 600;
        }}
        .issue-card {{
            background: #0d1117;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 1.5rem;
            margin-bottom: 1rem;
            border-left: 4px solid #30363d;
        }}
        .issue-card.critical {{
            border-left-color: #f85149;
        }}
        .issue-card.suspicious {{
            border-left-color: #d29922;
        }}
        .issue-card.low {{
            border-left-color: #58a6ff;
        }}
        .issue-header {{
            display: flex;
            justify-content: space-between;
            align-items: start;
            margin-bottom: 1rem;
        }}
        .issue-title {{
            color: #f0f6fc;
            font-size: 1.1rem;
            margin-bottom: 0.25rem;
        }}
        .issue-path {{
            color: #8b949e;
            font-size: 0.875rem;
            font-family: 'Consolas', monospace;
        }}
        .badge {{
            display: inline-block;
            padding: 0.25rem 0.75rem;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 600;
            margin-left: 0.5rem;
        }}
        .badge-danger {{
            background: #f85149;
            color: #fff;
        }}
        .badge-warning {{
            background: #d29922;
            color: #fff;
        }}
        .badge-info {{
            background: #58a6ff;
            color: #fff;
        }}
        .badge-success {{
            background: #238636;
            color: #fff;
        }}
        .issue-details {{
            margin-top: 1rem;
            padding-top: 1rem;
            border-top: 1px solid #30363d;
        }}
        .issue-details div {{
            margin-bottom: 0.5rem;
            color: #c9d1d9;
        }}
        .issue-details strong {{
            color: #8b949e;
        }}
        .issue-details code {{
            background: #0d1117;
            padding: 0.25rem 0.5rem;
            border-radius: 4px;
            font-family: 'Consolas', monospace;
            font-size: 0.875rem;
            color: #58a6ff;
        }}
        .feedback-section {{
            margin-top: 1rem;
            padding: 1rem;
            background: #0d1117;
            border-radius: 6px;
            border: 1px solid #30363d;
        }}
        .feedback-section h4 {{
            color: #8b949e;
            font-size: 0.875rem;
            margin-bottom: 0.5rem;
        }}
        .footer {{
            margin-top: 3rem;
            padding-top: 2rem;
            border-top: 1px solid #30363d;
            text-align: center;
            color: #8b949e;
            font-size: 0.875rem;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔍 ASPERS Projects - Reporte de Escaneo</h1>
            <p>Generado el {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</p>
        </div>
        
        <div class="summary">
            <div class="summary-card">
                <h3>Escaneo ID</h3>
                <div class="value">#{scan['id']}</div>
            </div>
            <div class="summary-card">
                <h3>Máquina</h3>
                <div class="value">{scan['machine_name'] or 'N/A'}</div>
            </div>
            <div class="summary-card">
                <h3>Archivos Escaneados</h3>
                <div class="value">{scan['total_files_scanned'] or 0}</div>
            </div>
            <div class="summary-card">
                <h3>Issues Detectados</h3>
                <div class="value">{scan['issues_found'] or 0}</div>
            </div>
            <div class="summary-card">
                <h3>Duración</h3>
                <div class="value">{scan['scan_duration'] or 0:.1f}s</div>
            </div>
            <div class="summary-card">
                <h3>Fecha</h3>
                <div class="value">{scan['started_at'] or 'N/A'}</div>
            </div>
        </div>
        
        <h2 style="color: #1f6feb; margin-bottom: 1rem; margin-top: 2rem;">Issues Detectados</h2>
'''
    
    # Agregar cada issue
    for result in results:
        alert_class = 'critical' if result['alert_level'] == 'CRITICAL' else ('suspicious' if result['alert_level'] == 'SOSPECHOSO' else 'low')
        badge_class = 'danger' if result['alert_level'] == 'CRITICAL' else ('warning' if result['alert_level'] == 'SOSPECHOSO' else 'info')
        
        html += f'''
        <div class="issue-card {alert_class}">
            <div class="issue-header">
                <div>
                    <div class="issue-title">{result['issue_name'] or 'Issue Desconocido'}</div>
                    <div class="issue-path">{result['issue_path'] or 'N/A'}</div>
                </div>
                <div>
                    <span class="badge badge-{badge_class}">{result['alert_level'] or 'N/A'}</span>
                    {f'<span class="badge badge-info">{result["confidence"]}%</span>' if result.get('confidence') else ''}
                    {f'<span class="badge badge-success">✓ Verificado: {result["feedback"]}</span>' if result.get('feedback') else ''}
                </div>
            </div>
            <div class="issue-details">
                {f'<div><strong>Tipo:</strong> {result["issue_type"]}</div>' if result.get('issue_type') else ''}
                {f'<div><strong>Categoría:</strong> {result["issue_category"]}</div>' if result.get('issue_category') else ''}
                {f'<div><strong>Análisis IA:</strong> {result["ai_analysis"]}</div>' if result.get('ai_analysis') else ''}
                {f'<div><strong>Confianza IA:</strong> {result["ai_confidence"]}%</div>' if result.get('ai_confidence') else ''}
                {f'<div><strong>Patrones detectados:</strong> {", ".join(result["detected_patterns"])}</div>' if result.get('detected_patterns') and len(result['detected_patterns']) > 0 else ''}
                {f'<div><strong>Hash:</strong> <code>{result["file_hash"]}</code></div>' if result.get('file_hash') else ''}
                {f'<div><strong>Ofuscación detectada:</strong> {"Sí" if result["obfuscation_detected"] else "No"}</div>'}
            </div>
'''
        
        if result.get('feedback'):
            html += f'''
            <div class="feedback-section">
                <h4>Feedback del Staff</h4>
                <div><strong>Verificación:</strong> {result['feedback']}</div>
                {f'<div><strong>Notas:</strong> {result["feedback_notes"]}</div>' if result.get('feedback_notes') else ''}
                {f'<div><strong>Fecha:</strong> {result["feedback_date"]}</div>' if result.get('feedback_date') else ''}
            </div>
'''
        
        html += '</div>'
    
    html += f'''
        <div class="footer">
            <p>Reporte generado por ASPERS Projects - Sistema de Detección Avanzada</p>
            <p>Este reporte puede ser compartido con el staff superior para revisión de archivos sospechosos.</p>
        </div>
    </div>
</body>
</html>
'''
    
    from flask import Response
    return Response(html, mimetype='text/html', headers={
        'Content-Disposition': f'attachment; filename=ASPERS_Report_Scan_{scan_id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.html'
    })

@app.route('/api/scans', methods=['GET'])
@require_api_key
def list_scans():
    """Lista todos los escaneos - OPTIMIZADO CON CACHÉ Y QUERY ÚNICA"""
    limit = request.args.get('limit', 50, type=int)
    offset = request.args.get('offset', 0, type=int)
    
    cache_key = f'scans_list_{limit}_{offset}'
    cached = get_cached(cache_key)
    if cached:
        return jsonify(cached)
    
    try:
        with get_db_cursor() as cursor:
            cursor.execute('''
                SELECT id, scan_token, started_at, completed_at, status,
                       total_files_scanned, issues_found, scan_duration, machine_name
                FROM scans
                ORDER BY started_at DESC
                LIMIT ? OFFSET ?
            ''', (limit, offset))
            
            scans = []
            scan_ids = []
            for row in cursor.fetchall():
                scan_id = row[0]
                scan_ids.append(scan_id)
                scans.append({
                    'id': scan_id,
                    'scan_token': row[1],
                    'started_at': row[2],
                    'completed_at': row[3],
                    'status': row[4],
                    'total_files_scanned': row[5],
                    'issues_found': row[6],
                    'scan_duration': row[7],
                    'machine_name': row[8]
                })
            
            # Calcular preview de severidad para cada scan (una sola query optimizada)
            if scan_ids:
                placeholders = ','.join(['?'] * len(scan_ids))
                cursor.execute(f'''
                    SELECT scan_id, 
                           SUM(CASE WHEN alert_level = 'CRITICAL' THEN 1 ELSE 0 END) as critical,
                           SUM(CASE WHEN alert_level IN ('SOSPECHOSO', 'HACKS') THEN 1 ELSE 0 END) as suspicious,
                           SUM(CASE WHEN alert_level = 'POCO_SOSPECHOSO' THEN 1 ELSE 0 END) as low,
                           COUNT(*) as total
                    FROM scan_results
                    WHERE scan_id IN ({placeholders})
                    GROUP BY scan_id
                ''', scan_ids)
                
                severity_map = {}
                for row in cursor.fetchall():
                    scan_id, critical, suspicious, low, total = row
                    if critical > 0:
                        severity_map[scan_id] = {'summary': 'CRITICO', 'badge': 'danger'}
                    elif suspicious > 0:
                        severity_map[scan_id] = {'summary': 'SOSPECHOSO', 'badge': 'warning'}
                    elif low > 0:
                        severity_map[scan_id] = {'summary': 'POCO_SOSPECHOSO', 'badge': 'info'}
                    elif total == 0:
                        severity_map[scan_id] = {'summary': 'LIMPIO', 'badge': 'success'}
                    else:
                        severity_map[scan_id] = {'summary': 'NORMAL', 'badge': 'secondary'}
                
                # Agregar preview a cada scan
                for scan in scans:
                    if scan['id'] in severity_map:
                        scan['severity_summary'] = severity_map[scan['id']]['summary']
                        scan['severity_badge'] = severity_map[scan['id']]['badge']
                    else:
                        # Si no hay resultados, es limpio
                        scan['severity_summary'] = 'LIMPIO' if scan['issues_found'] == 0 else 'SOSPECHOSO'
                        scan['severity_badge'] = 'success' if scan['issues_found'] == 0 else 'warning'
            
            result = {'scans': scans}
            set_cached(cache_key, result)
            return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================================
# ENDPOINTS DE ACTUALIZACIONES
# ============================================================

@app.route('/api/versions', methods=['GET'])
def get_versions():
    """Obtiene todas las versiones disponibles"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, version, release_date, download_url, changelog,
               is_active, file_size, file_hash, min_required_version
        FROM app_versions
        WHERE is_active = 1
        ORDER BY release_date DESC
    ''')
    
    versions = []
    for row in cursor.fetchall():
        versions.append({
            'id': row[0],
            'version': row[1],
            'release_date': row[2],
            'download_url': row[3],
            'changelog': row[4],
            'is_active': bool(row[5]),
            'file_size': row[6],
            'file_hash': row[7],
            'min_required_version': row[8]
        })
    
    conn.close()
    return jsonify({'versions': versions})

@app.route('/api/versions/latest', methods=['GET'])
def get_latest_version():
    """Obtiene la última versión disponible"""
    current_version = request.args.get('current_version', '1.0.0')
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT version, release_date, download_url, changelog,
               file_size, file_hash, min_required_version
        FROM app_versions
        WHERE is_active = 1
        ORDER BY release_date DESC
        LIMIT 1
    ''')
    
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return jsonify({'update_available': False})
    
    latest_version = row[0]
    update_available = latest_version != current_version
    
    return jsonify({
        'update_available': update_available,
        'latest_version': latest_version,
        'current_version': current_version,
        'release_date': row[1],
        'download_url': row[2],
        'changelog': row[3],
        'file_size': row[4],
        'file_hash': row[5],
        'min_required_version': row[6]
    })

@app.route('/api/versions', methods=['POST'])
@require_api_key
def create_version():
    """Crea una nueva versión de la aplicación"""
    data = request.json
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO app_versions (
                version, download_url, changelog, file_size, file_hash, min_required_version
            ) VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            data.get('version'),
            data.get('download_url'),
            data.get('changelog', ''),
            data.get('file_size', 0),
            data.get('file_hash', ''),
            data.get('min_required_version', '1.0.0')
        ))
        
        conn.commit()
        version_id = cursor.lastrowid
        conn.close()
        
        return jsonify({
            'success': True,
            'version_id': version_id,
            'message': 'Versión creada exitosamente'
        }), 201
    except Exception as e:
        conn.close()
        return jsonify({'error': str(e)}), 500

# ============================================================
# ENDPOINTS DE ESTADÍSTICAS
# ============================================================

# ============================================================
# ENDPOINTS DE FEEDBACK Y APRENDIZAJE
# ============================================================

@app.route('/api/feedback', methods=['POST'])
@require_api_key
def submit_feedback():
    """El staff marca un resultado como hack o legítimo - OPTIMIZADO"""
    try:
        if not request.json:
            return jsonify({'error': 'No se recibieron datos JSON'}), 400
        
        data = request.json
        
        result_id = data.get('result_id')
        if not result_id:
            return jsonify({'error': 'Se requiere result_id'}), 400
        
        # Aceptar ambos formatos: 'verification' o 'staff_verification'
        staff_verification = data.get('verification') or data.get('staff_verification')
        # Aceptar ambos formatos: 'notes' o 'staff_notes'
        staff_notes = data.get('notes') or data.get('staff_notes', '')
        verified_by = data.get('verified_by', 'staff')
        
        if not staff_verification:
            return jsonify({'error': 'Se requiere verification o staff_verification'}), 400
        
        if staff_verification not in ['hack', 'legitimate']:
            return jsonify({'error': f'Verificación debe ser "hack" o "legitimate", recibido: "{staff_verification}"'}), 400
    except Exception as e:
        return jsonify({'error': f'Error procesando datos: {str(e)}'}), 400
    
    try:
        with get_db_cursor() as cursor:
            # Obtener información del resultado
            cursor.execute('''
                SELECT scan_id, issue_name, issue_path, file_hash, detected_patterns, 
                       obfuscation_detected, confidence
                FROM scan_results
                WHERE id = ?
            ''', (result_id,))
            
            result = cursor.fetchone()
            if not result:
                return jsonify({'error': f'Resultado con id {result_id} no encontrado en la base de datos'}), 404
            
            scan_id, issue_name, issue_path, file_hash, detected_patterns_json, obfuscation, confidence = result
            
            # Guardar feedback
            cursor.execute('''
                INSERT INTO staff_feedback (
                    result_id, scan_id, staff_verification, staff_notes, verified_by,
                    file_hash, issue_name, issue_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (result_id, scan_id, staff_verification, staff_notes, verified_by,
                  file_hash, issue_name, issue_path))
            
            feedback_id = cursor.lastrowid
    
            # Extraer características y patrones del hack confirmado
            extracted_patterns = []
            extracted_features = {}
            
            if staff_verification == 'hack':
                # Extraer patrones del nombre y ruta
                import re
                name_lower = (issue_name or '').lower()
                path_lower = (issue_path or '').lower()
                
                # Extraer palabras clave sospechosas
                hack_keywords = re.findall(r'\b(vape|entropy|inject|bypass|killaura|aimbot|reach|velocity|scaffold|fly|xray|ghost|stealth|undetected|sigma|flux|future|astolfo|whiteout|liquidbounce|wurst|impact)\w*\b', name_lower + ' ' + path_lower, re.IGNORECASE)
                extracted_patterns = list(set(hack_keywords))
                
                # Determinar tipo de hack principal
                hack_type = 'Unknown'
                if any(kw in ['killaura', 'aimbot', 'triggerbot'] for kw in extracted_patterns):
                    hack_type = 'Combat'
                elif any(kw in ['reach', 'velocity', 'hitbox'] for kw in extracted_patterns):
                    hack_type = 'Reach/Velocity'
                elif any(kw in ['xray', 'fullbright', 'esp'] for kw in extracted_patterns):
                    hack_type = 'Visual'
                elif any(kw in ['fly', 'scaffold', 'noclip'] for kw in extracted_patterns):
                    hack_type = 'Movement'
                elif any(kw in ['vape', 'entropy', 'sigma', 'flux'] for kw in extracted_patterns):
                    hack_type = 'Client'
                elif extracted_patterns:
                    hack_type = extracted_patterns[0].capitalize()
                
                # Registrar ban en historial si es un hack confirmado
                try:
                    # Obtener información del escaneo para el ban
                    cursor.execute('''
                        SELECT machine_id, minecraft_username, ip_address
                        FROM scans
                        WHERE id = ?
                    ''', (scan_id,))
                    
                    scan_info = cursor.fetchone()
                    if scan_info:
                        machine_id_ban = scan_info[0]
                        minecraft_username_ban = scan_info[1]
                        ip_address_ban = scan_info[2]
                        
                        # Registrar ban
                        cursor.execute('''
                            INSERT INTO ban_history (
                                machine_id, minecraft_username, ip_address,
                                ban_reason, hack_type, scan_id
                            ) VALUES (?, ?, ?, ?, ?, ?)
                        ''', (
                            machine_id_ban,
                            minecraft_username_ban,
                            ip_address_ban,
                            f'Hack confirmado: {issue_name}',
                            hack_type,
                            scan_id
                        ))
                except Exception as e:
                    print(f"Error registrando ban: {e}")
                
                # Guardar hash si existe
                if file_hash:
                    cursor.execute('''
                        INSERT OR REPLACE INTO learned_hashes (
                            file_hash, is_hack, confirmed_count, last_confirmed_at, source_feedback_id
                        ) VALUES (?, 1, 
                            COALESCE((SELECT confirmed_count FROM learned_hashes WHERE file_hash = ?), 0) + 1,
                            CURRENT_TIMESTAMP, ?
                        )
                    ''', (file_hash, file_hash, feedback_id))
                
                # Guardar patrones aprendidos en batch (más eficiente)
                if extracted_patterns:
                    pattern_data = [(pattern, feedback_id, pattern) for pattern in extracted_patterns]
                    cursor.executemany('''
                        INSERT OR REPLACE INTO learned_patterns (
                            pattern_type, pattern_value, pattern_category, source_feedback_id,
                            learned_from_count, last_updated_at
                        ) VALUES ('keyword', ?, 'high_risk',
                            ?,
                            COALESCE((SELECT learned_from_count FROM learned_patterns WHERE pattern_value = ?), 0) + 1,
                            CURRENT_TIMESTAMP
                        )
                    ''', pattern_data)
                
                extracted_features = {
                    'obfuscation': bool(obfuscation),
                    'confidence': confidence or 0,
                    'location_suspicious': any(x in path_lower for x in ['temp', 'downloads', 'desktop', 'appdata'])
                }
            
            elif staff_verification == 'legitimate':
                # Si es legítimo, guardar hash en whitelist y aprender patrones
                if file_hash:
                    cursor.execute('''
                        INSERT OR REPLACE INTO learned_hashes (
                            file_hash, is_hack, confirmed_count, last_confirmed_at, source_feedback_id
                        ) VALUES (?, 0, 
                            COALESCE((SELECT confirmed_count FROM learned_hashes WHERE file_hash = ?), 0) + 1,
                            CURRENT_TIMESTAMP, ?
                        )
                    ''', (file_hash, file_hash, feedback_id))
                
                # Aprender patrones legítimos del nombre y ruta
                if issue_name:
                    # Extraer palabras del nombre que son comunes en archivos legítimos
                    import re
                    name_words = re.findall(r'\b\w{4,}\b', issue_name.lower())
                    # Guardar palabras comunes como patrones legítimos
                    for word in name_words[:5]:  # Limitar a 5 palabras más relevantes
                        if len(word) > 3 and word not in ['file', 'path', 'name', 'minecraft', 'mod']:
                            # Verificar si la columna is_active existe antes de insertar
                            try:
                                cursor.execute('''
                                    INSERT OR IGNORE INTO learned_patterns (
                                        pattern_type, pattern_value, pattern_category, is_active, learned_from_count
                                    ) VALUES ('legitimate_keyword', ?, 'legitimate', 1, 1)
                                ''', (word,))
                            except sqlite3.OperationalError:
                                # Si la columna no existe, insertar sin ella
                                cursor.execute('''
                                    INSERT OR IGNORE INTO learned_patterns (
                                        pattern_type, pattern_value, pattern_category, learned_from_count
                                    ) VALUES ('legitimate_keyword', ?, 'legitimate', 1)
                                ''', (word,))
                
                # Actualizar contador de feedbacks legítimos para este archivo
                cursor.execute('''
                    SELECT COUNT(*) FROM staff_feedback 
                    WHERE file_hash = ? AND staff_verification = 'legitimate'
                ''', (file_hash,))
                legit_count = cursor.fetchone()[0]
                
                # Si hay múltiples confirmaciones de que es legítimo, aumentar confianza
                if legit_count >= 2:
                    cursor.execute('''
                        UPDATE learned_hashes 
                        SET confirmed_count = ?, is_active = 1
                        WHERE file_hash = ?
                    ''', (legit_count, file_hash))
            
            # Actualizar feedback con características extraídas
            cursor.execute('''
                UPDATE staff_feedback
                SET extracted_patterns = ?, extracted_features = ?
                WHERE id = ?
            ''', (json.dumps(extracted_patterns), json.dumps(extracted_features), feedback_id))
            
            # Verificar si hay suficientes feedbacks para actualizar el modelo (optimizado)
            cursor.execute('SELECT COUNT(*) FROM staff_feedback WHERE staff_verification = "hack"')
            hack_feedbacks = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM staff_feedback')
            total_feedbacks = cursor.fetchone()[0]
            
            # Limpiar caché relacionado
            clear_cache('scan_')
            clear_cache('statistics')
            clear_cache('learned')
            
            # Si hay 10+ hacks confirmados, sugerir actualización del modelo
            should_update = hack_feedbacks >= 10 and total_feedbacks >= 15
            
            return jsonify({
                'success': True,
                'feedback_id': feedback_id,
                'extracted_patterns': extracted_patterns,
                'extracted_features': extracted_features,
                'should_update_model': should_update,
                'message': 'Feedback guardado. Patrones extraídos y aprendidos.'
            }), 201
    except Exception as e:
        import traceback
        return jsonify({
            'error': f'Error inesperado al procesar feedback: {str(e)}',
            'traceback': traceback.format_exc()
        }), 500

@app.route('/api/feedback/batch', methods=['POST'])
@require_api_key
def submit_feedback_batch():
    """Procesa múltiples feedbacks a la vez - OPTIMIZADO"""
    try:
        if not request.json:
            return jsonify({'error': 'No se recibieron datos JSON'}), 400
        
        data = request.json
        
        result_ids = data.get('result_ids', [])
        if not result_ids or not isinstance(result_ids, list):
            return jsonify({'error': 'Se requiere result_ids como lista'}), 400
        
        if len(result_ids) == 0:
            return jsonify({'error': 'La lista de result_ids está vacía'}), 400
        
        # Aceptar ambos formatos: 'verification' o 'staff_verification'
        staff_verification = data.get('verification') or data.get('staff_verification')
        staff_notes = data.get('notes') or data.get('staff_notes', '')
        verified_by = data.get('verified_by', 'staff')
        
        if not staff_verification:
            return jsonify({'error': 'Se requiere verification o staff_verification'}), 400
        
        if staff_verification not in ['hack', 'legitimate']:
            return jsonify({'error': f'Verificación debe ser "hack" o "legitimate", recibido: "{staff_verification}"'}), 400
        
        # Procesar cada resultado
        results = []
        errors = []
        total_extracted_patterns = []
        
        with get_db_cursor() as cursor:
            for result_id in result_ids:
                try:
                    # Obtener información del resultado
                    cursor.execute('''
                        SELECT scan_id, issue_name, issue_path, file_hash, detected_patterns, 
                               obfuscation_detected, confidence
                        FROM scan_results
                        WHERE id = ?
                    ''', (result_id,))
                    
                    result = cursor.fetchone()
                    if not result:
                        errors.append(f'Resultado {result_id} no encontrado')
                        continue
                    
                    scan_id, issue_name, issue_path, file_hash, detected_patterns_json, obfuscation, confidence = result
                    
                    # Guardar feedback
                    cursor.execute('''
                        INSERT INTO staff_feedback (
                            result_id, scan_id, staff_verification, staff_notes, verified_by,
                            file_hash, issue_name, issue_path
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (result_id, scan_id, staff_verification, staff_notes, verified_by,
                          file_hash, issue_name, issue_path))
                    
                    feedback_id = cursor.lastrowid
                    
                    # Extraer características y patrones
                    extracted_patterns = []
                    extracted_features = {}
                    
                    if staff_verification == 'hack':
                        # Extraer patrones del nombre y ruta
                        import re
                        name_lower = (issue_name or '').lower()
                        path_lower = (issue_path or '').lower()
                        
                        # Extraer palabras clave sospechosas
                        hack_keywords = re.findall(r'\b(vape|entropy|inject|bypass|killaura|aimbot|reach|velocity|scaffold|fly|xray|ghost|stealth|undetected|sigma|flux|future|astolfo|whiteout|liquidbounce|wurst|impact)\w*\b', name_lower + ' ' + path_lower, re.IGNORECASE)
                        extracted_patterns = list(set(hack_keywords))
                        total_extracted_patterns.extend(extracted_patterns)
                        
                        # Guardar hash si existe
                        if file_hash:
                            cursor.execute('''
                                INSERT OR REPLACE INTO learned_hashes (
                                    file_hash, is_hack, confirmed_count, last_confirmed_at, source_feedback_id
                                ) VALUES (?, 1, 
                                    COALESCE((SELECT confirmed_count FROM learned_hashes WHERE file_hash = ?), 0) + 1,
                                    CURRENT_TIMESTAMP, ?
                                )
                            ''', (file_hash, file_hash, feedback_id))
                        
                        # Guardar patrones aprendidos en batch
                        if extracted_patterns:
                            pattern_data = [(pattern, feedback_id, pattern) for pattern in extracted_patterns]
                            cursor.executemany('''
                                INSERT OR REPLACE INTO learned_patterns (
                                    pattern_type, pattern_value, pattern_category, source_feedback_id,
                                    learned_from_count, last_updated_at
                                ) VALUES ('keyword', ?, 'high_risk',
                                    ?,
                                    COALESCE((SELECT learned_from_count FROM learned_patterns WHERE pattern_value = ?), 0) + 1,
                                    CURRENT_TIMESTAMP
                                )
                            ''', pattern_data)
                        
                        extracted_features = {
                            'obfuscation': bool(obfuscation),
                            'confidence': confidence or 0,
                            'location_suspicious': any(x in path_lower for x in ['temp', 'downloads', 'desktop', 'appdata'])
                        }
                    
                    elif staff_verification == 'legitimate':
                        # Si es legítimo, guardar hash en whitelist
                        if file_hash:
                            cursor.execute('''
                                INSERT OR REPLACE INTO learned_hashes (
                                    file_hash, is_hack, confirmed_count, last_confirmed_at, source_feedback_id
                                ) VALUES (?, 0, 
                                    COALESCE((SELECT confirmed_count FROM learned_hashes WHERE file_hash = ?), 0) + 1,
                                    CURRENT_TIMESTAMP, ?
                                )
                            ''', (file_hash, file_hash, feedback_id))
                        
                        # Aprender patrones legítimos del nombre
                        if issue_name:
                            import re
                            name_words = re.findall(r'\b\w{4,}\b', issue_name.lower())
                            for word in name_words[:5]:
                                if len(word) > 3 and word not in ['file', 'path', 'name', 'minecraft', 'mod']:
                                    try:
                                        cursor.execute('''
                                            INSERT OR IGNORE INTO learned_patterns (
                                                pattern_type, pattern_value, pattern_category, is_active, learned_from_count
                                            ) VALUES ('legitimate_keyword', ?, 'legitimate', 1, 1)
                                        ''', (word,))
                                    except sqlite3.OperationalError:
                                        cursor.execute('''
                                            INSERT OR IGNORE INTO learned_patterns (
                                                pattern_type, pattern_value, pattern_category, learned_from_count
                                            ) VALUES ('legitimate_keyword', ?, 'legitimate', 1)
                                        ''', (word,))
                    
                    # Actualizar feedback con características extraídas
                    cursor.execute('''
                        UPDATE staff_feedback
                        SET extracted_patterns = ?, extracted_features = ?
                        WHERE id = ?
                    ''', (json.dumps(extracted_patterns), json.dumps(extracted_features), feedback_id))
                    
                    results.append({
                        'result_id': result_id,
                        'feedback_id': feedback_id,
                        'success': True
                    })
                    
                except Exception as e:
                    errors.append(f'Error procesando resultado {result_id}: {str(e)}')
                    continue
            
            # Limpiar caché relacionado
            clear_cache('scan_')
            clear_cache('statistics')
            clear_cache('learned')
            
            # Verificar si hay suficientes feedbacks para actualizar el modelo
            cursor.execute('SELECT COUNT(*) FROM staff_feedback WHERE staff_verification = "hack"')
            hack_feedbacks = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM staff_feedback')
            total_feedbacks = cursor.fetchone()[0]
            
            should_update = hack_feedbacks >= 10 and total_feedbacks >= 15
            
            return jsonify({
                'success': True,
                'processed': len(results),
                'total': len(result_ids),
                'errors': errors,
                'extracted_patterns': list(set(total_extracted_patterns)),
                'should_update_model': should_update,
                'message': f'Procesados {len(results)} de {len(result_ids)} feedbacks exitosamente.'
            }), 201
            
    except Exception as e:
        import traceback
        return jsonify({
            'error': f'Error inesperado al procesar feedback masivo: {str(e)}',
            'traceback': traceback.format_exc()
        }), 500

@app.route('/api/feedback/<int:result_id>', methods=['GET'])
@require_api_key
def get_feedback(result_id):
    """Obtiene feedback de un resultado - OPTIMIZADO"""
    try:
        with get_db_cursor() as cursor:
            cursor.execute('''
                SELECT id, staff_verification, staff_notes, verified_by, verified_at,
                       extracted_patterns, extracted_features
                FROM staff_feedback
                WHERE result_id = ?
                ORDER BY verified_at DESC
                LIMIT 1
            ''', (result_id,))
            
            result = cursor.fetchone()
            
            if not result:
                return jsonify({'feedback': None})
            
            return jsonify({
                'feedback': {
                    'id': result[0],
                    'verification': result[1],
                    'notes': result[2],
                    'verified_by': result[3],
                    'verified_at': result[4],
                    'extracted_patterns': json.loads(result[5]) if result[5] else [],
                    'extracted_features': json.loads(result[6]) if result[6] else {}
                }
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/learned-patterns', methods=['GET'])
@require_api_key
def get_learned_patterns():
    """Obtiene todos los patrones aprendidos - OPTIMIZADO CON CACHÉ"""
    cache_key = 'learned_patterns'
    cached = get_cached(cache_key)
    if cached:
        return jsonify(cached)
    
    try:
        with get_db_cursor() as cursor:
            cursor.execute('''
                SELECT pattern_type, pattern_value, pattern_category, confidence,
                       learned_from_count, first_learned_at, is_active
                FROM learned_patterns
                WHERE is_active = 1
                ORDER BY learned_from_count DESC, confidence DESC
            ''')
            
            patterns = []
            for row in cursor.fetchall():
                patterns.append({
                    'type': row[0],
                    'value': row[1],
                    'category': row[2],
                    'confidence': row[3],
                    'learned_from_count': row[4],
                    'first_learned_at': row[5],
                    'is_active': bool(row[6])
                })
            
            result = {'patterns': patterns, 'total': len(patterns)}
            set_cached(cache_key, result)
            return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/learned-hashes', methods=['GET'])
@require_api_key
def get_learned_hashes():
    """Obtiene todos los hashes aprendidos - OPTIMIZADO CON CACHÉ"""
    cache_key = 'learned_hashes'
    cached = get_cached(cache_key)
    if cached:
        return jsonify(cached)
    
    try:
        with get_db_cursor() as cursor:
            cursor.execute('''
                SELECT file_hash, is_hack, confirmed_count, first_confirmed_at
                FROM learned_hashes
                ORDER BY confirmed_count DESC
                LIMIT 1000
            ''')
            
            hashes = []
            for row in cursor.fetchall():
                hashes.append({
                    'hash': row[0],
                    'is_hack': bool(row[1]),
                    'confirmed_count': row[2],
                    'first_confirmed_at': row[3]
                })
            
            result = {'hashes': hashes, 'total': len(hashes)}
            set_cached(cache_key, result)
            return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ai-model/latest', methods=['GET'])
def get_latest_ai_model():
    """Obtiene el modelo de IA más reciente - OPTIMIZADO CON CACHÉ"""
    cache_key = 'ai_model_latest'
    cached = get_cached(cache_key)
    if cached:
        return jsonify(cached)
    
    try:
        with get_db_cursor() as cursor:
            # Obtener patrones aprendidos
            cursor.execute('''
                SELECT pattern_value, pattern_category, confidence, learned_from_count
                FROM learned_patterns
                WHERE is_active = 1
                ORDER BY learned_from_count DESC
            ''')
            
            patterns = {
                'high_risk': [],
                'medium_risk': [],
                'low_risk': []
            }
            
            for row in cursor.fetchall():
                pattern_value, category, confidence, count = row
                if category in patterns:
                    patterns[category].append({
                        'value': pattern_value,
                        'confidence': confidence,
                        'learned_from_count': count
                    })
            
            # Obtener hashes aprendidos
            cursor.execute('''
                SELECT file_hash, is_hack, confirmed_count
                FROM learned_hashes
                WHERE is_hack = 1
                ORDER BY confirmed_count DESC
            ''')
            
            hashes = []
            for row in cursor.fetchall():
                hashes.append({
                    'hash': row[0],
                    'is_hack': bool(row[1]),
                    'confirmed_count': row[2]
                })
            
            # Obtener versión del modelo
            cursor.execute('''
                SELECT version, created_at, patterns_count, hashes_count
                FROM ai_model_versions
                WHERE is_active = 1
                ORDER BY created_at DESC
                LIMIT 1
            ''')
            
            model_version = None
            version_row = cursor.fetchone()
            if version_row:
                model_version = {
                    'version': version_row[0],
                    'created_at': version_row[1],
                    'patterns_count': version_row[2],
                    'hashes_count': version_row[3]
                }
            
            result = {
                'version': model_version['version'] if model_version else '1.0.0',
                'updated_at': model_version['created_at'] if model_version else None,
                'patterns': patterns,
                'hashes': hashes,
                'patterns_count': sum(len(p) for p in patterns.values()),
                'hashes_count': len(hashes)
            }
            
            set_cached(cache_key, result)
            return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/update-model', methods=['POST'])
@require_api_key
def update_ai_model():
    """Actualiza el modelo de IA - OPTIMIZADO"""
    import os
    from datetime import datetime
    
    try:
        with get_db_cursor() as cursor:
    
            # Obtener patrones aprendidos
            cursor.execute('''
                SELECT pattern_value, pattern_category, confidence, learned_from_count
                FROM learned_patterns
                WHERE is_active = 1
                ORDER BY learned_from_count DESC
            ''')
            learned_patterns = cursor.fetchall()
            
            # Obtener hashes aprendidos
            cursor.execute('''
                SELECT file_hash, is_hack, confirmed_count
                FROM learned_hashes
                WHERE is_hack = 1
            ''')
            learned_hashes_data = cursor.fetchall()
            learned_hashes = [row[0] for row in learned_hashes_data]
            
            # Contar feedbacks
            cursor.execute('SELECT COUNT(*) FROM staff_feedback')
            feedback_count = cursor.fetchone()[0]
            
            # Generar nueva versión del modelo
            version = f"1.{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            # Guardar versión del modelo
            cursor.execute('''
                UPDATE ai_model_versions SET is_active = 0 WHERE is_active = 1
            ''')
            cursor.execute('''
                INSERT INTO ai_model_versions (
                    version, patterns_count, hashes_count, feedback_count, changelog
                ) VALUES (?, ?, ?, ?, ?)
            ''', (version, len(learned_patterns), len(learned_hashes), feedback_count,
                  f"Modelo actualizado con {len(learned_patterns)} patrones y {len(learned_hashes)} hashes aprendidos"))
            
            # Limpiar caché relacionado
            clear_cache('ai_model')
            clear_cache('learned')
    
            # Generar archivo de actualización del modelo (formato completo para API)
            model_update = {
                'version': version,
                'updated_at': datetime.now().isoformat(),
                'patterns': {
                    'high_risk': [{'value': p[0], 'confidence': p[2], 'learned_from_count': p[3]} 
                                 for p in learned_patterns if p[1] == 'high_risk'],
                    'medium_risk': [{'value': p[0], 'confidence': p[2], 'learned_from_count': p[3]} 
                                   for p in learned_patterns if p[1] == 'medium_risk'],
                    'low_risk': [{'value': p[0], 'confidence': p[2], 'learned_from_count': p[3]} 
                                for p in learned_patterns if p[1] == 'low_risk']
                },
                'hashes': [{'hash': row[0], 'is_hack': bool(row[1]), 'confirmed_count': row[2]} 
                          for row in learned_hashes_data]
            }
            
            # Guardar modelo actualizado (los clientes lo descargarán automáticamente)
            model_file = f'models/ai_model_latest.json'
            os.makedirs('models', exist_ok=True)
            with open(model_file, 'w', encoding='utf-8') as f:
                json.dump(model_update, f, indent=2)
            
            print(f"✅ Modelo actualizado guardado en: {model_file}")
            print(f"📡 Los clientes descargarán automáticamente este modelo al iniciar")
            
            return jsonify({
                'success': True,
                'version': version,
                'patterns_count': len(learned_patterns),
                'hashes_count': len(learned_hashes),
                'model_file': model_file,
                'message': 'Modelo actualizado. Los clientes descargarán automáticamente los nuevos patrones sin necesidad de recompilar.'
            }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Nota: El endpoint /api/statistics ya está optimizado más arriba con caché

# ============================================================
# INICIALIZACIÓN
# ============================================================

if __name__ == '__main__':
    print("🚀 Iniciando API REST OPTIMIZADA de Aspers Projects Security Scanner...")
    # La base de datos ya se inicializó al cargar el módulo, pero la inicializamos de nuevo por si acaso
    try:
        init_db()
    except Exception:
        pass  # Ya está inicializada
    print("⚡ Optimizaciones activas: WAL mode, conexión pooling, caché en memoria")
    
    # Detectar si estamos en Render
    port = int(os.environ.get('PORT', 5000))
    is_render = bool(os.environ.get('RENDER'))
    
    if is_render:
        print(f"📡 API disponible en Render (puerto {port})")
    else:
        print(f"📡 API disponible en http://localhost:{port}")
    
    print("🔑 API Key:", API_SECRET_KEY)
    app.run(
        host='0.0.0.0', 
        port=port, 
        threaded=True,  # Habilitar threading para mejor concurrencia
        debug=False  # Deshabilitar debug en producción para mejor rendimiento
    )

