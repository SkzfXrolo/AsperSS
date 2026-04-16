"""
Aplicación Web Flask para Panel del Staff de ASPERS Projects
"""
from flask import Flask, render_template, request, jsonify, session, Response, redirect, url_for, make_response
from flask_cors import CORS
import os
import requests
import json
import datetime
import secrets
import traceback
from functools import wraps

# Importar sistema de autenticación
from auth import (
    init_auth_db, authenticate_user, create_user, create_registration_token,
    verify_registration_token, login_required, admin_required, company_admin_required,
    company_user_required, get_user_by_id, list_registration_tokens, list_users,
    create_company, get_company_by_id, list_companies, update_company,
    has_role, is_admin, is_company_admin, is_company_user
)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'aspers-secret-key-change-in-production')
CORS(app)

# Inicializar base de datos de autenticación al iniciar (en background para no bloquear)
def init_db_async():
    """Inicializa la BD de forma asíncrona para no bloquear el inicio"""
    try:
        init_auth_db()
        print("✅ Base de datos de autenticación inicializada correctamente")
    except Exception as e:
        print(f"⚠️ Error al inicializar base de datos: {e}")
        print("⚠️ La aplicación continuará, pero algunas funciones pueden no funcionar")

# Inicializar en un thread separado para no bloquear el inicio
import threading
threading.Thread(target=init_db_async, daemon=True).start()

# Health check endpoints (simplificado - sin import externo)

# Configuración
# Detectar si estamos en Render o en desarrollo local
RENDER_EXTERNAL_URL = os.environ.get('RENDER_EXTERNAL_URL')  # Render proporciona esta variable
IS_RENDER = bool(RENDER_EXTERNAL_URL)

if IS_RENDER:
    # En Render, verificar si hay una API_URL configurada (servicio separado)
    # Por defecto, usar la URL de la API en Render
    api_url_env = os.environ.get('API_URL')
    if api_url_env:
        # API en servicio separado de Render (configurado explícitamente)
        API_BASE_URL = api_url_env.rstrip('/')
    else:
        # Por defecto en Render, usar la API separada
        API_BASE_URL = 'https://ssapi-cfni.onrender.com'
        print(f"⚠️ API_URL no configurada en Render, usando por defecto: {API_BASE_URL}")
else:
    # En desarrollo local, usar localhost:5000
    API_BASE_URL = os.environ.get('API_URL', 'http://localhost:5000')

# IMPORTANTE: La API Key debe coincidir con la que genera api_server.py
# Por defecto, api_server.py genera una aleatoria. Para desarrollo, puedes usar una fija.
API_KEY = os.environ.get('API_KEY', None)  # None = no requiere API key para desarrollo

def get_api_url(endpoint):
    """Construye la URL completa de la API para un endpoint"""
    # Asegurar que el endpoint empiece con /api/
    endpoint = endpoint.lstrip('/')
    if not endpoint.startswith('api/'):
        endpoint = f"api/{endpoint}"
    
    # Si API_URL está configurado explícitamente, usarlo
    api_url_env = os.environ.get('API_URL')
    if api_url_env:
        return f"{api_url_env.rstrip('/')}/{endpoint}"
    
    # Usar API_BASE_URL (que ya tiene el valor correcto según el entorno)
    if API_BASE_URL:
        return f"{API_BASE_URL.rstrip('/')}/{endpoint}"
    
    # Fallback: si nada está configurado, usar el valor por defecto según el entorno
    if IS_RENDER:
        default_url = 'https://ssapi-cfni.onrender.com'
    else:
        default_url = 'http://localhost:5000'
    
    return f"{default_url}/{endpoint}"

