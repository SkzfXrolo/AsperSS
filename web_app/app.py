"""
Aplicación Web Flask para Panel del Staff de ASPERS Projects
"""
import sys as _sys
_sys.stdout.reconfigure(line_buffering=True)  # forzar stdout unbuffered
from flask import Flask, render_template, request, jsonify, session, Response, redirect, url_for, make_response, flash
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
    has_role, is_admin, is_company_admin, is_company_user,
    get_staff_role, can_change_verdict, can_manage_tokens, can_manage_staff,
    STAFF_ROLE_HIERARCHY
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
    # Migración de seguridad: crear download_links en PostgreSQL si no existe
    try:
        with get_api_db_cursor() as _cur:
            _cur.execute('''
                CREATE TABLE IF NOT EXISTS download_links (
                    id SERIAL PRIMARY KEY,
                    token VARCHAR(255) UNIQUE NOT NULL,
                    filename VARCHAR(255) NOT NULL,
                    created_by VARCHAR(100),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP,
                    max_downloads INTEGER DEFAULT 1,
                    download_count INTEGER DEFAULT 0,
                    is_active BOOLEAN DEFAULT TRUE,
                    description TEXT
                )
            ''')
            _cur.execute('CREATE INDEX IF NOT EXISTS idx_dl_token ON download_links(token)')
        print("✅ Tabla download_links verificada/creada en PostgreSQL")
    except Exception as _e:
        print(f"⚠️ Error verificando download_links: {_e}")

# Inicializar en un thread separado para no bloquear el inicio
import threading
threading.Thread(target=init_db_async, daemon=True).start()

# P3 #20 — Reentrenamiento automático semanal del clasificador RF
def _weekly_ml_retrain():
    """Reentrena el clasificador RF y registra el resultado."""
    try:
        from ml_classifier import get_classifier
        clf = get_classifier()
        with get_api_db_cursor() as cursor:
            result = clf.train(cursor)
        if result.get('trained'):
            print(f"[ML Weekly] Reentrenamiento OK: accuracy={result.get('accuracy')}, samples={result.get('samples')}")
        else:
            print(f"[ML Weekly] No reentrenado: {result.get('error')}")
    except Exception as e:
        print(f"[ML Weekly] Error: {e}")

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(_weekly_ml_retrain, 'cron', day_of_week='sun', hour=3, minute=0,
                       id='weekly_ml_retrain', replace_existing=True)
    _scheduler.start()
    print('[Scheduler] Reentrenamiento semanal ML activado (domingos 03:00 UTC)')
except Exception as _sch_err:
    print(f'[Scheduler] APScheduler no disponible: {_sch_err}')

# Discord HTTP Interactions (sin gateway, sin rate-limit)
try:
    import discord_interactions as _di
    print('[Discord] HTTP Interactions activado.')
except Exception as _disc_err:
    print(f'[Discord] Interactions no disponible: {_disc_err}')

# Health check endpoints (simplificado - sin import externo)

# Configuración
# Detectar si estamos en Render o en desarrollo local
RENDER_EXTERNAL_URL = os.environ.get('RENDER_EXTERNAL_URL')  # Render proporciona esta variable
IS_RENDER = bool(RENDER_EXTERNAL_URL)

if IS_RENDER:
    # La API está integrada en esta misma app — usar la propia URL de Render
    api_url_env = os.environ.get('API_URL')
    if api_url_env:
        API_BASE_URL = api_url_env.rstrip('/')
    else:
        API_BASE_URL = RENDER_EXTERNAL_URL.rstrip('/')
        print(f"✅ API_URL apunta a esta misma app: {API_BASE_URL}")
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

@app.route('/discord/interactions', methods=['POST'])
def discord_interactions():
    """Endpoint para Discord HTTP Interactions (slash commands sin gateway)."""
    try:
        import discord_interactions as _di
        from flask import request as _req
        sig  = _req.headers.get('X-Signature-Ed25519', '')
        ts   = _req.headers.get('X-Signature-Timestamp', '')
        body = _req.get_data(as_text=True)
        if not _di.verify_signature(sig, ts, body):
            return make_response('Invalid signature', 401)
        data = _req.get_json(force=True)
        result = _di.handle_interaction(data)
        return jsonify(result)
    except Exception as e:
        print(f'[Discord] Error en /discord/interactions: {e}')
        return make_response('Internal error', 500)


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
        
        try:
            result = authenticate_user(username, password)
        except Exception as e:
            print(f"❌ Error en authenticate_user: {e}")
            error_msg = 'Error interno al conectar con la base de datos. Intenta de nuevo.'
            if request.is_json:
                return jsonify({'success': False, 'error': error_msg}), 500
            return render_template('login.html', error=error_msg)

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
    staff_role = get_staff_role(user) if user else 'helper'
    return render_template('panel.html', user=user, staff_role=staff_role)

@app.route('/aspers-sa', methods=['GET', 'POST'])
def admin_subscriptions():
    """Panel SuperAdmin — acceso solo mediante URL directa (no linkada públicamente)"""
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        if username == 'Rodrigo' and password == 'Rodrigo@1':
            session['admin_subscriptions'] = True
            return redirect('/aspers-sa')
        else:
            return render_template('admin_subscriptions_login.html', error='Credenciales incorrectas')

    if not session.get('admin_subscriptions'):
        return render_template('admin_subscriptions_login.html')

    try:
        from auth import list_companies, list_users
        companies = list_companies() or []
        users = list_users() or []
        individual_users = [u for u in users if not u.get('company_id')]
        company_users = [u for u in users if u.get('company_id')]
        # Convertir Decimal a float para que Jinja2 lo maneje sin problemas
        for c in companies:
            if c.get('subscription_price') is not None:
                c['subscription_price'] = float(c['subscription_price'])
        return render_template('admin_subscriptions.html',
                               companies=companies,
                               individual_users=individual_users,
                               company_users=company_users)
    except Exception as _e:
        import traceback as _tb
        _err = _tb.format_exc()
        print(f"❌ Error en /aspers-sa: {_e}\n{_err}")
        return f"<pre style='color:red;padding:20px'>Error interno en Super Admin:\n{_err}</pre>", 500

@app.route('/aspers-sa/logout')
def admin_subscriptions_logout():
    session.pop('admin_subscriptions', None)
    return redirect('/aspers-sa')

@app.route('/aspers-sa/create-company', methods=['POST'])
def admin_subscriptions_create_company():
    if not session.get('admin_subscriptions'):
        return redirect('/aspers-sa')
    from auth import create_company, update_company
    name = request.form.get('name', '').strip()
    if not name:
        flash('El nombre de empresa es requerido', 'error')
        return redirect('/aspers-sa')
    contact_email = request.form.get('contact_email', '').strip() or None
    try:
        subscription_price = float(request.form.get('subscription_price', 13.0))
    except (ValueError, TypeError):
        subscription_price = 13.0
    subscription_status = request.form.get('subscription_status', 'active')
    try:
        max_users = int(request.form.get('max_users', 8))
    except (ValueError, TypeError):
        max_users = 8
    try:
        max_admins = int(request.form.get('max_admins', 3))
    except (ValueError, TypeError):
        max_admins = 3
    subscription_end_date = request.form.get('subscription_end_date') or None
    notes = request.form.get('notes', '').strip() or None
    result = create_company(
        name=name,
        contact_email=contact_email,
        subscription_type='enterprise',
        subscription_status=subscription_status,
        subscription_price=subscription_price,
        max_users=max_users,
        max_admins=max_admins,
        created_by=None,
        notes=notes
    )
    if result.get('success'):
        if subscription_end_date:
            update_company(company_id=result['company_id'], subscription_end_date=subscription_end_date)
        flash(f'Empresa "{name}" creada exitosamente', 'ok')
    else:
        flash(result.get('error', 'Error al crear empresa'), 'error')
    return redirect('/aspers-sa')

@app.route('/aspers-sa/update-company', methods=['POST'])
def admin_subscriptions_update_company():
    if not session.get('admin_subscriptions'):
        return redirect('/aspers-sa')
    from auth import update_company
    company_id = request.form.get('company_id')
    if not company_id:
        flash('ID de empresa requerido', 'error')
        return redirect('/aspers-sa')
    kwargs = {}
    for field in ('name', 'contact_email', 'subscription_status', 'subscription_end_date'):
        val = request.form.get(field, '').strip()
        if val:
            kwargs[field] = val
    for field in ('subscription_price', 'max_users', 'max_admins'):
        raw = request.form.get(field, '').strip()
        if raw:
            try:
                kwargs[field] = float(raw) if field == 'subscription_price' else int(raw)
            except (ValueError, TypeError):
                pass
    result = update_company(company_id=company_id, **kwargs)
    if result.get('success'):
        flash('Empresa actualizada exitosamente', 'ok')
    else:
        flash(result.get('error', 'Error al actualizar empresa'), 'error')
    return redirect('/aspers-sa')

@app.route('/aspers-sa/toggle-status', methods=['POST'])
def admin_subscriptions_toggle_status():
    if not session.get('admin_subscriptions'):
        return redirect('/aspers-sa')
    from auth import update_company
    company_id = request.form.get('company_id')
    new_status = request.form.get('new_status', 'active')
    if not company_id:
        flash('ID de empresa requerido', 'error')
        return redirect('/aspers-sa')
    result = update_company(company_id=company_id, subscription_status=new_status)
    if result.get('success'):
        label = 'activada' if new_status == 'active' else 'suspendida'
        flash(f'Empresa {label} exitosamente', 'ok')
    else:
        flash(result.get('error', 'Error al cambiar estado'), 'error')
    return redirect('/aspers-sa')

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
            
            # Consulta optimizada para PostgreSQL
            for query, key in [
                ("SELECT COUNT(*) FROM scans", 'total_scans'),
                ("SELECT COUNT(*) FROM scans WHERE status = 'running'", 'active_scans'),
                ("SELECT COUNT(DISTINCT machine_id) FROM scans WHERE machine_id IS NOT NULL AND machine_id != ''", 'unique_machines'),
                ("SELECT COUNT(*) FROM scan_results WHERE alert_level = 'CRITICAL'", 'severe_detections'),
                ("SELECT COUNT(*) FROM scan_results", 'total_results'),
                ("SELECT COUNT(*) FROM scan_tokens WHERE is_active = TRUE", 'active_tokens'),
                ("SELECT COUNT(*) FROM ban_history", 'total_bans'),
            ]:
                try:
                    cursor.execute(query)
                    row = cursor.fetchone()
                    stats[key] = (_row_get(row, 0, list(row.keys())[0]) if row else 0) or 0
                except Exception:
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