def require_api_key(f):
    """Decorador para requerir API key"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # En producción, verificar API key del staff
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    """Página principal - Sobre ASPERS"""
    response = make_response(render_template('index.html'))
    # Agregar headers de caché para recursos estáticos
    response.headers['Cache-Control'] = 'public, max-age=300'  # 5 minutos
    return response

@app.route('/health', methods=['GET'])
@app.route('/healthz', methods=['GET'])
@app.route('/ping', methods=['GET'])
def health_check():
    """Health check endpoint para Render - Optimizado para ser ultra-rápido"""
    # Respuesta mínima y rápida para evitar spinning down
    # Este endpoint se puede llamar periódicamente para mantener el servicio activo
    response = make_response('OK', 200)
    response.headers['Content-Type'] = 'text/plain'
    response.headers['Cache-Control'] = 'no-cache'
    return response

@app.route('/diagnostico-login')
def diagnostico_login():
    """Página de diagnóstico para problemas de login"""
    return render_template('diagnostico_login.html')

@app.route('/api/test-login', methods=['POST'])
def api_test_login():
    """Endpoint de prueba para login"""
    data = request.json or {}
    username = data.get('username', '').strip()
    password = data.get('password', '')
    login_type = data.get('login_type', 'individual')
    
    print(f"API TEST LOGIN - Usuario: '{username}', Tipo: {login_type}")
    
    result = authenticate_user(username, password)
    
    if result['success']:
        user = result['user']
        # Validar tipo de login
        if login_type == 'empresa' and not user.get('company_id'):
            return jsonify({'success': False, 'error': 'Usuario no pertenece a empresa'}), 403
        elif login_type == 'individual' and user.get('company_id'):
            return jsonify({'success': False, 'error': 'Usuario pertenece a empresa'}), 403
        
        return jsonify({'success': True, 'user': user})
    
    return jsonify({'success': False, 'error': result.get('error', 'Error desconocido')}), 401

@app.route('/api/admin/check-user')
def api_check_user():
    """Verifica si un usuario existe"""
    username = request.args.get('username', '').strip()
    if not username:
        return jsonify({'error': 'Username requerido'}), 400

    from auth import list_users
    try:
        users = list_users() or []
        match = next((u for u in users if u.get('username', '').lower() == username.lower()), None)
        if match:
            return jsonify({
                'exists': True,
                'id': match.get('id'),
                'username': match.get('username'),
                'email': match.get('email'),
                'is_active': match.get('is_active'),
                'company_id': match.get('company_id')
            })
        return jsonify({
            'exists': False,
            'available_users': [u['username'] for u in users[:10]]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Página de login"""
    if request.method == 'POST':
        data = request.form
        username = data.get('username', '').strip()
        password = data.get('password', '')
        login_type = data.get('login_type', 'individual')
        company_name = data.get('company_name', '').strip()
        
        # Validación básica
        if not username or not password:
            error_msg = 'Usuario y contraseña son requeridos'
            if request.is_json:
                return jsonify({'success': False, 'error': error_msg}), 400
            return render_template('login.html', error=error_msg)
        
        # Debug logging
        result = authenticate_user(username, password)
        
        if result['success']:
            user = result['user']
            
            # Validación de tipo de login
            if login_type == 'empresa':
                # Si es login empresarial, verificar que el usuario tenga empresa
                if not user.get('company_id'):
                    error_msg = 'Este usuario no pertenece a ninguna empresa. Use el login individual.'
                    if request.is_json:
                        return jsonify({'success': False, 'error': error_msg}), 403
                    return render_template('login.html', error=error_msg)
                
                # Opcional: verificar nombre de empresa si se proporciona
                if company_name:
                    from auth import get_company_by_id
                    company = get_company_by_id(user.get('company_id'))
                    if company and company.get('name', '').lower() != company_name.lower():
                        error_msg = f'El nombre de empresa no coincide. Empresa del usuario: {company.get("name", "N/A")}'
                        if request.is_json:
                            return jsonify({'success': False, 'error': error_msg}), 403
                        return render_template('login.html', error=error_msg)
            
            elif login_type == 'individual':
                # Si es login individual, verificar que NO tenga empresa
                if user.get('company_id'):
                    error_msg = 'Este usuario pertenece a una empresa. Use el login empresarial.'
                    if request.is_json:
                        return jsonify({'success': False, 'error': error_msg}), 403
                    return render_template('login.html', error=error_msg)
            
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['roles'] = user['roles']  # Múltiples roles
            session['company_id'] = user.get('company_id')
            
            if request.is_json:
                return jsonify({'success': True, 'user': user})
            
            return redirect(url_for('panel'))
        else:
            if request.is_json:
                return jsonify({'success': False, 'error': result['error']}), 401
            
            return render_template('login.html', error=result['error'])
    
    # Si ya está logueado, redirigir al panel
    if 'user_id' in session:
        return redirect(url_for('panel'))
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Página de registro con token"""
    if request.method == 'POST':
        data = request.form
        token = data.get('token', '')
        username = data.get('username', '')
        password = data.get('password', '')
        email = data.get('email', '')
        
        # Verificar token
        token_result = verify_registration_token(token)
        if not token_result['success']:
            if request.is_json:
                return jsonify({'success': False, 'error': token_result['error']}), 400
            return render_template('register.html', error=token_result['error'])
        
        # Determinar roles según el tipo de token
        company_id = token_result.get('company_id')
        is_admin_token = token_result.get('is_admin_token', False)
        
        # Debug: Verificar valores del token
        print(f"  company_id: {company_id}")
        print(f"  is_admin_token (raw): {is_admin_token}")
        print(f"  is_admin_token (type): {type(is_admin_token)}")
        print(f"  is_admin_token (bool): {bool(is_admin_token)}")
        
        # Asegurar que is_admin_token sea un booleano
        if isinstance(is_admin_token, int):
            is_admin_token = bool(is_admin_token)
        elif isinstance(is_admin_token, str):
            is_admin_token = is_admin_token.lower() in ('true', '1', 'yes')
        
        if company_id:
            # Usuario de empresa
            if is_admin_token:
                roles = ['empresa', 'administrador']
            else:
                roles = ['empresa', 'staff']
        else:
            # Usuario normal (sin empresa)
            roles = ['user']
        
        # Crear usuario
        user_result = create_user(
            username=username,
            password=password,
            email=email if email else None,
            roles=roles,
            company_id=company_id,
            created_by=token_result['created_by']
        )
        
        if user_result['success']:
            if request.is_json:
                return jsonify({'success': True, 'message': 'Usuario creado exitosamente'})
            
            return render_template('register.html', success=True)
        else:
            if request.is_json:
                return jsonify({'success': False, 'error': user_result['error']}), 400
            
            return render_template('register.html', error=user_result['error'])
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    """Cerrar sesión"""
    session.clear()
    return redirect(url_for('index'))

@app.route('/panel')
@login_required
def panel():
    """Panel del staff - Requiere autenticación"""
    user = get_user_by_id(session.get('user_id'))
    # Asegurar que user tiene roles como lista para el template
    if user and isinstance(user.get('roles'), str):
        import json
        try:
            user['roles'] = json.loads(user['roles'])
        except:
            user['roles'] = [user.get('roles', 'user')]
    return render_template('panel.html', user=user)

@app.route('/admin/subscriptions', methods=['GET', 'POST'])
def admin_subscriptions():
    """Página secreta de administrador para gestionar suscripciones"""
    # Autenticación especial para esta página
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        
        # Verificar credenciales de admin (puedes cambiar esto)
        if username == 'admin' and password == 'admin123':  # ⚠️ CAMBIAR EN PRODUCCIÓN
            session['admin_subscriptions'] = True
            return redirect('/admin/subscriptions')
        else:
            return render_template('admin_subscriptions_login.html', error='Credenciales incorrectas')
    
    # Verificar si está autenticado
    if not session.get('admin_subscriptions'):
        return render_template('admin_subscriptions_login.html')
    
    # Si está autenticado, mostrar panel de gestión
    from auth import list_companies, list_users, create_company, update_company
    
    companies = list_companies()
    users = list_users()
    
    # Separar usuarios individuales (sin empresa) y usuarios de empresa
    individual_users = [u for u in users if not u.get('company_id')]
    company_users = [u for u in users if u.get('company_id')]
    
    return render_template('admin_subscriptions.html', 
                         companies=companies, 
                         individual_users=individual_users,
                         company_users=company_users)

@app.route('/admin/subscriptions/logout')
def admin_subscriptions_logout():
    """Cerrar sesión de admin de suscripciones"""
    session.pop('admin_subscriptions', None)
    return redirect('/admin/subscriptions')

# ============================================================
# API PROXY - Conecta con la API REST
# ============================================================

# ============================================================
# FUNCIONES DE BASE DE DATOS COMPARTIDAS (SIN LATENCIA DE RED)
# ============================================================
import sqlite3
from contextlib import contextmanager
from auth import DATABASE as AUTH_DATABASE

# Resolver backend de BD una sola vez al arrancar
try:
    from auth import USE_POSTGRESQL as _USE_PG, USE_MYSQL as _USE_MYSQL
except Exception:
    _USE_PG = _USE_MYSQL = False

# Placeholder SQL fijo para todo el proceso
_PH = '%s' if (_USE_PG or _USE_MYSQL) else '?'

# La BD del scanner está INTEGRADA en la misma BD que auth (un único archivo/servicio)
API_DB_AVAILABLE_LOCALLY = True

@contextmanager
def get_api_db_cursor():
    """Cursor para tablas del scanner — usa la misma BD que auth (SQLite o PostgreSQL/MySQL)"""
    if _USE_PG or _USE_MYSQL:
        from db_mysql import get_db_cursor
        with get_db_cursor() as cursor:
            yield cursor
        return

    conn = sqlite3.connect(AUTH_DATABASE, check_same_thread=False, timeout=10.0)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=NORMAL')
    conn.execute('PRAGMA busy_timeout=5000')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def _row_get(row, index, key):
    """Extrae un valor de una fila independientemente de si es sqlite3.Row o dict-like (PostgreSQL)."""
    return row[key] if hasattr(row, 'keys') else row[index]

def _insert_id(cursor, sql, params):
    """Ejecuta un INSERT y devuelve el id generado. Usa RETURNING id en PostgreSQL, lastrowid en SQLite/MySQL."""
    if _USE_PG:
        cursor.execute(sql + ' RETURNING id', params)
        row = cursor.fetchone()
        return _row_get(row, 0, 'id')
    cursor.execute(sql, params)
    return cursor.lastrowid

# Caché simple en memoria para estadísticas
_stats_cache = {}
_stats_cache_time = {}

@app.route('/api/statistics', methods=['GET'])
@login_required
def get_statistics():
    """Obtiene estadísticas - OPTIMIZADO: Acceso directo a BD sin HTTP"""
    import time
    
    # Verificar caché (30 segundos TTL)
    cache_key = 'statistics'
    if cache_key in _stats_cache:
        if time.time() - _stats_cache_time.get(cache_key, 0) < 30:
            return jsonify(_stats_cache[cache_key]), 200
    
    try:
        # Acceso directo a la base de datos (SIN HTTP - MUCHO MÁS RÁPIDO)
        with get_api_db_cursor() as cursor:
            stats = {
                'total_scans': 0,
                'active_scans': 0,
                'unique_machines': 0,
                'severe_detections': 0,
                'total_results': 0,
                'active_tokens': 0,
                'total_bans': 0
            }
            
            # Consulta optimizada: una sola query
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
            except sqlite3.OperationalError:
                # Fallback: consultas individuales si alguna tabla no existe
                for query, key in [
                    ('SELECT COUNT(*) FROM scans', 'total_scans'),
                    ('SELECT COUNT(*) FROM scans WHERE status = "running"', 'active_scans'),
                    ('SELECT COUNT(DISTINCT machine_id) FROM scans WHERE machine_id IS NOT NULL AND machine_id != ""', 'unique_machines'),
                    ('SELECT COUNT(*) FROM scan_results WHERE alert_level = "CRITICAL"', 'severe_detections'),
                    ('SELECT COUNT(*) FROM scan_results', 'total_results'),
                    ('SELECT COUNT(*) FROM scan_tokens WHERE is_active = 1', 'active_tokens'),
                    ('SELECT COUNT(*) FROM ban_history', 'total_bans')
                ]:
                    try:
                        cursor.execute(query)
                        stats[key] = cursor.fetchone()[0] or 0
                    except sqlite3.OperationalError:
                        pass
            
            stats['timestamp'] = datetime.datetime.now().isoformat()
            
            # Guardar en caché
            _stats_cache[cache_key] = stats
            _stats_cache_time[cache_key] = time.time()
            
            return jsonify(stats), 200
    except Exception as e:
        print(f"Error en get_statistics: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': f'Error inesperado: {str(e)}'}), 500

# ============================================================
# API DE AUTENTICACIÓN
# ============================================================

@app.route('/api/auth/login', methods=['POST'])
def api_login():
    """API endpoint para login"""
    data = request.json or {}
    username = data.get('username', '')
    password = data.get('password', '')
    
    result = authenticate_user(username, password)
    
    if result['success']:
        session['user_id'] = result['user']['id']
        session['username'] = result['user']['username']
        session['roles'] = result['user']['roles']
        session['company_id'] = result['user'].get('company_id')
        return jsonify({'success': True, 'user': result['user']})
    else:
        return jsonify({'success': False, 'error': result['error']}), 401

@app.route('/api/auth/logout', methods=['POST'])
@login_required
def api_logout():
    """API endpoint para logout"""
    session.clear()
    return jsonify({'success': True})

@app.route('/api/auth/me', methods=['GET'])
@login_required
def api_me():
    """Obtiene información del usuario actual"""
    user = get_user_by_id(session.get('user_id'))
    if user:
        return jsonify({'success': True, 'user': user})
    return jsonify({'success': False, 'error': 'Usuario no encontrado'}), 404

@app.route('/api/auth/register', methods=['POST'])
def api_register():
    """API endpoint para registro"""
    data = request.json or {}
    token = data.get('token', '')
    username = data.get('username', '')
    password = data.get('password', '')
    email = data.get('email', '')
    
    # Verificar token
    token_result = verify_registration_token(token)
    if not token_result['success']:
        return jsonify({'success': False, 'error': token_result['error']}), 400
    
    # Determinar roles según el tipo de token
    company_id = token_result.get('company_id')
    is_admin_token = token_result.get('is_admin_token', False)
    
    if company_id:
        # Usuario de empresa
        if is_admin_token:
            roles = ['empresa', 'administrador']
        else:
            roles = ['empresa', 'staff']
    else:
        # Usuario normal (sin empresa)
        roles = ['user']
    
    # Crear usuario
    user_result = create_user(
        username=username,
        password=password,
        email=email if email else None,
        roles=roles,
        company_id=company_id,
        created_by=token_result['created_by']
    )
    
    if user_result['success']:
        return jsonify({'success': True, 'message': 'Usuario creado exitosamente'})
    else:
        return jsonify({'success': False, 'error': user_result['error']}), 400

# ============================================================
# API DE ADMINISTRACIÓN (Solo para admins)
# ============================================================

@app.route('/api/admin/registration-tokens', methods=['GET'])
@admin_required
def api_list_registration_tokens():
    """Lista tokens de registro (solo admin)"""
    include_used = request.args.get('include_used', 'false').lower() == 'true'
    tokens = list_registration_tokens(include_used=include_used)
    return jsonify({'success': True, 'tokens': tokens})

@app.route('/api/admin/registration-tokens', methods=['POST'])
@admin_required
def api_create_registration_token():
    """Crea un token de registro (solo admin) - Puede ser para empresa o general"""
    data = request.json or {}
    expires_hours = data.get('expires_hours', 24)
    description = data.get('description', '')
    company_id = data.get('company_id')  # Opcional: si se proporciona, es token de empresa
    is_admin_token = data.get('is_admin_token', False)  # Si es True, crea admin de empresa
    
    created_by = session.get('user_id')
    if not created_by:
        return jsonify({'success': False, 'error': 'Usuario no autenticado'}), 401
    
    result = create_registration_token(
        created_by=created_by,
        company_id=company_id,
        expires_hours=expires_hours,
        description=description,
        is_admin_token=is_admin_token
    )
    
    if result['success']:
        return jsonify({
            'success': True,
            'token': result['token'],
            'token_id': result['token_id'],
            'expires_at': result['expires_at'].isoformat(),
            'company_id': company_id,
            'is_admin_token': is_admin_token
        }), 201
    else:
        return jsonify({'success': False, 'error': result['error']}), 400

@app.route('/api/admin/users', methods=['GET'])
@admin_required
def api_list_users():
    """Lista usuarios (solo admin) - Puede filtrar por empresa"""
    company_id = request.args.get('company_id', type=int)
    users = list_users(company_id=company_id)
    return jsonify({'success': True, 'users': users})

# ============================================================
# API DE GESTIÓN DE EMPRESAS
# ============================================================

@app.route('/api/admin/companies', methods=['GET'])
@admin_required
def api_list_companies():
    """Lista todas las empresas (solo super admin)"""
    companies = list_companies()
    return jsonify({'success': True, 'companies': companies})

@app.route('/api/admin/companies', methods=['POST'])
@admin_required
def api_create_company():
    """Crea una nueva empresa (solo super admin)"""
    data = request.json or {}
    
    name = data.get('name')
    if not name:
        return jsonify({'success': False, 'error': 'El nombre de la empresa es requerido'}), 400
    
    result = create_company(
        name=name,
        contact_email=data.get('contact_email'),
        contact_phone=data.get('contact_phone'),
        max_users=data.get('max_users', 8),
        max_admins=data.get('max_admins', 3),
        created_by=session.get('user_id'),
        notes=data.get('notes')
    )
    
    if result['success']:
        return jsonify({
            'success': True,
            'company_id': result['company_id']
        }), 201
    else:
        return jsonify({'success': False, 'error': result['error']}), 400

@app.route('/api/admin/companies/<int:company_id>', methods=['GET'])
@admin_required
def api_get_company(company_id):
    """Obtiene información de una empresa"""
    company = get_company_by_id(company_id)
    if company:
        return jsonify({'success': True, 'company': company})
    return jsonify({'success': False, 'error': 'Empresa no encontrada'}), 404

@app.route('/api/admin/companies/<int:company_id>', methods=['PUT'])
@admin_required
def api_update_company(company_id):
    """Actualiza una empresa"""
    data = request.json or {}
    
    result = update_company(
        company_id=company_id,
        name=data.get('name'),
        contact_email=data.get('contact_email'),
        contact_phone=data.get('contact_phone'),
        subscription_status=data.get('subscription_status'),
        subscription_end_date=data.get('subscription_end_date'),
        max_users=data.get('max_users'),
        max_admins=data.get('max_admins'),
        is_active=data.get('is_active'),
        notes=data.get('notes')
    )
    
    if result['success']:
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'error': result['error']}), 400

@app.route('/api/company/registration-tokens', methods=['GET'])
@company_admin_required
def api_list_company_tokens():
    """Lista tokens de registro de la empresa del usuario (admin de empresa)"""
    user = get_user_by_id(session.get('user_id'))
    if not user or not user.get('company_id'):
        return jsonify({'success': False, 'error': 'Usuario no pertenece a una empresa'}), 403
    
    include_used = request.args.get('include_used', 'false').lower() == 'true'
    tokens = list_registration_tokens(include_used=include_used, company_id=user['company_id'])
    return jsonify({'success': True, 'tokens': tokens})

@app.route('/api/company/registration-tokens', methods=['POST'])
@company_admin_required
def api_create_company_token():
    """Crea un token de registro para la empresa (admin de empresa)"""
    user = get_user_by_id(session.get('user_id'))
    if not user or not user.get('company_id'):
        return jsonify({'success': False, 'error': 'Usuario no pertenece a una empresa'}), 403
    
    data = request.json or {}
    expires_hours = data.get('expires_hours', 24)
    description = data.get('description', '')
    is_admin_token = data.get('is_admin_token', False)
    
    # Asegurar que is_admin_token sea un booleano
    if isinstance(is_admin_token, str):
        is_admin_token = is_admin_token.lower() in ('true', '1', 'yes')
    elif not isinstance(is_admin_token, bool):
        is_admin_token = bool(is_admin_token)
    
    result = create_registration_token(
        created_by=session.get('user_id'),
        company_id=user['company_id'],
        expires_hours=expires_hours,
        description=description,
        is_admin_token=is_admin_token
    )
    
    if result['success']:
        return jsonify({
            'success': True,
            'token': result['token'],
            'token_id': result['token_id'],
            'expires_at': result['expires_at'].isoformat(),
            'is_admin_token': is_admin_token
        }), 201
    else:
        return jsonify({'success': False, 'error': result['error']}), 400

@app.route('/api/company/users', methods=['GET'])
@company_admin_required
def api_list_company_users():
    """Lista usuarios de la empresa (admin de empresa)"""
    user = get_user_by_id(session.get('user_id'))
    if not user or not user.get('company_id'):
        return jsonify({'success': False, 'error': 'Usuario no pertenece a una empresa'}), 403
    
    users = list_users(company_id=user['company_id'])
    return jsonify({'success': True, 'users': users})

@app.route('/api/company/users/<int:user_id>/deactivate', methods=['POST'])
@company_admin_required
def api_deactivate_company_user(user_id):
    """Desactiva un usuario de la empresa (admin de empresa)"""
    user = get_user_by_id(session.get('user_id'))
    if not user or not user.get('company_id'):
        return jsonify({'success': False, 'error': 'Usuario no pertenece a una empresa'}), 403
    
    # Verificar que el usuario a desactivar pertenece a la misma empresa
    target_user = get_user_by_id(user_id)
    if not target_user:
        return jsonify({'success': False, 'error': 'Usuario no encontrado'}), 404
    
    if target_user.get('company_id') != user['company_id']:
        return jsonify({'success': False, 'error': 'No tienes permiso para modificar este usuario'}), 403
    
    # No permitir desactivarse a sí mismo
    if user_id == user['id']:
        return jsonify({'success': False, 'error': 'No puedes desactivar tu propia cuenta'}), 400
    
    try:
        with get_api_db_cursor() as cursor:
            cursor.execute(f'UPDATE users SET is_active = FALSE WHERE id = {_PH}', (user_id,))
        return jsonify({'success': True, 'message': 'Usuario desactivado exitosamente'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/company/users/<int:user_id>/activate', methods=['POST'])
@company_admin_required
def api_activate_company_user(user_id):
    """Activa un usuario de la empresa (admin de empresa)"""
    user = get_user_by_id(session.get('user_id'))
    if not user or not user.get('company_id'):
        return jsonify({'success': False, 'error': 'Usuario no pertenece a una empresa'}), 403
    
    # Verificar que el usuario a activar pertenece a la misma empresa
    target_user = get_user_by_id(user_id)
    if not target_user:
        return jsonify({'success': False, 'error': 'Usuario no encontrado'}), 404
    
    if target_user.get('company_id') != user['company_id']:
        return jsonify({'success': False, 'error': 'No tienes permiso para modificar este usuario'}), 403
    
    try:
        with get_api_db_cursor() as cursor:
            cursor.execute(f'UPDATE users SET is_active = TRUE WHERE id = {_PH}', (user_id,))
        return jsonify({'success': True, 'message': 'Usuario activado exitosamente'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/company/users/<int:user_id>/delete', methods=['DELETE'])
@company_admin_required
def api_delete_company_user(user_id):
    """Elimina un usuario de la empresa (admin de empresa)"""
    user = get_user_by_id(session.get('user_id'))
    if not user or not user.get('company_id'):
        return jsonify({'success': False, 'error': 'Usuario no pertenece a una empresa'}), 403
    
    # Verificar que el usuario a eliminar pertenece a la misma empresa
    target_user = get_user_by_id(user_id)
    if not target_user:
        return jsonify({'success': False, 'error': 'Usuario no encontrado'}), 404
    
    if target_user.get('company_id') != user['company_id']:
        return jsonify({'success': False, 'error': 'No tienes permiso para eliminar este usuario'}), 403
    
    # No permitir eliminarse a sí mismo
    if user_id == user['id']:
        return jsonify({'success': False, 'error': 'No puedes eliminar tu propia cuenta'}), 400
    
    try:
        with get_api_db_cursor() as cursor:
            cursor.execute(f'DELETE FROM users WHERE id = {_PH}', (user_id,))
        return jsonify({'success': True, 'message': 'Usuario eliminado exitosamente'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/company/info', methods=['GET'])
@company_user_required
def api_get_company_info():
    """Obtiene información de la empresa del usuario"""
    user = get_user_by_id(session.get('user_id'))
    if not user or not user.get('company_id'):
        return jsonify({'success': False, 'error': 'Usuario no pertenece a una empresa'}), 403
    
    company = get_company_by_id(user['company_id'])
    if company:
        return jsonify({'success': True, 'company': company})
    return jsonify({'success': False, 'error': 'Empresa no encontrada'}), 404

@app.route('/api/company/scan-tokens', methods=['GET'])
@company_user_required
def api_list_company_scan_tokens():
    """Lista tokens de ESCANEO de todos los usuarios de la empresa"""
    user = get_user_by_id(session.get('user_id'))
    if not user or not user.get('company_id'):
        return jsonify({'success': False, 'error': 'Usuario no pertenece a una empresa'}), 403
    
    company_id = user['company_id']
    
    try:
        # Obtener todos los usuarios de la empresa
        company_users = list_users(company_id=company_id)
        usernames = [u['username'] for u in company_users if u.get('username')]
        
        if not usernames:
            return jsonify({'success': True, 'tokens': []})
        
        # Intentar acceso directo a BD si está disponible localmente
        if API_DB_AVAILABLE_LOCALLY:
            try:
                with get_api_db_cursor() as cursor:
                    # Crear placeholders para la consulta IN
                    placeholders = ','.join(['?' for _ in usernames])
                    cursor.execute(f'''
                        SELECT id, token, created_at, expires_at, used_count, max_uses, 
                               is_active, created_by, description
                        FROM scan_tokens
                        WHERE created_by IN ({placeholders})
                        ORDER BY created_at DESC
                        LIMIT 100
                    ''', usernames)
                    
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
                            'description': row[8],
                            'type': 'scan_token'
                        })
                    
                    return jsonify({'success': True, 'tokens': tokens})
            except Exception as e:
                print(f"Error accediendo BD local para tokens de empresa, usando HTTP: {str(e)}")
        
        # Si no está disponible localmente, usar HTTP
        headers = {}
        if API_KEY:
            headers['X-API-Key'] = API_KEY
        
        try:
            response = requests.get(
                get_api_url('/api/tokens'),
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                all_tokens = data.get('tokens', [])
                # Filtrar solo tokens de usuarios de la empresa
                tokens = [t for t in all_tokens if t.get('created_by') in usernames]
                return jsonify({'success': True, 'tokens': tokens})
            else:
                return jsonify({'success': True, 'tokens': []})
        except Exception as e:
            print(f"Error obteniendo tokens de empresa: {str(e)}")
            return jsonify({'success': True, 'tokens': []})
            
    except Exception as e:
        print(f"Error listando tokens de escaneo de empresa: {str(e)}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

# ============================================================
# API DE ADMINISTRACIÓN DE SUSCRIPCIONES (Página Secreta)
# ============================================================

def admin_subscriptions_required(f):
    """Decorador para requerir autenticación de admin de suscripciones"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_subscriptions'):
            return jsonify({'error': 'No autorizado'}), 401
        return f(*args, **kwargs)
    return decorated_function