@app.route('/api/dashboard/extended', methods=['GET'])
@login_required
def get_dashboard_extended():
    """Estadísticas extendidas para el dashboard: veredictos, top hacks, tiempo promedio."""
    import time
    cache_key = 'dashboard_extended'
    if cache_key in _stats_cache:
        if time.time() - _stats_cache_time.get(cache_key, 0) < 60:
            return jsonify(_stats_cache[cache_key]), 200
    try:
        with get_api_db_cursor() as cursor:
            # Veredictos
            clean = hack = pending = 0
            try:
                cursor.execute("SELECT COUNT(*) FROM scans WHERE verdict = 'clean'")
                r = cursor.fetchone(); clean = (_row_get(r, 0, list(r.keys())[0]) if r else 0) or 0
                cursor.execute("SELECT COUNT(*) FROM scans WHERE verdict = 'hack'")
                r = cursor.fetchone(); hack = (_row_get(r, 0, list(r.keys())[0]) if r else 0) or 0
                cursor.execute("SELECT COUNT(*) FROM scans WHERE verdict IS NULL OR verdict = ''")
                r = cursor.fetchone(); pending = (_row_get(r, 0, list(r.keys())[0]) if r else 0) or 0
            except Exception:
                pass

            # Top hacks este mes
            top_issues = []
            try:
                cursor.execute(f"""
                    SELECT issue_name, COUNT(*) as cnt
                    FROM scan_results
                    WHERE alert_level IN ('CRITICAL','HIGH')
                      AND created_at >= DATE_TRUNC('month', CURRENT_DATE)
                    GROUP BY issue_name
                    ORDER BY cnt DESC
                    LIMIT 5
                """)
                for row in cursor.fetchall():
                    top_issues.append({'name': _row_get(row, 0, 'issue_name'), 'count': _row_get(row, 1, 'cnt')})
            except Exception:
                try:
                    # SQLite fallback
                    cursor.execute("""
                        SELECT issue_name, COUNT(*) as cnt
                        FROM scan_results
                        WHERE alert_level IN ('CRITICAL','HIGH')
                          AND created_at >= date('now','start of month')
                        GROUP BY issue_name
                        ORDER BY cnt DESC
                        LIMIT 5
                    """)
                    for row in cursor.fetchall():
                        top_issues.append({'name': _row_get(row, 0, 'issue_name'), 'count': _row_get(row, 1, 'cnt')})
                except Exception:
                    pass

            # Tiempo promedio de escaneo (en segundos)
            avg_duration = 0
            try:
                cursor.execute("SELECT AVG(scan_duration) FROM scans WHERE scan_duration IS NOT NULL AND scan_duration > 0")
                r = cursor.fetchone()
                avg_duration = round((_row_get(r, 0, list(r.keys())[0]) if r else 0) or 0, 1)
            except Exception:
                pass

            result = {
                'verdicts': {'clean': clean, 'hack': hack, 'pending': pending},
                'top_issues': top_issues,
                'avg_duration': avg_duration,
            }
            _stats_cache[cache_key] = result
            _stats_cache_time[cache_key] = time.time()
            return jsonify(result), 200
    except Exception as e:
        print(f"Error en get_dashboard_extended: {e}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/statistics/recidivism', methods=['GET'])
@login_required
def get_recidivism():
    """Máquinas con múltiples veredictos 'hack' en los últimos N días.
    Útil para identificar jugadores reincidentes."""
    import time
    days    = request.args.get('days', 90, type=int)
    min_h   = request.args.get('min_hacks', 2, type=int)
    limit   = min(request.args.get('limit', 20, type=int), 50)
    cache_key = f'recidivism_{days}_{min_h}_{limit}'
    if cache_key in _stats_cache:
        if time.time() - _stats_cache_time.get(cache_key, 0) < 120:
            return jsonify(_stats_cache[cache_key]), 200
    try:
        with get_api_db_cursor() as cursor:
            cursor.execute(f'''
                SELECT machine_name, minecraft_username,
                       COUNT(*) AS hack_count,
                       AVG(risk_score) AS avg_risk,
                       MAX(started_at) AS last_scan,
                       MAX(id) AS last_scan_id
                FROM scans
                WHERE verdict = 'hack'
                  AND started_at >= CURRENT_TIMESTAMP - INTERVAL '{days} days'
                GROUP BY machine_name, minecraft_username
                HAVING COUNT(*) >= {min_h}
                ORDER BY hack_count DESC, avg_risk DESC
                LIMIT {limit}
            ''')
            rows = cursor.fetchall() or []
        result = [{
            'machine_name':      str(_row_get(r, 0, 'machine_name') or ''),
            'minecraft_username': str(_row_get(r, 1, 'minecraft_username') or 'N/A'),
            'hack_count':        int(_row_get(r, 2, 'hack_count') or 0),
            'avg_risk':          round(float(_row_get(r, 3, 'avg_risk') or 0), 1),
            'last_scan':         str(_row_get(r, 4, 'last_scan') or '')[:19],
            'last_scan_id':      int(_row_get(r, 5, 'last_scan_id') or 0),
        } for r in rows]
        out = {'recidivists': result, 'days': days, 'min_hacks': min_h}
        _stats_cache[cache_key] = out
        _stats_cache_time[cache_key] = time.time()
        return jsonify(out), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/statistics/issue_types', methods=['GET'])
@login_required
def get_issue_type_stats():
    """Top issue_types por frecuencia y hack_rate. Útil para entender
    qué tipos de hacks están circulando en el servidor."""
    import time
    days  = request.args.get('days', 30, type=int)
    limit = min(request.args.get('limit', 15, type=int), 50)
    cache_key = f'issue_types_{days}_{limit}'
    if cache_key in _stats_cache:
        if time.time() - _stats_cache_time.get(cache_key, 0) < 120:
            return jsonify(_stats_cache[cache_key]), 200
    try:
        with get_api_db_cursor() as cursor:
            cursor.execute(f'''
                SELECT sr.issue_type,
                       COUNT(*) AS total,
                       COUNT(*) FILTER (WHERE s.verdict = 'hack') AS in_hacks,
                       AVG(sr.confidence) AS avg_conf,
                       MAX(sr.alert_level) AS max_alert
                FROM scan_results sr
                JOIN scans s ON sr.scan_id = s.id
                WHERE sr.created_at >= CURRENT_TIMESTAMP - INTERVAL '{days} days'
                  AND sr.issue_type IS NOT NULL
                GROUP BY sr.issue_type
                ORDER BY total DESC
                LIMIT {limit}
            ''')
            rows = cursor.fetchall() or []
        result = []
        for r in rows:
            total   = int(_row_get(r, 1, 'total') or 0)
            in_hacks = int(_row_get(r, 2, 'in_hacks') or 0)
            result.append({
                'issue_type':  str(_row_get(r, 0, 'issue_type') or ''),
                'total':       total,
                'in_hacks':    in_hacks,
                'hack_rate':   round(in_hacks / total, 3) if total else 0,
                'avg_conf':    round(float(_row_get(r, 3, 'avg_conf') or 0), 3),
                'max_alert':   str(_row_get(r, 4, 'max_alert') or ''),
            })
        out = {'issue_types': result, 'days': days}
        _stats_cache[cache_key] = out
        _stats_cache_time[cache_key] = time.time()
        return jsonify(out), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


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
    """Crea un token de escaneo: 1 uso, 30 minutos. Requiere feedback pendiente = 0."""
    try:
        user = get_user_by_id(session.get('user_id'))
        if not user:
            return jsonify({'success': False, 'error': 'Usuario no encontrado'}), 401
        if not can_manage_tokens(user):
            return jsonify({'success': False, 'error': 'No tienes permisos para crear tokens (se requiere Admin o superior)'}), 403

        created_by = user.get('username', 'web_app')
        user_id = user.get('id')

        # Verificar feedback pendiente: scans completados sin feedback enviado
        with get_api_db_cursor() as cursor:
            cursor.execute(
                f'''SELECT s.id FROM scans s
                    JOIN scan_tokens st ON s.scan_token = st.token
                    WHERE st.created_by = {_PH}
                    AND s.status = 'completed'
                    AND NOT EXISTS (
                        SELECT 1 FROM staff_feedback sf WHERE sf.scan_id = s.id
                    )
                    LIMIT 1''',
                (created_by,)
            )
            pending = cursor.fetchone()

        if pending:
            return jsonify({
                'success': False,
                'error': 'Tienes un escaneo sin feedback. Envía el feedback desde la aplicación antes de crear un nuevo token.'
            }), 400

        # Token: 1 uso, 30 minutos
        scan_token = secrets.token_urlsafe(32)
        expires_at = (datetime.datetime.now() + datetime.timedelta(minutes=30)).isoformat()
        max_uses = 1

        with get_api_db_cursor() as cursor:
            token_id = _insert_id(
                cursor,
                f'INSERT INTO scan_tokens (token, expires_at, max_uses, created_by)'
                f' VALUES ({_PH},{_PH},{_PH},{_PH})',
                (scan_token, expires_at, max_uses, created_by)
            )

        download_link = None
        try:
            dl_expires = (datetime.datetime.now() + datetime.timedelta(minutes=30)).isoformat()
            download_token = secrets.token_urlsafe(32)
            with get_api_db_cursor() as cursor:
                cursor.execute(
                    f'INSERT INTO download_links (token, filename, created_by, expires_at, max_downloads)'
                    f' VALUES ({_PH},{_PH},{_PH},{_PH},{_PH})',
                    (download_token, 'ArgusScanner.exe', user_id, dl_expires, 1)
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
            'created_by': created_by,
            'type': 'scan_token',
            'download_url': download_link
        }), 201

    except Exception as e:
        print(f"ERROR create_token: {type(e).__name__}: {e}")
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
        
        if not can_manage_tokens(user):
            return jsonify({'success': False, 'error': 'No tienes permisos para eliminar tokens (se requiere Admin o superior)'}), 403

        with get_api_db_cursor() as cursor:
            cursor.execute(f'SELECT id, created_by FROM scan_tokens WHERE id = {_PH}', (token_id,))
            token_row = cursor.fetchone()
            if not token_row:
                return jsonify({'success': False, 'error': 'Token no encontrado'}), 404

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
    """Valida un token de escaneo en la BD. Retorna (token_id, error_msg, created_by, allowed_mods)."""
    try:
        with get_api_db_cursor() as cursor:
            try:
                cursor.execute(
                    f'SELECT id, expires_at, used_count, max_uses, is_active, created_by, allowed_mods FROM scan_tokens WHERE token = {_PH}',
                    (token,)
                )
            except Exception:
                cursor.execute(
                    f'SELECT id, expires_at, used_count, max_uses, is_active, created_by FROM scan_tokens WHERE token = {_PH}',
                    (token,)
                )
            row = cursor.fetchone()

        if not row:
            return None, 'Token no encontrado', None, None

        token_id     = _row_get(row, 0, 'id')
        expires_at   = _row_get(row, 1, 'expires_at')
        used_count   = _row_get(row, 2, 'used_count') or 0
        max_uses     = _row_get(row, 3, 'max_uses')
        is_active    = _row_get(row, 4, 'is_active')
        created_by   = _row_get(row, 5, 'created_by')
        allowed_mods_raw = _row_get(row, 6, 'allowed_mods') if len(row) > 6 else None

        if not is_active:
            return None, 'Token desactivado', None, None

        if expires_at:
            if isinstance(expires_at, str):
                exp = datetime.datetime.fromisoformat(expires_at.replace('Z', '+00:00')).replace(tzinfo=None)
            else:
                exp = expires_at.replace(tzinfo=None) if hasattr(expires_at, 'tzinfo') else expires_at
            if datetime.datetime.now() > exp:
                return None, 'Token expirado', None, None

        if max_uses and max_uses > 0 and used_count >= max_uses:
            return None, 'Token ha alcanzado el limite de usos', None, None

        allowed_mods = []
        if allowed_mods_raw:
            try:
                allowed_mods = json.loads(allowed_mods_raw) if isinstance(allowed_mods_raw, str) else allowed_mods_raw
            except Exception:
                allowed_mods = []

        return token_id, None, created_by, allowed_mods
    except Exception as e:
        print(f"Error validando token: {e}\n{traceback.format_exc()}")
        return None, f'Error validando token: {str(e)}', None, None


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

        token_id, error, created_by, allowed_mods = _validate_scan_token_direct(token)
        if error:
            return jsonify({'valid': False, 'error': error}), 200

        return jsonify({
            'valid': True, 'token_id': token_id, 'created_by': created_by,
            'allowed_mods': allowed_mods or [],
            'message': 'Token valido',
        }), 200
    except Exception as e:
        print(f"Error en validate_token_endpoint: {e}\n{traceback.format_exc()}")
        return jsonify({'valid': False, 'error': str(e)}), 500


@app.route('/api/debug/last-scan')
def debug_last_scan():
    """Endpoint de diagnóstico — muestra el último scan en bruto desde la BD"""
    try:
        with get_api_db_cursor() as cursor:
            # Estado de columnas disponibles en la tabla scans
            cursor.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'scans' ORDER BY ordinal_position
            """)
            cols = [r['column_name'] if hasattr(r, 'keys') else r[0] for r in cursor.fetchall()]

            # Último scan
            cursor.execute('SELECT * FROM scans ORDER BY id DESC LIMIT 3')
            scans_raw = cursor.fetchall()
            scans_out = []
            for row in scans_raw:
                if hasattr(row, 'keys'):
                    d = dict(row)
                    # no mostrar screenshot completo
                    if d.get('screenshot'):
                        d['screenshot'] = f'<{len(d["screenshot"])} chars>'
                    scans_out.append(d)
                else:
                    scans_out.append(list(row))

            # Resultados del último scan
            results_count = 0
            if scans_raw:
                last_id = scans_raw[0]['id'] if hasattr(scans_raw[0], 'keys') else scans_raw[0][0]
                cursor.execute('SELECT COUNT(*) as cnt FROM scan_results WHERE scan_id = %s', (last_id,))
                r = cursor.fetchone()
                results_count = r['cnt'] if hasattr(r, 'keys') else r[0]

        return jsonify({
            'scans_columns': cols,
            'last_3_scans': scans_out,
            'last_scan_results_count': results_count,
            'ph': _PH,
            'use_pg': _USE_PG,
        })
    except Exception as e:
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500


# Current released scanner version — update this when distributing a new build
CURRENT_SCANNER_VERSION = "1.3.0"

@app.route('/sw.js')
def service_worker():
    """Serve service worker from root scope so it can control the full origin."""
    resp = make_response(app.send_static_file('sw.js'))
    resp.headers['Content-Type'] = 'application/javascript'
    resp.headers['Service-Worker-Allowed'] = '/'
    resp.headers['Cache-Control'] = 'no-cache'
    return resp


@app.route('/api/scanner/version', methods=['GET'])
def scanner_version():
    """Returns latest scanner version info so the .exe can self-update."""
    return jsonify({
        'version': CURRENT_SCANNER_VERSION,
        'download_url': '',   # fill in the direct .exe URL when hosting a new build
        'changelog': '',
    })


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
        os_name      = data.get('os', 'Windows')[:32]

        print(f"[DEBUG start_scan] token={scan_token[:12]}..., machine={machine_name}, ip={ip_address}")
        token_id, error, _created_by, _allowed_mods = _validate_scan_token_direct(scan_token)
        if error:
            print(f"[DEBUG start_scan] token inválido: {error}")
            return jsonify({'error': error}), 401

        mc_info = None
        if data.get('mc_version') or data.get('mc_launcher'):
            mc_info = json.dumps({
                'version': data.get('mc_version'),
                'launcher': data.get('mc_launcher'),
                'mods': data.get('mc_mods', []),
                'java_agents': data.get('java_agents', []),
            })

        with get_api_db_cursor() as cursor:
            cursor.execute(
                f'UPDATE scan_tokens SET used_count = used_count + 1,'
                f' is_active = CASE WHEN max_uses > 0 AND (used_count + 1) >= max_uses THEN FALSE ELSE is_active END'
                f' WHERE id = {_PH}',
                (token_id,)
            )
            scan_id = _insert_id(
                cursor,
                f'INSERT INTO scans (token_id, scan_token, status, machine_id, machine_name, ip_address, country, minecraft_username)'
                f" VALUES ({_PH},{_PH},'running',{_PH},{_PH},{_PH},{_PH},{_PH})",
                (token_id, scan_token, machine_id, machine_name, ip_address, country, mc_username)
            )
            if mc_info:
                try:
                    cursor.execute('SAVEPOINT mc_info_save')
                    cursor.execute(f'UPDATE scans SET mc_info = {_PH} WHERE id = {_PH}', (mc_info, scan_id))
                    cursor.execute('RELEASE SAVEPOINT mc_info_save')
                except Exception:
                    try:
                        cursor.execute('ROLLBACK TO SAVEPOINT mc_info_save')
                    except Exception:
                        pass
            try:
                cursor.execute('SAVEPOINT os_save')
                cursor.execute(f'UPDATE scans SET os = {_PH} WHERE id = {_PH}', (os_name, scan_id))
                cursor.execute('RELEASE SAVEPOINT os_save')
            except Exception:
                try:
                    cursor.execute('ROLLBACK TO SAVEPOINT os_save')
                except Exception:
                    pass

        print(f"[DEBUG start_scan] scan_id={scan_id} creado OK")
        return jsonify({'success': True, 'scan_id': scan_id, 'status': 'running', 'message': 'Escaneo iniciado'}), 201
    except Exception as e:
        print(f"[DEBUG start_scan] ERROR: {e}\n{traceback.format_exc()}")
        return jsonify({'error': f'Error iniciando escaneo: {str(e)}'}), 500


# Rutas/nombres de software legítimo que el scanner client puede mandar como falsos positivos.
# Aplicado server-side para que funcione con cualquier versión del exe.
_SERVER_FP_FRAGMENTS = [
    # Sistema Windows
    'windows\\system32', 'windows\\syswow64', 'windows\\winsxs',
    'program files\\microsoft', 'program files (x86)\\microsoft',
    # AppData — apps legítimas
    'webview2runtime', 'trust protection lists', 'pspc_sdk',
    'appdata\\local\\packages',        # Windows Store apps (firmadas, sandboxed)
    'appdata\\local\\origin',          # EA Origin
    'appdata\\local\\nvidia',
    'appdata\\roaming\\opera software',
    'electronic arts\\ea desktop',
    'site-packages',                   # librerías Python instaladas
    # Navegadores — rutas de datos del perfil
    'appdata\\local\\google\\chrome',
    'appdata\\local\\microsoft\\edge',
    'appdata\\local\\brave-browser',
    'appdata\\local\\vivaldi',
    'appdata\\roaming\\mozilla\\firefox',
    # Launchers / clientes legítimos de Minecraft
    'lunar client', 'lunarclient',
    'steam\\steamapps', 'epicgames', 'origin games',
    'tlauncher', 'prismlauncher', 'badlion client',
    'gdlauncher', 'multimc', 'atlauncher', 'curseforgeapp',
    # Dominios seguros en URLs de historial/descargas de navegador
    'github.com', 'modrinth.com', 'curseforge.com', 'files.minecraftforge.net',
    'spigotmc.org', 'papermc.io', 'fabricmc.net', 'quiltmc.org',
    'optifine.net', 'minecraftforge.net', 'cdn.modrinth.com',
    'minecraft.net', 'mojang.com', 'minecraftjava.com',
    'lifehacker.com', 'lifehack.org', 'medium.com',
    'stackoverflow.com', 'reddit.com', 'youtube.com',
    'google.com', 'bing.com', 'wikipedia.org',
    # Mods legítimos conocidos (nombres de archivo)
    'optifine', 'fabricmc', 'quiltmc', 'sodium', 'lithium', 'phosphor',
    'iris', 'indium', 'ferritecore', 'lazydfu', 'starlight',
    'journeymap', 'just enough items', 'jei-', 'rei-',
    # Otros programas legítimos
    'voicemod',
    'minecraftsstool',                 # el propio SS tool del servidor
    # Drivers y software de hardware
    'nvidia corporation', 'amd\\radeon', 'intel corporation',
    'discord\\app-', 'teamspeak 3 client',
]


_lp_cache: dict = {'paths': [], 'ts': 0.0}
_LP_CACHE_TTL = 300  # 5 minutos


def _get_learned_legit_paths() -> list:
    """Devuelve lista de rutas legítimas aprendidas por el staff (caché 5 min)."""
    import time as _time
    if _time.time() - _lp_cache['ts'] < _LP_CACHE_TTL:
        return _lp_cache['paths']
    try:
        with get_api_db_cursor() as _cur:
            _cur.execute(
                "SELECT pattern_value FROM learned_patterns"
                " WHERE is_active = TRUE AND pattern_type = 'legitimate_path'"
            )
            rows = _cur.fetchall()
        paths = [(_row_get(r, 0, 'pattern_value') or '').lower().replace('/', '\\')
                 for r in (rows or []) if r]
        _lp_cache['paths'] = paths
        _lp_cache['ts']    = _time.time()
    except Exception:
        pass  # si falla la BD usamos la caché vieja o lista vacía
    return _lp_cache['paths']


import re as _re_fp
# Categorías que solo existían en EXEs viejos con parsers buggeados — 100% FP
_LEGACY_FP_CATEGORIES = {'EXECUTED_DELETED', 'APPCOMPAT', 'USN_FORENSICS'}
# Patrones de basura binaria en nombres — parser viejo decodificaba .pf como UTF-16
_BINARY_GARBAGE_RE = _re_fp.compile(
    r'\bLMEM\b|Windows\.Data\.|Matrix3x2|\.CenterX|\.CenterY|'
    r'ItemReference|MEOW\b|CloudData|RevealBrush|XamlAnim|'
    r'BaseM\s+I&|BorderBrush\s+[A-Z]|\bMEM\s+[A-Z]|\bLE[A-Z]\b',
    _re_fp.IGNORECASE
)


def _is_server_false_positive(result: dict) -> bool:
    """Devuelve True si el resultado es un falso positivo conocido y debe descartarse."""
    # Categorías de EXE antiguo con parsers buggeados
    categoria = (result.get('categoria') or result.get('issue_category') or '').upper()
    if categoria in _LEGACY_FP_CATEGORIES:
        return True

    ruta     = (result.get('ruta', '') or '').lower().replace('/', '\\')
    nombre   = (result.get('nombre', '') or result.get('archivo', '') or '')
    combined = ruta + '|' + nombre.lower()

    # Basura binaria decodificada por parsers viejos (prefetch/shimcache binario)
    if _BINARY_GARBAGE_RE.search(nombre):
        return True

    if any(frag in combined for frag in _SERVER_FP_FRAGMENTS):
        return True
    # También revisar rutas aprendidas por el staff (cacheadas 5 min)
    for lp in _get_learned_legit_paths():
        if lp and lp in combined:
            return True
    return False


def _calculate_risk_score(results, return_breakdown=False):
    """Calcula el risk score de un scan según las evidencias encontradas.
    Retorna score 0–100. Con return_breakdown=True devuelve (score, breakdown_list).
    """
    score = 0
    breakdown = []
    _counted = set()  # evitar sumar el mismo tipo varias veces (solo el primer hit)

    CATEGORY_SCORES = {
        'java_agent':       90,
        'javaagent':        90,
        'ahk':              70,
        'autohotkey':       70,
        'macro':            60,
        'logitech':         55,
        'razer':            55,
        'dns':              40,
        'dns_cache':        40,
        'event_log':        30,
        'jna':              35,
        'rar':              20,
        'compressed':       20,
        'amcache':          45,
        'recentdocs':       25,
        'runmru':           20,
        'compatibility_store': 35,
        'usn_journal':      30,
        'prefetch':         35,
        'vm':               15,
        'debugger':         55,
        'process_hacker':   40,
        'explorer_suspicious': 60,
    }

    ALERT_SCORES = {
        'CRITICAL':         50,
        'MUY_SOSPECHOSO':   40,
        'SOSPECHOSO':       25,
        'POCO_SOSPECHOSO':  10,
    }

    for r in results:
        tipo   = (r.get('tipo') or '').lower().replace(' ', '_')
        cat    = (r.get('categoria') or '').lower().replace(' ', '_')
        alerta = (r.get('alerta') or '').upper()
        nombre = (r.get('issue_name') or r.get('nombre') or tipo)[:80]

        # Bonus por categoría/tipo (una sola vez por categoría)
        for key, pts in CATEGORY_SCORES.items():
            if key in tipo or key in cat:
                if key not in _counted:
                    score += pts
                    _counted.add(key)
                    breakdown.append({'source': nombre, 'points': pts, 'reason': f'Tipo detectado: {key}'})
                break

        # Puntos adicionales por nivel de alerta
        alert_pts = ALERT_SCORES.get(alerta, 0)
        if alert_pts > 0:
            score += alert_pts
            breakdown.append({'source': nombre, 'points': alert_pts, 'reason': f'Nivel de alerta: {alerta}'})

    final_score = min(score, 100)
    if return_breakdown:
        # Sort by points desc, only keep top contributors
        breakdown_sorted = sorted(breakdown, key=lambda x: x['points'], reverse=True)[:15]
        return final_score, breakdown_sorted
    return final_score


@app.route('/api/scans/<int:scan_id>/results', methods=['POST'])
def submit_scan_results(scan_id):
    """Recibe y almacena resultados de escaneo (usado por el cliente .exe) — sin login requerido"""
    print(f"\n[DEBUG submit_scan_results] ===== RECIBIENDO RESULTADOS =====")
    print(f"[DEBUG] scan_id={scan_id}, IP={request.remote_addr}")
    data = request.json
    if not data:
        print(f"[DEBUG] ERROR: no JSON recibido")
        return jsonify({'error': 'No se recibieron datos'}), 400

    print(f"[DEBUG] status={data.get('status')}, files={data.get('total_files_scanned')}, "
          f"issues={data.get('issues_found')}, duration={data.get('scan_duration')}, "
          f"results_count={len(data.get('results', []))}, "
          f"has_screenshot={'si' if data.get('screenshot') else 'no'}")

    try:
        with get_api_db_cursor() as cursor:
            print(f"[DEBUG] Ejecutando UPDATE scans WHERE id={scan_id}")
            cursor.execute(
                f'UPDATE scans SET status = {_PH}, completed_at = CURRENT_TIMESTAMP,'
                f' total_files_scanned = {_PH}, total_dirs_scanned = {_PH},'
                f' issues_found = {_PH}, scan_duration = {_PH}'
                f' WHERE id = {_PH}',
                (data.get('status', 'completed'), data.get('total_files_scanned', 0),
                 data.get('total_dirs_scanned', 0),
                 data.get('issues_found', 0), data.get('scan_duration', 0), scan_id)
            )
            print(f"[DEBUG] UPDATE rowcount={cursor.rowcount}")
            if cursor.rowcount == 0:
                print(f"[DEBUG] ERROR: scan_id={scan_id} no encontrado en BD (rowcount=0)")
                return jsonify({'error': f'Escaneo {scan_id} no encontrado'}), 404

            # Guardar screenshot y mc_info si vienen en el payload (columnas opcionales)
            screenshot = data.get('screenshot') or None
            mc_info = None
            if data.get('mc_version') or data.get('mc_launcher'):
                import json as _j
                mc_info = _j.dumps({
                    'version': data.get('mc_version'),
                    'launcher': data.get('mc_launcher'),
                    'mods': data.get('mc_mods', []),
                    'java_agents': data.get('java_agents', []),
                })
            if screenshot or mc_info:
                try:
                    cursor.execute('SAVEPOINT opt_save')
                    updates, vals = [], []
                    if screenshot:
                        updates.append(f'screenshot = {_PH}')
                        vals.append(screenshot)
                    if mc_info:
                        updates.append(f'mc_info = {_PH}')
                        vals.append(mc_info)
                    vals.append(scan_id)
                    cursor.execute(f'UPDATE scans SET {", ".join(updates)} WHERE id = {_PH}', vals)
                    cursor.execute('RELEASE SAVEPOINT opt_save')
                except Exception:
                    try:
                        cursor.execute('ROLLBACK TO SAVEPOINT opt_save')
                    except Exception:
                        pass

            results = data.get('results', [])
            # Filtro server-side: descartar falsos positivos conocidos (funciona con cualquier version del exe)
            before = len(results)
            results = [r for r in results if not _is_server_false_positive(r)]
            if len(results) < before:
                print(f"[DEBUG] FP filter: {before} → {len(results)} resultados ({before - len(results)} descartados)")
            print(f"[DEBUG] Insertando {len(results)} resultados en scan_results")
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
                if results:
                    print(f"[DEBUG] Primer resultado: tipo={results[0].get('tipo')}, "
                          f"nombre={results[0].get('nombre') or results[0].get('archivo')}, "
                          f"alerta={results[0].get('alerta')}")
                cursor.executemany(
                    f'INSERT INTO scan_results'
                    f' (scan_id, issue_type, issue_name, issue_path, issue_category,'
                    f'  alert_level, confidence, detected_patterns, obfuscation_detected,'
                    f'  file_hash, ai_analysis, ai_confidence)'
                    f' VALUES ({_PH},{_PH},{_PH},{_PH},{_PH},{_PH},{_PH},{_PH},{_PH},{_PH},{_PH},{_PH})',
                    batch
                )
                print(f"[DEBUG] executemany completado")

            # Calcular y guardar risk_score
            try:
                cursor.execute('SAVEPOINT risk_score_save')
                risk_score = _calculate_risk_score(results)
                cursor.execute(
                    f'UPDATE scans SET risk_score = {_PH} WHERE id = {_PH}',
                    (risk_score, scan_id)
                )
                cursor.execute('RELEASE SAVEPOINT risk_score_save')
                print(f"[DEBUG] risk_score={risk_score} guardado")
            except Exception:
                try:
                    cursor.execute('ROLLBACK TO SAVEPOINT risk_score_save')
                except Exception:
                    pass

        print(f"[DEBUG] ===== SCAN {scan_id} COMPLETADO OK: "
              f"{len(data.get('results',[]))} resultados, status={data.get('status','completed')} =====\n")

        try:
            _di.notify_new_scan(
                scan_id,
                data.get('machine_name', 'N/A'),
                data.get('username', data.get('minecraft_username', 'N/A')),
                locals().get('risk_score', 0),
                len(results),
            )
        except Exception:
            pass

        return jsonify({'success': True, 'message': 'Resultados almacenados'})
    except Exception as e:
        print(f"[DEBUG] ===== ERROR en submit_scan_results scan_id={scan_id} =====")
        print(f"[DEBUG] {e}")
        print(traceback.format_exc())
        return jsonify({'error': f'Error almacenando resultados: {str(e)}'}), 500


@app.route('/api/scans', methods=['GET'])
@login_required
def list_scans():
    """Lista escaneos - Usa BD directa si está disponible, sino HTTP"""
    import time
    
    limit       = request.args.get('limit', 50, type=int)
    offset      = request.args.get('offset', 0, type=int)
    search      = (request.args.get('search') or '').strip()
    verdict_f   = (request.args.get('verdict') or '').strip().lower()
    date_from   = (request.args.get('date_from') or '').strip()
    date_to     = (request.args.get('date_to') or '').strip()
    machine_name_f = (request.args.get('machine_name') or '').strip()
    country_f   = (request.args.get('country') or '').strip()
    risk_f      = (request.args.get('risk') or '').strip().lower()  # hack|suspicious|clean
    os_f        = (request.args.get('os') or '').strip()
    staff_f     = (request.args.get('staff') or '').strip()

    has_filters = bool(search or verdict_f or date_from or date_to or machine_name_f or country_f or risk_f or os_f or staff_f)

    # Caché solo cuando no hay filtros activos
    cache_key = f'scans_list_{limit}_{offset}'
    if not has_filters and cache_key in _stats_cache:
        if time.time() - _stats_cache_time.get(cache_key, 0) < 10:
            return jsonify(_stats_cache[cache_key]), 200

    # Intentar acceso directo a BD primero (más rápido) - BD unificada siempre disponible
    if API_DB_AVAILABLE_LOCALLY:
        try:
            print(f"🔄 Intentando obtener escaneos directamente de la BD local...")
            with get_api_db_cursor() as cursor:
                # Construir WHERE dinámico
                conditions = []
                params = []
                if machine_name_f:
                    conditions.append(f's.machine_name ILIKE {_PH}')
                    params.append(f'%{machine_name_f}%')
                if search:
                    conditions.append(f'(s.machine_name ILIKE {_PH} OR s.minecraft_username ILIKE {_PH} OR s.ip_address ILIKE {_PH})')
                    params.extend([f'%{search}%'] * 3)
                if verdict_f:
                    if verdict_f == 'pending':
                        conditions.append(f"(s.verdict IS NULL OR s.verdict = '')")
                    else:
                        conditions.append(f's.verdict = {_PH}')
                        params.append(verdict_f)
                if date_from:
                    conditions.append(f's.started_at >= {_PH}')
                    params.append(date_from)
                if date_to:
                    conditions.append(f's.started_at <= {_PH}')
                    params.append(date_to + ' 23:59:59')
                if country_f:
                    conditions.append(f's.country ILIKE {_PH}')
                    params.append(f'%{country_f}%')
                if risk_f == 'hack':
                    conditions.append(f's.risk_score >= 70')
                elif risk_f == 'suspicious':
                    conditions.append(f's.risk_score >= 30 AND s.risk_score < 70')
                elif risk_f == 'clean':
                    conditions.append(f's.risk_score < 30')
                if os_f:
                    conditions.append(f's.os ILIKE {_PH}')
                    params.append(f'%{os_f}%')
                if staff_f:
                    conditions.append(f'st.created_by ILIKE {_PH}')
                    params.append(f'%{staff_f}%')
                where = ('WHERE ' + ' AND '.join(conditions)) if conditions else ''
                params += [limit, offset]

                cursor.execute(f'''
                    SELECT s.id, s.scan_token, s.started_at, s.completed_at, s.status,
                           s.total_files_scanned, s.issues_found, s.scan_duration, s.machine_name,
                           s.minecraft_username, s.ip_address, s.country,
                           st.created_by AS scanned_by, s.risk_score, s.verdict
                    FROM scans s
                    LEFT JOIN scan_tokens st ON s.token_id = st.id
                    {where}
                    ORDER BY s.started_at DESC
                    LIMIT {_PH} OFFSET {_PH}
                ''', params)

                scans = []
                scan_ids = []
                for row in cursor.fetchall():
                    scan_id = _row_get(row, 0, 'id')
                    scan_ids.append(scan_id)
                    scans.append({
                        'id': scan_id,
                        'scan_token': _row_get(row, 1, 'scan_token'),
                        'started_at': _row_get(row, 2, 'started_at'),
                        'completed_at': _row_get(row, 3, 'completed_at'),
                        'status': _row_get(row, 4, 'status'),
                        'total_files_scanned': _row_get(row, 5, 'total_files_scanned'),
                        'issues_found': _row_get(row, 6, 'issues_found'),
                        'scan_duration': _row_get(row, 7, 'scan_duration'),
                        'machine_name': _row_get(row, 8, 'machine_name'),
                        'minecraft_username': _row_get(row, 9, 'minecraft_username'),
                        'ip_address': _row_get(row, 10, 'ip_address'),
                        'country': _row_get(row, 11, 'country'),
                        'scanned_by': _row_get(row, 12, 'scanned_by') or '',
                        'risk_score': int(_row_get(row, 13, 'risk_score') or 0),
                        'verdict': _row_get(row, 14, 'verdict') or 'pending',
                    })
                
                print(f"📊 Escaneos encontrados en BD local: {len(scans)}")
                
                # Calcular preview de severidad (una sola query optimizada)
                if scan_ids:
                    placeholders = ','.join([_PH] * len(scan_ids))
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
                        scan_id = _row_get(row, 0, 'scan_id')
                        critical = _row_get(row, 1, 'critical') or 0
                        suspicious = _row_get(row, 2, 'suspicious') or 0
                        low = _row_get(row, 3, 'low') or 0
                        total = _row_get(row, 4, 'total') or 0
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
                            is_clean = not (scan.get('issues_found') or 0)
                            scan['severity_summary'] = 'LIMPIO' if is_clean else 'SOSPECHOSO'
                            scan['severity_badge'] = 'success' if is_clean else 'warning'

                # Obtener verdict y risk_score de columnas opcionales
                if scan_ids:
                    try:
                        cursor.execute('SAVEPOINT opt_verdict')
                        placeholders2 = ','.join([_PH] * len(scan_ids))
                        cursor.execute(f'''
                            SELECT id, verdict, risk_score
                            FROM scans WHERE id IN ({placeholders2})
                        ''', scan_ids)
                        for vrow in cursor.fetchall():
                            sid = _row_get(vrow, 0, 'id')
                            for s in scans:
                                if s['id'] == sid:
                                    s['verdict'] = _row_get(vrow, 1, 'verdict')
                                    s['risk_score'] = int(_row_get(vrow, 2, 'risk_score') or 0)
                                    break
                        cursor.execute('RELEASE SAVEPOINT opt_verdict')
                    except Exception:
                        try:
                            cursor.execute('ROLLBACK TO SAVEPOINT opt_verdict')
                        except Exception:
                            pass

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
                # Columnas base (siempre existen desde la primera versión del schema)
                cursor.execute(f'''
                    SELECT id, token_id, scan_token, started_at, completed_at, status,
                           total_files_scanned, issues_found, scan_duration,
                           machine_id, machine_name, ip_address, country, minecraft_username
                    FROM scans
                    WHERE id = {_PH}
                ''', (scan_id,))

                row = cursor.fetchone()
                if not row:
                    return jsonify({'error': 'Escaneo no encontrado'}), 404

                scan = {
                    'id': _row_get(row, 0, 'id'),
                    'token_id': _row_get(row, 1, 'token_id'),
                    'scan_token': _row_get(row, 2, 'scan_token'),
                    'started_at': str(_row_get(row, 3, 'started_at') or ''),
                    'completed_at': str(_row_get(row, 4, 'completed_at') or ''),
                    'status': _row_get(row, 5, 'status'),
                    'total_files_scanned': _row_get(row, 6, 'total_files_scanned') or 0,
                    'total_dirs_scanned': 0,
                    'issues_found': _row_get(row, 7, 'issues_found') or 0,
                    'scan_duration': _row_get(row, 8, 'scan_duration') or 0,
                    'machine_id': _row_get(row, 9, 'machine_id'),
                    'machine_name': _row_get(row, 10, 'machine_name'),
                    'ip_address': _row_get(row, 11, 'ip_address'),
                    'country': _row_get(row, 12, 'country'),
                    'minecraft_username': _row_get(row, 13, 'minecraft_username'),
                    'verdict': None, 'verdict_reason': None,
                    'verdict_by': None, 'verdict_at': '',
                }

                # Columnas opcionales: total_dirs_scanned, verdict, screenshot, mc_info
                # Usa SAVEPOINT para que un fallo (columna inexistente) no aborte la transacción
                scan['screenshot'] = None
                scan['mc_info'] = None
                scan['risk_score'] = 0
                try:
                    cursor.execute('SAVEPOINT opt_cols')
                    cursor.execute(f'''
                        SELECT total_dirs_scanned, verdict, verdict_reason, verdict_by, verdict_at,
                               screenshot, mc_info, risk_score
                        FROM scans WHERE id = {_PH}
                    ''', (scan_id,))
                    vrow = cursor.fetchone()
                    if vrow:
                        scan['total_dirs_scanned'] = _row_get(vrow, 0, 'total_dirs_scanned') or 0
                        scan['verdict']        = _row_get(vrow, 1, 'verdict')
                        scan['verdict_reason'] = _row_get(vrow, 2, 'verdict_reason')
                        scan['verdict_by']     = _row_get(vrow, 3, 'verdict_by')
                        scan['verdict_at']     = str(_row_get(vrow, 4, 'verdict_at') or '')
                        scan['screenshot']     = _row_get(vrow, 5, 'screenshot')
                        raw_mc_info = _row_get(vrow, 6, 'mc_info')
                        if raw_mc_info:
                            import json as _json2
                            try:
                                scan['mc_info'] = _json2.loads(raw_mc_info)
                            except Exception:
                                scan['mc_info'] = None
                        scan['risk_score'] = int(_row_get(vrow, 7, 'risk_score') or 0)
                    cursor.execute('RELEASE SAVEPOINT opt_cols')
                except Exception:
                    try:
                        cursor.execute('ROLLBACK TO SAVEPOINT opt_cols')
                    except Exception:
                        pass
                
                # Obtener resultados (incluye feedback_status para mostrar veredicto del staff)
                cursor.execute(f'''
                    SELECT id, issue_type, issue_name, issue_path, issue_category,
                           alert_level, confidence, detected_patterns, obfuscation_detected,
                           file_hash, ai_analysis, ai_confidence, feedback_status
                    FROM scan_results
                    WHERE scan_id = {_PH}
                ''', (scan_id,))

                results = []
                for r in cursor.fetchall():
                    raw_patterns = _row_get(r, 7, 'detected_patterns')
                    results.append({
                        'id': _row_get(r, 0, 'id'),
                        'issue_type': _row_get(r, 1, 'issue_type'),
                        'issue_name': _row_get(r, 2, 'issue_name'),
                        'issue_path': _row_get(r, 3, 'issue_path'),
                        'issue_category': _row_get(r, 4, 'issue_category'),
                        'alert_level': _row_get(r, 5, 'alert_level'),
                        'confidence': _row_get(r, 6, 'confidence'),
                        'detected_patterns': json.loads(raw_patterns) if raw_patterns else [],
                        'obfuscation_detected': bool(_row_get(r, 8, 'obfuscation_detected')),
                        'file_hash': _row_get(r, 9, 'file_hash'),
                        'ai_analysis': _row_get(r, 10, 'ai_analysis'),
                        'ai_confidence': _row_get(r, 11, 'ai_confidence'),
                        'feedback_status': _row_get(r, 12, 'feedback_status'),
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
                WHERE id = %s
            ''', (result_id,))
            
            result = cursor.fetchone()
            if not result:
                return jsonify({'error': f'Resultado con id {result_id} no encontrado'}), 404

            scan_id = _row_get(result, 0, 'scan_id')
            issue_name = (_row_get(result, 1, 'issue_name') or '')[:255]
            issue_path = (_row_get(result, 2, 'issue_path') or '')[:255]
            file_hash = _row_get(result, 3, 'file_hash')
            detected_patterns_json = _row_get(result, 4, 'detected_patterns')
            obfuscation = _row_get(result, 5, 'obfuscation_detected')
            confidence = _row_get(result, 6, 'confidence')

            # Guardar feedback
            cursor.execute('''
                INSERT INTO staff_feedback (
                    result_id, scan_id, staff_verification, staff_notes, verified_by,
                    file_hash, issue_name, issue_path
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            ''', (result_id, scan_id, staff_verification, staff_notes, verified_by,
                  file_hash, issue_name, issue_path))

            row = cursor.fetchone()
            feedback_id = _row_get(row, 0, 'id')

            # Extraer patrones si es hack
            extracted_patterns = []
            extracted_features = {}

            if staff_verification == 'hack':
                name_lower = (issue_name or '').lower()
                path_lower = (issue_path or '').lower()

                # 1) Patrones ya identificados por el scanner (fuente primaria)
                scanner_patterns = []
                try:
                    raw = detected_patterns_json
                    if isinstance(raw, str):
                        raw = json.loads(raw)
                    if isinstance(raw, list):
                        scanner_patterns = [str(p).strip().lower() for p in raw if p and len(str(p).strip()) >= 3]
                except Exception:
                    pass

                # 2) Keywords del nombre/ruta usando lista extendida
                _HACK_KW_PATTERN = re.compile(
                    r'\b(vape|vapelite|entropy|entropyclient|liquidbounce|wurst|wurstclient|'
                    r'sigma|flux|future|astolfo|novoline|phobos|rusherhack|salhack|inertia|'
                    r'meteor|riseclient|aristois|konasen|kami|pandora|tenacity|weave|'
                    r'killaura|aimbot|triggerbot|autoclicker|dllinjector|cheatengine|'
                    r'bspoof|ghostclient|silentclient|fluxclient|bypasser)\w*',
                    re.IGNORECASE
                )
                regex_patterns = [m.group(0).lower() for m in _HACK_KW_PATTERN.finditer(name_lower + ' ' + path_lower)]

                extracted_patterns = list(set(scanner_patterns + regex_patterns))

                # Guardar hash si existe
                if file_hash:
                    cursor.execute(f'''
                        INSERT INTO learned_hashes (
                            file_hash, is_hack, confirmed_count, last_confirmed_at, source_feedback_id
                        ) VALUES ({_PH}, TRUE, 1, CURRENT_TIMESTAMP, {_PH})
                        ON CONFLICT (file_hash) DO UPDATE SET
                            is_hack = TRUE,
                            confirmed_count = learned_hashes.confirmed_count + 1,
                            last_confirmed_at = CURRENT_TIMESTAMP,
                            source_feedback_id = EXCLUDED.source_feedback_id
                    ''', (file_hash, feedback_id))

                # Guardar patrones aprendidos
                for pattern in extracted_patterns:
                    if not pattern or len(pattern) < 3:
                        continue
                    cursor.execute(f'''
                        INSERT INTO learned_patterns (
                            pattern_type, pattern_value, pattern_category, source_feedback_id,
                            learned_from_count, last_updated_at, is_active
                        ) VALUES ('keyword', {_PH}, 'high_risk', {_PH}, 1, CURRENT_TIMESTAMP, TRUE)
                        ON CONFLICT (pattern_value) DO UPDATE SET
                            learned_from_count = learned_patterns.learned_from_count + 1,
                            last_updated_at = CURRENT_TIMESTAMP,
                            is_active = TRUE
                    ''', (pattern, feedback_id))

                extracted_features = {
                    'obfuscation': bool(obfuscation),
                    'confidence': confidence or 0
                }
            elif staff_verification == 'legitimate' and file_hash:
                # Si es legítimo, guardar hash en whitelist
                cursor.execute('''
                    INSERT INTO learned_hashes (
                        file_hash, is_hack, confirmed_count, last_confirmed_at, source_feedback_id
                    ) VALUES (%s, FALSE, 1, CURRENT_TIMESTAMP, %s)
                    ON CONFLICT (file_hash) DO UPDATE SET
                        is_hack = FALSE,
                        confirmed_count = learned_hashes.confirmed_count + 1,
                        last_confirmed_at = CURRENT_TIMESTAMP,
                        source_feedback_id = EXCLUDED.source_feedback_id
                ''', (file_hash, feedback_id))

            # Actualizar feedback con características extraídas
            cursor.execute('''
                UPDATE staff_feedback
                SET extracted_patterns = %s, extracted_features = %s
                WHERE id = %s
            ''', (json.dumps(extracted_patterns), json.dumps(extracted_features), feedback_id))

            # Persistir feedback_status en scan_results para que sobreviva recargas
            cursor.execute(
                f'UPDATE scan_results SET feedback_status = {_PH} WHERE id = {_PH}',
                (staff_verification, result_id)
            )

            # Aprender rutas legítimas (no solo file_hash) para mejorar el filtro server-side
            if staff_verification == 'legitimate' and issue_path:
                cursor.execute(f'''
                    INSERT INTO learned_patterns
                        (pattern_type, pattern_value, pattern_category, source_feedback_id,
                         learned_from_count, last_updated_at, is_active)
                    VALUES ('legitimate_path', {_PH}, 'whitelist', {_PH}, 1, CURRENT_TIMESTAMP, TRUE)
                    ON CONFLICT (pattern_value) DO UPDATE SET
                        learned_from_count = learned_patterns.learned_from_count + 1,
                        last_updated_at = CURRENT_TIMESTAMP,
                        is_active = TRUE
                ''', (issue_path, feedback_id))

            # P2 #30 — Feedback loop: si 3+ marcas de "legítimo" para el mismo issue_type
            # en los últimos 30 días, subir el umbral mínimo de confianza un 10% para ese tipo.
            if staff_verification == 'legitimate':
                try:
                    issue_type_val = data.get('issue_type', '').strip()
                    if issue_type_val:
                        if _USE_PG:
                            cursor.execute('''
                                SELECT COUNT(*) FROM staff_feedback sf
                                JOIN scan_results sr ON sf.result_id = sr.id
                                WHERE sf.staff_verification = 'legitimate'
                                  AND sr.issue_type = %s
                                  AND sf.created_at >= NOW() - INTERVAL '30 days'
                            ''', (issue_type_val,))
                        else:
                            cursor.execute('''
                                SELECT COUNT(*) FROM staff_feedback sf
                                JOIN scan_results sr ON sf.result_id = sr.id
                                WHERE sf.staff_verification = 'legitimate'
                                  AND sr.issue_type = ?
                                  AND sf.created_at >= datetime('now', '-30 days')
                            ''', (issue_type_val,))
                        count_row = cursor.fetchone()
                        legit_count = int(_row_get(count_row, 0, 'count') or 0)
                        if legit_count > 0 and legit_count % 3 == 0:
                            bump = 10 * (legit_count // 3)
                            if _USE_PG:
                                cursor.execute('''
                                    INSERT INTO type_confidence_thresholds (issue_type, min_confidence, auto_bumps)
                                    VALUES (%s, LEAST(90, 30 + %s), 1)
                                    ON CONFLICT (issue_type) DO UPDATE
                                    SET min_confidence = LEAST(90, type_confidence_thresholds.min_confidence + 10),
                                        auto_bumps = type_confidence_thresholds.auto_bumps + 1,
                                        updated_at = NOW()
                                ''', (issue_type_val, bump))
                            print(f"[Feedback loop] {issue_type_val}: {legit_count} legit marks → threshold bumped")
                except Exception as _fe:
                    print(f"[Feedback loop] Error: {_fe}")

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
                    WHERE id = %s
                ''', (result_id,))
                
                result = cursor.fetchone()
                if not result:
                    continue  # Saltar si no existe

                scan_id = _row_get(result, 0, 'scan_id')
                issue_name = (_row_get(result, 1, 'issue_name') or '')[:255]
                issue_path = (_row_get(result, 2, 'issue_path') or '')[:255]
                file_hash = _row_get(result, 3, 'file_hash')
                detected_patterns_json = _row_get(result, 4, 'detected_patterns')
                obfuscation = _row_get(result, 5, 'obfuscation_detected')
                confidence = _row_get(result, 6, 'confidence')
                
                # Guardar feedback
                cursor.execute('''
                    INSERT INTO staff_feedback (
                        result_id, scan_id, staff_verification, staff_notes, verified_by,
                        file_hash, issue_name, issue_path
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                ''', (result_id, scan_id, staff_verification, staff_notes, verified_by,
                      file_hash, issue_name, issue_path))

                row = cursor.fetchone()
                feedback_id = _row_get(row, 0, 'id')
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
                            INSERT INTO learned_hashes (
                                file_hash, is_hack, confirmed_count, last_confirmed_at, source_feedback_id
                            ) VALUES (%s, 1, 1, CURRENT_TIMESTAMP, %s)
                            ON CONFLICT (file_hash) DO UPDATE SET
                                is_hack = 1,
                                confirmed_count = learned_hashes.confirmed_count + 1,
                                last_confirmed_at = CURRENT_TIMESTAMP,
                                source_feedback_id = EXCLUDED.source_feedback_id
                        ''', (file_hash, feedback_id))

                    # Guardar patrones aprendidos
                    for pattern in extracted_patterns:
                        cursor.execute('''
                            INSERT INTO learned_patterns (
                                pattern_type, pattern_value, pattern_category, source_feedback_id,
                                learned_from_count, last_updated_at, is_active
                            ) VALUES ('keyword', %s, 'high_risk', %s, 1, CURRENT_TIMESTAMP, 1)
                            ON CONFLICT (pattern_value) DO UPDATE SET
                                learned_from_count = learned_patterns.learned_from_count + 1,
                                last_updated_at = CURRENT_TIMESTAMP,
                                is_active = 1
                        ''', (pattern, feedback_id))

                    extracted_features = {
                        'obfuscation': bool(obfuscation),
                        'confidence': confidence or 0
                    }
                elif staff_verification == 'legitimate':
                    # Guardar hash si existe
                    if file_hash:
                        cursor.execute('''
                            INSERT INTO learned_hashes (
                                file_hash, is_hack, confirmed_count, last_confirmed_at, source_feedback_id
                            ) VALUES (%s, 0, 1, CURRENT_TIMESTAMP, %s)
                            ON CONFLICT (file_hash) DO UPDATE SET
                                is_hack = 0,
                                confirmed_count = learned_hashes.confirmed_count + 1,
                                last_confirmed_at = CURRENT_TIMESTAMP,
                                source_feedback_id = EXCLUDED.source_feedback_id
                        ''', (file_hash, feedback_id))
                    # Aprender ruta legítima (aunque no haya hash)
                    if issue_path:
                        cursor.execute(f'''
                            INSERT INTO learned_patterns
                                (pattern_type, pattern_value, pattern_category, source_feedback_id,
                                 learned_from_count, last_updated_at, is_active)
                            VALUES ('legitimate_path', {_PH}, 'whitelist', {_PH}, 1, CURRENT_TIMESTAMP, TRUE)
                            ON CONFLICT (pattern_value) DO UPDATE SET
                                learned_from_count = learned_patterns.learned_from_count + 1,
                                last_updated_at = CURRENT_TIMESTAMP,
                                is_active = TRUE
                        ''', (issue_path, feedback_id))

                # Persistir feedback_status en scan_results para que sobreviva recargas
                cursor.execute(
                    f'UPDATE scan_results SET feedback_status = {_PH} WHERE id = {_PH}',
                    (staff_verification, result_id)
                )

                # Actualizar feedback con características extraídas
                cursor.execute('''
                    UPDATE staff_feedback
                    SET extracted_patterns = %s, extracted_features = %s
                    WHERE id = %s
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
                WHERE result_id = %s
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
    """Retorna estadísticas de patrones aprendidos directamente desde BD"""
    try:
        with get_api_db_cursor() as cursor:
            cursor.execute("SELECT COUNT(*) as c FROM learned_patterns WHERE is_active = TRUE AND pattern_type != 'legitimate_path'")
            patterns_count = _row_get(cursor.fetchone(), 0, 'c') or 0
            cursor.execute("SELECT COUNT(*) as c FROM learned_patterns WHERE is_active = TRUE AND pattern_type = 'legitimate_path'")
            legit_paths_count = _row_get(cursor.fetchone(), 0, 'c') or 0
            cursor.execute('SELECT COUNT(*) as c FROM learned_hashes')
            hashes_count = _row_get(cursor.fetchone(), 0, 'c') or 0
        return jsonify({
            'success': True,
            'message': 'Modelo actualizado. Los clientes descargarán automáticamente los nuevos patrones al iniciar.',
            'version': '1.0',
            'patterns_count': patterns_count,
            'hashes_count': hashes_count,
            'legit_paths_count': legit_paths_count,
        })
    except Exception as e:
        print(f"Error en update_model: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': f'Error inesperado: {str(e)}'}), 500

@app.route('/api/learning-stats', methods=['GET'])
def get_learning_stats():
    """Estadísticas del sistema de aprendizaje: patrones, hashes y feedbacks."""
    try:
        with get_api_db_cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM learned_patterns WHERE is_active = TRUE AND pattern_type != 'legitimate_path'")
            patterns_count = (_row_get(cursor.fetchone(), 0, 'count') or 0)
            cursor.execute("SELECT COUNT(*) FROM learned_hashes")
            hashes_count = (_row_get(cursor.fetchone(), 0, 'count') or 0)
            cursor.execute("SELECT COUNT(*) FROM staff_feedback")
            feedbacks_count = (_row_get(cursor.fetchone(), 0, 'count') or 0)
        return jsonify({
            'patterns_count': int(patterns_count),
            'hashes_count': int(hashes_count),
            'feedbacks_count': int(feedbacks_count),
        }), 200
    except Exception as e:
        return jsonify({'patterns_count': 0, 'hashes_count': 0, 'feedbacks_count': 0, 'error': str(e)}), 200


@app.route('/api/admin/scans/bulk-delete', methods=['POST'])
@login_required
def bulk_delete_scans():
    """Elimina scans de prueba por machine_name o machine_id. Solo admin."""
    current_user = get_user_by_id(session.get('user_id'))
    if not is_admin(current_user):
        return jsonify({'error': 'Se requiere rol admin'}), 403
    data = request.json or {}
    machine_name = (data.get('machine_name') or '').strip()
    machine_id   = (data.get('machine_id') or '').strip()
    if not machine_name and not machine_id:
        return jsonify({'error': 'Se requiere machine_name o machine_id'}), 400
    try:
        with get_api_db_cursor() as cursor:
            if machine_name:
                cursor.execute(f'SELECT id FROM scans WHERE machine_name = {_PH}', (machine_name,))
            else:
                cursor.execute(f'SELECT id FROM scans WHERE machine_id = {_PH}', (machine_id,))
            scan_ids = [_row_get(r, 0, 'id') for r in cursor.fetchall()]
            if not scan_ids:
                return jsonify({'deleted': 0, 'message': 'No se encontraron scans para ese equipo'}), 200
            _ids_ph = ','.join([_PH] * len(scan_ids))
            cursor.execute(f'DELETE FROM scan_results WHERE scan_id IN ({_ids_ph})', scan_ids)
            cursor.execute(f'DELETE FROM staff_feedback WHERE scan_id IN ({_ids_ph})', scan_ids)
            cursor.execute(f'DELETE FROM scans WHERE id IN ({_ids_ph})', scan_ids)
        return jsonify({'deleted': len(scan_ids), 'message': f'{len(scan_ids)} scan(s) eliminados'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/purge-garbage-results', methods=['POST'])
@login_required
def purge_garbage_results():
    """Elimina resultados basura de EXEs viejos (EXECUTED_DELETED + nombres binarios). Solo admin."""
    current_user = get_user_by_id(session.get('user_id'))
    if not is_admin(current_user):
        return jsonify({'error': 'Se requiere rol admin'}), 403
    try:
        with get_api_db_cursor() as cursor:
            # Eliminar por categoría legacy
            cursor.execute(
                f"DELETE FROM scan_results WHERE issue_category IN ('EXECUTED_DELETED','APPCOMPAT','USN_FORENSICS')"
            )
            deleted_cat = cursor.rowcount or 0
            # Eliminar por nombres de basura binaria
            garbage_patterns = [
                '%LMEM%', '%Windows.Data.%', '%Matrix3x2%', '%ItemReference%',
                '%CloudData%', '%RevealBrush%', '%XamlAnim%', '%MEOW%',
            ]
            deleted_bin = 0
            for pat in garbage_patterns:
                cursor.execute(f"DELETE FROM scan_results WHERE issue_name LIKE {_PH}", (pat,))
                deleted_bin += (cursor.rowcount or 0)
        total = deleted_cat + deleted_bin
        return jsonify({'deleted': total, 'message': f'{total} resultados basura eliminados'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


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
                    WHERE is_active = TRUE
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
                    WHERE is_active = TRUE
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
    """Genera una nueva versión de la aplicación.
    En Render: sirve el exe pre-compilado + muestra modelo actualizado.
    En local Windows: compila con PyInstaller.
    """
    # En Render no se puede compilar (Linux, sin PyInstaller).
    # En cambio, servimos el exe pre-compilado que viene en el repo
    # y mostramos las estadísticas del modelo (que el scanner descarga en runtime).
    if IS_RENDER:
        def generate_render():
            try:
                yield f"data: {json.dumps({'step': '🔍 Verificando modelo de IA...', 'progress': 20})}\n\n"

                # Leer estadísticas del modelo
                try:
                    with get_api_db_cursor() as _cur:
                        _cur.execute('SELECT COUNT(*) as c FROM learned_patterns WHERE is_active = TRUE')
                        patterns_count = _row_get(_cur.fetchone(), 0, 'c') or 0
                        _cur.execute('SELECT COUNT(*) as c FROM learned_hashes')
                        hashes_count = _row_get(_cur.fetchone(), 0, 'c') or 0
                except Exception:
                    patterns_count = hashes_count = 0

                yield f"data: {json.dumps({'step': f'✅ Modelo activo: {patterns_count} patrones aprendidos, {hashes_count} hashes confirmados', 'progress': 40})}\n\n"
                yield f"data: {json.dumps({'step': '📡 El scanner descarga automáticamente el modelo actualizado en cada inicio — no requiere recompilar.', 'progress': 60})}\n\n"

                # Buscar el exe pre-compilado en el repo
                project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                exe_candidates = [
                    os.path.join(project_root, 'source', 'dist', 'ArgusScanner.exe'),
                    os.path.join(project_root, 'source', 'dist', 'MinecraftSSTool.exe'),
                    os.path.join(project_root, 'ArgusScanner.exe'),
                ]
                exe_path = next((p for p in exe_candidates if os.path.exists(p)), None)

                if not exe_path:
                    _msg = ('⚠️ No se encontró un ejecutable pre-compilado en el repositorio.\n\n'
                            'Para distribuir el scanner:\n1. Compila localmente: pyinstaller ArgusScanner.spec\n'
                            '2. Haz commit de source/dist/ArgusScanner.exe\n'
                            '3. Pushea a GitHub — Render lo incluirá en el siguiente deploy.')
                    yield "data: " + json.dumps({'step': _msg, 'progress': 100, 'error': True}) + "\n\n"
                    return

                import hashlib
                file_size = os.path.getsize(exe_path)
                with open(exe_path, 'rb') as f:
                    file_hash = hashlib.sha256(f.read()).hexdigest()
                exe_name = os.path.basename(exe_path)

                yield f"data: {json.dumps({'step': f'✅ Ejecutable listo: {exe_name} ({file_size / (1024*1024):.1f} MB)', 'progress': 90})}\n\n"

                # Registrar en BD como versión disponible
                import datetime as _dt
                version = _dt.datetime.now().strftime('%Y%m%d_%H%M%S')
                try:
                    with get_api_db_cursor() as _cur:
                        _cur.execute(
                            f'INSERT INTO app_versions (version, download_url, changelog, file_size, file_hash) VALUES ({_PH},{_PH},{_PH},{_PH},{_PH}) ON CONFLICT (version) DO NOTHING',
                            (f'1.{version}', f'/download/{exe_name}',
                             f'Modelo: {patterns_count} patrones, {hashes_count} hashes. IA se actualiza automáticamente en runtime.',
                             file_size, file_hash)
                        )
                except Exception:
                    pass

                _done_msg = (f'✅ Listo para distribuir.\n\nArchivo: {exe_name}\n'
                             f'Tamaño: {file_size / (1024*1024):.1f} MB\n'
                             f'Modelo: {patterns_count} patrones + {hashes_count} hashes\n\n'
                             '💡 El modelo de IA se actualiza automáticamente sin recompilar.')
                yield "data: " + json.dumps({'step': _done_msg, 'progress': 100, 'success': True, 'download_url': f'/download/{exe_name}', 'filename': exe_name}) + "\n\n"

            except Exception as e:
                yield f"data: {json.dumps({'step': f'ERROR: {str(e)}', 'progress': 100, 'error': True})}\n\n"

        return Response(generate_render(), mimetype='text/event-stream')

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
            
            # Obtener estadísticas del modelo directamente desde BD
            try:
                with get_api_db_cursor() as _cur:
                    _cur.execute('SELECT COUNT(*) as c FROM learned_patterns WHERE is_active = TRUE')
                    patterns_count = _row_get(_cur.fetchone(), 0, 'c') or 0
                    _cur.execute('SELECT COUNT(*) as c FROM learned_hashes')
                    hashes_count = _row_get(_cur.fetchone(), 0, 'c') or 0
                step_message = f'✅ Modelo: {patterns_count} patrones, {hashes_count} hashes. Los clientes descargarán automáticamente.'
                yield f"data: {json.dumps({'step': step_message, 'progress': 50})}\n\n"
                model_data = {'patterns_count': patterns_count, 'hashes_count': hashes_count}
            except Exception as e:
                model_data = {'patterns_count': 0, 'hashes_count': 0}
                yield f"data: {json.dumps({'step': f'Advertencia: Error leyendo modelo: {str(e)}', 'progress': 50})}\n\n"
            
            time.sleep(0.5)
            
            # Paso 2: Compilar ejecutable con PyInstaller
            yield f"data: {json.dumps({'step': 'Compilando ejecutable con PyInstaller (esto puede tardar varios minutos)...', 'progress': 60})}\n\n"
            time.sleep(0.5)

            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            source_dir = os.path.join(project_root, 'source')

            # Usar ArgusScanner.spec si existe, si no MinecraftSSTool.spec como fallback
            spec_candidates = ['ArgusScanner.spec', 'MinecraftSSTool.spec']
            spec_file = next((os.path.join(source_dir, s) for s in spec_candidates if os.path.exists(os.path.join(source_dir, s))), None)

            if not spec_file:
                yield f"data: {json.dumps({'step': 'ERROR: No se encontró ArgusScanner.spec en source/', 'progress': 100, 'error': True})}\n\n"
                return

            yield f"data: {json.dumps({'step': f'✅ Spec encontrado: {os.path.basename(spec_file)}', 'progress': 58})}\n\n"
            yield f"data: {json.dumps({'step': 'Ejecutando PyInstaller (puede tardar varios minutos)...', 'progress': 60})}\n\n"

            process = subprocess.Popen(
                ['pyinstaller', '--noconfirm', spec_file],
                cwd=source_dir,
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
                    if any(keyword in line.lower() for keyword in ['compilando', 'building', 'creating', 'success', 'error', 'completado', 'pyinstaller', 'copying']):
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

            exe_candidates_local = [
                os.path.join(project_root, 'source', 'dist', 'ArgusScanner.exe'),
                os.path.join(project_root, 'source', 'dist', 'MinecraftSSTool.exe'),
            ]
            exe_path = next((p for p in exe_candidates_local if os.path.exists(p)), None)
            if not exe_path:
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
            base_name = os.path.splitext(os.path.basename(exe_path))[0]
            download_filename = f'{base_name}_v{version}.exe'
            download_path = os.path.join(downloads_dir, download_filename)
            
            import shutil
            shutil.copy2(exe_path, download_path)
            
            # Paso 6: Registrar versión en BD directamente
            try:
                with get_api_db_cursor() as _cur:
                    _cur.execute(
                        f'INSERT INTO app_versions (version, download_url, changelog, file_size, file_hash) VALUES ({_PH},{_PH},{_PH},{_PH},{_PH}) ON CONFLICT (version) DO NOTHING',
                        (f'1.{version}', f'/download/{download_filename}',
                         f'Versión generada con {model_data.get("patterns_count", 0)} patrones aprendidos',
                         file_size, file_hash)
                    )
            except Exception:
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
    
    # Lista de ubicaciones posibles en orden de prioridad
    possible_paths = [
        os.path.join(project_root, 'downloads', filename),
        os.path.join(project_root, 'source', 'dist', filename),
        os.path.join(project_root, filename),
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
    from datetime import datetime

    try:
        # Buscar el enlace en la BD (PostgreSQL)
        with get_api_db_cursor() as cursor:
            cursor.execute(
                f'SELECT id, filename, expires_at, max_downloads, download_count, is_active'
                f' FROM download_links WHERE token = {_PH} AND is_active = TRUE',
                (token,)
            )
            link = cursor.fetchone()

            if not link:
                return jsonify({'error': 'Enlace de descarga inválido o expirado'}), 404

            link_id       = _row_get(link, 0, 'id')
            filename      = _row_get(link, 1, 'filename')
            expires_at    = _row_get(link, 2, 'expires_at')
            max_downloads = _row_get(link, 3, 'max_downloads')
            download_count= _row_get(link, 4, 'download_count')

            # Obtener el token de escaneo del parámetro de la URL (si existe)
            scan_token = request.args.get('token', None)

            try:
                max_downloads  = int(max_downloads)  if max_downloads  is not None else -1
                download_count = int(download_count) if download_count is not None else 0
            except (ValueError, TypeError):
                max_downloads = -1
                download_count = 0

            print(f"🔍 Verificando enlace: ID={link_id}, max={max_downloads}, count={download_count}")

            # Verificar expiración
            if expires_at:
                if isinstance(expires_at, str):
                    expires_dt = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                else:
                    expires_dt = expires_at  # psycopg2 ya devuelve datetime
                if datetime.now() > expires_dt.replace(tzinfo=None):
                    print(f"❌ Enlace expirado: {expires_at}")
                    return jsonify({'error': 'Este enlace de descarga ha expirado'}), 410

            # Verificar límite de descargas (-1 = ilimitado)
            if max_downloads != -1 and download_count >= max_downloads:
                print(f"❌ Límite alcanzado: {download_count} >= {max_downloads}")
                return jsonify({'error': 'Este enlace ha alcanzado el límite de descargas'}), 403

            print(f"✅ Enlace válido, procediendo con descarga")

            # Incrementar contador
            cursor.execute(
                f'UPDATE download_links SET download_count = download_count + 1 WHERE id = {_PH}',
                (link_id,)
            )
            if max_downloads != -1 and download_count + 1 >= max_downloads:
                cursor.execute(
                    f'UPDATE download_links SET is_active = FALSE WHERE id = {_PH}',
                    (link_id,)
                )
        
        # Buscar y enviar el archivo
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        possible_paths = [
            os.path.join(project_root, 'downloads', filename),
            os.path.join(project_root, 'source', 'dist', filename),
            os.path.join(project_root, filename),
            # Fallback: buscar ArgusScanner.exe si se pidió el nombre viejo
            os.path.join(project_root, 'source', 'dist', 'ArgusScanner.exe') if filename == 'MinecraftSSTool.exe' else None,
        ]
        
        file_path = None
        for path in possible_paths:
            if path and os.path.exists(path) and os.path.isfile(path):
                file_path = path
                break
        
        if file_path:
            # Si hay un token de escaneo en la URL, crear un ZIP con el ejecutable y config.json
            if scan_token and filename in ('ArgusScanner.exe', 'MinecraftSSTool.exe'):
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
                    response = send_file(zip_path, as_attachment=True, download_name='ArgusScanner.zip', mimetype='application/zip')
                    
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
                WHERE id = %s
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
                WHERE sr.scan_id = %s
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
    
    # Si no hay en downloads, buscar en source/dist (priorizar ArgusScanner)
    if not latest_file:
        for candidate in ['ArgusScanner.exe', 'MinecraftSSTool.exe']:
            p = os.path.join(project_root, 'source', 'dist', candidate)
            if os.path.exists(p):
                latest_file = p
                latest_time = os.path.getmtime(p)
                latest_filename = candidate
                break

    # También buscar en la raíz del proyecto
    if not latest_file:
        for candidate in ['ArgusScanner.exe', 'MinecraftSSTool.exe']:
            p = os.path.join(project_root, candidate)
            if os.path.exists(p):
                latest_file = p
                latest_time = os.path.getmtime(p)
                latest_filename = candidate
                break
    
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
    from datetime import datetime, timedelta

    print(f"🔗 Solicitud de creación de enlace de descarga recibida")
    print(f"📋 Datos recibidos: {request.json}")

    # Verificar permisos (solo admin)
    user_id = session.get('user_id')
    current_user = get_user_by_id(user_id)
    if not is_admin(current_user):
        print(f"❌ Usuario {user_id} no tiene permisos de admin")
        return jsonify({'error': 'No tienes permisos para crear enlaces de descarga'}), 403

    data = request.json or {}
    filename      = data.get('filename', 'MinecraftSSTool.exe')
    expires_hours = data.get('expires_hours', 24)
    max_downloads = data.get('max_downloads', 1)
    description   = data.get('description', '')

    print(f"📁 Archivo: {filename}, ⏰ {expires_hours}h, 📊 max={max_downloads}")

    token      = secrets.token_urlsafe(32)
    expires_at = datetime.now() + timedelta(hours=expires_hours)

    try:
        with get_api_db_cursor() as cursor:
            link_id = _insert_id(
                cursor,
                f'INSERT INTO download_links (token, filename, created_by, expires_at, max_downloads, description)'
                f' VALUES ({_PH},{_PH},{_PH},{_PH},{_PH},{_PH})',
                (token, filename, str(user_id), expires_at.isoformat(), max_downloads, description)
            )

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
    if not is_admin(get_user_by_id(session.get('user_id'))):
        return jsonify({'error': 'No tienes permisos para ver enlaces de descarga'}), 403

    try:
        with get_api_db_cursor() as cursor:
            cursor.execute('''
                SELECT dl.id, dl.token, dl.filename, dl.created_at, dl.expires_at,
                       dl.max_downloads, dl.download_count, dl.is_active, dl.description,
                       u.username as created_by_username
                FROM download_links dl
                LEFT JOIN users u ON dl.created_by::text = u.id::text
                ORDER BY dl.created_at DESC
                LIMIT 50
            ''')
            rows = cursor.fetchall()

        links = []
        for row in rows:
            links.append({
                'id':             _row_get(row, 0, 'id'),
                'token':          _row_get(row, 1, 'token'),
                'filename':       _row_get(row, 2, 'filename'),
                'created_at':     str(_row_get(row, 3, 'created_at') or ''),
                'expires_at':     str(_row_get(row, 4, 'expires_at') or ''),
                'max_downloads':  _row_get(row, 5, 'max_downloads'),
                'download_count': _row_get(row, 6, 'download_count'),
                'is_active':      bool(_row_get(row, 7, 'is_active')),
                'description':    _row_get(row, 8, 'description'),
                'created_by':     _row_get(row, 9, 'created_by_username'),
            })
        
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
    if not is_admin(get_user_by_id(session.get('user_id'))):
        return jsonify({'error': 'No tienes permisos para eliminar enlaces'}), 403

    try:
        with get_api_db_cursor() as cursor:
            cursor.execute(
                f'UPDATE download_links SET is_active = FALSE WHERE id = {_PH}',
                (link_id,)
            )
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

# ============================================================
# EXPORTAR SCAN (CSV)
# ============================================================

@app.route('/api/scans/<int:scan_id>/export/csv', methods=['GET'])
@login_required
def export_scan_csv(scan_id):
    """Exporta los resultados de un escaneo como archivo CSV."""
    import csv, io
    try:
        with get_api_db_cursor() as cursor:
            cursor.execute(
                f'SELECT id, machine_name, minecraft_username, started_at, completed_at,'
                f' status, total_files_scanned, issues_found, scan_duration,'
                f' ip_address, country, verdict, verdict_reason, verdict_by'
                f' FROM scans WHERE id = {_PH}',
                (scan_id,)
            )
            scan_row = cursor.fetchone()
            if not scan_row:
                return jsonify({'error': 'Escaneo no encontrado'}), 404

            def g(i, k): return _row_get(scan_row, i, k)
            machine = g(1,'machine_name') or 'desconocido'

            cursor.execute(
                f'SELECT issue_type, issue_name, issue_path, issue_category, alert_level,'
                f' confidence, obfuscation_detected, file_hash, ai_analysis, ai_confidence'
                f' FROM scan_results WHERE scan_id = {_PH} ORDER BY alert_level',
                (scan_id,)
            )
            results = cursor.fetchall()

        buf = io.StringIO()
        w   = csv.writer(buf)

        # Header metadata
        w.writerow(['# Reporte de Escaneo - ASPERS Projects'])
        w.writerow(['# Scan ID', scan_id])
        w.writerow(['# Máquina', g(1,'machine_name')])
        w.writerow(['# Minecraft Username', g(2,'minecraft_username') or 'No detectado'])
        w.writerow(['# Fecha inicio', g(3,'started_at')])
        w.writerow(['# Fecha fin', g(4,'completed_at')])
        w.writerow(['# Archivos escaneados', g(6,'total_files_scanned')])
        w.writerow(['# Issues totales', g(7,'issues_found')])
        w.writerow(['# Veredicto', g(11,'verdict') or 'pendiente'])
        w.writerow(['# Razón veredicto', g(12,'verdict_reason') or ''])
        w.writerow([])

        # Column headers
        w.writerow(['Tipo', 'Nombre', 'Ruta', 'Categoría', 'Nivel de alerta',
                    'Confianza %', 'Ofuscación detectada', 'Hash SHA256',
                    'Análisis IA', 'Confianza IA %'])

        for r in results:
            w.writerow([
                _row_get(r, 0, 'issue_type'),
                _row_get(r, 1, 'issue_name'),
                _row_get(r, 2, 'issue_path'),
                _row_get(r, 3, 'issue_category'),
                _row_get(r, 4, 'alert_level'),
                _row_get(r, 5, 'confidence'),
                'Sí' if _row_get(r, 6, 'obfuscation_detected') else 'No',
                _row_get(r, 7, 'file_hash'),
                _row_get(r, 8, 'ai_analysis'),
                _row_get(r, 9, 'ai_confidence'),
            ])

        csv_bytes = buf.getvalue().encode('utf-8-sig')  # BOM para Excel
        filename  = f'scan_{scan_id}_{machine}.csv'
        return Response(
            csv_bytes,
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/scans/<int:scan_id>/export/pdf', methods=['GET'])
@login_required
def export_scan_pdf(scan_id):
    """Exporta el reporte de un escaneo como PDF con logo ASPERS Projects."""
    try:
        from fpdf import FPDF
    except ImportError:
        return jsonify({'error': 'fpdf2 no instalado en el servidor'}), 501

    try:
        with get_api_db_cursor() as cursor:
            cursor.execute(
                f'SELECT id, machine_name, minecraft_username, started_at, completed_at,'
                f' status, total_files_scanned, issues_found, scan_duration,'
                f' ip_address, country, verdict, verdict_reason, verdict_by, risk_score'
                f' FROM scans WHERE id = {_PH}',
                (scan_id,)
            )
            scan_row = cursor.fetchone()
            if not scan_row:
                return jsonify({'error': 'Escaneo no encontrado'}), 404

            def g(i, k): return _row_get(scan_row, i, k) or ''
            machine    = str(g(1, 'machine_name') or 'desconocido')
            username   = str(g(2, 'minecraft_username') or 'No detectado')
            started    = str(g(3, 'started_at') or '')[:19]
            completed  = str(g(4, 'completed_at') or '')[:19]
            status_val = str(g(5, 'status') or 'completed')
            files_n    = int(g(6, 'total_files_scanned') or 0)
            issues_n   = int(g(7, 'issues_found') or 0)
            duration   = int(g(8, 'scan_duration') or 0)
            ip_addr    = str(g(9, 'ip_address') or 'N/A')
            country    = str(g(10, 'country') or 'N/A')
            verdict_v  = str(g(11, 'verdict') or 'pendiente')
            verdict_r  = str(g(12, 'verdict_reason') or '')
            verdict_by = str(g(13, 'verdict_by') or '')
            risk_score = int(g(14, 'risk_score') or 0)

            cursor.execute(
                f'SELECT issue_type, issue_name, issue_path, issue_category, alert_level, confidence'
                f' FROM scan_results WHERE scan_id = {_PH}'
                f' ORDER BY CASE alert_level WHEN \'CRITICAL\' THEN 0 WHEN \'SOSPECHOSO\' THEN 1'
                f' WHEN \'MUY_SOSPECHOSO\' THEN 2 ELSE 3 END',
                (scan_id,)
            )
            results = cursor.fetchall()

        # ── Build PDF ──
        _LOGO_PATH = os.path.join(os.path.dirname(__file__), 'static', 'img', 'logo.png')
        _has_logo  = os.path.isfile(_LOGO_PATH)

        class _PDF(FPDF):
            def header(self):
                self.set_fill_color(13, 17, 36)
                self.rect(0, 0, 210, 18, 'F')
                # Logo in header (12mm tall, auto-width to preserve aspect)
                if _has_logo:
                    self.image(_LOGO_PATH, x=6, y=3, h=12)
                    text_x = 24
                else:
                    text_x = 8
                self.set_font('Helvetica', 'B', 10)
                self.set_text_color(139, 92, 246)
                self.set_xy(text_x, 4)
                self.cell(0, 10, 'ASPERS PROJECTS  |  REPORTE DE SS', ln=False)
                self.set_text_color(100, 100, 120)
                self.set_xy(0, 4)
                self.cell(200, 10, f'Scan #{scan_id}', align='R')
                self.set_text_color(0, 0, 0)
                self.ln(14)

            def footer(self):
                self.set_y(-12)
                self.set_font('Helvetica', 'I', 8)
                self.set_text_color(150, 150, 170)
                self.cell(0, 8, f'ASPERS Projects  |  Pagina {self.page_no()}  |  Confidencial', align='C')

        pdf = _PDF()
        pdf.set_auto_page_break(auto=True, margin=16)
        pdf.add_page()
        pdf.set_margins(14, 20, 14)

        # Accent bar
        pdf.set_fill_color(139, 92, 246)
        pdf.rect(14, 22, 2, 12, 'F')

        # Title
        pdf.set_xy(18, 22)
        pdf.set_font('Helvetica', 'B', 16)
        pdf.set_text_color(20, 20, 50)
        pdf.cell(0, 8, f'Reporte de Escaneo — {machine}', ln=True)
        pdf.set_font('Helvetica', '', 10)
        pdf.set_text_color(100, 100, 130)
        pdf.set_x(18)
        pdf.cell(0, 6, f'Usuario: {username}  |  Scan ID: {scan_id}  |  {started}', ln=True)
        pdf.ln(4)

        # Verdict banner
        VERDICT_COLORS = {
            'hack':     (220, 38, 38),
            'clean':    (16, 185, 129),
            'pendiente': (100, 116, 139),
        }
        vc = VERDICT_COLORS.get(verdict_v.lower(), (100, 116, 139))
        pdf.set_fill_color(*vc)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font('Helvetica', 'B', 11)
        verdict_label = {'hack': 'CON HACKS', 'clean': 'LIMPIO', 'pendiente': 'PENDIENTE'}.get(verdict_v.lower(), verdict_v.upper())
        pdf.cell(0, 10, f'  Veredicto: {verdict_label}', fill=True, ln=True)
        if verdict_r:
            pdf.set_fill_color(240, 240, 248)
            pdf.set_text_color(60, 60, 90)
            pdf.set_font('Helvetica', 'I', 9)
            pdf.cell(0, 7, f'  Razon: {verdict_r}  (por {verdict_by})', fill=True, ln=True)
        pdf.ln(5)

        # Summary grid
        def _info_row(label, value, color=(30, 30, 60)):
            pdf.set_font('Helvetica', 'B', 9)
            pdf.set_text_color(100, 100, 130)
            pdf.cell(48, 7, label + ':', ln=False)
            pdf.set_font('Helvetica', '', 9)
            pdf.set_text_color(*color)
            pdf.cell(0, 7, str(value), ln=True)

        mins, secs = divmod(duration, 60)
        dur_str = f'{mins}m {secs}s' if mins else f'{secs}s'
        risk_label = 'HACK' if risk_score >= 70 else 'Sospechoso' if risk_score >= 30 else 'Limpio'

        _info_row('Maquina',          machine)
        _info_row('IP / Pais',        f'{ip_addr}  /  {country}')
        _info_row('Inicio',           started)
        _info_row('Fin',              completed or 'En curso')
        _info_row('Archivos escaneados', f'{files_n:,}')
        _info_row('Hallazgos',        issues_n)
        _info_row('Duracion',         dur_str)
        _info_row('Risk Score',       f'{risk_score}/100  ({risk_label})',
                  color=(180, 30, 30) if risk_score >= 70 else (200, 130, 0) if risk_score >= 30 else (16, 140, 90))
        pdf.ln(6)

        # Issues table
        if results:
            pdf.set_font('Helvetica', 'B', 11)
            pdf.set_text_color(20, 20, 50)
            pdf.cell(0, 8, f'Hallazgos ({len(results)})', ln=True)
            pdf.ln(1)

            # Table header
            ALERT_BG = {
                'CRITICAL':        (220, 38, 38),
                'SOSPECHOSO':      (245, 158, 11),
                'MUY_SOSPECHOSO':  (234, 88, 12),
                'POCO_SOSPECHOSO': (99, 102, 241),
            }
            col_w = [28, 72, 28, 22, 20]
            headers = ['Nivel', 'Nombre', 'Categoria', 'Tipo', 'Conf%']
            pdf.set_fill_color(13, 17, 36)
            pdf.set_text_color(200, 200, 220)
            pdf.set_font('Helvetica', 'B', 8)
            for h, w in zip(headers, col_w):
                pdf.cell(w, 7, h, border=0, fill=True, ln=False)
            pdf.ln(7)

            pdf.set_font('Helvetica', '', 8)
            for i, r in enumerate(results):
                alert = str(_row_get(r, 4, 'alert_level') or '')
                name  = str(_row_get(r, 1, 'issue_name') or '')[:55]
                cat   = str(_row_get(r, 3, 'issue_category') or '')[:18]
                tipo  = str(_row_get(r, 0, 'issue_type') or '')[:14]
                conf  = str(_row_get(r, 5, 'confidence') or 0)
                bg = ALERT_BG.get(alert, (180, 180, 200))
                pdf.set_fill_color(*bg)
                pdf.set_text_color(255, 255, 255)
                pdf.cell(col_w[0], 6, alert[:14], fill=True, ln=False)
                fill_alt = i % 2 == 0
                pdf.set_fill_color(248, 248, 252) if fill_alt else pdf.set_fill_color(255, 255, 255)
                pdf.set_text_color(30, 30, 60)
                pdf.cell(col_w[1], 6, name, fill=fill_alt, ln=False)
                pdf.cell(col_w[2], 6, cat, fill=fill_alt, ln=False)
                pdf.cell(col_w[3], 6, tipo, fill=fill_alt, ln=False)
                pdf.cell(col_w[4], 6, conf + '%', fill=fill_alt, ln=True)
        else:
            pdf.set_font('Helvetica', 'I', 10)
            pdf.set_text_color(100, 120, 150)
            pdf.cell(0, 8, 'Sin hallazgos en este escaneo.', ln=True)

        pdf_bytes = bytes(pdf.output())
        safe_machine = ''.join(c for c in machine if c.isalnum() or c in '-_')
        filename = f'ss_scan_{scan_id}_{safe_machine}.pdf'
        return Response(
            pdf_bytes,
            mimetype='application/pdf',
            headers={'Content-Disposition': f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================
# VEREDICTOS
# ============================================================

@app.route('/api/scans/<int:scan_id>/verdict', methods=['POST'])
@login_required
def set_scan_verdict(scan_id):
    """Establece el veredicto final de un escaneo (clean | hack | pending)."""
    current_user = get_user_by_id(session.get('user_id'))
    if not can_change_verdict(current_user):
        return jsonify({'error': 'No tienes permisos para cambiar veredictos (se requiere Moderador o superior)'}), 403
    data   = request.json or {}
    verdict = (data.get('verdict') or '').strip().lower()
    reason  = (data.get('reason') or '').strip()
    if verdict not in ('clean', 'hack', 'pending'):
        return jsonify({'error': 'Veredicto inválido. Usar: clean, hack, pending'}), 400
    if not reason:
        return jsonify({'error': 'La razón del veredicto es obligatoria'}), 400
    user = session.get('username', 'staff')
    try:
        with get_api_db_cursor() as cursor:
            cursor.execute(
                f'UPDATE scans SET verdict={_PH}, verdict_reason={_PH}, verdict_by={_PH},'
                f' verdict_at=CURRENT_TIMESTAMP WHERE id={_PH}',
                (verdict, reason, user, scan_id)
            )
            _insert_id(
                cursor,
                f'INSERT INTO verdict_history (scan_id, verdict, reason, changed_by)'
                f' VALUES ({_PH},{_PH},{_PH},{_PH})',
                (scan_id, verdict, reason, user)
            )
            cursor.execute(
                f'SELECT machine_name, minecraft_username FROM scans WHERE id={_PH}',
                (scan_id,)
            )
            srow = cursor.fetchone()
        machine  = (_row_get(srow, 0, 'machine_name')       or 'N/A') if srow else 'N/A'
        username = (_row_get(srow, 1, 'minecraft_username')  or 'N/A') if srow else 'N/A'
        # Invalidar caché de estadísticas
        if 'statistics' in _stats_cache: del _stats_cache['statistics']
        if 'dashboard_extended' in _stats_cache: del _stats_cache['dashboard_extended']
        try:
            _di.notify_verdict_change(scan_id, machine, username, verdict, reason, user)
        except Exception:
            pass
        return jsonify({'success': True}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/scans/<int:scan_id>/verdict/history', methods=['GET'])
@login_required
def get_verdict_history(scan_id):
    """Historial de cambios de veredicto de un escaneo."""
    try:
        with get_api_db_cursor() as cursor:
            cursor.execute(
                f'SELECT verdict, reason, changed_by, changed_at'
                f' FROM verdict_history WHERE scan_id={_PH} ORDER BY changed_at DESC',
                (scan_id,)
            )
            history = []
            for row in cursor.fetchall():
                history.append({
                    'verdict':    _row_get(row, 0, 'verdict'),
                    'reason':     _row_get(row, 1, 'reason'),
                    'changed_by': _row_get(row, 2, 'changed_by'),
                    'changed_at': str(_row_get(row, 3, 'changed_at') or ''),
                })
        return jsonify({'history': history}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================
# NOTAS DE ESCANEO
# ============================================================

@app.route('/api/scans/<int:scan_id>/notes', methods=['GET'])
@login_required
def get_scan_notes(scan_id):
    """Obtiene las notas de staff para un escaneo."""
    try:
        with get_api_db_cursor() as cursor:
            cursor.execute(
                f'SELECT id, author, body, created_at FROM scan_notes WHERE scan_id = {_PH} ORDER BY created_at ASC',
                (scan_id,)
            )
            notes = []
            for row in cursor.fetchall():
                notes.append({
                    'id':         _row_get(row, 0, 'id'),
                    'author':     _row_get(row, 1, 'author'),
                    'body':       _row_get(row, 2, 'body'),
                    'created_at': str(_row_get(row, 3, 'created_at') or ''),
                })
        return jsonify({'notes': notes}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/scans/<int:scan_id>/notes', methods=['POST'])
@login_required
def add_scan_note(scan_id):
    """Agrega una nota de staff a un escaneo."""
    data = request.json or {}
    body = (data.get('body') or '').strip()
    if not body:
        return jsonify({'error': 'El cuerpo de la nota no puede estar vacío'}), 400
    user = session.get('username', 'staff')
    try:
        with get_api_db_cursor() as cursor:
            note_id = _insert_id(
                cursor,
                f'INSERT INTO scan_notes (scan_id, author, body) VALUES ({_PH},{_PH},{_PH})',
                (scan_id, user, body)
            )
        return jsonify({'success': True, 'note_id': note_id}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/scans/<int:scan_id>/notes/<int:note_id>', methods=['DELETE'])
@login_required
def delete_scan_note(scan_id, note_id):
    """Elimina una nota de staff (solo el autor o admin)."""
    user = session.get('username', '')
    roles = session.get('roles', [])
    try:
        with get_api_db_cursor() as cursor:
            cursor.execute(
                f'SELECT author FROM scan_notes WHERE id = {_PH} AND scan_id = {_PH}',
                (note_id, scan_id)
            )
            row = cursor.fetchone()
            if not row:
                return jsonify({'error': 'Nota no encontrada'}), 404
            author = _row_get(row, 0, 'author')
            if author != user and 'admin' not in roles and 'owner' not in roles:
                return jsonify({'error': 'No tienes permiso para eliminar esta nota'}), 403
            cursor.execute(
                f'DELETE FROM scan_notes WHERE id = {_PH}',
                (note_id,)
            )
        return jsonify({'success': True}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================
# BASE DE DATOS DE HASHES EN LA NUBE
# ============================================================

@app.route('/api/hashes', methods=['GET'])
def get_hack_hashes():
    """Returns all known hack hashes — used by the scanner at startup."""
    try:
        with get_api_db_cursor() as cursor:
            cursor.execute(
                'SELECT sha256, hack_name, confirmed_count FROM hack_hashes ORDER BY confirmed_count DESC'
            )
            rows = cursor.fetchall()
        hashes = [
            {
                'sha256': _row_get(r, 0, 'sha256'),
                'hack_name': _row_get(r, 1, 'hack_name') or '',
                'confirmed_count': _row_get(r, 2, 'confirmed_count') or 1,
            }
            for r in rows
        ]
        return jsonify({'hashes': hashes, 'count': len(hashes)}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/hashes', methods=['POST'])
@login_required
def add_hack_hash():
    """Add or confirm a known hack hash. Requires admin/owner role."""
    current_user = get_user_by_id(session.get('user_id'))
    if not can_manage_tokens(current_user):
        return jsonify({'error': 'Se requiere rol Admin o superior'}), 403
    data = request.json or {}
    sha256 = (data.get('sha256') or '').strip().lower()
    hack_name = (data.get('hack_name') or '').strip()
    if len(sha256) != 64 or not all(c in '0123456789abcdef' for c in sha256):
        return jsonify({'error': 'SHA256 inválido (debe ser 64 hex chars)'}), 400
    added_by = current_user.get('username', '') if current_user else ''
    try:
        with get_api_db_cursor() as cursor:
            if _USE_PG:
                cursor.execute(
                    '''INSERT INTO hack_hashes (sha256, hack_name, added_by)
                       VALUES (%s, %s, %s)
                       ON CONFLICT (sha256) DO UPDATE
                       SET confirmed_count = hack_hashes.confirmed_count + 1,
                           hack_name = EXCLUDED.hack_name''',
                    (sha256, hack_name, added_by)
                )
            else:
                cursor.execute('SELECT id FROM hack_hashes WHERE sha256 = ?', (sha256,))
                if cursor.fetchone():
                    cursor.execute(
                        'UPDATE hack_hashes SET confirmed_count = confirmed_count + 1, hack_name = ? WHERE sha256 = ?',
                        (hack_name, sha256)
                    )
                else:
                    cursor.execute(
                        'INSERT INTO hack_hashes (sha256, hack_name, added_by) VALUES (?, ?, ?)',
                        (sha256, hack_name, added_by)
                    )
        return jsonify({'success': True}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/hashes/<string:sha256>', methods=['DELETE'])
@login_required
def delete_hack_hash(sha256):
    """Remove a hash from the cloud DB. Requires admin/owner role."""
    current_user = get_user_by_id(session.get('user_id'))
    if not can_manage_tokens(current_user):
        return jsonify({'error': 'Se requiere rol Admin o superior'}), 403
    sha256 = sha256.strip().lower()
    try:
        with get_api_db_cursor() as cursor:
            cursor.execute(f'DELETE FROM hack_hashes WHERE sha256 = {_PH}', (sha256,))
        return jsonify({'success': True}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── P3 #4 — Clustering de perfiles de scan ───────────────────────────────────

@app.route('/api/ml/cluster', methods=['POST'])
@login_required
def ml_cluster():
    """K-Means clustering sobre los últimos N scans completados.
    Detecta grupos de scans con patrones similares y alerta si un cluster nuevo emerge.
    Body: {days: 30, n_clusters: 5}
    """
    current_user = get_user_by_id(session.get('user_id'))
    if not can_manage_tokens(current_user):
        return jsonify({'error': 'Se requiere rol Admin o superior'}), 403
    data = request.json or {}
    days       = int(data.get('days', 30))
    n_clusters = int(data.get('n_clusters', 5))
    try:
        import numpy as np
        from sklearn.cluster import KMeans
        from sklearn.preprocessing import StandardScaler
    except ImportError:
        return jsonify({'error': 'scikit-learn no instalado'}), 500

    try:
        with get_api_db_cursor() as cursor:
            if _USE_PG:
                cursor.execute(f'''
                    SELECT s.id, s.issues_found, s.risk_score,
                           COUNT(CASE WHEN sr.alert_level = 'CRITICAL' THEN 1 END) AS criticals,
                           COUNT(CASE WHEN sr.alert_level = 'SOSPECHOSO' THEN 1 END) AS suspicious,
                           COUNT(DISTINCT sr.issue_category) AS categories
                    FROM scans s
                    LEFT JOIN scan_results sr ON sr.scan_id = s.id
                    WHERE s.status = 'completed'
                      AND s.started_at >= NOW() - INTERVAL '{days} days'
                    GROUP BY s.id
                    ORDER BY s.id DESC
                    LIMIT 500
                ''')
            else:
                cursor.execute(f'''
                    SELECT s.id, s.issues_found, s.risk_score,
                           SUM(CASE WHEN sr.alert_level='CRITICAL' THEN 1 ELSE 0 END),
                           SUM(CASE WHEN sr.alert_level='SOSPECHOSO' THEN 1 ELSE 0 END),
                           COUNT(DISTINCT sr.issue_category)
                    FROM scans s LEFT JOIN scan_results sr ON sr.scan_id=s.id
                    WHERE s.status='completed' AND s.started_at >= datetime('now','-{days} days')
                    GROUP BY s.id ORDER BY s.id DESC LIMIT 500
                ''')
            rows = cursor.fetchall() or []

        if len(rows) < n_clusters * 2:
            return jsonify({'error': f'Insuficientes scans: {len(rows)} (mín {n_clusters*2})'}), 200

        scan_ids = []
        X = []
        for r in rows:
            scan_ids.append(int(_row_get(r, 0, 'id') or 0))
            X.append([
                float(_row_get(r, 1, 'issues_found') or 0),
                float(_row_get(r, 2, 'risk_score') or 0),
                float(_row_get(r, 3, 'criticals') or 0),
                float(_row_get(r, 4, 'suspicious') or 0),
                float(_row_get(r, 5, 'categories') or 0),
            ])

        X_arr = np.array(X)
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X_arr)

        km = KMeans(n_clusters=min(n_clusters, len(rows)), random_state=42, n_init=10)
        labels = km.fit_predict(X_scaled)

        # Resumir clusters
        clusters = {}
        for i, label in enumerate(labels):
            label = int(label)
            if label not in clusters:
                clusters[label] = {'scan_ids': [], 'avg_risk': 0, 'avg_issues': 0, 'size': 0}
            clusters[label]['scan_ids'].append(scan_ids[i])
            clusters[label]['avg_risk']   += X[i][1]
            clusters[label]['avg_issues'] += X[i][0]
            clusters[label]['size']       += 1

        result_clusters = []
        for label, info in clusters.items():
            sz = info['size']
            result_clusters.append({
                'cluster_id':  label,
                'size':        sz,
                'avg_risk':    round(info['avg_risk'] / sz, 1),
                'avg_issues':  round(info['avg_issues'] / sz, 1),
                'scan_ids':    info['scan_ids'][:10],
                'alert': sz >= 3 and (info['avg_risk'] / sz) >= 60,
            })

        result_clusters.sort(key=lambda c: c['avg_risk'], reverse=True)
        high_risk_clusters = [c for c in result_clusters if c['alert']]

        return jsonify({
            'total_scans': len(rows),
            'n_clusters': len(result_clusters),
            'clusters': result_clusters,
            'high_risk_clusters': len(high_risk_clusters),
            'alert': len(high_risk_clusters) > 0,
            'alert_message': (f'⚠ {len(high_risk_clusters)} cluster(s) de alto riesgo detectados con risk_score promedio ≥ 60'
                             if high_risk_clusters else None),
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── P3 #1 — Clasificador Random Forest ───────────────────────────────────────

@app.route('/api/ml/train', methods=['POST'])
@login_required
def ml_train():
    """Reentrena el clasificador RF con todos los feedbacks disponibles. Solo Admin+."""
    current_user = get_user_by_id(session.get('user_id'))
    if not can_manage_tokens(current_user):
        return jsonify({'error': 'Se requiere rol Admin o superior'}), 403
    try:
        from ml_classifier import get_classifier
        clf = get_classifier()
        with get_api_db_cursor() as cursor:
            result = clf.train(cursor)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'trained': False, 'error': str(e)}), 500


@app.route('/api/ml/predict', methods=['POST'])
@login_required
def ml_predict():
    """Predice hack/clean para un hallazgo dado sus features. Solo Admin+."""
    current_user = get_user_by_id(session.get('user_id'))
    if not can_manage_tokens(current_user):
        return jsonify({'error': 'Se requiere rol Admin o superior'}), 403
    data = request.json or {}
    try:
        from ml_classifier import get_classifier
        clf = get_classifier()
        result = clf.predict(data)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'available': False, 'error': str(e)}), 500


@app.route('/api/ml/status', methods=['GET'])
@login_required
def ml_status():
    """Estado del clasificador ML: si está disponible y con cuántas muestras."""
    try:
        from ml_classifier import get_classifier
        clf = get_classifier()
        return jsonify({
            'available': clf.is_available,
            'trained_on': clf._trained_on,
            'model_path_exists': __import__('os').path.isfile(
                __import__('ml_classifier').MODEL_PATH
            ),
        }), 200
    except Exception as e:
        return jsonify({'available': False, 'error': str(e)}), 200


# ── P2 #1 — Whitelist dinámica de mods legítimos ─────────────────────────────

@app.route('/api/mod_whitelist', methods=['GET'])
def get_mod_whitelist():
    """Returns SHA256 hashes of known-legitimate Minecraft mods.
    Used by the scanner to skip false-positive mod detections.
    """
    try:
        with get_api_db_cursor() as cursor:
            cursor.execute('SELECT sha256, mod_name FROM mod_whitelist ORDER BY mod_name')
            rows = cursor.fetchall() or []
        hashes  = [_row_get(r, 0, 'sha256') for r in rows]
        details = [{'sha256': _row_get(r, 0, 'sha256'), 'mod_name': _row_get(r, 1, 'mod_name')} for r in rows]
        return jsonify({'hashes': hashes, 'details': details, 'count': len(hashes)}), 200
    except Exception as e:
        return jsonify({'hashes': [], 'error': str(e)}), 200  # 200 so scanner doesn't abort on missing table


@app.route('/api/mod_whitelist', methods=['POST'])
@login_required
def add_mod_whitelist():
    """Add a known-legitimate mod hash. Requires Admin or above."""
    current_user = get_user_by_id(session.get('user_id'))
    if not can_manage_tokens(current_user):
        return jsonify({'error': 'Se requiere rol Admin o superior'}), 403
    data = request.json or {}
    sha256   = (data.get('sha256') or '').strip().lower()
    mod_name = (data.get('mod_name') or '').strip()
    if len(sha256) != 64 or not all(c in '0123456789abcdef' for c in sha256):
        return jsonify({'error': 'SHA256 inválido'}), 400
    if not mod_name:
        return jsonify({'error': 'mod_name es obligatorio'}), 400
    try:
        with get_api_db_cursor() as cursor:
            if _USE_PG:
                cursor.execute(
                    'INSERT INTO mod_whitelist (sha256, mod_name) VALUES (%s, %s) ON CONFLICT (sha256) DO UPDATE SET mod_name = EXCLUDED.mod_name',
                    (sha256, mod_name)
                )
            else:
                cursor.execute('INSERT OR REPLACE INTO mod_whitelist (sha256, mod_name) VALUES (?, ?)', (sha256, mod_name))
        return jsonify({'success': True}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/mod_whitelist/<string:sha256>', methods=['DELETE'])
@login_required
def delete_mod_whitelist(sha256):
    """Remove a mod from the whitelist. Requires Admin or above."""
    current_user = get_user_by_id(session.get('user_id'))
    if not can_manage_tokens(current_user):
        return jsonify({'error': 'Se requiere rol Admin o superior'}), 403
    sha256 = sha256.strip().lower()
    try:
        with get_api_db_cursor() as cursor:
            cursor.execute(f'DELETE FROM mod_whitelist WHERE sha256 = {_PH}', (sha256,))
        return jsonify({'success': True}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── P3 #18 — Score breakdown (SHAP-style explanation) ────────────────────────

@app.route('/api/scans/<int:scan_id>/score_breakdown', methods=['GET'])
@login_required
def get_score_breakdown(scan_id):
    """Returns which findings contributed most to the risk_score, SHAP-style.
    [{source, points, reason}] sorted by contribution descending.
    """
    try:
        with get_api_db_cursor() as cursor:
            cursor.execute(
                f'''SELECT issue_type, issue_name, issue_category, alert_level, confidence
                    FROM scan_results WHERE scan_id = {_PH}''',
                (scan_id,)
            )
            rows = cursor.fetchall() or []
        results = [
            {
                'tipo':      _row_get(r, 0, 'issue_type') or '',
                'nombre':    _row_get(r, 1, 'issue_name') or '',
                'categoria': _row_get(r, 2, 'issue_category') or '',
                'alerta':    _row_get(r, 3, 'alert_level') or '',
                'confidence': float(_row_get(r, 4, 'confidence') or 0),
            }
            for r in rows
        ]
        score, breakdown = _calculate_risk_score(results, return_breakdown=True)

        # P3 #12 — Intervalo de confianza basado en varianza de confidence de los hallazgos
        confidences = [r['confidence'] for r in results if r.get('confidence', 0) > 0]
        if len(confidences) >= 2:
            avg_conf = sum(confidences) / len(confidences)
            variance = sum((c - avg_conf)**2 for c in confidences) / len(confidences)
            std_dev  = variance ** 0.5
            # Margen ±15 puntos de risk_score cuando std_dev es alto
            margin = round(min(25, std_dev * 30), 1)
            ci = {'low': max(0, score - margin), 'high': min(100, score + margin), 'margin': margin}
            needs_review = margin > 12  # Alta incertidumbre
        else:
            ci = {'low': score, 'high': score, 'margin': 0}
            needs_review = False

        return jsonify({
            'scan_id': scan_id, 'risk_score': score,
            'breakdown': breakdown,
            'confidence_interval': ci,
            'needs_manual_review': needs_review,
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── P2 #30 — Umbrales de confianza por tipo (feedback loop) ──────────────────

@app.route('/api/thresholds', methods=['GET'])
def get_confidence_thresholds():
    """Returns per-issue-type confidence thresholds adjusted by feedback loop.
    Scanner downloads this at startup and uses it to filter low-confidence results.
    """
    try:
        with get_api_db_cursor() as cursor:
            cursor.execute('SELECT issue_type, min_confidence, auto_bumps FROM type_confidence_thresholds ORDER BY issue_type')
            rows = cursor.fetchall() or []
        result = {
            _row_get(r, 0, 'issue_type'): {
                'min_confidence': int(_row_get(r, 1, 'min_confidence') or 30),
                'auto_bumps':     int(_row_get(r, 2, 'auto_bumps') or 0),
            }
            for r in rows
        }
        return jsonify({'thresholds': result}), 200
    except Exception as e:
        return jsonify({'thresholds': {}, 'error': str(e)}), 200  # 200 so scanner doesn't abort


# ── P3 #5 — Perfil de jugador / baseline ─────────────────────────────────────

@app.route('/api/player_baseline/<string:machine_id>', methods=['GET'])
def get_player_baseline(machine_id):
    """Returns historical baseline for a machine (avg issues_found, risk_score, known issue types).
    Used by the scanner to compare current scan vs historical behaviour.
    Only returns data for the last 10 scans of this machine.
    """
    machine_id = machine_id.strip()
    if not machine_id or len(machine_id) > 200:
        return jsonify({'error': 'machine_id inválido'}), 400
    try:
        with get_api_db_cursor() as cursor:
            # Last 10 completed scans for this machine
            cursor.execute(
                f'''SELECT s.id, s.issues_found, s.risk_score, s.verdict, s.started_at
                    FROM scans s
                    WHERE s.machine_id = {_PH}
                      AND s.status = 'completed'
                    ORDER BY s.id DESC LIMIT 10''',
                (machine_id,)
            )
            scans = cursor.fetchall() or []
            if not scans:
                return jsonify({'machine_id': machine_id, 'scan_count': 0, 'baseline': None}), 200

            scan_ids   = [_row_get(r, 0, 'id') for r in scans]
            issues_arr = [int(_row_get(r, 1, 'issues_found') or 0) for r in scans]
            risk_arr   = [float(_row_get(r, 2, 'risk_score') or 0) for r in scans]
            verdicts   = [str(_row_get(r, 3, 'verdict') or 'pending') for r in scans]

            # Get typical issue types seen in this machine's previous scans
            placeholders = ','.join([_PH] * len(scan_ids))
            cursor.execute(
                f'SELECT DISTINCT issue_type FROM scan_results WHERE scan_id IN ({placeholders}) AND issue_type IS NOT NULL',
                scan_ids
            )
            known_types = [str(r[0] if not hasattr(r, 'keys') else r['issue_type']) for r in (cursor.fetchall() or [])]

        baseline = {
            'avg_issues':    round(sum(issues_arr) / len(issues_arr), 1),
            'avg_risk':      round(sum(risk_arr) / len(risk_arr), 1),
            'max_issues':    max(issues_arr),
            'min_issues':    min(issues_arr),
            'known_types':   known_types,
            'hack_verdicts': sum(1 for v in verdicts if v == 'hack'),
            'scan_count':    len(scans),
        }
        return jsonify({'machine_id': machine_id, 'scan_count': len(scans), 'baseline': baseline}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/scans/<int:scan_a>/compare/<int:scan_b>', methods=['GET'])
@login_required
def compare_scans(scan_a, scan_b):
    """Compara dos scans del mismo jugador y retorna el diff de hallazgos.
    Útil para detectar qué apareció o desapareció entre sesiones."""
    try:
        with get_api_db_cursor() as cursor:
            def _fetch_scan(sid):
                cursor.execute(
                    f'SELECT id, machine_name, minecraft_username, started_at, risk_score,'
                    f' verdict, issues_found FROM scans WHERE id = {_PH}',
                    (sid,)
                )
                r = cursor.fetchone()
                if not r:
                    return None
                return {
                    'id':        _row_get(r, 0, 'id'),
                    'machine':   _row_get(r, 1, 'machine_name') or '',
                    'username':  _row_get(r, 2, 'minecraft_username') or '',
                    'date':      str(_row_get(r, 3, 'started_at') or '')[:19],
                    'risk':      int(_row_get(r, 4, 'risk_score') or 0),
                    'verdict':   _row_get(r, 5, 'verdict') or 'pending',
                    'total':     int(_row_get(r, 6, 'issues_found') or 0),
                }

            def _fetch_results(sid):
                cursor.execute(
                    f'SELECT issue_type, issue_name, alert_level, confidence, issue_category'
                    f' FROM scan_results WHERE scan_id = {_PH}',
                    (sid,)
                )
                out = {}
                for r in (cursor.fetchall() or []):
                    tipo = str(_row_get(r, 0, 'issue_type') or 'unknown')
                    out[tipo] = {
                        'name':       str(_row_get(r, 1, 'issue_name') or '')[:80],
                        'alert':      str(_row_get(r, 2, 'alert_level') or ''),
                        'confidence': float(_row_get(r, 3, 'confidence') or 0),
                        'category':   str(_row_get(r, 4, 'issue_category') or ''),
                    }
                return out

            meta_a = _fetch_scan(scan_a)
            meta_b = _fetch_scan(scan_b)
            if not meta_a or not meta_b:
                return jsonify({'error': 'Uno o ambos scans no existen'}), 404

            res_a = _fetch_results(scan_a)
            res_b = _fetch_results(scan_b)

        types_a = set(res_a.keys())
        types_b = set(res_b.keys())

        new_in_b    = sorted(types_b - types_a)   # appeared in B, not A
        gone_from_b = sorted(types_a - types_b)   # was in A, gone in B
        common      = sorted(types_a & types_b)

        diff = {
            'scan_a': meta_a,
            'scan_b': meta_b,
            'risk_delta':    meta_b['risk'] - meta_a['risk'],
            'verdict_change': meta_a['verdict'] != meta_b['verdict'],
            'new_findings': [
                {**res_b[t], 'type': t} for t in new_in_b
            ],
            'resolved_findings': [
                {**res_a[t], 'type': t} for t in gone_from_b
            ],
            'persistent_findings': [
                {
                    'type': t,
                    **res_b[t],
                    'conf_delta': round(res_b[t]['confidence'] - res_a[t]['confidence'], 3),
                }
                for t in common
            ],
            'summary': {
                'new_count':        len(new_in_b),
                'resolved_count':   len(gone_from_b),
                'persistent_count': len(common),
            }
        }
        return jsonify(diff), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── P3 #2 — Scoring por rareza ────────────────────────────────────────────────

@app.route('/api/rarity', methods=['GET'])
def get_issue_rarity():
    """Returns hack-rate per issue_type based on staff feedback + verdicts.
    Used by the scanner to dynamically adjust confidence.
    Formula: hack_rate = feedback_hacks / (feedback_hacks + feedback_legitimos)
    """
    try:
        with get_api_db_cursor() as cursor:
            if _USE_PG:
                cursor.execute('''
                    SELECT
                        sr.issue_type,
                        COUNT(*) FILTER (WHERE s.verdict = 'hack')   AS hack_count,
                        COUNT(*) FILTER (WHERE s.verdict = 'clean')  AS clean_count,
                        COUNT(*)                                       AS total
                    FROM scan_results sr
                    JOIN scans s ON sr.scan_id = s.id
                    WHERE s.verdict IN ('hack', 'clean')
                      AND sr.issue_type IS NOT NULL
                      AND sr.issue_type != ''
                    GROUP BY sr.issue_type
                    HAVING COUNT(*) >= 5
                    ORDER BY (COUNT(*) FILTER (WHERE s.verdict = 'hack')::float / COUNT(*)) DESC
                ''')
            else:
                cursor.execute('''
                    SELECT sr.issue_type,
                        SUM(CASE WHEN s.verdict='hack'  THEN 1 ELSE 0 END) AS hack_count,
                        SUM(CASE WHEN s.verdict='clean' THEN 1 ELSE 0 END) AS clean_count,
                        COUNT(*) AS total
                    FROM scan_results sr
                    JOIN scans s ON sr.scan_id = s.id
                    WHERE s.verdict IN ('hack','clean')
                      AND sr.issue_type IS NOT NULL AND sr.issue_type != ''
                    GROUP BY sr.issue_type HAVING COUNT(*) >= 5
                    ORDER BY (SUM(CASE WHEN s.verdict='hack' THEN 1.0 ELSE 0 END)/COUNT(*)) DESC
                ''')
            rows = cursor.fetchall() or []
        result = []
        for r in rows:
            issue_type  = _row_get(r, 0, 'issue_type') or ''
            hack_count  = int(_row_get(r, 1, 'hack_count') or 0)
            clean_count = int(_row_get(r, 2, 'clean_count') or 0)
            total       = int(_row_get(r, 3, 'total') or 1)
            hack_rate   = round(hack_count / total, 4) if total > 0 else 0.5
            result.append({
                'issue_type':  issue_type,
                'hack_rate':   hack_rate,
                'hack_count':  hack_count,
                'clean_count': clean_count,
                'total':       total,
            })
        return jsonify({'rarity': result, 'count': len(result)}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── P3 #16 — Patrones de bans (cruce con historial) ──────────────────────────

@app.route('/api/ban_patterns', methods=['GET'])
def get_ban_patterns():
    """Returns issue types that appear frequently in banned players.
    Used by the scanner to multiply confidence when a pattern matches ban history.
    Returns: [{issue_type, ban_rate, ban_count, total_banned_scans}]
    """
    try:
        with get_api_db_cursor() as cursor:
            if _USE_PG:
                cursor.execute('''
                    SELECT
                        sr.issue_type,
                        COUNT(DISTINCT s.id)    AS banned_scans_with_issue,
                        (SELECT COUNT(DISTINCT id) FROM scans WHERE verdict = 'hack') AS total_banned
                    FROM scan_results sr
                    JOIN scans s ON sr.scan_id = s.id
                    WHERE s.verdict = 'hack'
                      AND sr.issue_type IS NOT NULL AND sr.issue_type != ''
                    GROUP BY sr.issue_type
                    HAVING COUNT(DISTINCT s.id) >= 3
                    ORDER BY COUNT(DISTINCT s.id) DESC
                    LIMIT 100
                ''')
            else:
                cursor.execute('''
                    SELECT sr.issue_type,
                        COUNT(DISTINCT s.id) AS banned_scans_with_issue,
                        (SELECT COUNT(DISTINCT id) FROM scans WHERE verdict='hack') AS total_banned
                    FROM scan_results sr
                    JOIN scans s ON sr.scan_id = s.id
                    WHERE s.verdict='hack' AND sr.issue_type IS NOT NULL AND sr.issue_type!=''
                    GROUP BY sr.issue_type HAVING COUNT(DISTINCT s.id) >= 3
                    ORDER BY COUNT(DISTINCT s.id) DESC LIMIT 100
                ''')
            rows = cursor.fetchall() or []
        result = []
        for r in rows:
            issue_type   = _row_get(r, 0, 'issue_type') or ''
            banned_with  = int(_row_get(r, 1, 'banned_scans_with_issue') or 0)
            total_banned = int(_row_get(r, 2, 'total_banned') or 1)
            ban_rate     = round(banned_with / total_banned, 4) if total_banned > 0 else 0.0
            result.append({
                'issue_type':  issue_type,
                'ban_rate':    ban_rate,
                'ban_count':   banned_with,
                'total_banned': total_banned,
            })
        return jsonify({'ban_patterns': result, 'count': len(result)}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================
# GESTIÓN DE STAFF / ROLES
# ============================================================

@app.route('/api/staff/users', methods=['GET'])
@login_required
def list_staff_users():
    """Lista todos los usuarios con su rol de staff. Solo Admin o superior."""
    current_user = get_user_by_id(session.get('user_id'))
    if not can_manage_staff(current_user):
        return jsonify({'error': 'Se requiere rol Admin o superior'}), 403
    users = list_users() or []
    result = []
    for u in users:
        result.append({
            'id':         u.get('id'),
            'username':   u.get('username'),
            'email':      u.get('email', ''),
            'roles':      u.get('roles', []),
            'staff_role': get_staff_role(u),
            'is_active':  u.get('is_active', True),
            'created_at': str(u.get('created_at', '')),
            'avatar_url': u.get('avatar_url') or '',
        })
    return jsonify({'users': result}), 200


@app.route('/api/staff/users/<int:user_id>/role', methods=['PUT'])
@login_required
def update_staff_role(user_id):
    """Asigna un rol de staff a un usuario. Solo Admin o superior."""
    current_user = get_user_by_id(session.get('user_id'))
    if not can_manage_staff(current_user):
        return jsonify({'error': 'Se requiere rol Admin o superior'}), 403
    data = request.json or {}
    new_role = (data.get('role') or '').strip().lower()
    if new_role not in STAFF_ROLE_HIERARCHY:
        return jsonify({'error': f'Rol inválido. Opciones: {", ".join(STAFF_ROLE_HIERARCHY)}'}), 400
    # Owner no puede ser asignado a través de la API para evitar escalada
    if new_role == 'owner' and get_staff_role(current_user) != 'owner':
        return jsonify({'error': 'Solo un Owner puede asignar el rol de Owner'}), 403
    target = get_user_by_id(user_id)
    if not target:
        return jsonify({'error': 'Usuario no encontrado'}), 404
    # Build updated roles: keep non-staff roles, replace staff role
    existing = target.get('roles', []) if isinstance(target.get('roles'), list) else []
    non_staff = [r for r in existing if r not in STAFF_ROLE_HIERARCHY]
    updated = non_staff + [new_role]
    import json as _json
    try:
        from auth import _auth_cursor, _ph
        ph = _ph()
        with _auth_cursor() as cursor:
            cursor.execute(
                f'UPDATE users SET roles = {ph} WHERE id = {ph}',
                (_json.dumps(updated), user_id)
            )
        return jsonify({'success': True, 'role': new_role}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/staff/users/<int:user_id>/avatar', methods=['PUT'])
@login_required
def update_user_avatar(user_id):
    """Actualiza el avatar de un usuario. Acepta URL externa o data URL base64. Admin o superior."""
    current_user = get_user_by_id(session.get('user_id'))
    if not can_manage_staff(current_user):
        return jsonify({'error': 'Se requiere rol Admin o superior'}), 403
    data = request.json or {}
    avatar_url = (data.get('avatar_url') or '').strip()
    # Validar tamaño: máx 600 KB de texto (cubre imágenes base64 de ~430 KB originales)
    if len(avatar_url) > 614_400:
        return jsonify({'error': 'Imagen demasiado grande (máx 450 KB)'}), 413
    # Validar que sea URL o data URL de imagen
    if avatar_url and not (
        avatar_url.startswith('http://') or
        avatar_url.startswith('https://') or
        avatar_url.startswith('data:image/')
    ):
        return jsonify({'error': 'Formato no válido: se esperaba URL o data URL de imagen'}), 400
    try:
        from auth import _auth_cursor, _ph
        ph = _ph()
        with _auth_cursor() as cursor:
            cursor.execute(
                f'UPDATE users SET avatar_url = {ph} WHERE id = {ph}',
                (avatar_url or None, user_id)
            )
        return jsonify({'success': True}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── ENDPOINT TEMPORAL: promover usuario a admin ─────────────────────────────
# Eliminar después de usar. Token hardcoded — solo sirve para una operación puntual.
_PROMOTE_SECRET = 'aspers-fix-arefy2024'

@app.route('/internal/promote-admin')
def promote_admin_once():
    token    = request.args.get('token', '')
    username = request.args.get('user', 'arefy_admin')
    new_role = request.args.get('role', 'admin')

    if token != _PROMOTE_SECRET:
        return 'Acceso denegado', 403
    if new_role not in STAFF_ROLE_HIERARCHY:
        return f'Rol inválido. Válidos: {STAFF_ROLE_HIERARCHY}', 400

    try:
        import json as _j
        with get_api_db_cursor() as cur:
            cur.execute(f'SELECT id, roles FROM users WHERE username = {_PH}', (username,))
            row = cur.fetchone()
            if not row:
                return f'Usuario {username!r} no encontrado', 404
            uid = _row_get(row, 0, 'id')
            try:
                roles = _j.loads(_row_get(row, 1, 'roles') or '[]')
            except Exception:
                roles = []
            # Quitar roles de staff anteriores y añadir el nuevo
            roles = [r for r in roles if r not in STAFF_ROLE_HIERARCHY]
            roles.append(new_role)
            if new_role in ('admin', 'owner') and 'admin' not in roles:
                roles.append('admin')
            cur.execute(f'UPDATE users SET roles = {_PH} WHERE id = {_PH}', (_j.dumps(roles), uid))
        return f'✅ Roles de {username!r} actualizados a: {roles}', 200
    except Exception as exc:
        return f'❌ Error: {exc}', 500
# ── FIN ENDPOINT TEMPORAL ────────────────────────────────────────────────────


if __name__ == '__main__':
    print("🌐 Iniciando aplicación web de ASPERS Projects...")
    api_url_display = os.environ.get('API_URL') or (API_BASE_URL if IS_RENDER else API_BASE_URL)
    print(f"📡 Conectado a API: {api_url_display}")
    print(f"🔑 API Key configurada: {'Sí' if API_KEY != 'change-this-in-production' else 'No (usar valor por defecto)'}")
    print("⚠️  NOTA: Asegúrate de que la API esté corriendo en http://localhost:5000")
    print("⚠️  NOTA: La API Key debe coincidir con la configurada en api_server.py")
    app.run(host='0.0.0.0', port=8080, debug=True)