@app.route('/api/admin/create-subscription', methods=['POST'])
@admin_subscriptions_required
def api_create_subscription():
    """Crea una nueva suscripción (individual o empresarial)"""
    data = request.json or {}
    
    subscription_type = data.get('subscription_type', 'individual')
    price = data.get('price', 5.0 if subscription_type == 'individual' else 13.0)
    duration = data.get('duration', 1)  # meses
    is_free = data.get('is_free', False)
    
    if is_free:
        price = 0.0
    
    try:
        if subscription_type == 'enterprise':
            # Crear empresa
            company_name = data.get('company_name')
            if not company_name:
                return jsonify({'success': False, 'error': 'Nombre de empresa requerido'}), 400
            
            result = create_company(
                name=company_name,
                contact_email=data.get('email'),
                subscription_type='enterprise',
                subscription_status='active',
                subscription_price=price,
                max_users=8,
                max_admins=3,
                created_by=None,
                notes=f'Suscripción creada desde panel admin. Duración: {duration} meses'
            )
            
            if result['success']:
                # Calcular fecha de expiración
                if duration > 0:
                    from datetime import datetime, timedelta
                    end_date = datetime.now() + timedelta(days=duration * 30)
                    update_company(
                        company_id=result['company_id'],
                        subscription_end_date=end_date.isoformat()
                    )
                
                return jsonify({
                    'success': True,
                    'company_id': result['company_id'],
                    'message': 'Suscripción empresarial creada'
                })
            else:
                return jsonify({'success': False, 'error': result['error']}), 400
        
        else:  # individual
            # Crear usuario individual
            username = data.get('username')
            email = data.get('email')
            
            if not username:
                return jsonify({'success': False, 'error': 'Nombre de usuario requerido'}), 400
            
            # Generar contraseña temporal
            import secrets
            temp_password = secrets.token_urlsafe(12)
            
            result = create_user(
                username=username,
                password=temp_password,
                email=email,
                roles=['user'],
                company_id=None,
                created_by='admin_subscriptions'
            )
            
            if result['success']:
                return jsonify({
                    'success': True,
                    'user_id': result['user_id'],
                    'temp_password': temp_password,
                    'message': f'Suscripción individual creada. Contraseña temporal: {temp_password}'
                })
            else:
                return jsonify({'success': False, 'error': result['error']}), 400
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/make-free', methods=['POST'])
@admin_subscriptions_required
def api_make_free():
    """Marca una suscripción como gratuita"""
    data = request.json or {}
    sub_id = data.get('id')
    sub_type = data.get('type')  # 'company' o 'user'
    
    try:
        if sub_type == 'company':
            result = update_company(
                company_id=sub_id,
                subscription_price=0.0,
                subscription_status='active'
            )
            if result['success']:
                return jsonify({'success': True, 'message': 'Empresa marcada como gratuita'})
        else:  # user
            # Para usuarios individuales, podríamos crear una "empresa" especial o solo marcarlos
            # Por ahora, solo confirmamos
            return jsonify({'success': True, 'message': 'Usuario individual marcado como gratuito'})
        
        return jsonify({'success': False, 'error': 'Error al actualizar'}), 400
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/update-company', methods=['POST'])
@admin_subscriptions_required
def api_admin_update_company():
    """Actualiza una empresa desde el panel de administración secreto"""
    data = request.json or {}
    company_id = data.get('company_id')
    
    if not company_id:
        return jsonify({'success': False, 'error': 'ID de empresa requerido'}), 400
    
    try:
        result = update_company(
            company_id=company_id,
            name=data.get('name'),
            contact_email=data.get('contact_email'),
            subscription_price=data.get('subscription_price'),
            max_users=data.get('max_users'),
            max_admins=data.get('max_admins'),
            subscription_status=data.get('subscription_status'),
            subscription_end_date=data.get('subscription_end_date')
        )
        
        if result['success']:
            return jsonify({'success': True, 'message': 'Empresa actualizada exitosamente'})
        else:
            return jsonify({'success': False, 'error': result.get('error', 'Error desconocido')}), 400
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/update-subscription', methods=['POST'])
@login_required
def api_update_subscription():
    """Actualiza suscripción de empresa (precio, estado, extensión). Solo para admins."""
    user = get_user_by_id(session.get('user_id'))
    if not user or 'admin' not in user.get('roles', []):
        return jsonify({'success': False, 'error': 'No autorizado'}), 403

    data = request.json or {}
    company_id = data.get('company_id')
    if not company_id:
        return jsonify({'success': False, 'error': 'company_id requerido'}), 400

    try:
        update_kwargs = {}
        if 'subscription_price' in data:
            update_kwargs['subscription_price'] = data['subscription_price']
        if 'subscription_status' in data:
            update_kwargs['subscription_status'] = data['subscription_status']
        if data.get('notes'):
            update_kwargs['notes'] = data['notes']

        if data.get('extend_months', 0) > 0:
            from datetime import datetime, timedelta
            company = get_company_by_id(company_id)
            if company:
                current_end = company.get('subscription_end_date')
                if current_end and str(current_end) > datetime.now().isoformat():
                    base = datetime.fromisoformat(str(current_end).split('.')[0])
                else:
                    base = datetime.now()
                new_end = base + timedelta(days=int(data['extend_months']) * 30)
                update_kwargs['subscription_end_date'] = new_end.isoformat()
                if data.get('subscription_status') != 'cancelled':
                    update_kwargs['subscription_status'] = 'active'

        result = update_company(company_id=company_id, **update_kwargs)
        if result['success']:
            return jsonify({'success': True, 'message': 'Suscripción actualizada'})
        return jsonify({'success': False, 'error': result.get('error', 'Error')}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================
# API PROXY - Conecta con la API REST
# ============================================================

# IMPORTANTE: Separación COMPLETA de tokens
# 
# TOKENS DE ESCANEO (para la aplicación .exe SS):
# - Endpoint: /api/tokens (GET/POST/DELETE)
# - Tabla: scan_tokens (en BD de la API)
# - Permisos: CUALQUIER usuario autenticado puede crear/listar/eliminar sus propios tokens
#             Los admins pueden ver/eliminar todos los tokens
# - Uso: Autenticación en la aplicación cliente SS (.exe)
#
# TOKENS DE REGISTRO (para crear usuarios):
# - Endpoints: /api/admin/registration-tokens (solo admin)
#              /api/company/registration-tokens (admin de empresa)
# - Tabla: registration_tokens (en BD de autenticación)
# - Permisos: Solo admins y admins de empresa pueden crear tokens de registro
# - Uso: Registro de nuevos usuarios en el sistema web

@app.route('/api/tokens', methods=['GET'])
@login_required
def list_tokens():
    """Lista tokens de ESCANEO (para la aplicación SS) - Cualquier usuario autenticado puede ver sus tokens"""
    try:
        user = get_user_by_id(session.get('user_id'))
        if not user:
            return jsonify({'success': False, 'error': 'Usuario no encontrado'}), 401

        username = user.get('username', '')
        is_admin_user = is_admin(user)

        with get_api_db_cursor() as cursor:
            if is_admin_user:
                cursor.execute(
                    'SELECT id, token, created_at, expires_at, used_count, max_uses,'
                    ' is_active, created_by, description FROM scan_tokens'
                    ' ORDER BY created_at DESC LIMIT 100'
                )
            else:
                cursor.execute(
                    f'SELECT id, token, created_at, expires_at, used_count, max_uses,'
                    f' is_active, created_by, description FROM scan_tokens'
                    f' WHERE created_by = {_PH} ORDER BY created_at DESC LIMIT 100',
                    (username,)
                )

            tokens = []
            for row in cursor.fetchall():
                exp = _row_get(row, 3, 'expires_at')
                tokens.append({
                    'id':          _row_get(row, 0, 'id'),
                    'token':       _row_get(row, 1, 'token'),
                    'created_at':  str(_row_get(row, 2, 'created_at') or ''),
                    'expires_at':  str(exp) if exp else None,
                    'used_count':  _row_get(row, 4, 'used_count') or 0,
                    'max_uses':    _row_get(row, 5, 'max_uses'),
                    'is_active':   bool(_row_get(row, 6, 'is_active')),
                    'created_by':  _row_get(row, 7, 'created_by') or '',
                    'description': _row_get(row, 8, 'description') or '',
                    'type':        'scan_token',
                })

        return jsonify({'success': True, 'tokens': tokens})

    except Exception as e:
        print(f"Error en list_tokens: {e}")
        print(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/tokens', methods=['POST'])
@login_required
def create_token():
    """Crea un nuevo token de ESCANEO (para la aplicación SS) - Cualquier usuario autenticado puede crear"""
    try:
        data = request.json or {}

        expires_days = data.get('expires_days', 30)
        if 'expires_hours' in data:
            expires_days = data.get('expires_hours', 24) / 24

        max_uses = data.get('max_uses', -1)  # -1 = ilimitado
        description = data.get('description', '')

        user = get_user_by_id(session.get('user_id'))
        if not user:
            return jsonify({'success': False, 'error': 'Usuario no encontrado'}), 401

        created_by = user.get('username', 'web_app')
        user_id = user.get('id')

        # Verificar límite de 5 tokens activos por usuario no-admin
        if not is_admin(user):
            with get_api_db_cursor() as cursor:
                cursor.execute(
                    f'SELECT COUNT(*) FROM scan_tokens WHERE created_by = {_PH} AND is_active = 1',
                    (created_by,)
                )
                row = cursor.fetchone()
                try:
                    token_count = row[0]
                except TypeError:
                    token_count = list(row.values())[0]

            if token_count >= 5:
                return jsonify({
                    'success': False,
                    'error': 'Has alcanzado el limite de 5 tokens activos. Elimina uno antes de crear otro.'
                }), 400

        scan_token = secrets.token_urlsafe(32)
        expires_at = None
        if expires_days and expires_days > 0:
            expires_at = (datetime.datetime.now() + datetime.timedelta(days=expires_days)).isoformat()

        with get_api_db_cursor() as cursor:
            token_id = _insert_id(
                cursor,
                f'INSERT INTO scan_tokens (token, expires_at, max_uses, description, created_by)'
                f' VALUES ({_PH},{_PH},{_PH},{_PH},{_PH})',
                (scan_token, expires_at, max_uses, description, created_by)
            )

        download_link = None
        try:
            dl_hours = (expires_days * 24) if (expires_days and expires_days > 0) else 168
            dl_expires = (datetime.datetime.now() + datetime.timedelta(hours=dl_hours)).isoformat()
            download_token = secrets.token_urlsafe(32)

            with get_api_db_cursor() as cursor:
                cursor.execute(
                    f'INSERT INTO download_links (token, filename, created_by, expires_at, max_downloads, description)'
                    f' VALUES ({_PH},{_PH},{_PH},{_PH},{_PH},{_PH})',
                    (download_token, 'MinecraftSSTool.exe', user_id, dl_expires, -1,
                     f'Enlace del token: {description or "Sin descripcion"}')
                )

            base_url = os.environ.get('RENDER_EXTERNAL_URL', request.host_url).rstrip('/')
            download_link = f"{base_url}/d/{download_token}?token={scan_token}"
        except Exception as dl_err:
            print(f"Error creando enlace de descarga: {dl_err}")

        return jsonify({
            'success': True,
            'token': scan_token,
            'token_id': token_id,
            'expires_at': expires_at,
            'max_uses': max_uses,
            'description': description,
            'created_by': created_by,
            'type': 'scan_token',
            'download_url': download_link
        }), 201

    except Exception as e:
        print(f"ERROR create_token: {e}")
        print(traceback.format_exc())
        return jsonify({'success': False, 'error': f'Error al crear token: {str(e)}'}), 500

@app.route('/api/tokens/<int:token_id>', methods=['DELETE'])
@login_required
def delete_token(token_id):
    """Elimina permanentemente un token de ESCANEO - Usuario puede eliminar sus propios tokens, admin puede eliminar todos"""
    try:
        user = get_user_by_id(session.get('user_id'))
        if not user:
            return jsonify({'success': False, 'error': 'Usuario no encontrado'}), 401
        
        username = user.get('username', '')
        is_admin_user = is_admin(user)
        
        with get_api_db_cursor() as cursor:
            cursor.execute(f'SELECT id, created_by FROM scan_tokens WHERE id = {_PH}', (token_id,))
            token_row = cursor.fetchone()
            if not token_row:
                return jsonify({'success': False, 'error': 'Token no encontrado'}), 404

            token_creator = _row_get(token_row, 1, 'created_by')

            if not is_admin_user and token_creator != username:
                return jsonify({'success': False, 'error': 'No tienes permiso para eliminar este token'}), 403

            cursor.execute(f'DELETE FROM scan_tokens WHERE id = {_PH}', (token_id,))
        
        return jsonify({'success': True, 'message': 'Token de escaneo eliminado exitosamente'}), 200
    except Exception as e:
        print(f"Error al eliminar token: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'success': False, 'error': f'Error al eliminar token: {str(e)}'}), 500

# ============================================================
# ENDPOINTS PARA EL CLIENTE .EXE (sin login requerido, usan scan token)
# ============================================================

def _validate_scan_token_direct(token):
    """Valida un token de escaneo en la BD. Retorna (token_id, error_msg)."""
    try:
        with get_api_db_cursor() as cursor:
            cursor.execute(
                f'SELECT id, expires_at, used_count, max_uses, is_active FROM scan_tokens WHERE token = {_PH}',
                (token,)
            )
            row = cursor.fetchone()

        if not row:
            return None, 'Token no encontrado'

        token_id   = _row_get(row, 0, 'id')
        expires_at = _row_get(row, 1, 'expires_at')
        used_count = _row_get(row, 2, 'used_count') or 0
        max_uses   = _row_get(row, 3, 'max_uses')
        is_active  = _row_get(row, 4, 'is_active')

        if not is_active:
            return None, 'Token desactivado'

        if expires_at:
            if isinstance(expires_at, str):
                exp = datetime.datetime.fromisoformat(expires_at.replace('Z', '+00:00')).replace(tzinfo=None)
            else:
                exp = expires_at.replace(tzinfo=None) if hasattr(expires_at, 'tzinfo') else expires_at
            if datetime.datetime.now() > exp:
                return None, 'Token expirado'

        if max_uses and max_uses > 0 and used_count >= max_uses:
            return None, 'Token ha alcanzado el limite de usos'

        return token_id, None
    except Exception as e:
        print(f"Error validando token: {e}\n{traceback.format_exc()}")
        return None, f'Error validando token: {str(e)}'


@app.route('/setup-admin-aspers2024', methods=['GET'])
def setup_admin():
    """Endpoint de setup único para crear el admin inicial. Solo funciona si no existe."""
    try:
        import hashlib as _hl
        with get_api_db_cursor() as cursor:
            cursor.execute(f'SELECT COUNT(*) as count FROM users WHERE username = {_PH}', ('arefy_admin',))
            row = cursor.fetchone()
            count = _row_get(row, 0, 'count')
            if count > 0:
                return jsonify({'status': 'already_exists', 'message': 'El usuario arefy_admin ya existe'}), 200

            cursor.execute(f'SELECT id FROM companies WHERE name = {_PH}', ('arefy',))
            company_row = cursor.fetchone()
            if not company_row:
                cursor.execute(
                    f"INSERT INTO companies (name, subscription_type, subscription_status, subscription_price, max_users, max_admins, notes) VALUES ({_PH},'enterprise','active',13.0,8,3,'Empresa default')",
                    ('arefy',)
                )
                cursor.execute(f'SELECT id FROM companies WHERE name = {_PH}', ('arefy',))
                company_row = cursor.fetchone()

            company_id = _row_get(company_row, 0, 'id')
            password_hash = _hl.sha256('arefy2024!'.encode()).hexdigest()
            _insert_id(cursor,
                f'INSERT INTO users (username, email, password_hash, roles, company_id, created_by) VALUES ({_PH},{_PH},{_PH},{_PH},{_PH},{_PH})',
                ('arefy_admin', 'admin@arefy.com', password_hash, '["admin", "empresa", "administrador"]', company_id, 'system')
            )
        return jsonify({'status': 'ok', 'message': 'Usuario arefy_admin creado. Contraseña: arefy2024!'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/db-status', methods=['GET'])
def api_db_status():
    """Muestra qué backend de BD está activo — útil para verificar deploys"""
    try:
        with get_api_db_cursor() as cursor:
            cursor.execute('SELECT COUNT(*) as count FROM users')
            row = cursor.fetchone()
            user_count = _row_get(row, 0, 'count')
            cursor.execute('SELECT COUNT(*) as count FROM companies')
            row = cursor.fetchone()
            company_count = _row_get(row, 0, 'count')
        backend = 'postgresql' if _USE_PG else ('mysql' if _USE_MYSQL else 'sqlite')
        db_url_set = bool(os.environ.get('DATABASE_URL'))
        return jsonify({
            'backend': backend,
            'DATABASE_URL_set': db_url_set,
            'users': user_count,
            'companies': company_count,
            'persistent': _USE_PG or _USE_MYSQL,
        })
    except Exception as e:
        return jsonify({'backend': 'error', 'error': str(e)}), 500


@app.route('/api/validate-token', methods=['POST'])
def validate_token_endpoint():
    """Valida un token de escaneo (usado por el cliente .exe) — sin login requerido"""
    try:
        data = request.json or {}
        token = data.get('token', '').strip()
        if not token:
            return jsonify({'valid': False, 'error': 'Token no proporcionado'}), 400

        token_id, error = _validate_scan_token_direct(token)
        if error:
            return jsonify({'valid': False, 'error': error}), 200

        return jsonify({'valid': True, 'token_id': token_id, 'message': 'Token valido'}), 200
    except Exception as e:
        print(f"Error en validate_token_endpoint: {e}\n{traceback.format_exc()}")
        return jsonify({'valid': False, 'error': str(e)}), 500


@app.route('/api/scans', methods=['POST'])
def start_scan():
    """Inicia un nuevo escaneo (usado por el cliente .exe) — sin login requerido"""
    try:
        data = request.json or {}
        scan_token   = data.get('token', '').strip()
        machine_id   = data.get('machine_id', '')
        machine_name = data.get('machine_name', '')
        ip_address   = data.get('ip_address') or request.remote_addr
        country      = data.get('country', '')
        mc_username  = data.get('minecraft_username', '')

        token_id, error = _validate_scan_token_direct(scan_token)
        if error:
            return jsonify({'error': error}), 401

        with get_api_db_cursor() as cursor:
            cursor.execute(
                f'UPDATE scan_tokens SET used_count = used_count + 1,'
                f' is_active = CASE WHEN max_uses > 0 AND (used_count + 1) >= max_uses THEN 0 ELSE is_active END'
                f' WHERE id = {_PH}',
                (token_id,)
            )
            scan_id = _insert_id(
                cursor,
                f'INSERT INTO scans (token_id, scan_token, status, machine_id, machine_name, ip_address, country, minecraft_username)'
                f" VALUES ({_PH},{_PH},'running',{_PH},{_PH},{_PH},{_PH},{_PH})",
                (token_id, scan_token, machine_id, machine_name, ip_address, country, mc_username)
            )

        return jsonify({'success': True, 'scan_id': scan_id, 'status': 'running', 'message': 'Escaneo iniciado'}), 201
    except Exception as e:
        print(f"Error en start_scan: {e}\n{traceback.format_exc()}")
        return jsonify({'error': f'Error iniciando escaneo: {str(e)}'}), 500


@app.route('/api/scans/<int:scan_id>/results', methods=['POST'])
def submit_scan_results(scan_id):
    """Recibe y almacena resultados de escaneo (usado por el cliente .exe) — sin login requerido"""
    data = request.json
    if not data:
        return jsonify({'error': 'No se recibieron datos'}), 400

    try:
        with get_api_db_cursor() as cursor:
            cursor.execute(
                f'UPDATE scans SET status = {_PH}, completed_at = CURRENT_TIMESTAMP,'
                f' total_files_scanned = {_PH}, issues_found = {_PH}, scan_duration = {_PH}'
                f' WHERE id = {_PH}',
                (data.get('status', 'completed'), data.get('total_files_scanned', 0),
                 data.get('issues_found', 0), data.get('scan_duration', 0), scan_id)
            )
            if cursor.rowcount == 0:
                return jsonify({'error': f'Escaneo {scan_id} no encontrado'}), 404

            results = data.get('results', [])
            if results:
                batch = [
                    (scan_id,
                     r.get('tipo', ''), r.get('nombre', '') or r.get('archivo', ''),
                     r.get('ruta', ''), r.get('categoria', ''), r.get('alerta', ''),
                     r.get('confidence', 0), json.dumps(r.get('detected_patterns', [])),
                     r.get('obfuscation', False), r.get('file_hash', ''),
                     r.get('ai_analysis', ''), r.get('ai_confidence', 0))
                    for r in results
                ]
                cursor.executemany(
                    f'INSERT INTO scan_results'
                    f' (scan_id, issue_type, issue_name, issue_path, issue_category,'
                    f'  alert_level, confidence, detected_patterns, obfuscation_detected,'
                    f'  file_hash, ai_analysis, ai_confidence)'
                    f' VALUES ({_PH},{_PH},{_PH},{_PH},{_PH},{_PH},{_PH},{_PH},{_PH},{_PH},{_PH},{_PH})',
                    batch
                )

        print(f"Scan {scan_id} completado: {len(results)} resultados, status={data.get('status', 'completed')}")
        return jsonify({'success': True, 'message': 'Resultados almacenados'})
    except Exception as e:
        print(f"Error en submit_scan_results: {e}\n{traceback.format_exc()}")
        return jsonify({'error': f'Error almacenando resultados: {str(e)}'}), 500


@app.route('/api/scans', methods=['GET'])
@login_required
def list_scans():
    """Lista escaneos - Usa BD directa si está disponible, sino HTTP"""
    import time
    
    limit = request.args.get('limit', 50, type=int)
    offset = request.args.get('offset', 0, type=int)
    
    # Caché por limit/offset (10 segundos TTL)
    cache_key = f'scans_list_{limit}_{offset}'
    if cache_key in _stats_cache:
        if time.time() - _stats_cache_time.get(cache_key, 0) < 10:
            return jsonify(_stats_cache[cache_key]), 200
    
    # Intentar acceso directo a BD primero (más rápido) - BD unificada siempre disponible
    if API_DB_AVAILABLE_LOCALLY:
        try:
            print(f"🔄 Intentando obtener escaneos directamente de la BD local...")
            with get_api_db_cursor() as cursor:
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
                
                print(f"📊 Escaneos encontrados en BD local: {len(scans)}")
                
                # Calcular preview de severidad (una sola query optimizada)
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
                            scan['severity_summary'] = 'LIMPIO' if scan['issues_found'] == 0 else 'SOSPECHOSO'
                            scan['severity_badge'] = 'success' if scan['issues_found'] == 0 else 'warning'
                
                result = {'scans': scans}
                
                # Guardar en caché
                _stats_cache[cache_key] = result
                _stats_cache_time[cache_key] = time.time()
                
                print(f"✅ Escaneos obtenidos directamente de BD. Total: {len(scans)}")
                return jsonify(result), 200
        except Exception as e:
            print(f"⚠️ Error accediendo BD directamente en list_scans: {str(e)}")
            print(traceback.format_exc())
            print("Intentando via HTTP como fallback...")
    
    # Fallback: usar HTTP para obtener escaneos desde la API
    print(f"🔄 Obteniendo escaneos vía HTTP desde: {get_api_url('/api/scans')}")
    try:
        api_url = get_api_url('/api/scans')
        print(f"🌐 URL completa: {api_url}")
        print(f"🌐 Parámetros: limit={limit}, offset={offset}")
        
        headers = {}
        if API_KEY:
            headers['X-API-Key'] = API_KEY
            print(f"🔑 Enviando API Key en headers")
        else:
            print(f"⚠️ No hay API_KEY configurada, la API puede rechazar la petición")
        
        response = requests.get(
            api_url,
            params={'limit': limit, 'offset': offset},
            headers=headers,
            timeout=15  # Aumentado timeout para Render
        )
        
        print(f"📡 Respuesta de API: Status {response.status_code}")
        print(f"📡 Headers de respuesta: {dict(response.headers)}")
        
        if response.status_code == 200:
            result = response.json()
            scans_count = len(result.get('scans', []))
            print(f"✅ Obtenidos {scans_count} escaneos desde la API")
            
            # Log detallado de los primeros escaneos
            if scans_count > 0:
                print(f"📋 Primeros escaneos recibidos:")
                for i, scan in enumerate(result.get('scans', [])[:3]):
                    print(f"   [{i+1}] Scan ID: {scan.get('id')}, Machine: {scan.get('machine_name')}, Issues: {scan.get('issues_found')}, Status: {scan.get('status')}")
            else:
                print(f"⚠️ La API devolvió 200 pero sin escaneos en la respuesta")
                print(f"📋 Respuesta completa: {result}")
            
            # Guardar en caché
            _stats_cache[cache_key] = result
            _stats_cache_time[cache_key] = time.time()
            return jsonify(result), 200
        else:
            print(f"❌ Error obteniendo escaneos: {response.status_code}")
            print(f"❌ Respuesta completa: {response.text[:500]}")
            return jsonify({'error': f'Error obteniendo escaneos: {response.status_code}', 'scans': []}), response.status_code
    except requests.exceptions.Timeout as te:
        print(f"❌ Timeout al obtener escaneos desde la API: {te}")
        return jsonify({'error': 'Timeout al conectar con la API', 'scans': []}), 504
    except requests.exceptions.ConnectionError as ce:
        print(f"❌ Error de conexión con la API: {ce}")
        return jsonify({'error': f'No se pudo conectar con la API: {str(ce)}', 'scans': []}), 503
    except Exception as e:
        print(f"❌ Error inesperado en list_scans (HTTP): {str(e)}")
        print(f"❌ Traceback:")
        print(traceback.format_exc())
        return jsonify({'error': f'Error inesperado: {str(e)}', 'scans': []}), 500

@app.route('/api/scans/<int:scan_id>', methods=['GET'])
@login_required
def get_scan(scan_id):
    """Obtiene un escaneo específico - Usa BD directa si está disponible, sino HTTP"""
    import time
    
    # Caché por scan_id (5 segundos TTL)
    cache_key = f'scan_{scan_id}'
    if cache_key in _stats_cache:
        if time.time() - _stats_cache_time.get(cache_key, 0) < 5:
            return jsonify(_stats_cache[cache_key]), 200
    
    # Intentar acceso directo a BD primero (más rápido)
    if API_DB_AVAILABLE_LOCALLY:
        try:
            with get_api_db_cursor() as cursor:
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
                
                # Obtener resultados
                cursor.execute('''
                    SELECT id, issue_type, issue_name, issue_path, issue_category,
                           alert_level, confidence, detected_patterns, obfuscation_detected,
                           file_hash, ai_analysis, ai_confidence
                    FROM scan_results
                    WHERE scan_id = ?
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
                        'ai_confidence': r[11]
                    })
                
                scan['results'] = results
                
                # Guardar en caché
                _stats_cache[cache_key] = scan
                _stats_cache_time[cache_key] = time.time()
                
                return jsonify(scan), 200
        except Exception as e:
            print(f"⚠️ Error accediendo BD directamente en get_scan: {e}")
            print("🔄 Intentando vía HTTP...")
    
    # Fallback: usar HTTP para obtener escaneo desde la API
    try:
        api_url = get_api_url(f'/api/scans/{scan_id}')
        print(f"🔄 Obteniendo escaneo {scan_id} vía HTTP desde: {api_url}")
        
        headers = {}
        if API_KEY:
            headers['X-API-Key'] = API_KEY
        
        response = requests.get(
            api_url,
            headers=headers,
            timeout=10
        )
        
        print(f"📡 Respuesta de API para scan {scan_id}: Status {response.status_code}")
        
        if response.status_code == 200:
            scan = response.json()
            results_count = len(scan.get('results', []))
            print(f"✅ Obtenido escaneo {scan_id} con {results_count} resultados desde la API")
            # Guardar en caché
            _stats_cache[cache_key] = scan
            _stats_cache_time[cache_key] = time.time()
            return jsonify(scan), 200
        else:
            print(f"❌ Error obteniendo escaneo {scan_id}: {response.status_code} - {response.text[:200]}")
            return jsonify({'error': f'Error obteniendo escaneo: {response.text}'}), response.status_code
    except requests.exceptions.Timeout:
        print(f"❌ Timeout al obtener escaneo {scan_id} desde la API")
        return jsonify({'error': 'Timeout al conectar con la API'}), 504
    except requests.exceptions.ConnectionError as e:
        print(f"❌ Error de conexión con la API: {e}")
        return jsonify({'error': f'No se pudo conectar con la API: {str(e)}'}), 503
    except Exception as e:
        print(f"❌ Error en get_scan (HTTP): {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/api/feedback', methods=['POST'])
@login_required
def submit_feedback():
    """Envía feedback del staff sobre un resultado - OPTIMIZADO: Acceso directo a BD"""
    import re
    
    try:
        data = request.json or {}
        if not data:
            return jsonify({'error': 'No se recibieron datos'}), 400
        
        result_id = data.get('result_id')
        if not result_id:
            return jsonify({'error': 'Se requiere result_id'}), 400
        
        staff_verification = data.get('verification') or data.get('staff_verification')
        staff_notes = data.get('notes') or data.get('staff_notes', '')
        verified_by = data.get('verified_by', session.get('username', 'staff'))
        
        if not staff_verification:
            return jsonify({'error': 'Se requiere verification o staff_verification'}), 400
        
        if staff_verification not in ['hack', 'legitimate']:
            return jsonify({'error': f'Verificación debe ser "hack" o "legitimate"'}), 400
        
        # Acceso directo a BD (SIN HTTP - MUCHO MÁS RÁPIDO)
        with get_api_db_cursor() as cursor:
            # Obtener información del resultado
            cursor.execute('''
                SELECT scan_id, issue_name, issue_path, file_hash, detected_patterns, 
                       obfuscation_detected, confidence
                FROM scan_results
                WHERE id = ?
            ''', (result_id,))
            
            result = cursor.fetchone()
            if not result:
                return jsonify({'error': f'Resultado con id {result_id} no encontrado'}), 404
            
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
            
            # Extraer patrones si es hack
            extracted_patterns = []
            extracted_features = {}
            
            if staff_verification == 'hack':
                name_lower = (issue_name or '').lower()
                path_lower = (issue_path or '').lower()
                hack_keywords = re.findall(r'\b(vape|entropy|inject|bypass|killaura|aimbot|reach|velocity|scaffold|fly|xray|ghost|stealth|undetected|sigma|flux|future|astolfo|whiteout|liquidbounce|wurst|impact)\w*\b', 
                                          name_lower + ' ' + path_lower, re.IGNORECASE)
                extracted_patterns = list(set(hack_keywords))
                
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
                
                # Guardar patrones aprendidos
                if extracted_patterns:
                    pattern_data = [(pattern, feedback_id, pattern) for pattern in extracted_patterns]
                    cursor.executemany('''
                        INSERT OR REPLACE INTO learned_patterns (
                            pattern_type, pattern_value, pattern_category, source_feedback_id,
                            learned_from_count, last_updated_at, is_active
                        ) VALUES ('keyword', ?, 'high_risk', ?, 
                            COALESCE((SELECT learned_from_count FROM learned_patterns WHERE pattern_value = ?), 0) + 1,
                            CURRENT_TIMESTAMP, 1
                        )
                    ''', pattern_data)
                
                extracted_features = {
                    'obfuscation': bool(obfuscation),
                    'confidence': confidence or 0
                }
            elif staff_verification == 'legitimate' and file_hash:
                # Si es legítimo, guardar hash en whitelist
                cursor.execute('''
                    INSERT OR REPLACE INTO learned_hashes (
                        file_hash, is_hack, confirmed_count, last_confirmed_at, source_feedback_id
                    ) VALUES (?, 0, 
                        COALESCE((SELECT confirmed_count FROM learned_hashes WHERE file_hash = ?), 0) + 1,
                        CURRENT_TIMESTAMP, ?
                    )
                ''', (file_hash, file_hash, feedback_id))
            
            # Actualizar feedback con características extraídas
            cursor.execute('''
                UPDATE staff_feedback
                SET extracted_patterns = ?, extracted_features = ?
                WHERE id = ?
            ''', (json.dumps(extracted_patterns), json.dumps(extracted_features), feedback_id))
            
            # Limpiar caché relacionado
            if f'scan_{scan_id}' in _stats_cache:
                del _stats_cache[f'scan_{scan_id}']
            if 'statistics' in _stats_cache:
                del _stats_cache['statistics']
            if 'learned_patterns' in _stats_cache:
                del _stats_cache['learned_patterns']
        
        return jsonify({
            'success': True,
            'feedback_id': feedback_id,
            'extracted_patterns': extracted_patterns,
            'extracted_features': extracted_features,
            'message': 'Feedback guardado exitosamente'
        }), 201
    except Exception as e:
        print(f"Error en submit_feedback: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': f'Error inesperado: {str(e)}'}), 500

@app.route('/api/feedback/batch', methods=['POST'])
@login_required
def submit_feedback_batch():
    """Envía feedback masivo del staff sobre múltiples resultados - OPTIMIZADO: Acceso directo a BD"""
    import re
    
    try:
        data = request.json or {}
        if not data:
            return jsonify({'error': 'No se recibieron datos'}), 400
        
        result_ids = data.get('result_ids', [])
        if not result_ids or not isinstance(result_ids, list):
            return jsonify({'error': 'Se requiere result_ids como lista'}), 400
        
        if len(result_ids) == 0:
            return jsonify({'error': 'La lista de result_ids está vacía'}), 400
        
        staff_verification = data.get('verification') or data.get('staff_verification')
        staff_notes = data.get('notes') or data.get('staff_notes', '')
        verified_by = data.get('verified_by', session.get('username', 'staff'))
        
        if not staff_verification:
            return jsonify({'error': 'Se requiere verification o staff_verification'}), 400
        
        if staff_verification not in ['hack', 'legitimate']:
            return jsonify({'error': f'Verificación debe ser "hack" o "legitimate"'}), 400
        
        # Acceso directo a BD (SIN HTTP - MUCHO MÁS RÁPIDO)
        feedback_ids = []
        all_extracted_patterns = []
        
        with get_api_db_cursor() as cursor:
            # Procesar cada resultado
            for result_id in result_ids:
                # Obtener información del resultado
                cursor.execute('''
                    SELECT scan_id, issue_name, issue_path, file_hash, detected_patterns, 
                           obfuscation_detected, confidence
                    FROM scan_results
                    WHERE id = ?
                ''', (result_id,))
                
                result = cursor.fetchone()
                if not result:
                    continue  # Saltar si no existe
                
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
                feedback_ids.append(feedback_id)
                
                # Extraer patrones si es hack
                extracted_patterns = []
                extracted_features = {}
                
                if staff_verification == 'hack':
                    name_lower = (issue_name or '').lower()
                    path_lower = (issue_path or '').lower()
                    hack_keywords = re.findall(r'\b(vape|entropy|inject|bypass|killaura|aimbot|reach|velocity|scaffold|fly|xray|ghost|stealth|undetected|sigma|flux|future|astolfo|whiteout|liquidbounce|wurst|impact)\w*\b', 
                                              name_lower + ' ' + path_lower, re.IGNORECASE)
                    extracted_patterns = list(set(hack_keywords))
                    all_extracted_patterns.extend(extracted_patterns)
                    
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
                    
                    # Guardar patrones aprendidos
                    if extracted_patterns:
                        pattern_data = [(pattern, feedback_id, pattern) for pattern in extracted_patterns]
                        cursor.executemany('''
                            INSERT OR REPLACE INTO learned_patterns (
                                pattern_type, pattern_value, pattern_category, source_feedback_id,
                                learned_from_count, last_updated_at, is_active
                            ) VALUES ('keyword', ?, 'high_risk', ?, 
                                COALESCE((SELECT learned_from_count FROM learned_patterns WHERE pattern_value = ?), 0) + 1,
                                CURRENT_TIMESTAMP, 1
                            )
                        ''', pattern_data)
                    
                    extracted_features = {
                        'obfuscation': bool(obfuscation),
                        'confidence': confidence or 0
                    }
                elif staff_verification == 'legitimate' and file_hash:
                    # Si es legítimo, guardar hash en whitelist
                    cursor.execute('''
                        INSERT OR REPLACE INTO learned_hashes (
                            file_hash, is_hack, confirmed_count, last_confirmed_at, source_feedback_id
                        ) VALUES (?, 0, 
                            COALESCE((SELECT confirmed_count FROM learned_hashes WHERE file_hash = ?), 0) + 1,
                            CURRENT_TIMESTAMP, ?
                        )
                    ''', (file_hash, file_hash, feedback_id))
                
                # Actualizar feedback con características extraídas
                cursor.execute('''
                    UPDATE staff_feedback
                    SET extracted_patterns = ?, extracted_features = ?
                    WHERE id = ?
                ''', (json.dumps(extracted_patterns), json.dumps(extracted_features), feedback_id))
            
            # Limpiar caché relacionado
            for key in list(_stats_cache.keys()):
                if key.startswith('scan_') or key in ['statistics', 'learned_patterns']:
                    del _stats_cache[key]
        
            return jsonify({
            'success': True,
            'feedback_ids': feedback_ids,
            'processed_count': len(feedback_ids),
            'extracted_patterns': list(set(all_extracted_patterns)),
            'message': f'Feedback masivo guardado: {len(feedback_ids)} resultados procesados'
        }), 201
    except Exception as e:
        print(f"Error en submit_feedback_batch: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': f'Error inesperado: {str(e)}'}), 500

@app.route('/api/feedback/<int:result_id>', methods=['GET'])
def get_feedback(result_id):
    """Obtiene feedback de un resultado específico - OPTIMIZADO: Acceso directo a BD"""
    try:
        # Acceso directo a BD (SIN HTTP - MUCHO MÁS RÁPIDO)
        with get_api_db_cursor() as cursor:
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
                return jsonify({'feedback': None}), 200
            
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
            }), 200
    except Exception as e:
        print(f"Error en get_feedback: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/api/update-model', methods=['POST'])
def update_model():
    """Actualiza el modelo de IA con patrones aprendidos - SOLO ACTUALIZA EL MODELO, NO COMPILA"""
    try:
        headers = {}
        if API_KEY:
            headers['X-API-Key'] = API_KEY
        response = requests.post(
            get_api_url('/api/update-model'),
            headers=headers,
            timeout=30
        )
        if response.status_code == 200:
            data = response.json()
            # NO compilar aquí - solo actualizar el modelo
            # Los clientes descargarán el modelo actualizado automáticamente
            return jsonify({
                'success': True,
                'message': 'Modelo actualizado. Los clientes descargarán automáticamente los nuevos patrones al iniciar.',
                'version': data.get('version'),
                'patterns_count': data.get('patterns_count'),
                'hashes_count': data.get('hashes_count')
            })
        return jsonify({'error': f'Error al actualizar modelo: {response.status_code}', 'details': response.text}), response.status_code
    except requests.exceptions.ConnectionError:
        error_msg = 'No se pudo conectar a la API.'
        if IS_RENDER:
            error_msg += ' En Render, asegúrate de que la API esté configurada correctamente.'
        else:
            error_msg += ' Verifica que esté corriendo en http://localhost:5000'
        return jsonify({'error': error_msg}), 503
    except requests.exceptions.Timeout:
        return jsonify({'error': 'Timeout al conectar con la API. La API puede estar sobrecargada.'}), 504
    except Exception as e:
        print(f"Error en create_token: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': f'Error inesperado: {str(e)}'}), 500

@app.route('/api/learned-patterns', methods=['GET'])
def get_learned_patterns():
    """Obtiene patrones aprendidos - OPTIMIZADO: Acceso directo a BD sin HTTP"""
    import time
    
    # Caché (60 segundos TTL - los patrones no cambian tan frecuentemente)
    cache_key = 'learned_patterns'
    if cache_key in _stats_cache:
        if time.time() - _stats_cache_time.get(cache_key, 0) < 60:
            return jsonify(_stats_cache[cache_key]), 200
    
    try:
        # Acceso directo a BD (SIN HTTP - MUCHO MÁS RÁPIDO)
        with get_api_db_cursor() as cursor:
            # Verificar si la tabla existe y tiene la columna is_active
            try:
                cursor.execute('''
                    SELECT pattern_type, pattern_value, pattern_category, confidence,
                           learned_from_count, first_learned_at, is_active
                    FROM learned_patterns
                    WHERE is_active = 1
                    ORDER BY learned_from_count DESC, confidence DESC
                ''')
            except sqlite3.OperationalError:
                # Si no tiene is_active, consultar sin ese filtro
                try:
                    cursor.execute('''
                        SELECT pattern_type, pattern_value, pattern_category, confidence,
                               learned_from_count, first_learned_at, 1 as is_active
                        FROM learned_patterns
                        ORDER BY learned_from_count DESC, confidence DESC
                    ''')
                except sqlite3.OperationalError:
                    # Si la tabla no existe, retornar vacío
                    result = {'patterns': [], 'total': 0}
                    _stats_cache[cache_key] = result
                    _stats_cache_time[cache_key] = time.time()
                    return jsonify(result), 200
            
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
            
            # Guardar en caché
            _stats_cache[cache_key] = result
            _stats_cache_time[cache_key] = time.time()
            
            return jsonify(result), 200
    except Exception as e:
        print(f"Error en get_learned_patterns: {str(e)}")
        print(traceback.format_exc())
        # Retornar respuesta vacía en lugar de error para no romper la app
        return jsonify({'patterns': [], 'total': 0, 'error': str(e)}), 200

@app.route('/api/ai-model/latest', methods=['GET'])
def get_latest_ai_model():
    """Obtiene el modelo de IA más reciente - OPTIMIZADO: Acceso directo a BD sin HTTP"""
    import time
    
    # Caché (300 segundos TTL - el modelo no cambia tan frecuentemente)
    cache_key = 'ai_model_latest'
    if cache_key in _stats_cache:
        if time.time() - _stats_cache_time.get(cache_key, 0) < 300:
            return jsonify(_stats_cache[cache_key]), 200
    
    try:
        # Acceso directo a BD (SIN HTTP - MUCHO MÁS RÁPIDO)
        with get_api_db_cursor() as cursor:
            # Obtener patrones aprendidos
            try:
                cursor.execute('''
                    SELECT pattern_value, pattern_category, confidence, learned_from_count
                    FROM learned_patterns
                    WHERE is_active = 1
                    ORDER BY learned_from_count DESC
                ''')
            except sqlite3.OperationalError:
                cursor.execute('''
                    SELECT pattern_value, pattern_category, confidence, learned_from_count
                    FROM learned_patterns
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
            try:
                cursor.execute('''
                    SELECT file_hash, is_hack, confirmed_count
                    FROM learned_hashes
                    WHERE is_hack = 1
                    ORDER BY confirmed_count DESC
                ''')
            except sqlite3.OperationalError:
                hashes = []
            else:
                hashes = []
                for row in cursor.fetchall():
                    hashes.append({
                        'hash': row[0],
                        'is_hack': bool(row[1]),
                        'confirmed_count': row[2]
                    })
            
            result = {
                'version': '1.0.0',
                'updated_at': None,
                'patterns': patterns,
                'hashes': hashes,
                'patterns_count': sum(len(p) for p in patterns.values()),
                'hashes_count': len(hashes)
            }
            
            # Guardar en caché
            _stats_cache[cache_key] = result
            _stats_cache_time[cache_key] = time.time()
            
            return jsonify(result), 200
    except Exception as e:
        print(f"Error en get_latest_ai_model: {str(e)}")
        print(traceback.format_exc())
        # Retornar modelo vacío en lugar de error
        return jsonify({
            'version': '1.0.0',
            'updated_at': None,
            'patterns': {'high_risk': [], 'medium_risk': [], 'low_risk': []},
            'hashes': [],
            'patterns_count': 0,
            'hashes_count': 0
        }), 200

@app.route('/api/generate-app', methods=['POST'])
@admin_required
def generate_app():
    """Genera una nueva versión de la aplicación - COMPILA REALMENTE EL EJECUTABLE"""
    # En Render no se puede compilar (requiere PyInstaller y herramientas de Windows)
    if IS_RENDER:
        return jsonify({
            'success': False,
            'error': 'No se puede compilar el ejecutable en Render. Debes compilarlo localmente en Windows usando PyInstaller.'
        }), 400
    
    import subprocess
    import os
    import time
    import hashlib
    from datetime import datetime
    
    def generate():
        try:
            # Paso 1: Actualizar modelo de IA primero (SIN COMPILAR)
            yield f"data: {json.dumps({'step': 'Actualizando modelo de IA con patrones aprendidos...', 'progress': 20})}\n\n"
            time.sleep(0.5)
            
            # Llamar al endpoint de actualización de modelo
            try:
                headers = {}
                if API_KEY:
                    headers['X-API-Key'] = API_KEY
                update_response = requests.post(
                    get_api_url('/api/update-model'),
                    headers=headers,
                    timeout=30
                )
                if update_response.status_code == 200:
                    model_data = update_response.json()
                    patterns_count = model_data.get('patterns_count', 0)
                    hashes_count = model_data.get('hashes_count', 0)
                    step_message = f'✅ Modelo actualizado: {patterns_count} patrones, {hashes_count} hashes. Los clientes descargarán automáticamente.'
                    yield f"data: {json.dumps({'step': step_message, 'progress': 50})}\n\n"
                else:
                    yield f"data: {json.dumps({'step': 'Advertencia: No se pudo actualizar modelo, continuando...', 'progress': 50})}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'step': f'Advertencia: Error actualizando modelo: {str(e)}', 'progress': 50})}\n\n"
            
            time.sleep(0.5)
            
            # Paso 2: Compilar ejecutable (solo si se solicita explícitamente)
            yield f"data: {json.dumps({'step': 'Compilando ejecutable con PyInstaller (esto puede tardar varios minutos)...', 'progress': 60})}\n\n"
            time.sleep(0.5)
            
            # Ruta al script de compilación
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            compile_script = os.path.join(project_root, 'BAT', '01-Compilar', 'COMPILAR_FINAL.bat')
            
            yield f"data: {json.dumps({'step': f'Buscando script en: {compile_script}', 'progress': 55})}\n\n"
            
            if not os.path.exists(compile_script):
                yield f"data: {json.dumps({'step': f'ERROR: Script de compilación no encontrado en: {compile_script}', 'progress': 100, 'error': True})}\n\n"
                return
            
            yield f"data: {json.dumps({'step': f'✅ Script encontrado: {compile_script}', 'progress': 58})}\n\n"
            
            # Ejecutar compilación
            yield f"data: {json.dumps({'step': 'Ejecutando compilación (esto puede tardar varios minutos)...', 'progress': 60})}\n\n"
            
            # Cambiar al directorio del script para ejecutarlo correctamente
            compile_dir = os.path.dirname(compile_script)
            compile_script_name = os.path.basename(compile_script)
            
            # Ejecutar en segundo plano y capturar salida
            # Usar cmd.exe /c para ejecutar el .bat correctamente en Windows
            process = subprocess.Popen(
                ['cmd.exe', '/c', compile_script_name],
                cwd=compile_dir,
                shell=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Combinar stderr con stdout
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Monitorear progreso y capturar salida en tiempo real
            progress = 60
            output_lines = []
            last_update = time.time()
            
            while process.poll() is None:
                # Leer salida línea por línea
                line = process.stdout.readline()
                if line:
                    output_lines.append(line.strip())
                    # Mostrar últimas líneas importantes
                    if any(keyword in line.lower() for keyword in ['compilando', 'building', 'creating', 'success', 'error', 'completado']):
                        yield f"data: {json.dumps({'step': f'Compilando: {line.strip()[:100]}', 'progress': progress})}\n\n"
                
                # Actualizar progreso cada 3 segundos
                current_time = time.time()
                if current_time - last_update >= 3:
                    progress = min(90, progress + 2)
                    yield f"data: {json.dumps({'step': 'Compilando... (por favor espera)', 'progress': progress})}\n\n"
                    last_update = current_time
                
                time.sleep(0.5)
            
            # Leer cualquier salida restante
            remaining_output = process.stdout.read()
            if remaining_output:
                output_lines.extend(remaining_output.splitlines())
            
            # Verificar resultado
            return_code = process.returncode
            output_text = '\n'.join(output_lines)
            
            if return_code != 0:
                error_msg = output_text[-500:] if len(output_text) > 500 else output_text
                yield f"data: {json.dumps({'step': f'ERROR en compilación (código {return_code}): {error_msg}', 'progress': 100, 'error': True})}\n\n"
                return
            
            # Verificar si hay mensajes de error en la salida
            if 'error' in output_text.lower() or 'failed' in output_text.lower():
                error_msg = output_text[-500:] if len(output_text) > 500 else output_text
                yield f"data: {json.dumps({'step': f'Advertencia en compilación: {error_msg}', 'progress': 95})}\n\n"
            
            # Paso 3: Buscar ejecutable compilado
            yield f"data: {json.dumps({'step': 'Buscando ejecutable compilado...', 'progress': 92})}\n\n"
            time.sleep(0.5)
            
            exe_path = os.path.join(project_root, 'source', 'dist', 'MinecraftSSTool.exe')
            if not os.path.exists(exe_path):
                yield f"data: {json.dumps({'step': 'ERROR: Ejecutable no encontrado después de compilación', 'progress': 100, 'error': True})}\n\n"
                return
            
            # Paso 4: Calcular hash y tamaño
            yield f"data: {json.dumps({'step': 'Verificando integridad del ejecutable...', 'progress': 95})}\n\n"
            time.sleep(0.5)
            
            file_size = os.path.getsize(exe_path)
            with open(exe_path, 'rb') as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()
            
            # Paso 5: Copiar a carpeta de descargas
            downloads_dir = os.path.join(project_root, 'downloads')
            os.makedirs(downloads_dir, exist_ok=True)
            
            version = datetime.now().strftime('%Y%m%d_%H%M%S')
            download_filename = f'MinecraftSSTool_v{version}.exe'
            download_path = os.path.join(downloads_dir, download_filename)
            
            import shutil
            shutil.copy2(exe_path, download_path)
            
            # Paso 6: Registrar versión en BD
            try:
                headers = {}
                if API_KEY:
                    headers['X-API-Key'] = API_KEY
                version_response = requests.post(
                    get_api_url('/api/versions'),
                    json={
                        'version': f'1.{version}',
                        'download_url': f'/download/{download_filename}',
                        'changelog': f'Versión generada automáticamente con {model_data.get("patterns_count", 0)} patrones aprendidos',
                        'file_size': file_size,
                        'file_hash': file_hash
                    },
                    headers=headers,
                    timeout=5
                )
            except:
                pass
            
            # Paso 7: Completado
            step_message = f'✅ Aplicación generada exitosamente.\n\nArchivo: {download_filename}\nTamaño: {file_size / (1024*1024):.1f} MB\nHash: {file_hash[:16]}...\n\nNOTA: Las actualizaciones de IA se descargan automáticamente sin necesidad de recompilar.'
            yield f"data: {json.dumps({'step': step_message, 'progress': 100, 'success': True, 'download_url': f'/download/{download_filename}', 'filename': download_filename})}\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'step': f'ERROR: {str(e)}', 'progress': 100, 'error': True})}\n\n"
    
    return Response(generate(), mimetype='text/event-stream')

@app.route('/download/<filename>')
def download_file(filename):
    """Endpoint para descargar el ejecutable generado - Requiere autenticación o token"""
    import os
    from flask import send_file, request
    
    # Verificar si hay un token en la query string
    token = request.args.get('token')
    if token:
        # Usar el endpoint con token
        return download_with_token(token)
    
    # Si no hay token, requerir autenticación (comportamiento anterior)
    from auth import login_required
    return login_required(lambda: _send_file_download(filename))()

def _send_file_download(filename):
    """Función auxiliar para enviar el archivo"""
    import os
    from flask import send_file, jsonify
    
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Lista de ubicaciones posibles en orden de prioridad (optimizado)
    possible_paths = [
        os.path.join(project_root, 'downloads', filename),
        os.path.join(project_root, 'source', 'dist', filename) if filename == 'MinecraftSSTool.exe' else None,
        os.path.join(project_root, filename)
    ]
    
    # Buscar el primer archivo que exista (evita múltiples checks)
    file_path = None
    for path in possible_paths:
        if path and os.path.exists(path) and os.path.isfile(path):
            file_path = path
            break
    
    if file_path:
        return send_file(file_path, as_attachment=True, download_name=filename)
    else:
        return jsonify({'error': f'Archivo no encontrado: {filename}'}), 404

@app.route('/d/<token>')
def download_with_token(token):
    """Endpoint público para descargar usando token temporal (similar a Ocean)"""
    import os
    import sqlite3
    from flask import send_file, jsonify, request
    from datetime import datetime
    from auth import DATABASE
    
    try:
        # Buscar el enlace en la BD
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, filename, expires_at, max_downloads, download_count, is_active
            FROM download_links
            WHERE token = ? AND is_active = 1
        ''', (token,))
        
        link = cursor.fetchone()
        
        if not link:
            conn.close()
            return jsonify({'error': 'Enlace de descarga inválido o expirado'}), 404
        
        link_id, filename, expires_at, max_downloads, download_count, is_active = link
        
        # Obtener el token de escaneo del parámetro de la URL (si existe)
        scan_token = request.args.get('token', None)
        
        # Asegurar que max_downloads sea un entero (puede venir como string desde SQLite)
        try:
            max_downloads = int(max_downloads) if max_downloads is not None else -1
            download_count = int(download_count) if download_count is not None else 0
        except (ValueError, TypeError):
            max_downloads = -1
            download_count = 0
        
        print(f"🔍 Verificando enlace de descarga: ID={link_id}, max_downloads={max_downloads}, download_count={download_count}, is_active={is_active}")
        
        # Verificar expiración
        if expires_at:
            expires_dt = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
            if datetime.now() > expires_dt:
                conn.close()
                print(f"❌ Enlace expirado: {expires_at}")
                return jsonify({'error': 'Este enlace de descarga ha expirado'}), 410
        
        # Verificar límite de descargas (solo si max_downloads no es -1, que significa ilimitado)
        if max_downloads != -1 and download_count >= max_downloads:
            conn.close()
            print(f"❌ Límite alcanzado: download_count={download_count} >= max_downloads={max_downloads}")
            return jsonify({'error': 'Este enlace ha alcanzado el límite de descargas'}), 403
        
        print(f"✅ Enlace válido, procediendo con descarga")
        
        # Incrementar contador de descargas
        cursor.execute('''
            UPDATE download_links
            SET download_count = download_count + 1
            WHERE id = ?
        ''', (link_id,))
        
        # Si alcanzó el límite, desactivar el enlace (solo si max_downloads no es -1)
        if max_downloads != -1 and download_count + 1 >= max_downloads:
            cursor.execute('''
                UPDATE download_links
                SET is_active = 0
                WHERE id = ?
            ''', (link_id,))
        
        conn.commit()
        conn.close()
        
        # Buscar y enviar el archivo
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        possible_paths = [
            os.path.join(project_root, 'downloads', filename),
            os.path.join(project_root, 'source', 'dist', filename) if filename == 'MinecraftSSTool.exe' else None,
            os.path.join(project_root, filename)
        ]
        
        file_path = None
        for path in possible_paths:
            if path and os.path.exists(path) and os.path.isfile(path):
                file_path = path
                break
        
        if file_path:
            # Si hay un token de escaneo en la URL, crear un ZIP con el ejecutable y config.json
            if scan_token and filename == 'MinecraftSSTool.exe':
                try:
                    import zipfile
                    import tempfile
                    import json as json_lib
                    
                    # Crear un archivo ZIP temporal
                    temp_dir = tempfile.gettempdir()
                    zip_path = os.path.join(temp_dir, f'MinecraftSSTool_with_token_{secrets.token_hex(8)}.zip')
                    
                    # Crear config.json con el token y todos los campos necesarios
                    api_url = get_api_url('').rstrip('/api')
                    web_url = request.host_url.rstrip('/') if not IS_RENDER else os.environ.get('RENDER_EXTERNAL_URL', request.host_url).rstrip('/')
                    
                    config_data = {
                        "discord_webhook": "",
                        "auth_token": "",
                        "scan_timeout": 300,
                        "scan_token": scan_token,
                        "api_url": api_url,
                        "web_url": web_url,
                        "enable_db_integration": True,
                        "enable_ai_analysis": True,
                        "enable_discord_report": False,
                        "enable_web_report": True
                    }
                    
                    # Crear el ZIP con el ejecutable y el config.json
                    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                        # Agregar el ejecutable
                        zipf.write(file_path, filename)
                        # Agregar el config.json
                        zipf.writestr('config.json', json_lib.dumps(config_data, indent=2))
                    
                    print(f"✅ ZIP creado con ejecutable y config.json: {zip_path}")
                    print(f"🔑 Token incluido en config: {scan_token[:20]}...")
                    
                    # Enviar el ZIP
                    response = send_file(zip_path, as_attachment=True, download_name='MinecraftSSTool.zip', mimetype='application/zip')
                    
                    # Limpiar el archivo temporal después de enviarlo (en un thread separado)
                    def cleanup_temp_file():
                        import time
                        time.sleep(5)  # Esperar 5 segundos antes de eliminar
                        try:
                            if os.path.exists(zip_path):
                                os.remove(zip_path)
                                print(f"🗑️ Archivo temporal eliminado: {zip_path}")
                        except Exception as e:
                            print(f"⚠️ Error eliminando archivo temporal: {e}")
                    
                    import threading
                    threading.Thread(target=cleanup_temp_file, daemon=True).start()
                    
                    return response
                except Exception as e:
                    print(f"⚠️ Error creando ZIP con token: {e}")
                    traceback.print_exc()
                    # Continuar con la descarga normal si falla la creación del ZIP
            
            return send_file(file_path, as_attachment=True, download_name=filename)
        else:
            return jsonify({'error': f'Archivo no encontrado: {filename}'}), 404
    except Exception as e:
        print(f"❌ Error en download_with_token: {e}")
        print(traceback.format_exc())
        return jsonify({'error': f'Error al procesar descarga: {str(e)}'}), 500

@app.route('/api/scans/<int:scan_id>/report-html', methods=['GET'])
@login_required
def get_scan_report_html(scan_id):
    """Genera un reporte HTML descargable para un escaneo específico - OPTIMIZADO: Acceso directo a BD"""
    from datetime import datetime
    
    try:
        # Acceso directo a BD (SIN HTTP - MUCHO MÁS RÁPIDO)
        with get_api_db_cursor() as cursor:
            # Obtener información del escaneo
            cursor.execute('''
                SELECT id, started_at, completed_at, status,
                       total_files_scanned, issues_found, scan_duration, machine_id, machine_name
                FROM scans
                WHERE id = ?
            ''', (scan_id,))
            
            row = cursor.fetchone()
            if not row:
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
        
        # Generar HTML (mismo formato que la API)
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
        
        return Response(html, mimetype='text/html', headers={
            'Content-Disposition': f'attachment; filename=ASPERS_Report_Scan_{scan_id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.html'
        })
    except Exception as e:
        print(f"Error en get_scan_report_html: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/api/get-latest-exe', methods=['GET'])
def get_latest_exe():
    """Obtiene el ejecutable más reciente disponible (ya compilado)"""
    import os
    from datetime import datetime
    
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Buscar en downloads/ primero (versiones con timestamp)
    downloads_dir = os.path.join(project_root, 'downloads')
    latest_file = None
    latest_time = 0
    latest_filename = None
    
    if os.path.exists(downloads_dir):
        try:
            for filename in os.listdir(downloads_dir):
                if filename.endswith('.exe'):
                    file_path = os.path.join(downloads_dir, filename)
                    if os.path.isfile(file_path):
                        file_time = os.path.getmtime(file_path)
                        if file_time > latest_time:
                            latest_time = file_time
                            latest_file = file_path
                            latest_filename = filename
        except Exception as e:
            print(f"Error buscando en downloads: {e}")
    
    # Si no hay en downloads, buscar en source/dist
    if not latest_file:
        exe_path = os.path.join(project_root, 'source', 'dist', 'MinecraftSSTool.exe')
        if os.path.exists(exe_path):
            latest_file = exe_path
            latest_time = os.path.getmtime(exe_path)
            latest_filename = 'MinecraftSSTool.exe'
    
    # También buscar en la raíz del proyecto (por si se subió directamente)
    if not latest_file:
        root_exe = os.path.join(project_root, 'MinecraftSSTool.exe')
        if os.path.exists(root_exe):
            latest_file = root_exe
            latest_time = os.path.getmtime(root_exe)
            latest_filename = 'MinecraftSSTool.exe'
    
    if latest_file and os.path.exists(latest_file):
        if not latest_filename:
            latest_filename = os.path.basename(latest_file)
        file_size = os.path.getsize(latest_file)
        return jsonify({
            'success': True,
            'download_url': f'/download/{latest_filename}',
            'filename': latest_filename,
            'file_size': file_size,
            'modified_at': datetime.fromtimestamp(latest_time).isoformat()
        })
    else:
        error_msg = 'No se encontró ejecutable compilado.'
        if IS_RENDER:
            error_msg += '\n\nEl archivo .exe debe estar en GitHub en una de estas ubicaciones:\n'
            error_msg += '• source/dist/MinecraftSSTool.exe\n'
            error_msg += '• downloads/MinecraftSSTool.exe\n\n'
            error_msg += 'Pasos para solucionarlo:\n'
            error_msg += '1. Compila el .exe localmente\n'
            error_msg += '2. Ejecuta SUBIR_EXE_A_GITHUB.bat\n'
            error_msg += '3. Sube los cambios a GitHub\n'
            error_msg += '4. Render se actualizará automáticamente'
        else:
            error_msg += ' Asegúrate de que el archivo .exe esté en la carpeta downloads/, source/dist/, o en la raíz del proyecto.'
        
        return jsonify({
            'success': False,
            'error': error_msg,
            'is_render': IS_RENDER
        }), 404

@app.route('/api/download-links', methods=['POST'])
@login_required
def create_download_link():
    """Crea un nuevo enlace de descarga temporal (solo para staff/admin)"""
    import secrets
    import sqlite3
    from datetime import datetime, timedelta
    from auth import is_admin, DATABASE
    
    print(f"🔗 Solicitud de creación de enlace de descarga recibida")
    print(f"📋 Datos recibidos: {request.json}")
    
    # Verificar permisos (solo staff/admin)
    user_id = session.get('user_id')
    print(f"👤 User ID: {user_id}")
    
    if not is_admin(user_id):
        print(f"❌ Usuario {user_id} no tiene permisos de admin")
        return jsonify({'error': 'No tienes permisos para crear enlaces de descarga'}), 403
    
    data = request.json or {}
    filename = data.get('filename', 'MinecraftSSTool.exe')
    expires_hours = data.get('expires_hours', 24)  # Por defecto 24 horas
    max_downloads = data.get('max_downloads', 1)  # Por defecto 1 descarga
    description = data.get('description', '')
    
    print(f"📁 Archivo: {filename}")
    print(f"⏰ Expira en: {expires_hours} horas")
    print(f"📊 Máximo de descargas: {max_downloads}")
    
    # Generar token único
    token = secrets.token_urlsafe(32)
    print(f"🔑 Token generado: {token[:20]}...")
    
    # Calcular fecha de expiración
    expires_at = datetime.now() + timedelta(hours=expires_hours)
    
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO download_links (token, filename, created_by, expires_at, max_downloads, description)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (token, filename, user_id, expires_at.isoformat(), max_downloads, description))
        
        link_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        print(f"✅ Enlace guardado en BD con ID: {link_id}")
        
        # Generar URL completa
        base_url = request.host_url.rstrip('/')
        if IS_RENDER:
            render_url = os.environ.get('RENDER_EXTERNAL_URL', '')
            if render_url:
                base_url = render_url.rstrip('/')
        download_url = f"{base_url}/d/{token}"
        
        print(f"🌐 URL generada: {download_url}")
        
        return jsonify({
            'success': True,
            'link_id': link_id,
            'token': token,
            'download_url': download_url,
            'expires_at': expires_at.isoformat(),
            'max_downloads': max_downloads,
            'filename': filename
        }), 201
        
    except Exception as e:
        print(f"❌ Error creando enlace de descarga: {e}")
        print(traceback.format_exc())
        return jsonify({'error': f'Error al crear enlace: {str(e)}'}), 500

@app.route('/api/download-links', methods=['GET'])
@login_required
def list_download_links():
    """Lista todos los enlaces de descarga (solo para staff/admin)"""
    import sqlite3
    from auth import is_admin
    
    # Verificar permisos
    if not is_admin(session.get('user_id')):
        return jsonify({'error': 'No tienes permisos para ver enlaces de descarga'}), 403
    
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT dl.id, dl.token, dl.filename, dl.created_at, dl.expires_at,
                   dl.max_downloads, dl.download_count, dl.is_active, dl.description,
                   u.username as created_by_username
            FROM download_links dl
            LEFT JOIN users u ON dl.created_by = u.id
            ORDER BY dl.created_at DESC
            LIMIT 50
        ''')
        
        links = []
        for row in cursor.fetchall():
            links.append({
                'id': row[0],
                'token': row[1],
                'filename': row[2],
                'created_at': row[3],
                'expires_at': row[4],
                'max_downloads': row[5],
                'download_count': row[6],
                'is_active': bool(row[7]),
                'description': row[8],
                'created_by': row[9]
            })
        
        conn.close()
        
        # Generar URLs completas
        base_url = request.host_url.rstrip('/')
        if IS_RENDER:
            render_url = os.environ.get('RENDER_EXTERNAL_URL', '')
            if render_url:
                base_url = render_url.rstrip('/')
        
        for link in links:
            link['download_url'] = f"{base_url}/d/{link['token']}"
        
        return jsonify({'success': True, 'links': links}), 200
        
    except Exception as e:
        print(f"❌ Error listando enlaces: {e}")
        print(traceback.format_exc())
        return jsonify({'error': f'Error al listar enlaces: {str(e)}'}), 500

@app.route('/api/download-links/<int:link_id>', methods=['DELETE'])
@login_required
def delete_download_link(link_id):
    """Desactiva un enlace de descarga (solo para staff/admin)"""
    import sqlite3
    from auth import is_admin
    
    # Verificar permisos
    if not is_admin(session.get('user_id')):
        return jsonify({'error': 'No tienes permisos para eliminar enlaces'}), 403
    
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE download_links
            SET is_active = 0
            WHERE id = ?
        ''', (link_id,))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Enlace desactivado'}), 200
        
    except Exception as e:
        return jsonify({'error': f'Error al desactivar enlace: {str(e)}'}), 500

@app.route('/api/import/echo', methods=['POST'])
@login_required
def import_echo_scan():
    """Importa resultados históricos de Echo Scanner"""
    try:
        data = request.json or {}
        
        # Validar datos requeridos
        if 'echo_id' not in data:
            return jsonify({'error': 'Se requiere echo_id'}), 400
        
        # Importar usando el script
        import sys
        import os
        sys.path.insert(0, os.path.dirname(__file__))
        from importar_resultados_echo import create_echo_scan, init_db_if_needed
        
        init_db_if_needed()
        scan_id = create_echo_scan(data)
        
        if scan_id:
            return jsonify({
                'success': True,
                'scan_id': scan_id,
                'message': f'Escaneo de Echo importado exitosamente con ID {scan_id}'
            }), 201
        else:
            return jsonify({
                'success': False,
                'error': 'Error al importar el escaneo'
            }), 500
            
    except Exception as e:
        return jsonify({
            'error': f'Error inesperado: {str(e)}',
            'traceback': traceback.format_exc()
        }), 500

if __name__ == '__main__':
    print("🌐 Iniciando aplicación web de ASPERS Projects...")
    api_url_display = os.environ.get('API_URL') or (API_BASE_URL if IS_RENDER else API_BASE_URL)
    print(f"📡 Conectado a API: {api_url_display}")
    print(f"🔑 API Key configurada: {'Sí' if API_KEY != 'change-this-in-production' else 'No (usar valor por defecto)'}")
    print("⚠️  NOTA: Asegúrate de que la API esté corriendo en http://localhost:5000")
    print("⚠️  NOTA: La API Key debe coincidir con la configurada en api_server.py")
    app.run(host='0.0.0.0', port=8080, debug=True)

