"""
AplicaciÃ³n Web Flask para Panel del Staff de ASPERS Projects
"""
import sys as _sys
try:
    _sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
    _sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass
from flask import Flask, render_template, request, jsonify, session, Response, redirect, url_for, make_response, flash, send_file
from flask_cors import CORS
from flask_wtf.csrf import CSRFProtect, generate_csrf
import os
from bootstrap_env import bootstrap_local_env, is_local_dev as _is_local_dev
bootstrap_local_env()
import requests
import json
import datetime
import secrets
import traceback
from functools import wraps
from cache import cache as _app_cache
from cache import cached as _cached
from api_keys import generate_api_key as _gen_api_key, hash_api_key as _hash_api_key
from webhooks import deliver_with_retries as _deliver_webhook
from trust_score import calculate_trust_score as _calculate_trust_score
from admin_backup import encrypt_json_payload as _encrypt_backup_payload, save_backup as _save_backup, list_backups as _list_backups, read_backup as _read_backup, rotate_backups as _rotate_backups
from gdpr import build_user_export_zip as _build_user_export_zip
try:
    from utils.request_id import bind_request_id as _bind_request_id
except Exception:
    _bind_request_id = None
try:
    from utils.structured_logging import JSONFormatter as _JSONFormatter
except Exception:
    _JSONFormatter = None
try:
    from utils.pagination import Paginator as _Paginator
except Exception:
    _Paginator = None
try:
    from flask_socketio import SocketIO, emit, join_room
except Exception:
    SocketIO = None
    emit = None
    join_room = None
try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
except Exception:
    Limiter = None
    get_remote_address = None

# Importar sistema de autenticaciÃ³n
from auth import (
    init_auth_db, authenticate_user, create_user, create_registration_token,
    verify_registration_token, login_required, admin_required, company_admin_required,
    company_user_required, get_user_by_id, list_registration_tokens, list_users,
    create_company, get_company_by_id, list_companies, update_company,
    has_role, is_admin, is_super_admin, is_company_admin, is_company_user,
    get_staff_role, can_change_verdict, can_manage_tokens, can_manage_staff, hash_password,
    STAFF_ROLE_HIERARCHY
)

# Pack 32 â€” Sistema de Trust + Cooldown (F#54, F#55, F#60).
# Se importa en try/except por compatibilidad: si el archivo no estÃ¡
# (deploy parcial, rollback), el resto de la app sigue funcionando.
try:
    import ai_trust as _ai_trust
    _AI_TRUST_AVAILABLE = True
except Exception as _ai_trust_err:
    _ai_trust = None
    _AI_TRUST_AVAILABLE = False
    print(f'[boot] ai_trust no disponible: {_ai_trust_err}')

# Pack 35 â€” AI Quality + Adaptive Thresholds + RF Retraining trigger.
try:
    import ai_quality as _ai_quality
    _AI_QUALITY_AVAILABLE = True
except Exception as _ai_quality_err:
    _ai_quality = None
    _AI_QUALITY_AVAILABLE = False
    print(f'[boot] ai_quality no disponible: {_ai_quality_err}')

# Pack 36 â€” Auto-learn de patterns de hack desde verdicts confirmados
# por staff con alto trust + Player Risk Profile.
try:
    import ai_autolearn as _ai_autolearn
    _AI_AUTOLEARN_AVAILABLE = True
except Exception as _ai_autolearn_err:
    _ai_autolearn = None
    _AI_AUTOLEARN_AVAILABLE = False
    print(f'[boot] ai_autolearn no disponible: {_ai_autolearn_err}')

# Pack 37 â€” Mantenimiento automÃ¡tico (decay, recompute, cleanup) +
# ranking de reincidentes + sugerencias de Ã­ndices DB.
try:
    import ai_maintenance as _ai_maint
    _AI_MAINT_AVAILABLE = True
except Exception as _ai_maint_err:
    _ai_maint = None
    _AI_MAINT_AVAILABLE = False
    print(f'[boot] ai_maintenance no disponible: {_ai_maint_err}')

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'aspers-secret-key-change-in-production')
app.config['WTF_CSRF_CHECK_DEFAULT'] = False
_SOCKETIO_CORS = os.environ.get('SOCKETIO_CORS_ALLOWED_ORIGINS', '*')
socketio = SocketIO(app, async_mode='threading', cors_allowed_origins=_SOCKETIO_CORS) if SocketIO else None
_RATE_LIMIT_STORAGE = os.environ.get('REDIS_URL', 'memory://')


def _rate_limit_user_or_ip():
    uid = session.get('user_id')
    if uid:
        return f"user:{uid}"
    if get_remote_address is not None:
        return f"ip:{get_remote_address()}"
    return f"ip:{request.remote_addr or 'unknown'}"


def _limit(rule: str, key_func=None):
    if limiter is None:
        def _noop(fn):
            return fn
        return _noop
    return limiter.limit(rule, key_func=key_func) if key_func else limiter.limit(rule)


limiter = Limiter(
    key_func=_rate_limit_user_or_ip,
    app=app,
    storage_uri=_RATE_LIMIT_STORAGE,
    strategy="fixed-window",
    default_limits=[]
) if Limiter is not None else None


@app.errorhandler(404)
def _handle_not_found(e):
    return render_template('errors/404.html'), 404


@app.errorhandler(500)
def _handle_server_error(e):
    return render_template('errors/500.html'), 500


@app.errorhandler(429)
def _handle_rate_limit(e):
    retry_after = 60
    try:
        retry_after = int(getattr(e, "retry_after", 60) or 60)
    except Exception:
        pass
    return jsonify({
        'success': False,
        'error': 'Rate limit exceeded',
        'retry_after_seconds': retry_after,
    }), 429, {'Retry-After': str(retry_after)}
try:
    from api_v2 import api_v2 as _api_v2_bp
    app.register_blueprint(_api_v2_bp)
except Exception as _e_v2:
    print(f"[api_v2] no disponible: {_e_v2}")

# Sesion persistente: 30 dias (de lo contrario las cookies expiran al cerrar el navegador
# y el usuario se queda "deslogueado" sin previo aviso, viendo todo en 0 porque los
# endpoints /api/* devuelven 401 y el JS no valida response.ok).
from datetime import timedelta as _td
app.config['PERMANENT_SESSION_LIFETIME'] = _td(days=30)
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_HTTPONLY'] = True
# En produccion HTTPS forzamos cookie segura
if os.environ.get('RENDER') or os.environ.get('FLASK_ENV') == 'production':
    app.config['SESSION_COOKIE_SECURE'] = True

if os.environ.get('LOG_FORMAT', '').strip().lower() == 'json' and _JSONFormatter is not None:
    import logging as _logging
    _h = _logging.StreamHandler()
    _h.setFormatter(_JSONFormatter())
    app.logger.handlers = [_h]
    app.logger.setLevel(_logging.INFO)


@app.before_request
def _local_dev_access_guard():
    """Solo localhost (+ secreto opcional) cuando ARGUS_LOCAL_DEV=1."""
    if not _is_local_dev() or IS_RENDER:
        return None
    remote = (request.remote_addr or '').strip()
    if remote not in ('127.0.0.1', '::1'):
        return jsonify({
            'success': False,
            'error': 'Panel local: acceso solo desde esta máquina (127.0.0.1).',
        }), 403
    _secret = (os.environ.get('LOCAL_DEV_SECRET') or '').strip()
    if _secret:
        _got = (
            (request.headers.get('X-Local-Dev-Secret') or '').strip()
            or (request.args.get('_local_dev') or '').strip()
            or (request.cookies.get('argus_local_dev') or '').strip()
        )
        if _got != _secret:
            return jsonify({
                'success': False,
                'error': 'Falta LOCAL_DEV_SECRET (header X-Local-Dev-Secret o cookie argus_local_dev).',
            }), 403
    return None


@app.before_request
def _make_session_permanent():
    """Marca la sesion como permanente para que dure PERMANENT_SESSION_LIFETIME
    en lugar de morir al cerrar el navegador."""
    from flask import session as _s
    _s.permanent = True
    if _bind_request_id is not None:
        try:
            _bind_request_id()
        except Exception:
            pass


@app.before_request
def _auth_with_api_key():
    """Permite Authorization: Bearer argus_xxx en endpoints API."""
    if session.get('user_id'):
        return None
    auth = (request.headers.get('Authorization') or '').strip()
    if not auth.lower().startswith('bearer '):
        return None
    token = auth.split(' ', 1)[1].strip()
    if not token.startswith('argus_'):
        return None
    key_hash = _hash_api_key(token)
    try:
        with get_api_db_cursor() as cur:
            cur.execute(
                f"SELECT id, user_id, company_id FROM api_keys WHERE key_hash = {_PH} AND revoked_at IS NULL LIMIT 1",
                (key_hash,)
            )
            row = cur.fetchone()
            if not row:
                return None
            d = dict(row) if not isinstance(row, dict) else row
            uid = int(d.get('user_id') or 0)
            if uid <= 0:
                return None
            session['user_id'] = uid
            session['company_id'] = int(d.get('company_id') or 0) or None
            cur.execute(f"UPDATE api_keys SET last_used_at = CURRENT_TIMESTAMP WHERE id = {_PH}", (int(d.get('id') or 0),))
            _write_audit('api_key.used', 'api_key', str(d.get('id') or ''), {'path': request.path})
    except Exception:
        return None
    return None


csrf = CSRFProtect(app)
_CSRF_EXEMPT_ENDPOINTS = {
    ('POST', '/api/auth/login'),
    ('POST', '/api/auth/register'),
    ('POST', '/api/validate-token'),
    ('POST', '/setup-admin-aspers2024'),
    ('POST', '/api/scans'),
    ('POST', '/api/plugin/issue-token'),
    ('POST', '/api/plugin/violation'),
    ('POST', '/api/plugin/ai-evaluate'),
    ('POST', '/api/plugin/assistant/query'),
}


def _is_csrf_exempt_path(path: str, method: str) -> bool:
    if (method, path) in _CSRF_EXEMPT_ENDPOINTS:
        return True
    # Toda la familia superadmin — protegida por URL secreta + password, sin CSRF tokens en forms.
    if path.startswith('/aspers-sa'):
        return True
    # Endpoint dinámico de entrega de resultados del scanner.
    if method == 'POST' and path.startswith('/api/scans/') and path.endswith('/results'):
        return True
    return False


@app.before_request
def _csrf_protect_state_changes():
    method = request.method.upper()
    if method not in ('POST', 'PUT', 'PATCH', 'DELETE'):
        return None
    path = request.path or ''
    if _is_csrf_exempt_path(path, method):
        return None
    if request.headers.get('X-Argus-Plugin-Key'):
        return None
    auth_header = (request.headers.get('Authorization') or '').strip()
    if auth_header.startswith('Bearer argus_pk_'):
        return None
    if not (session.get('user_id') or session.get('admin_subscriptions')):
        return None
    return csrf.protect()


@app.after_request
def _propagate_request_id(resp):
    try:
        from flask import g
        rid = getattr(g, 'request_id', '')
        if rid:
            resp.headers['X-Request-ID'] = rid
    except Exception:
        pass
    return resp


if socketio is not None:
    @socketio.on('connect')
    def _ws_connect():
        uid = int(session.get('user_id') or 0)
        if uid <= 0:
            return False
        if join_room is not None:
            join_room(f"user:{uid}")
            cid = int(session.get('company_id') or 0)
            if cid > 0:
                join_room(f"company:{cid}")
        if emit is not None:
            emit('notification', {'kind': 'socket', 'message': 'Conectado a tiempo real'})

    @socketio.on('disconnect')
    def _ws_disconnect():
        return None

    @socketio.on('oracle_message')
    def _ws_oracle_message(data):
        uid = int(session.get('user_id') or 0)
        if uid <= 0:
            return
        msg = str((data or {}).get('message') or '').strip()
        if not msg:
            if emit is not None:
                emit('oracle_response', {'error': 'Mensaje vacío'})
            return
        try:
            import argus_ai_assistant as A
            out = A.generate_response(msg, None, None, None)
            ans = (out or {}).get('answer') or 'Sin respuesta.'
        except Exception as e:
            ans = f"Error Oracle WS: {e}"
        if emit is not None:
            emit('oracle_response', {'reply': ans, 'via': 'ws'})


def _emit_realtime_notification(user_id: int | None = None, company_id: int | None = None, payload: dict | None = None):
    if socketio is None:
        return
    data = payload or {}
    event_type = str((data or {}).get('kind') or 'security_alert').lower()
    try:
        if user_id:
            allow = True
            try:
                with get_api_db_cursor() as cur:
                    cur.execute(
                        f"SELECT enabled FROM user_notification_prefs WHERE user_id = {_PH} AND channel = 'in_app' AND event_type = {_PH} LIMIT 1",
                        (int(user_id), event_type)
                    )
                    rr = cur.fetchone()
                    if rr is not None:
                        allow = bool(_row_get(rr, 0, 'enabled'))
            except Exception:
                pass
            if allow:
                socketio.emit('notification', data, room=f"user:{int(user_id)}")
        if company_id:
            # respetar prefs por usuario cuando emitimos por company
            targets = []
            try:
                with get_api_db_cursor() as cur:
                    cur.execute(
                        f"SELECT id FROM users WHERE company_id = {_PH} AND deleted_at IS NULL",
                        (int(company_id),)
                    )
                    targets = [int(_row_get(r, 0, 'id') or 0) for r in (cur.fetchall() or [])]
            except Exception:
                targets = []
            if not targets:
                socketio.emit('notification', data, room=f"company:{int(company_id)}")
            else:
                for uid in targets:
                    _emit_realtime_notification(user_id=uid, payload=data)
    except Exception as e:
        print(f"[ws] emit notification error: {e}")


def require_superadmin(f):
    """Restringe endpoint a usuarios superadmin autenticados."""
    @wraps(f)
    def _wrapped(*args, **kwargs):
        user_id = session.get('user_id')
        user = get_user_by_id(user_id) if user_id else None
        if not user or not is_super_admin(user):
            return jsonify({'error': 'Acceso restringido a superadmin'}), 403
        return f(*args, **kwargs)
    return _wrapped


def _write_audit(action: str, resource_type: str = '', resource_id: str = '', details: dict | None = None):
    try:
        uid = int(session.get('user_id') or 0) or None
        sid = request.cookies.get('session') if request else None
        ip = request.remote_addr if request else None
        ua = request.headers.get('User-Agent') if request else None
        with get_api_db_cursor() as cur:
            cur.execute(
                f"INSERT INTO audit_log_v2 (user_id, session_id, action, resource_type, resource_id, details, ip_address, user_agent) "
                f"VALUES ({_PH},{_PH},{_PH},{_PH},{_PH},{_PH},{_PH},{_PH})",
                (uid, sid, action, resource_type, str(resource_id or ''), json.dumps(details or {}), ip, ua)
            )
    except Exception as e:
        print(f"[audit_v2] write error: {e}")


def audit_action(action_name: str, resource_type: str = ''):
    def _decorator(fn):
        @wraps(fn)
        def _wrapped(*args, **kwargs):
            resp = fn(*args, **kwargs)
            rid = kwargs.get('scan_id') or kwargs.get('company_id') or kwargs.get('id') or ''
            _write_audit(action_name, resource_type, str(rid), {'method': request.method, 'path': request.path})
            return resp
        return _wrapped
    return _decorator


CORS(app)

# Inicializar base de datos de autenticaciÃ³n al iniciar (en background para no bloquear)
_ARGUS_VERSION = '1.6.58'  # sincronizar con SCANNER_VERSION en main.py y CURRENT_SCANNER_VERSION abajo

# URL de invitacion permanente al Discord oficial. Se inyecta en todos los
# templates como `discord_invite` via @app.context_processor (ver mas abajo).
# Se puede sobreescribir desde .env / Render con la variable DISCORD_INVITE_URL.
DISCORD_INVITE_URL = os.environ.get(
    'DISCORD_INVITE_URL',
    'https://discord.gg/aMRJhbgNUZ',  # invitacion permanente oficial Argus Projects
).strip()


@app.context_processor
def _inject_globals():
    """Variables disponibles en TODOS los templates sin pasarlas explicitamente."""
    return {
        'discord_invite': DISCORD_INVITE_URL,
        'argus_version': _ARGUS_VERSION,
        'csrf_token_value': generate_csrf(),
    }


def _notify_new_deploy():
    """Detecta si es un deploy nuevo comparando RENDER_GIT_COMMIT con el Ãºltimo
    commit almacenado en BD. Si es nuevo, envÃ­a embed a Discord vÃ­a webhook.
    Solo se ejecuta en Render (RENDER_GIT_COMMIT presente).

    Variable de entorno requerida:
      DISCORD_DEPLOY_WEBHOOK â€” URL completa del webhook de Discord
    """
    commit  = os.environ.get('RENDER_GIT_COMMIT', '').strip()
    branch  = os.environ.get('RENDER_GIT_BRANCH', 'main').strip()
    service = os.environ.get('RENDER_SERVICE_NAME', 'argus-web').strip()
    webhook = os.environ.get('DISCORD_DEPLOY_WEBHOOK', '').strip()

    print(f'[Deploy] DEBUG commit={commit[:7] if commit else "VACÃO"} branch={branch} service={service}')
    print(f'[Deploy] DEBUG webhook={"SET ("+webhook[:30]+"...)" if webhook else "NO CONFIGURADO"}')

    if not commit:
        print('[Deploy] Sin RENDER_GIT_COMMIT â€” entorno local, saliendo')
        return
    if not webhook:
        print('[Deploy] âŒ DISCORD_DEPLOY_WEBHOOK no estÃ¡ configurado como variable de entorno en Render')
        return

    try:
        with get_api_db_cursor() as cur:
            cur.execute('''
                CREATE TABLE IF NOT EXISTS app_meta (
                    key   VARCHAR(100) PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cur.execute('SELECT value FROM app_meta WHERE key = %s', ('last_deploy_commit',))
            row = cur.fetchone()
            last_commit = (row[0] if isinstance(row, (list, tuple)) else row.get('value', '')) if row else ''
            print(f'[Deploy] DEBUG last_commit_en_bd={last_commit[:7] if last_commit else "NINGUNO"}')

            if last_commit == commit:
                print(f'[Deploy] Mismo commit ({commit[:7]}) â€” restart sin deploy nuevo, no se notifica')
                return

            cur.execute('''
                INSERT INTO app_meta (key, value, updated_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
            ''', ('last_deploy_commit', commit))
            print(f'[Deploy] BD actualizada con nuevo commit {commit[:7]}')

    except Exception as e:
        print(f'[Deploy] âŒ Error leyendo/escribiendo BD: {e}')
        return

    # Guardar webhook pendiente en BD â€” el scheduler lo reintentarÃ¡ cada 10 min
    # hasta que el ban de Cloudflare expire (error 1015 puede durar horas).
    try:
        import json as _json_d
        pending_val = _json_d.dumps({
            'webhook': webhook,
            'commit':  commit,
            'branch':  branch,
            'service': service,
            'version': _ARGUS_VERSION,
            'queued_at': __import__('datetime').datetime.utcnow().isoformat(),
            'attempts': 0,
        })
        with get_api_db_cursor() as cur:
            cur.execute('''
                INSERT INTO app_meta (key, value, updated_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
            ''', ('pending_deploy_webhook', pending_val))
        print('[Deploy] NotificaciÃ³n guardada en BD â€” el scheduler reintentarÃ¡ cada 10 min')
    except Exception as e:
        print(f'[Deploy] âŒ No se pudo guardar notificaciÃ³n pendiente: {e}')

    # Primer intento inmediato en background (puede fallar por 429 de CF)
    threading.Thread(target=_try_send_deploy_webhook, daemon=True).start()
    # Telegram â€” backup instantÃ¡neo (no tiene el problema de IP ban de Cloudflare)
    _tg_msg = (
        f'ðŸš€ <b>Nuevo Deploy</b> â€” Argus {_ARGUS_VERSION}\n'
        f'Servicio: {service} | Rama: {branch}\n'
        f'Commit: <code>{commit[:7]}</code>'
    )
    threading.Thread(target=lambda: _notify_telegram(_tg_msg), daemon=True).start()


def _try_send_deploy_webhook():
    """Intenta enviar el webhook de deploy pendiente guardado en BD.
    Llamado al startup y por el scheduler cada 10 min.
    """
    import json as _json
    import urllib.request as _urlreq
    import urllib.error  as _urlerr
    import datetime as _dt

    try:
        with get_api_db_cursor() as cur:
            cur.execute('SELECT value FROM app_meta WHERE key = %s', ('pending_deploy_webhook',))
            row = cur.fetchone()
    except Exception as e:
        print(f'[Deploy] Error leyendo pending webhook: {e}')
        return

    if not row:
        return  # nada pendiente

    raw = row[0] if isinstance(row, (list, tuple)) else row.get('value', '')
    try:
        meta = _json.loads(raw)
    except Exception:
        return

    webhook  = meta.get('webhook', '')
    attempts = meta.get('attempts', 0)
    max_att  = 15  # ~2.5h a 10 min/intento

    if not webhook or attempts >= max_att:
        # Darse por vencido
        try:
            with get_api_db_cursor() as cur:
                cur.execute('DELETE FROM app_meta WHERE key = %s', ('pending_deploy_webhook',))
        except Exception:
            pass
        if attempts >= max_att:
            print(f'[Deploy] âŒ Webhook fallido tras {max_att} intentos â€” abandonando')
        return

    short   = meta.get('commit', '')[:7]
    now     = _dt.datetime.utcnow().strftime('%d/%m/%Y %H:%M UTC')
    version = meta.get('version', _ARGUS_VERSION)
    branch  = meta.get('branch', 'main')
    service = meta.get('service', 'argus-web')

    payload = {
        'embeds': [{
            'title': 'ðŸš€ ArgusScanner desplegado',
            'description': 'El sistema de detecciÃ³n de hacks ha sido desplegado exitosamente en producciÃ³n.',
            'color': 0x7C3AED,
            'fields': [
                {'name': 'ðŸ“¦ VersiÃ³n',   'value': f'`{version}`', 'inline': True},
                {'name': 'ðŸ”– Commit',    'value': f'`{short}`',   'inline': True},
                {'name': 'ðŸŒ¿ Rama',      'value': f'`{branch}`',  'inline': True},
                {'name': 'ðŸ–¥ï¸ Servicio', 'value': f'`{service}`', 'inline': True},
                {'name': 'âœ… Estado',    'value': 'Operativo',    'inline': True},
                {'name': 'ðŸ• Hora',      'value': now,            'inline': True},
            ],
            'footer': {'text': 'ASPERS Projects â€” Sistema Argus'},
        }]
    }

    headers = {
        'Content-Type': 'application/json',
        'User-Agent': 'DiscordBot (https://aspers.gg, 1.0)',
    }
    body = _json.dumps(payload).encode('utf-8')

    print(f'[Deploy] Intentando webhook (intento {attempts + 1}/{max_att}) commit={short}')
    try:
        req = _urlreq.Request(webhook, data=body, headers=headers, method='POST')
        with _urlreq.urlopen(req, timeout=12) as resp:
            print(f'âœ… [Deploy] Webhook enviado â€” HTTP {resp.status} â€” commit {short}')
            # Ã‰xito: borrar de BD
            with get_api_db_cursor() as cur:
                cur.execute('DELETE FROM app_meta WHERE key = %s', ('pending_deploy_webhook',))
            return
    except _urlerr.HTTPError as e:
        body_preview = e.read(200).decode('utf-8', errors='replace').strip()
        retry_after  = e.headers.get('Retry-After', '?')
        print(f'âš ï¸ [Deploy] HTTP {e.code} (Retry-After: {retry_after}s) â€” {body_preview[:120]}')
    except Exception as e:
        print(f'âš ï¸ [Deploy] Error de red: {e}')

    # FracasÃ³ â€” incrementar contador en BD para el prÃ³ximo intento del scheduler
    meta['attempts'] = attempts + 1
    try:
        with get_api_db_cursor() as cur:
            cur.execute('''
                INSERT INTO app_meta (key, value, updated_at) VALUES (%s, %s, NOW())
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
            ''', ('pending_deploy_webhook', _json.dumps(meta)))
        print(f'[Deploy] Reintento programado en ~10 min (intento {attempts + 1}/{max_att})')
    except Exception as e:
        print(f'[Deploy] Error actualizando contador: {e}')


def init_db_async():
    """Inicializa la BD de forma asÃ­ncrona para no bloquear el inicio"""
    try:
        init_auth_db()
        print("âœ… Base de datos de autenticaciÃ³n inicializada correctamente")
    except Exception as e:
        print(f"âš ï¸ Error al inicializar base de datos: {e}")
        print("âš ï¸ La aplicaciÃ³n continuarÃ¡, pero algunas funciones pueden no funcionar")
    # MigraciÃ³n: columna short_code en scan_tokens (cÃ³digos de 6 chars)
    try:
        with get_api_db_cursor() as _cur:
            _cur.execute("ALTER TABLE scan_tokens ADD COLUMN IF NOT EXISTS short_code VARCHAR(8) UNIQUE")
            _cur.execute("CREATE INDEX IF NOT EXISTS idx_st_short_code ON scan_tokens(short_code)")
        print("âœ… Columna short_code en scan_tokens verificada/creada")
    except Exception as _e:
        print(f"âš ï¸ Error migrando short_code: {_e}")
    # MigraciÃ³n de seguridad: crear download_links en PostgreSQL si no existe
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
        print("âœ… Tabla download_links verificada/creada en PostgreSQL")
    except Exception as _e:
        print(f"âš ï¸ Error verificando download_links: {_e}")
    # Tabla hack_blacklist â€” hashes confirmados como hacks en 3+ scans
    try:
        with get_api_db_cursor() as _cur:
            _cur.execute('''
                CREATE TABLE IF NOT EXISTS hack_blacklist (
                    sha256 VARCHAR(128) PRIMARY KEY,
                    hack_name VARCHAR(255),
                    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    times_confirmed INTEGER DEFAULT 1
                )
            ''')
        print("âœ… Tabla hack_blacklist verificada/creada")
    except Exception as _e:
        print(f"âš ï¸ Error creando hack_blacklist: {_e}")
    # MigraciÃ³n: columna ensemble_data en scans (veredicto 6-sistemas)
    try:
        with get_api_db_cursor() as _cur:
            _cur.execute("ALTER TABLE scans ADD COLUMN IF NOT EXISTS ensemble_data TEXT")
        print("âœ… Columna ensemble_data en scans verificada/creada")
    except Exception as _e:
        print(f"âš ï¸ Error migrando ensemble_data: {_e}")
    # Migración H-001: company_id en scans para reportes multi-empresa.
    try:
        with get_api_db_cursor() as _cur:
            _cur.execute(
                "ALTER TABLE scans ADD COLUMN IF NOT EXISTS company_id INTEGER "
                "REFERENCES companies(id) ON DELETE SET NULL"
            )
            # Backfill por token->created_by(username)->users.company_id.
            try:
                _cur.execute(
                    f"UPDATE scans s "
                    f"SET company_id = u.company_id "
                    f"FROM scan_tokens st "
                    f"JOIN users u ON LOWER(u.username) = LOWER(st.created_by) "
                    f"WHERE s.company_id IS NULL "
                    f"  AND s.token_id = st.id "
                    f"  AND u.company_id IS NOT NULL"
                )
            except Exception:
                _cur.execute(
                    "UPDATE scans "
                    "SET company_id = ("
                    "  SELECT u.company_id FROM scan_tokens st "
                    "  JOIN users u ON LOWER(u.username) = LOWER(st.created_by) "
                    "  WHERE st.id = scans.token_id LIMIT 1"
                    ") "
                    "WHERE company_id IS NULL"
                )
            _cur.execute("CREATE INDEX IF NOT EXISTS idx_scans_company_id ON scans(company_id)")
        print("âœ… Columna company_id en scans verificada/creada + backfill")
    except Exception as _e:
        print(f"âš ï¸ Error migrando scans.company_id: {_e}")
    # MigraciÃ³n: tablas/columnas para sistema de plugin keys (Minecraft).
    # IMPORTANTE: ejecutar UNA SOLA VEZ al startup. Antes esto se ejecutaba
    # on-demand desde @before_request via _plugin_schema_guard(), lo cual
    # provocaba DEADLOCKs entre el ALTER TABLE scan_tokens (AccessExclusiveLock)
    # y los SELECTs concurrentes con LEFT JOIN scan_tokens en /api/scans/<id>.
    try:
        _ensure_plugin_keys_schema()
        global _PLUGIN_SCHEMA_READY
        _PLUGIN_SCHEMA_READY = True
        print("âœ… Schema de plugin_keys verificado/creado")
    except Exception as _e:
        print(f"âš ï¸ Error migrando plugin_keys schema: {_e}")
    # NotificaciÃ³n de deploy nuevo â€” se dispara una sola vez por commit
    _notify_new_deploy()

# Inicializar en un thread separado para no bloquear el inicio.
# IMPORTANTE: el Thread.start() real estÃ¡ al FINAL del mÃ³dulo (justo antes
# de `if __name__ == '__main__':`) para evitar una race condition de import:
# init_db_async() llama get_api_db_cursor() (definida en lÃ­nea ~1091) y
# _ensure_plugin_keys_schema() (lÃ­nea ~2203). Si arrancamos el thread aquÃ­,
# Python aÃºn no ha evaluado esas defs y falla con NameError, rompiendo TODAS
# las migraciones (short_code, download_links, hack_blacklist, ensemble_data,
# plugin_keys schema) y la notificaciÃ³n de deploy a Discord.
# Hotfix Pack 41 (v1.6.50, post-rebuild): el .start() vive al final.
import threading

def _autonomous_daily_learning():
    """Pipeline de aprendizaje autÃ³nomo â€” corre cada dÃ­a a las 2:00 UTC.

    Pasos en orden:
      1. Hash consensus  â€” detecta hashes maliciosos por frecuencia estadÃ­stica
      2. Auto-labels     â€” genera pseudo-etiquetas para scans extremos sin veredicto humano
      3. RF retrain      â€” reentrena Random Forest con humanos + auto-labels
      4. Isolation Forestâ€” reentrena detector de anomalÃ­as con todos los scans
    No requiere ningÃºn input externo ni veredicto humano para operar.
    """
    try:
        from ml_classifier import get_classifier
        clf = get_classifier()
        with get_api_db_cursor() as cursor:
            # 1. Hash consensus
            h = clf.learn_hash_consensus(cursor)
            print(f"[ML Auto] Hash consensus: {h.get('promoted',0)} promovidos")

            # 2. Auto-labels from extreme heuristic scores
            al = clf.generate_auto_labels(cursor)
            print(f"[ML Auto] Auto-labels: {al.get('labeled',0)} nuevos")

            # 3. RF retraining (human verdicts + auto-labels)
            rf = clf.train(cursor)
            if rf.get('trained'):
                print(f"[ML Auto] RF: acc={rf.get('accuracy')}, "
                      f"muestras={rf.get('samples')} "
                      f"({rf.get('human_samples')} humanas + {rf.get('auto_samples')} auto)")
            else:
                print(f"[ML Auto] RF no reentrenado: {rf.get('error')}")

            # 4. Isolation Forest (unsupervised, all scans)
            iso = clf.train_isolation_forest(cursor)
            if iso.get('trained'):
                print(f"[ML Auto] IsoForest: {iso.get('scans')} scans")
            else:
                print(f"[ML Auto] IsoForest no entrenado: {iso.get('error')}")

    except Exception as e:
        import traceback
        print(f"[ML Auto] Error en pipeline autÃ³nomo: {e}")
        print(traceback.format_exc())

def _daily_summary_job():
    """P3 #25 â€” Resumen diario de scans del dÃ­a anterior, enviado a Discord a las 9:00 UTC."""
    try:
        import datetime as _dts
        yesterday = (_dts.datetime.utcnow() - _dts.timedelta(days=1)).strftime('%Y-%m-%d')
        with get_api_db_cursor() as cur:
            if _USE_PG:
                cur.execute('''
                    SELECT COUNT(*) AS total,
                           SUM(CASE WHEN verdict='hack' THEN 1 ELSE 0 END) AS hacks,
                           SUM(CASE WHEN verdict='clean' THEN 1 ELSE 0 END) AS clean,
                           SUM(CASE WHEN verdict IS NULL OR verdict='pending' THEN 1 ELSE 0 END) AS pending,
                           AVG(risk_score) AS avg_risk
                    FROM scans
                    WHERE DATE(started_at) = %s
                ''', (yesterday,))
            else:
                cur.execute('''
                    SELECT COUNT(*), SUM(verdict='hack'), SUM(verdict='clean'),
                           SUM(verdict IS NULL OR verdict='pending'), AVG(risk_score)
                    FROM scans WHERE DATE(started_at) = ?
                ''', (yesterday,))
            row = cur.fetchone()
        if not row or (row[0] or 0) == 0:
            return  # No scans yesterday
        total   = int(row[0] or 0)
        hacks   = int(row[1] or 0)
        clean   = int(row[2] or 0)
        pending = int(row[3] or 0)
        avg_risk = round(float(row[4] or 0), 1)

        # Top hack types
        with get_api_db_cursor() as cur:
            if _USE_PG:
                cur.execute('''
                    SELECT issue_type, COUNT(*) AS n FROM scan_results sr
                    JOIN scans s ON sr.scan_id = s.id
                    WHERE s.verdict = 'hack' AND DATE(s.started_at) = %s
                    GROUP BY issue_type ORDER BY n DESC LIMIT 3
                ''', (yesterday,))
            else:
                cur.execute('''
                    SELECT issue_type, COUNT(*) AS n FROM scan_results sr
                    JOIN scans s ON sr.scan_id = s.id
                    WHERE s.verdict = 'hack' AND DATE(s.started_at) = ?
                    GROUP BY issue_type ORDER BY n DESC LIMIT 3
                ''', (yesterday,))
            top_types = [f"{_row_get(r, 0, 'issue_type')} Ã—{int(_row_get(r, 1, 'n') or 0)}" for r in (cur.fetchall() or [])]

        from web_app.discord_bot import notify_daily_summary
        notify_daily_summary(
            date=yesterday, total=total, hacks=hacks, clean=clean,
            pending=pending, avg_risk=avg_risk, top_types=top_types,
        )
    except Exception as e:
        print(f'[Daily Summary] Error: {e}')

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(_autonomous_daily_learning, 'cron', hour=2, minute=0,
                       id='autonomous_ml_daily', replace_existing=True)
    _scheduler.add_job(_daily_summary_job, 'cron', hour=9, minute=0,
                       id='daily_summary', replace_existing=True)
    _scheduler.add_job(lambda: globals().get('_send_daily_digest_emails', lambda: None)(), 'cron', hour=8, minute=0,
                       id='daily_digest_email', replace_existing=True)
    _scheduler.add_job(lambda: globals().get('aggregate_fp_feedback', lambda: None)(), 'cron', hour=7, minute=30,
                       id='aggregate_fp_feedback', replace_existing=True)
    _scheduler.add_job(lambda: globals().get('audit_retention_cleanup', lambda: None)(), 'cron', hour=4, minute=15,
                       id='audit_retention_cleanup', replace_existing=True)
    _scheduler.add_job(lambda: globals().get('purge_soft_deleted_older_than_90d', lambda: None)(), 'cron', hour=4, minute=45,
                       id='purge_soft_deleted_90d', replace_existing=True)
    _scheduler.add_job(lambda: globals().get('recalc_all_trust_scores', lambda: None)(), 'cron', hour=3, minute=20,
                       id='recalc_user_trust_scores', replace_existing=True)
    _scheduler.add_job(lambda: globals().get('scan_scheduler_tick', lambda: None)(), 'interval', minutes=5,
                       id='scan_scheduler_tick', replace_existing=True)
    _scheduler.add_job(_try_send_deploy_webhook, 'interval', minutes=10,
                       id='deploy_webhook_retry', replace_existing=True)
    _scheduler.start()
    print('[Scheduler] ML autÃ³nomo diario (2:00 UTC) + resumen diario + deploy webhook retry activados')
except Exception as _sch_err:
    print(f'[Scheduler] APScheduler no disponible: {_sch_err}')

# Discord HTTP Interactions (sin gateway, sin rate-limit)
try:
    import discord_interactions as _di
    print('[Discord] HTTP Interactions activado.')
except Exception as _disc_err:
    print(f'[Discord] Interactions no disponible: {_disc_err}')

# Health check endpoints (simplificado - sin import externo)

# ConfiguraciÃ³n
# Detectar si estamos en Render o en desarrollo local
RENDER_EXTERNAL_URL = os.environ.get('RENDER_EXTERNAL_URL')  # Render proporciona esta variable
IS_RENDER = bool(RENDER_EXTERNAL_URL)

if IS_RENDER:
    # La API estÃ¡ integrada en esta misma app â€” usar la propia URL de Render
    api_url_env = os.environ.get('API_URL')
    if api_url_env:
        API_BASE_URL = api_url_env.rstrip('/')
    else:
        API_BASE_URL = RENDER_EXTERNAL_URL.rstrip('/')
        print(f"âœ… API_URL apunta a esta misma app: {API_BASE_URL}")
elif _is_local_dev():
    # Réplica local de asperss.onrender.com: misma app monolítica en un solo puerto
    _local_port = int(os.environ.get('PORT', '8080'))
    API_BASE_URL = (os.environ.get('API_URL') or f'http://127.0.0.1:{_local_port}').rstrip('/')
    print(f"[local-dev] API_URL → {API_BASE_URL} (modo Render local)")
else:
    # Legacy: API separada en :5000
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
    
    # Si API_URL estÃ¡ configurado explÃ­citamente, usarlo
    api_url_env = os.environ.get('API_URL')
    if api_url_env:
        return f"{api_url_env.rstrip('/')}/{endpoint}"
    
    # Usar API_BASE_URL (que ya tiene el valor correcto segÃºn el entorno)
    if API_BASE_URL:
        return f"{API_BASE_URL.rstrip('/')}/{endpoint}"
    
    # Fallback: si nada estÃ¡ configurado, usar el valor por defecto segÃºn el entorno
    if IS_RENDER:
        default_url = 'https://ssapi-cfni.onrender.com'
    else:
        default_url = 'http://localhost:5000'
    
    return f"{default_url}/{endpoint}"

def require_api_key(f):
    """Decorador para requerir API key"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # En producciÃ³n, verificar API key del staff
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    """Página oficial de Argus Projects — hub que deriva a cada proyecto."""
    response = make_response(render_template('hub.html'))
    response.headers['Cache-Control'] = 'public, max-age=300'  # 5 minutos
    return response


@app.route('/scanner')
def scanner_landing():
    """Sub-index del producto Argus Scanner (la landing anterior de /)."""
    response = make_response(render_template('index.html'))
    response.headers['Cache-Control'] = 'public, max-age=300'  # 5 minutos
    return response


@app.route('/terminos')
def terminos():
    return render_template('terminos.html')

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
    """Health check endpoint para Render - Optimizado para ser ultra-rÃ¡pido"""
    # Respuesta mÃ­nima y rÃ¡pida para evitar spinning down
    # Este endpoint se puede llamar periÃ³dicamente para mantener el servicio activo
    response = make_response('OK', 200)
    response.headers['Content-Type'] = 'text/plain'
    response.headers['Cache-Control'] = 'no-cache'
    return response


# Visual #38 - timestamp de arranque para calcular uptime
import time as _time_mod
_APP_START_TIME = _time_mod.time()


@app.route('/healthz', methods=['GET'])
def healthz():
    """Healthcheck mÃ­nimo SIN tocar la BD. Sirve para distinguir entre:
      * worker caÃ­do (TCP OK pero esto da timeout)        â†’ problema de proceso
      * worker vivo pero BD muerta (esto OK + /api/version db_ok=False)
    Ãštil cuando el servicio parece caÃ­do para diagnosticar la causa real
    sin bloquearse 30s+ esperando a la BD.
    """
    return jsonify({
        'ok':       True,
        'version':  _ARGUS_VERSION,
        'uptime_s': int(_time_mod.time() - _APP_START_TIME),
    }), 200


@app.route('/api/db-stats', methods=['GET'])
@login_required
@require_superadmin
def api_db_stats():
    """DiagnÃ³stico de espacio de BD. Ãštil para saber si Render Postgres estÃ¡
    cerca del lÃ­mite (1 GB en plan Free). Acceso pÃºblico sÃ³lo al tamaÃ±o total
    y al # de filas top â€” sin datos sensibles.
    """
    info = {
        'backend': 'postgresql' if _USE_PG else ('mysql' if _USE_MYSQL else 'sqlite'),
        'size_bytes': None,
        'size_human': None,
        'limit_bytes': 1024 * 1024 * 1024,  # 1 GB Render Free
        'limit_human': '1 GB (Render Free)',
        'usage_percent': None,
        'top_tables': [],
        'error': None,
    }
    try:
        with get_api_db_cursor() as cur:
            if _USE_PG:
                try:
                    cur.execute('SELECT pg_database_size(current_database())')
                    row = cur.fetchone()
                    sb = int(_first_value(row) or 0) if row else 0
                    info['size_bytes'] = sb
                    info['size_human'] = _human_bytes(sb)
                    info['usage_percent'] = round((sb / info['limit_bytes']) * 100.0, 2)
                except Exception as _se:
                    info['error'] = f'pg_database_size: {str(_se)[:200]}'
                try:
                    cur.execute("""
                        SELECT relname AS table_name,
                               pg_total_relation_size(C.oid) AS total_bytes
                          FROM pg_class C
                          LEFT JOIN pg_namespace N ON (N.oid = C.relnamespace)
                         WHERE nspname NOT IN ('pg_catalog','information_schema')
                           AND C.relkind = 'r'
                         ORDER BY total_bytes DESC
                         LIMIT 15
                    """)
                    for r in (cur.fetchall() or []):
                        try:
                            name = _row_get(r, 0, 'table_name')
                            tb   = int(_row_get(r, 1, 'total_bytes') or 0)
                        except Exception:
                            name = r[0] if r else None
                            tb   = int(r[1] or 0) if r and len(r) > 1 else 0
                        info['top_tables'].append({
                            'table': name,
                            'bytes': tb,
                            'human': _human_bytes(tb),
                        })
                except Exception as _te:
                    if not info['error']:
                        info['error'] = f'top_tables: {str(_te)[:200]}'
            else:
                info['error'] = f'No size query implemented for backend={info["backend"]}'
    except Exception as e:
        info['error'] = str(e)[:300]
    return jsonify(info), 200


def _human_bytes(n):
    try:
        n = float(n or 0)
    except Exception:
        return '0 B'
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if n < 1024.0:
            return f'{n:.1f} {unit}'
        n /= 1024.0
    return f'{n:.1f} PB'


@app.route('/api/version', methods=['GET'])
def api_version():
    """Devuelve versiÃ³n, uptime y estado de la API. Usado por el footer del
    panel para mostrar 'Argus v1.6.36 Â· uptime 2d 4h Â· âœ“ DB OK'."""
    uptime_seconds = int(_time_mod.time() - _APP_START_TIME)
    days  = uptime_seconds // 86400
    hours = (uptime_seconds % 86400) // 3600
    mins  = (uptime_seconds % 3600) // 60
    if days > 0:
        uptime_human = f"{days}d {hours}h"
    elif hours > 0:
        uptime_human = f"{hours}h {mins}m"
    else:
        uptime_human = f"{mins}m"
    db_ok = True
    db_backend = 'sqlite'
    db_error = None
    if _USE_PG:
        db_backend = 'postgresql'
    elif _USE_MYSQL:
        db_backend = 'mysql'
    try:
        with get_api_db_cursor() as _cur:
            _cur.execute('SELECT 1')
            _cur.fetchone()
    except Exception as _e:
        db_ok = False
        db_error = str(_e)[:200]
    changelog = ''
    file_hash = ''
    try:
        with get_api_db_cursor() as cur:
            cur.execute(
                'SELECT version, changelog, file_hash FROM app_versions ORDER BY id DESC LIMIT 1'
            )
            row = cur.fetchone()
            if row:
                changelog = _row_get(row, 1, 'changelog') or ''
                file_hash = _row_get(row, 2, 'file_hash') or ''
    except Exception:
        pass
    return jsonify({
        'version':         _ARGUS_VERSION,
        'scanner_version': CURRENT_SCANNER_VERSION,
        'changelog':       changelog,
        'file_hash':       file_hash,
        'uptime_seconds':  uptime_seconds,
        'uptime_human':    uptime_human,
        'db_ok':           db_ok,
        'db_backend':      db_backend,
        'db_error':        db_error,
        'started_at':      int(_APP_START_TIME),
    })


@app.route('/api/public/banner', methods=['GET'])
def api_public_banner():
    """Banner superior dismissible (mantenimiento / nueva versión)."""
    msg = os.environ.get('ARGUS_PUBLIC_BANNER', '').strip()
    if not msg:
        try:
            with get_api_db_cursor() as cur:
                cur.execute(
                    "SELECT value FROM app_settings WHERE key = 'public_banner' LIMIT 1"
                )
                row = cur.fetchone()
                if row:
                    msg = _row_get(row, 0, 'value') or ''
        except Exception:
            pass
    if not msg:
        return jsonify({'message': None})
    return jsonify({'id': 'default', 'message': msg})


@app.route('/api/sa/search', methods=['GET'])
def api_sa_search():
    """Búsqueda global SuperAdmin (Cmd+K)."""
    if not session.get('admin_subscriptions'):
        return jsonify({'results': []}), 403
    q = (request.args.get('q') or '').strip()
    if not q or len(q) < 2:
        return jsonify({'results': []})
    results = []
    like = f'%{q}%'
    ph = _PH
    try:
        with get_api_db_cursor() as cur:
            try:
                cur.execute(f'SELECT id, name FROM companies WHERE name LIKE {ph} LIMIT 8', (like,))
            except Exception:
                cur.execute('SELECT id, name FROM companies WHERE name LIKE ? LIMIT 8', (like,))
            for row in cur.fetchall():
                results.append({
                    'label': _row_get(row, 1, 'name'),
                    'type': 'empresa',
                    'section': 'empresas',
                })
            try:
                cur.execute(f'SELECT id, username FROM users WHERE username LIKE {ph} LIMIT 8', (like,))
            except Exception:
                cur.execute('SELECT id, username FROM users WHERE username LIKE ? LIMIT 8', (like,))
            for row in cur.fetchall():
                uid = _row_get(row, 0, 'id')
                uname = _row_get(row, 1, 'username')
                results.append({
                    'label': uname,
                    'type': 'usuario',
                    'section': 'poder',
                    'user_id': uid,
                })
    except Exception:
        pass
    ql = q.lower()
    for ex in (
        {'label': 'Poder Imperial · God Mode', 'type': 'acción', 'section': 'poder'},
        {'label': 'Dashboard KPIs', 'type': 'acción', 'section': 'dashboard'},
        {'label': 'Audit log staff', 'type': 'acción', 'section': 'audit'},
    ):
        if ql in ex['label'].lower():
            results.append(ex)
    return jsonify({'results': results[:12]})

@app.route('/api/public/stats', methods=['GET'])
@app.route('/api/public_stats', methods=['GET'])
def api_public_stats():
    """Stats pÃºblicas agregadas para el live counter del index. NUNCA devuelve
    datos privados (no nombres de jugadores, empresas, etc.) â€” solo totales
    para el efecto 'Argus estÃ¡ vivo'.

    Visual #39 â€” alimenta el live counter del index. Cacheado en memoria 30s
    para no martillar la DB con cada visita.
    """
    global _public_stats_cache, _public_stats_cache_at
    now = _time_mod.time()
    try:
        cached = _public_stats_cache
        cached_at = _public_stats_cache_at
    except NameError:
        cached = None
        cached_at = 0
    if cached and (now - cached_at) < 30:
        return jsonify(cached)
    out = {
        'scans_total':     0,
        'scans_24h':       0,
        'verdicts_total':  0,
        'companies_total': 0,
        'generated_at':    int(now),
    }
    try:
        conn = get_db_connection()
        cur  = conn.cursor()
        # Totals defensivos: cualquier fallo individual no derriba el endpoint
        try:
            cur.execute('SELECT COUNT(*) FROM scans')
            row = cur.fetchone()
            out['scans_total'] = int(_first_value(row) or 0)
        except Exception:
            pass
        try:
            # H-003: schema actual usa started_at + companies; evitamos tablas legacy.
            try:
                cur.execute("SELECT COUNT(*) FROM scans WHERE started_at > NOW() - INTERVAL '24 hours'")
            except Exception:
                cur.execute("SELECT COUNT(*) FROM scans WHERE started_at > datetime('now', '-24 hours')")
            row = cur.fetchone()
            out['scans_24h'] = int(_first_value(row) or 0)
        except Exception:
            pass
        try:
            cur.execute("SELECT COUNT(*) FROM scans WHERE verdict IS NOT NULL AND verdict != ''")
            row = cur.fetchone()
            out['verdicts_total'] = int(_first_value(row) or 0)
        except Exception:
            pass
        try:
            cur.execute('SELECT COUNT(*) FROM companies')
            row = cur.fetchone()
            out['companies_total'] = int(_first_value(row) or 0)
        except Exception:
            pass
    except Exception:
        pass  # fallback con todos en 0 si no hay DB
    _public_stats_cache    = out
    _public_stats_cache_at = now
    resp = jsonify(out)
    resp.headers['Cache-Control'] = 'public, max-age=30'
    return resp


def _first_value(row):
    """Devuelve el primer valor de un row de cursor sin importar si es
    RealDictCursor (dict) o cursor estÃ¡ndar (tuple)."""
    if row is None:
        return None
    if isinstance(row, dict):
        for v in row.values():
            return v
        return None
    try:
        return row[0]
    except Exception:
        return None


_public_stats_cache    = None
_public_stats_cache_at = 0


@app.route('/diagnostico-login')
def diagnostico_login():
    """PÃ¡gina de diagnÃ³stico para problemas de login"""
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
    """PÃ¡gina de login"""
    if request.method == 'POST':
        data = request.form
        username = data.get('username', '').strip()
        password = data.get('password', '')
        login_type = data.get('login_type', 'individual')
        company_name = data.get('company_name', '').strip()
        
        # ValidaciÃ³n bÃ¡sica
        if not username or not password:
            error_msg = 'Usuario y contraseÃ±a son requeridos'
            if request.is_json:
                return jsonify({'success': False, 'error': error_msg}), 400
            return render_template('login.html', error=error_msg)
        
        try:
            result = authenticate_user(username, password)
        except Exception as e:
            print(f"âŒ Error en authenticate_user: {e}")
            error_msg = 'Error interno al conectar con la base de datos. Intenta de nuevo.'
            if request.is_json:
                return jsonify({'success': False, 'error': error_msg}), 500
            return render_template('login.html', error=error_msg)

        if result['success']:
            user = result['user']
            
            # ValidaciÃ³n de tipo de login (omitida en dev local: misma cuenta en ambas pestañas)
            if not (_is_local_dev() and not IS_RENDER) and login_type == 'empresa':
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
            
            elif not (_is_local_dev() and not IS_RENDER) and login_type == 'individual':
                # Si es login individual, verificar que NO tenga empresa
                if user.get('company_id'):
                    error_msg = 'Este usuario pertenece a una empresa. Use el login empresarial.'
                    if request.is_json:
                        return jsonify({'success': False, 'error': error_msg}), 403
                    return render_template('login.html', error=error_msg)
            
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['roles'] = user['roles']  # MÃºltiples roles
            session['company_id'] = user.get('company_id')
            
            if request.is_json:
                return jsonify({'success': True, 'user': user})
            
            return redirect(url_for('panel'))
        else:
            if request.is_json:
                return jsonify({'success': False, 'error': result['error']}), 401
            
            return render_template('login.html', error=result['error'])
    
    # Si ya estÃ¡ logueado, redirigir al panel
    if 'user_id' in session:
        return redirect(url_for('panel'))
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """PÃ¡gina de registro con token"""
    if request.method == 'POST':
        if _sa_imperial_flags().get('registrations_frozen'):
            return render_template('register.html', error='Registros temporalmente congelados.')
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
        
        # Determinar roles segÃºn el tipo de token
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
    """Cerrar sesiÃ³n"""
    return _build_logout_response(redirect(url_for('index')))


def _build_logout_response(resp):
    """Invalida sesión actual y borra cookie de sesión del navegador."""
    session.clear()
    session.modified = True
    resp.delete_cookie(
        app.config.get('SESSION_COOKIE_NAME', 'session'),
        path=app.config.get('SESSION_COOKIE_PATH', '/'),
        domain=app.config.get('SESSION_COOKIE_DOMAIN'),
    )
    # Evita cachear páginas autenticadas al cerrar sesión.
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return resp

def _is_panel_owner(user):
    """Owner del panel: única cuenta que ve ADMIN en el sidebar (configurable por env)."""
    if not user:
        return False
    uname = (user.get('username') or '').strip().lower()
    raw = (os.environ.get('ARGUS_PANEL_OWNER_USERNAMES') or 'arefy_admin,arefy').strip().lower()
    allowed = {p.strip() for p in raw.split(',') if p.strip()}
    if uname in allowed:
        return True
    sa = (os.environ.get('SUPER_ADMIN_USER') or '').strip().lower()
    return bool(sa) and uname == sa


@app.route('/panel')
@login_required
def panel():
    """Panel del staff - Requiere autenticaciÃ³n"""
    user = get_user_by_id(session.get('user_id'))
    # Asegurar que user tiene roles como lista para el template
    if user and isinstance(user.get('roles'), str):
        import json
        try:
            user['roles'] = json.loads(user['roles'])
        except:
            user['roles'] = [user.get('roles', 'user')]
    staff_role = get_staff_role(user) if user else 'helper'
    is_panel_owner = _is_panel_owner(user)
    return render_template(
        'panel.html',
        user=user,
        staff_role=staff_role,
        scanner_version=_ARGUS_VERSION,
        is_panel_owner=is_panel_owner,
    )


# ============================================================================
#  ARGUS WAR ROOM  ·  Centro de mando en tiempo real
#  Vista nueva que reusa la auth de staff, el Socket.IO existente y la tabla
#  scans. NO toca nada del panel actual. Es la "cara" de la plataforma sobre la
#  que despues se enchufan los modulos Vision / Replay / Network.
# ============================================================================

@app.route('/warroom')
@login_required
def warroom():
    """Centro de mando en tiempo real del staff."""
    user = get_user_by_id(session.get('user_id'))
    if user and isinstance(user.get('roles'), str):
        try:
            user['roles'] = json.loads(user['roles'])
        except Exception:
            user['roles'] = [user.get('roles', 'user')]
    staff_role = get_staff_role(user) if user else 'helper'
    return render_template(
        'warroom.html',
        user=user,
        staff_role=staff_role,
        scanner_version=_ARGUS_VERSION,
    )


def _warroom_scope(user):
    """Devuelve (where_extra, params) para limitar scans a la empresa del staff.
    Superadmin global ve todo; el resto solo su empresa."""
    try:
        if user and is_super_admin(user):
            return '', []
    except Exception:
        pass
    cid = int(session.get('company_id') or 0)
    if cid > 0:
        return f' AND s.company_id = {_PH}', [cid]
    return '', []


def _wr_parse_dt(val):
    """Parsea started_at/completed_at sea datetime o string en algo comparable."""
    if val is None:
        return None
    if isinstance(val, datetime.datetime):
        return val
    s = str(val).strip().replace('T', ' ').replace('Z', '')
    if not s:
        return None
    for fmt in ('%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d'):
        try:
            return datetime.datetime.strptime(s[:26], fmt)
        except Exception:
            continue
    return None


def _warroom_collect(user):
    """Lee scans recientes (scoped por empresa) y arma todos los agregados que
    consume el War Room. Aggrega en Python para ser agnostico de BD."""
    where_extra, params = _warroom_scope(user)
    rows = []
    try:
        with get_api_db_cursor() as cur:
            cur.execute(
                f"SELECT s.id, s.machine_name, s.minecraft_username, s.started_at, "
                f"s.completed_at, s.status, s.risk_score, s.verdict, s.country, "
                f"s.ip_address "
                f"FROM scans s WHERE s.deleted_at IS NULL{where_extra} "
                f"ORDER BY s.started_at DESC LIMIT 1500",
                tuple(params)
            )
            rows = cur.fetchall() or []
    except Exception as e:
        print(f"[warroom] query error: {e}")
        rows = []

    now = datetime.datetime.now()
    today = now.date()
    hour_buckets = [0] * 24             # ultimas 24h (indice 0 = hace 23h ... 23 = esta hora)
    top_countries = {}
    verdicts = {'clean': 0, 'suspicious': 0, 'hack': 0, 'pending': 0}
    map_points = {}                     # country -> {count, hits, last_risk}
    active, recent = [], []
    today_total = 0
    today_detections = 0
    risk_sum = 0
    risk_n = 0

    for r in rows:
        sid = _row_get(r, 0, 'id')
        machine = _row_get(r, 1, 'machine_name') or ''
        mc = _row_get(r, 2, 'minecraft_username') or ''
        started = _wr_parse_dt(_row_get(r, 3, 'started_at'))
        completed = _wr_parse_dt(_row_get(r, 4, 'completed_at'))
        status = str(_row_get(r, 5, 'status') or '').lower()
        risk = int(_row_get(r, 6, 'risk_score') or 0)
        verdict = str(_row_get(r, 7, 'verdict') or '').lower()
        country = (str(_row_get(r, 8, 'country') or '').strip() or 'Desconocido')
        who = mc or machine or 'PC sin nombre'

        is_hack = (verdict == 'hack') or (risk >= 70)
        is_susp = (not is_hack) and (verdict == 'suspicious' or risk >= 30)

        # Verdict distribution
        if verdict in ('clean', 'suspicious', 'hack'):
            verdicts[verdict] += 1
        elif is_hack:
            verdicts['hack'] += 1
        elif is_susp:
            verdicts['suspicious'] += 1
        else:
            verdicts['pending'] += 1

        # Map + countries
        mp = map_points.setdefault(country, {'count': 0, 'hits': 0, 'max_risk': 0})
        mp['count'] += 1
        mp['max_risk'] = max(mp['max_risk'], risk)
        if is_hack:
            mp['hits'] += 1
        top_countries[country] = top_countries.get(country, 0) + 1

        # Today + 24h buckets
        if started:
            if started.date() == today:
                today_total += 1
                if is_hack:
                    today_detections += 1
                risk_sum += risk
                risk_n += 1
            delta_h = (now - started).total_seconds() / 3600.0
            if 0 <= delta_h < 24:
                hour_buckets[23 - int(delta_h)] += 1

        # Active (running, sin completar, iniciado hace < 30 min)
        is_running = (status in ('running', 'in_progress', 'scanning')) or (completed is None and status not in ('completed', 'done', 'finished'))
        if is_running and started and (now - started).total_seconds() < 1800:
            active.append({
                'scan_id': sid, 'who': who, 'country': country,
                'started_at': started.isoformat(), 'risk': risk,
            })

        if len(recent) < 24:
            recent.append({
                'scan_id': sid, 'who': who, 'country': country,
                'started_at': started.isoformat() if started else '',
                'risk': risk, 'verdict': verdict or ('hack' if is_hack else ('suspicious' if is_susp else 'pending')),
            })

    top_sorted = sorted(top_countries.items(), key=lambda kv: kv[1], reverse=True)[:8]
    map_list = [{'country': k, **v} for k, v in sorted(map_points.items(), key=lambda kv: kv[1]['count'], reverse=True)[:60]]

    return {
        'kpis': {
            'today_total': today_total,
            'today_detections': today_detections,
            'active_count': len(active),
            'avg_risk': round(risk_sum / risk_n) if risk_n else 0,
            'total_window': len(rows),
        },
        'active': active[:30],
        'recent': recent,
        'hours_24': hour_buckets,
        'top_countries': [{'country': c, 'count': n} for c, n in top_sorted],
        'verdicts': verdicts,
        'map_points': map_list,
        'server_time': now.isoformat(),
    }


@app.route('/api/warroom/overview', methods=['GET'])
@login_required
def warroom_overview():
    user = get_user_by_id(session.get('user_id'))
    try:
        return jsonify({'success': True, **_warroom_collect(user)}), 200
    except Exception as e:
        print(f"[warroom] overview error: {e}\n{traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500


_WARROOM_MODULES = {
    'vision': {
        'icon': '👁️', 'name': 'Argus Vision',
        'tagline': 'IA / visión por computadora aplicada al anti-cheat',
        'desc': 'Analiza capturas y la pantalla del sospechoso durante el SS y detecta '
                'visualmente clientes de cheats, overlays y procesos sospechosos. El moat: '
                'difícil de copiar, dominio nuevo, ayuda directa al staff.',
        'features': ['Detección visual de clientes de cheats', 'Clasificación de overlays sospechosos',
                     'OCR de ventanas y procesos', 'Resaltado automático de hallazgos'],
    },
    'replay': {
        'icon': '🎯', 'name': 'Argus Replay',
        'tagline': 'Repetición forense + ML de comportamiento',
        'desc': 'Graba la sesión del sospechoso y la reproduce con timeline: heatmap de mouse, '
                'tiempos de reacción y anomalías de aim detectadas por modelos de comportamiento. '
                'Pruebas claras para que el staff decida con evidencia.',
        'features': ['Timeline de la sesión', 'Heatmap de movimiento de mouse',
                     'Análisis de tiempos de reacción', 'Detección de anomalías de aim'],
    },
    'network': {
        'icon': '🌐', 'name': 'Argus Network',
        'tagline': 'Red de reputación compartida entre servidores',
        'desc': 'Base de datos colaborativa de tramposos entre servidores con un explorador tipo '
                'grafo. Efecto red: cuantos más servidores aportan, más fuerte protege a todos.',
        'features': ['Reputación compartida entre servers', 'Explorador de grafo de relaciones',
                     'Alertas de reincidentes', 'API para integrar otros servidores'],
    },
}


@app.route('/warroom/<module>')
@login_required
def warroom_module(module):
    """Placeholder de los próximos módulos de la plataforma (Vision/Replay/Network)."""
    mod = _WARROOM_MODULES.get(str(module).lower())
    if not mod:
        return redirect('/warroom')
    return render_template('warroom_soon.html', mod=mod, module=module)


@app.route('/api/warroom/summary', methods=['GET'])
@login_required
def warroom_summary():
    """Resumen del dia en lenguaje natural. Usa la IA si esta disponible, con
    fallback a un resumen templado a partir de las metricas."""
    user = get_user_by_id(session.get('user_id'))
    try:
        data = _warroom_collect(user)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

    k = data['kpis']
    top = data['top_countries']
    peak_h = max(range(24), key=lambda i: data['hours_24'][i]) if any(data['hours_24']) else None
    top_txt = top[0]['country'] if top else 'sin datos'
    peak_txt = f"hace {23 - peak_h}h aprox." if peak_h is not None else 's/d'

    fallback = (
        f"Hoy se realizaron {k['today_total']} SS, con {k['today_detections']} "
        f"detecciones de riesgo alto. Riesgo promedio del dia: {k['avg_risk']}/100. "
        f"Pais mas activo: {top_txt}. Pico de actividad: {peak_txt}. "
        f"Scans activos ahora mismo: {k['active_count']}."
    )

    summary = fallback
    try:
        import argus_ai_assistant as A
        prompt = (
            "Resume en 2-3 frases, tono profesional y claro, el estado de hoy de un "
            "centro de anti-cheat de Minecraft con estos datos: "
            f"SS hoy={k['today_total']}, detecciones={k['today_detections']}, "
            f"riesgo_promedio={k['avg_risk']}/100, activos_ahora={k['active_count']}, "
            f"pais_top={top_txt}. Da una conclusion accionable al final."
        )
        out = A.generate_response(prompt, None, None, None)
        ans = (out or {}).get('answer')
        if ans and len(ans.strip()) > 10:
            summary = ans.strip()
    except Exception:
        pass

    return jsonify({'success': True, 'summary': summary, 'kpis': k}), 200


@app.route('/aspers-sa', methods=['GET', 'POST'])
def admin_subscriptions():
    """Panel SuperAdmin â€” acceso solo mediante URL directa (no linkada pÃºblicamente).

    Credenciales: env vars SUPER_ADMIN_USER / SUPER_ADMIN_PASS.
    Si faltan, la vista falla en modo seguro.
    """
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        expected_user = (os.environ.get('SUPER_ADMIN_USER') or '').strip()
        expected_pass = (os.environ.get('SUPER_ADMIN_PASS') or '').strip()
        if not expected_user or not expected_pass:
            app.logger.error('[security] SUPER_ADMIN_* no configuradas en entorno')
            return render_template('admin_subscriptions_login.html', error='SuperAdmin no configurado en entorno')
        if username == expected_user and password == expected_pass:
            session['admin_subscriptions'] = True
            session['admin_subscriptions_login_at'] = datetime.datetime.now().isoformat()
            return redirect('/aspers-sa')
        else:
            return render_template('admin_subscriptions_login.html', error='Credenciales incorrectas')

    if not session.get('admin_subscriptions'):
        return render_template('admin_subscriptions_login.html')

    try:
        # SPA Imperial carga empresas/usuarios vía API — evitar listar toda la BD en el HTML inicial.
        return render_template('admin_subscriptions.html',
                               companies=[],
                               individual_users=[],
                               company_users=[])
    except Exception as _e:
        import traceback as _tb
        _err = _tb.format_exc()
        print(f"âŒ Error en /aspers-sa: {_e}\n{_err}")
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

# La BD del scanner estÃ¡ INTEGRADA en la misma BD que auth (un Ãºnico archivo/servicio)
API_DB_AVAILABLE_LOCALLY = True

@contextmanager
def get_api_db_cursor():
    """Cursor para tablas del scanner â€” usa la misma BD que auth (SQLite o PostgreSQL/MySQL)"""
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

# CachÃ© simple en memoria para estadÃ­sticas
_stats_cache = {}
_stats_cache_time = {}

@app.route('/api/statistics', methods=['GET'])
@login_required
def get_statistics():
    """Obtiene estadÃ­sticas - OPTIMIZADO: Acceso directo a BD sin HTTP"""
    import time
    
    # Verificar cachÃ© (30 segundos TTL)
    cache_key = 'statistics'
    if cache_key in _stats_cache:
        if time.time() - _stats_cache_time.get(cache_key, 0) < 30:
            return jsonify(_stats_cache[cache_key]), 200
    
    try:
        # Acceso directo a la base de datos (SIN HTTP - MUCHO MÃS RÃPIDO)
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
            
            # Guardar en cachÃ©
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
    """EstadÃ­sticas extendidas para el dashboard: veredictos, top hacks, tiempo promedio."""
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
    """MÃ¡quinas con mÃºltiples veredictos 'hack' en los Ãºltimos N dÃ­as.
    Ãštil para identificar jugadores reincidentes."""
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
    """Top issue_types por frecuencia y hack_rate. Ãštil para entender
    quÃ© tipos de hacks estÃ¡n circulando en el servidor."""
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
# API DE AUTENTICACIÃ“N
# ============================================================

@app.route('/api/auth/login', methods=['POST'])
@_limit("5 per minute", key_func=lambda: f"ip:{request.remote_addr or 'unknown'}")
@audit_action('auth.login', 'user')
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
@audit_action('auth.logout', 'user')
def api_logout():
    """API endpoint para logout"""
    return _build_logout_response(jsonify({'success': True}))

@app.route('/api/auth/me', methods=['GET'])
@login_required
def api_me():
    """Obtiene informaciÃ³n del usuario actual"""
    user = get_user_by_id(session.get('user_id'))
    if user:
        return jsonify({'success': True, 'user': user})
    return jsonify({'success': False, 'error': 'Usuario no encontrado'}), 404

@app.route('/api/auth/register', methods=['POST'])
@_limit("3 per hour", key_func=lambda: f"ip:{request.remote_addr or 'unknown'}")
@audit_action('auth.register', 'user')
def api_register():
    """API endpoint para registro"""
    _flags = _sa_imperial_flags()
    if _flags.get('registrations_frozen'):
        return jsonify({'success': False, 'error': 'Registros temporalmente congelados por el administrador.'}), 503
    data = request.json or {}
    token = data.get('token', '')
    username = data.get('username', '')
    password = data.get('password', '')
    email = data.get('email', '')
    
    # Verificar token
    token_result = verify_registration_token(token)
    if not token_result['success']:
        return jsonify({'success': False, 'error': token_result['error']}), 400
    
    # Determinar roles segÃºn el tipo de token
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
        try:
            dispatch_webhook('user.created', {
                'username': username,
                'email': email,
                'company_id': company_id,
                'roles': roles,
            }, company_id=int(company_id or 0) or None)
        except Exception:
            pass
        return jsonify({'success': True, 'message': 'Usuario creado exitosamente'})
    else:
        return jsonify({'success': False, 'error': user_result['error']}), 400

# ============================================================
# API DE ADMINISTRACIÃ“N (Solo para admins)
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
@audit_action('admin.registration_token.create', 'registration_token')
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
# API DE GESTIÃ“N DE EMPRESAS
# ============================================================

@app.route('/api/servers', methods=['GET'])
@login_required
def list_servers():
    """P5 #29 â€” Lista servidores a los que el usuario tiene acceso.
    Admin ve todos; empresa-admin ve solo el suyo.
    Un 'servidor' corresponde a una company en la BD.
    """
    user = get_user_by_id(session.get('user_id'))
    is_admin = user and 'admin' in (user.get('roles') or [])
    try:
        if is_admin:
            companies = list_companies() or []
        else:
            cid = user.get('company_id') if user else None
            companies = [get_company_by_id(cid)] if cid else []
        servers = [
            {'id': c.get('id') or c.get('company_id'),
             'name': c.get('name') or c.get('company_name', 'Servidor')}
            for c in companies if c
        ]
        active_id = session.get('active_server_id')
        return jsonify({'servers': servers, 'active_server_id': active_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/servers/select', methods=['POST'])
@login_required
def select_server():
    """P5 #29 â€” Selecciona el servidor activo para filtrar vistas del panel."""
    data = request.json or {}
    server_id = data.get('server_id')
    user = get_user_by_id(session.get('user_id'))
    is_admin = user and 'admin' in (user.get('roles') or [])
    if server_id and not is_admin:
        if str(user.get('company_id', '')) != str(server_id):
            return jsonify({'error': 'Sin acceso a ese servidor'}), 403
    session['active_server_id'] = server_id
    session.modified = True
    return jsonify({'ok': True, 'active_server_id': server_id})


@app.route('/api/admin/companies', methods=['GET'])
@admin_required
def api_list_companies():
    """Lista todas las empresas (solo super admin)"""
    companies = list_companies()
    return jsonify({'success': True, 'companies': companies})

@app.route('/api/admin/companies', methods=['POST'])
@admin_required
@audit_action('company.create', 'company')
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
    """Obtiene informaciÃ³n de una empresa"""
    company = get_company_by_id(company_id)
    if company:
        return jsonify({'success': True, 'company': company})
    return jsonify({'success': False, 'error': 'Empresa no encontrada'}), 404

@app.route('/api/admin/companies/<int:company_id>', methods=['PUT'])
@admin_required
@audit_action('company.update', 'company')
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
@audit_action('company.registration_token.create', 'registration_token')
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
@audit_action('user.deactivate', 'user')
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
    
    # No permitir desactivarse a sÃ­ mismo
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
@audit_action('user.activate', 'user')
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
@audit_action('user.soft_delete', 'user')
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
    
    # No permitir eliminarse a sÃ­ mismo
    if user_id == user['id']:
        return jsonify({'success': False, 'error': 'No puedes eliminar tu propia cuenta'}), 400
    
    try:
        with get_api_db_cursor() as cursor:
            cursor.execute(f'UPDATE users SET deleted_at = CURRENT_TIMESTAMP WHERE id = {_PH}', (user_id,))
        return jsonify({'success': True, 'message': 'Usuario marcado como eliminado'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/company/info', methods=['GET'])
@company_user_required
def api_get_company_info():
    """Obtiene informaciÃ³n de la empresa del usuario"""
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
        
        # Intentar acceso directo a BD si estÃ¡ disponible localmente
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
        
        # Si no estÃ¡ disponible localmente, usar HTTP
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
# API DE ADMINISTRACIÃ“N DE SUSCRIPCIONES (PÃ¡gina Secreta)
# ============================================================

def admin_subscriptions_required(f):
    """Decorador para requerir autenticaciÃ³n de admin de suscripciones"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_subscriptions'):
            return jsonify({'error': 'No autorizado'}), 401
        return f(*args, **kwargs)
    return decorated_function

@app.route('/api/admin/create-subscription', methods=['POST'])
@admin_subscriptions_required
def api_create_subscription():
    """Crea una nueva suscripciÃ³n (individual o empresarial)"""
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
                notes=f'SuscripciÃ³n creada desde panel admin. DuraciÃ³n: {duration} meses'
            )
            
            if result['success']:
                # Calcular fecha de expiraciÃ³n
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
                    'message': 'SuscripciÃ³n empresarial creada'
                })
            else:
                return jsonify({'success': False, 'error': result['error']}), 400
        
        else:  # individual
            # Crear usuario individual
            username = data.get('username')
            email = data.get('email')
            
            if not username:
                return jsonify({'success': False, 'error': 'Nombre de usuario requerido'}), 400
            
            # Generar contraseÃ±a temporal
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
                    'message': f'SuscripciÃ³n individual creada. ContraseÃ±a temporal: {temp_password}'
                })
            else:
                return jsonify({'success': False, 'error': result['error']}), 400
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/make-free', methods=['POST'])
@admin_subscriptions_required
def api_make_free():
    """Marca una suscripciÃ³n como gratuita"""
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
            # Para usuarios individuales, podrÃ­amos crear una "empresa" especial o solo marcarlos
            # Por ahora, solo confirmamos
            return jsonify({'success': True, 'message': 'Usuario individual marcado como gratuito'})
        
        return jsonify({'success': False, 'error': 'Error al actualizar'}), 400
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/update-company', methods=['POST'])
@admin_subscriptions_required
def api_admin_update_company():
    """Actualiza una empresa desde el panel de administraciÃ³n secreto"""
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
    """Actualiza suscripciÃ³n de empresa (precio, estado, extensiÃ³n). Solo para admins."""
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
            return jsonify({'success': True, 'message': 'SuscripciÃ³n actualizada'})
        return jsonify({'success': False, 'error': result.get('error', 'Error')}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================
# API PROXY - Conecta con la API REST
# ============================================================

# IMPORTANTE: SeparaciÃ³n COMPLETA de tokens
# 
# TOKENS DE ESCANEO (para la aplicaciÃ³n .exe SS):
# - Endpoint: /api/tokens (GET/POST/DELETE)
# - Tabla: scan_tokens (en BD de la API)
# - Permisos: CUALQUIER usuario autenticado puede crear/listar/eliminar sus propios tokens
#             Los admins pueden ver/eliminar todos los tokens
# - Uso: AutenticaciÃ³n en la aplicaciÃ³n cliente SS (.exe)
#
# TOKENS DE REGISTRO (para crear usuarios):
# - Endpoints: /api/admin/registration-tokens (solo admin)
#              /api/company/registration-tokens (admin de empresa)
# - Tabla: registration_tokens (en BD de autenticaciÃ³n)
# - Permisos: Solo admins y admins de empresa pueden crear tokens de registro
# - Uso: Registro de nuevos usuarios en el sistema web

@app.route('/api/tokens', methods=['GET'])
@login_required
def list_tokens():
    """Lista tokens de ESCANEO (para la aplicaciÃ³n SS) - Cualquier usuario autenticado puede ver sus tokens"""
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
                    ' is_active, created_by, description, short_code FROM scan_tokens'
                    ' ORDER BY created_at DESC LIMIT 100'
                )
            else:
                cursor.execute(
                    f'SELECT id, token, created_at, expires_at, used_count, max_uses,'
                    f' is_active, created_by, description, short_code FROM scan_tokens'
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
                    'short_code':  _row_get(row, 9, 'short_code') or '',
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

        # Asegurar columna short_code existe (migraciÃ³n sÃ­ncrona por si el background thread aÃºn no corriÃ³)
        try:
            with get_api_db_cursor() as cursor:
                cursor.execute("ALTER TABLE scan_tokens ADD COLUMN IF NOT EXISTS short_code VARCHAR(8)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_st_short_code ON scan_tokens(short_code)")
        except Exception:
            pass

        # Token: 1 uso, 30 minutos. Short code: 6 chars A-Z2-9 (sin O/0/I/1/L)
        _CODE_CHARS = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'
        scan_token = secrets.token_urlsafe(32)
        expires_at = (datetime.datetime.now() + datetime.timedelta(minutes=30)).isoformat()
        max_uses = 1

        # Generar cÃ³digo Ãºnico de 6 caracteres
        for _ in range(20):
            short_code = ''.join(secrets.choice(_CODE_CHARS) for _ in range(6))
            try:
                with get_api_db_cursor() as cursor:
                    cursor.execute(f'SELECT 1 FROM scan_tokens WHERE short_code = {_PH}', (short_code,))
                    if not cursor.fetchone():
                        break
            except Exception:
                break

        with get_api_db_cursor() as cursor:
            token_id = _insert_id(
                cursor,
                f'INSERT INTO scan_tokens (token, expires_at, max_uses, created_by, short_code)'
                f' VALUES ({_PH},{_PH},{_PH},{_PH},{_PH})',
                (scan_token, expires_at, max_uses, created_by, short_code)
            )

        base_url = os.environ.get('RENDER_EXTERNAL_URL', request.host_url).rstrip('/')
        return jsonify({
            'success': True,
            'token': scan_token,
            'short_code': short_code,
            'token_id': token_id,
            'expires_at': expires_at,
            'max_uses': max_uses,
            'created_by': created_by,
            'type': 'scan_token',
            'download_url': f"{base_url}/descargar/exe",
        }), 201

    except Exception as e:
        print(f"ERROR create_token: {type(e).__name__}: {e}")
        print(traceback.format_exc())
        return jsonify({'success': False, 'error': f'Error al crear token: {str(e)}'}), 500


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#  PLUGIN KEYS â€” sistema multi-tenant para servidores Minecraft
#  -----------------------------------------------------------------
#  Cada empresa puede emitir N "plugin keys" (una por servidor MC). El plugin
#  Java que va dentro del server las usa para llamar a /api/plugin/issue-token
#  cuando el staff ejecuta /ss <player>. El backend genera un token de scan
#  marcado con `minecraft_staff` (quien ejecuto /ss) y `plugin_key_id` para
#  trackeo, y lo devuelve al plugin.
#
#  Compatibilidad: NO toca scan_tokens existentes; solo agrega columnas
#  nullable mediante ALTER TABLE IF NOT EXISTS.
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

_PLUGIN_SCHEMA_READY = False
_PLUGIN_SCHEMA_LOCK = threading.Lock() if 'threading' in globals() else None
_SOFT_DELETE_READY = False


def _column_exists(cursor, table, column):
    """Devuelve True si la columna existe. Usa information_schema (solo AccessShareLock)."""
    try:
        cursor.execute(
            f"SELECT 1 FROM information_schema.columns "
            f"WHERE table_name = {_PH} AND column_name = {_PH}",
            (table, column))
        return cursor.fetchone() is not None
    except Exception:
        return False


def _ensure_plugin_keys_schema():
    """Crea/migra las tablas para el sistema de plugin keys.

    IMPORTANTE: el problema previo era que ALTER TABLE ADD COLUMN IF NOT EXISTS
    en PostgreSQL toma AccessExclusiveLock sobre scan_tokens incluso cuando la
    columna ya existe (es no-op pero el lock se sigue tomando). Eso causaba
    DEADLOCK con SELECTs concurrentes que hacen LEFT JOIN scan_tokens (necesitan
    AccessShareLock) â€” caso tipico: get_scan() en /api/scans/<id>.

    Solucion: chequear primero con information_schema (solo share lock) y
    ejecutar el ALTER unicamente si la columna realmente NO existe."""
    import threading as _t
    global _PLUGIN_SCHEMA_LOCK
    if _PLUGIN_SCHEMA_LOCK is None:
        _PLUGIN_SCHEMA_LOCK = _t.Lock()
    with _PLUGIN_SCHEMA_LOCK:
        try:
            with get_api_db_cursor() as cursor:
                # Tabla nueva â€” CREATE IF NOT EXISTS no toma locks fuertes
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS company_plugin_keys (
                        id SERIAL PRIMARY KEY,
                        company_id INTEGER NOT NULL,
                        api_key VARCHAR(96) UNIQUE NOT NULL,
                        label VARCHAR(160),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        created_by VARCHAR(255),
                        last_used_at TIMESTAMP,
                        last_used_ip VARCHAR(64),
                        is_active BOOLEAN DEFAULT TRUE,
                        daily_quota INTEGER DEFAULT 200,
                        used_today INTEGER DEFAULT 0,
                        quota_reset_at DATE
                    )
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_cpk_api_key ON company_plugin_keys(api_key)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_cpk_company ON company_plugin_keys(company_id)")

                # Tabla de violations del anti-cheat (Pack 43).
                # Cada fila es una deteccion individual hecha por el plugin Bukkit.
                # Se crea via POST /api/plugin/violation y se consume desde el
                # panel staff (pestana Anti-Cheat) y opcionalmente Discord.
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS plugin_violations (
                        id SERIAL PRIMARY KEY,
                        plugin_key_id INTEGER,
                        company_id INTEGER,
                        player_uuid VARCHAR(40),
                        player_name VARCHAR(64),
                        check_name VARCHAR(64),
                        level VARCHAR(16),
                        details VARCHAR(500),
                        server_label VARCHAR(160),
                        related_token_id INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_pv_company ON plugin_violations(company_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_pv_player ON plugin_violations(player_name)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_pv_check ON plugin_violations(check_name)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_pv_level ON plugin_violations(level)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_pv_created ON plugin_violations(created_at DESC)")

                # â”€â”€â”€ Pack 44: Argus AI Oracle â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
                # Estado vigente por jugador. Una sola fila por (company_id, player_uuid).
                # last_action: none | watch | ss_issued | kicked | banned
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS ai_player_scores (
                        id SERIAL PRIMARY KEY,
                        company_id INTEGER NOT NULL,
                        player_uuid VARCHAR(40) NOT NULL,
                        player_name VARCHAR(64),
                        score REAL DEFAULT 0,
                        confidence REAL DEFAULT 0,
                        last_action VARCHAR(32) DEFAULT 'none',
                        last_reasoning TEXT,
                        last_evidence_json TEXT,
                        evaluations_count INTEGER DEFAULT 0,
                        first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_evaluated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_aps_unique ON ai_player_scores(company_id, player_uuid)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_aps_score ON ai_player_scores(company_id, score DESC)")

                # Log inmutable de cada decision tomada por la IA. Sirve para
                # auditoria, apelaciones y entrenamiento futuro de un modelo ML.
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS ai_decisions_log (
                        id SERIAL PRIMARY KEY,
                        company_id INTEGER,
                        plugin_key_id INTEGER,
                        player_uuid VARCHAR(40),
                        player_name VARCHAR(64),
                        score REAL,
                        confidence REAL,
                        action VARCHAR(32),
                        reasoning TEXT,
                        evidence_json TEXT,
                        triggered_by VARCHAR(40),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_adl_company ON ai_decisions_log(company_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_adl_player ON ai_decisions_log(player_name)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_adl_action ON ai_decisions_log(action)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_adl_created ON ai_decisions_log(created_at DESC)")

                # Pesos del modelo. Una sola fila por company_id (0 = pesos
                # globales â€” no usamos NULL para que UNIQUE funcione en ambos
                # dialectos sin necesidad de indices funcionales).
                # Se actualizan desde el panel super-admin sin redeploy.
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS ai_weights (
                        id SERIAL PRIMARY KEY,
                        company_id INTEGER NOT NULL DEFAULT 0,
                        weights_json TEXT NOT NULL,
                        updated_by VARCHAR(255),
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        CONSTRAINT uq_aw_company UNIQUE (company_id)
                    )
                """)

                # ──── Pack 45: ML hybrid (LogReg + KNN + Temporal + auto-labeling) ────
                # Feedback explicito del staff sobre decisiones del AI.
                # label: 0.0 = limpio, 1.0 = cheater confirmado, 0.5 = incierto.
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS ai_feedback (
                        id SERIAL PRIMARY KEY,
                        company_id INTEGER NOT NULL,
                        decision_id INTEGER,
                        player_uuid VARCHAR(40),
                        player_name VARCHAR(64),
                        label REAL NOT NULL,
                        confidence REAL DEFAULT 1.0,
                        source VARCHAR(40) DEFAULT 'staff',
                        staff_username VARCHAR(255),
                        reasoning TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_af_company ON ai_feedback(company_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_af_decision ON ai_feedback(decision_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_af_player ON ai_feedback(player_uuid)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_af_created ON ai_feedback(created_at DESC)")

                # Auto-labels generados por los 12 pipelines. source identifica
                # cual pipeline lo produjo. Una misma decision puede tener varios.
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS ai_auto_labels (
                        id SERIAL PRIMARY KEY,
                        company_id INTEGER NOT NULL,
                        decision_id INTEGER,
                        player_uuid VARCHAR(40),
                        player_name VARCHAR(64),
                        label REAL NOT NULL,
                        confidence REAL NOT NULL,
                        source VARCHAR(40) NOT NULL,
                        reasoning TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_aal_company ON ai_auto_labels(company_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_aal_decision ON ai_auto_labels(decision_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_aal_source ON ai_auto_labels(source)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_aal_created ON ai_auto_labels(created_at DESC)")

                # Estado serializado del modelo ML.
                # model_kind: 'logreg' | 'knn' | 'temporal'
                # state_json: JSON serializado del modelo (pesos, examples, etc).
                # version se incrementa con cada training run.
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS ai_model_state (
                        id SERIAL PRIMARY KEY,
                        company_id INTEGER NOT NULL DEFAULT 0,
                        model_kind VARCHAR(32) NOT NULL,
                        state_json TEXT NOT NULL,
                        version INTEGER DEFAULT 1,
                        samples_trained INTEGER DEFAULT 0,
                        accuracy REAL DEFAULT 0,
                        precision REAL DEFAULT 0,
                        recall REAL DEFAULT 0,
                        f1 REAL DEFAULT 0,
                        last_loss REAL DEFAULT 0,
                        trained_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        CONSTRAINT uq_aims_company_kind UNIQUE (company_id, model_kind)
                    )
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_aims_company ON ai_model_state(company_id)")

                # Perfiles de jugador: vector de features, ultima actualizacion.
                # Usado por KNN para clasificar por proximidad. Se refresca
                # periodicamente desde violations + scan history.
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS ai_player_profiles (
                        id SERIAL PRIMARY KEY,
                        company_id INTEGER NOT NULL,
                        player_uuid VARCHAR(40) NOT NULL,
                        player_name VARCHAR(64),
                        feature_vector_json TEXT NOT NULL,
                        last_label REAL,
                        last_label_confidence REAL DEFAULT 0,
                        last_label_source VARCHAR(40),
                        last_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        CONSTRAINT uq_app_company_uuid UNIQUE (company_id, player_uuid)
                    )
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_app_company ON ai_player_profiles(company_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_app_updated ON ai_player_profiles(last_updated_at DESC)")

                # Log de cada training run (cron de 10 min). Auditable y
                # permite analisis de drift / mejoras.
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS ai_training_history (
                        id SERIAL PRIMARY KEY,
                        company_id INTEGER NOT NULL DEFAULT 0,
                        model_kind VARCHAR(32) NOT NULL,
                        samples_used INTEGER DEFAULT 0,
                        samples_synthetic INTEGER DEFAULT 0,
                        samples_real INTEGER DEFAULT 0,
                        epochs INTEGER DEFAULT 0,
                        loss REAL DEFAULT 0,
                        accuracy REAL DEFAULT 0,
                        precision REAL DEFAULT 0,
                        recall REAL DEFAULT 0,
                        f1 REAL DEFAULT 0,
                        duration_ms INTEGER DEFAULT 0,
                        triggered_by VARCHAR(40) DEFAULT 'cron',
                        notes TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_ath_company ON ai_training_history(company_id, created_at DESC)")

                # Notificaciones Oracle por empresa (Telegram/Discord webhook)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS company_notification_settings (
                        id SERIAL PRIMARY KEY,
                        company_id INTEGER NOT NULL,
                        type VARCHAR(16) NOT NULL,
                        webhook_url TEXT NOT NULL,
                        enabled BOOLEAN DEFAULT TRUE,
                        filter_min_level VARCHAR(16) DEFAULT 'HIGH',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_cns_company ON company_notification_settings(company_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_cns_type ON company_notification_settings(type)")
                try:
                    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_cns_company_type ON company_notification_settings(company_id, type)")
                except Exception:
                    pass

                # Preferencias de usuario (tema, etc)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS user_preferences (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        pref_key VARCHAR(64) NOT NULL,
                        pref_value TEXT,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                try:
                    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_user_pref ON user_preferences(user_id, pref_key)")
                except Exception:
                    pass
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_pref_user ON user_preferences(user_id)")

                # Game profiles por compañía + reglas context-aware (#173-176)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS game_profiles (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(80) NOT NULL,
                        slug VARCHAR(60) NOT NULL,
                        filter_rules TEXT NOT NULL,
                        default_for_company INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                try:
                    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_game_profiles_slug ON game_profiles(slug)")
                except Exception:
                    pass
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS company_game_profile (
                        company_id INTEGER PRIMARY KEY,
                        game_profile_id INTEGER NOT NULL,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Agregaciones de feedback FP (#178)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS ai_feedback_aggregations (
                        id SERIAL PRIMARY KEY,
                        agg_date DATE NOT NULL,
                        feature_name VARCHAR(80) NOT NULL,
                        false_positive_count INTEGER DEFAULT 0,
                        true_positive_count INTEGER DEFAULT 0,
                        weight_adjustment REAL DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                try:
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_afa_date ON ai_feedback_aggregations(agg_date DESC)")
                except Exception:
                    pass

                # Marketplace de reglas compartidas (#181)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS shared_filter_rules (
                        id SERIAL PRIMARY KEY,
                        source_company_id INTEGER NOT NULL,
                        name VARCHAR(120) NOT NULL,
                        description TEXT,
                        rules_json TEXT NOT NULL,
                        public BOOLEAN DEFAULT TRUE,
                        downloads_count INTEGER DEFAULT 0,
                        rating_avg REAL DEFAULT 0,
                        rating_count INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                try:
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sfr_public ON shared_filter_rules(public)")
                except Exception:
                    pass
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS company_shared_rules (
                        id SERIAL PRIMARY KEY,
                        company_id INTEGER NOT NULL,
                        shared_rule_id INTEGER NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                try:
                    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_company_shared_rules ON company_shared_rules(company_id, shared_rule_id)")
                except Exception:
                    pass

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS webhook_subscriptions (
                        id SERIAL PRIMARY KEY,
                        company_id INTEGER NOT NULL,
                        url TEXT NOT NULL,
                        secret TEXT NOT NULL,
                        events TEXT NOT NULL,
                        is_active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS webhook_deliveries (
                        id SERIAL PRIMARY KEY,
                        subscription_id INTEGER NOT NULL,
                        event_type VARCHAR(80) NOT NULL,
                        payload TEXT NOT NULL,
                        status VARCHAR(32) DEFAULT 'pending',
                        response_code INTEGER,
                        attempts INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS api_keys (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        company_id INTEGER,
                        name VARCHAR(120) NOT NULL,
                        key_hash VARCHAR(128) NOT NULL,
                        scopes TEXT NOT NULL,
                        last_used_at TIMESTAMP,
                        revoked_at TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                try:
                    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_api_keys_hash ON api_keys(key_hash)")
                except Exception:
                    pass
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS user_notification_prefs (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        channel VARCHAR(32) NOT NULL,
                        event_type VARCHAR(80) NOT NULL,
                        enabled BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                try:
                    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_unp ON user_notification_prefs(user_id, channel, event_type)")
                except Exception:
                    pass
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS invitations (
                        id SERIAL PRIMARY KEY,
                        email VARCHAR(255) NOT NULL,
                        company_id INTEGER NOT NULL,
                        role VARCHAR(64) NOT NULL,
                        token VARCHAR(128) NOT NULL,
                        expires_at TIMESTAMP NOT NULL,
                        accepted_at TIMESTAMP,
                        created_by INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS user_trust_scores (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        score REAL DEFAULT 50,
                        factors_json TEXT NOT NULL,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                try:
                    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_user_trust ON user_trust_scores(user_id)")
                except Exception:
                    pass

                # Seed profiles default
                _seed_profiles = [
                    ('Minecraft', 'minecraft', json.dumps({'whitelist_checks': ['inventory_move'], 'allow_legit_clients': True})),
                    ('Fortnite', 'fortnite', json.dumps({'whitelist_checks': [], 'allow_legit_clients': False})),
                    ('CS2', 'cs2', json.dumps({'whitelist_checks': [], 'allow_legit_clients': False})),
                    ('Valorant', 'valorant', json.dumps({'whitelist_checks': [], 'allow_legit_clients': False})),
                    ('GTA RP', 'gta_rp', json.dumps({'whitelist_checks': [], 'allow_legit_clients': False})),
                    ('Roblox', 'roblox', json.dumps({'whitelist_checks': [], 'allow_legit_clients': False})),
                ]
                for _name, _slug, _rules in _seed_profiles:
                    try:
                        cursor.execute(f"SELECT id FROM game_profiles WHERE slug = {_PH} LIMIT 1", (_slug,))
                        if not cursor.fetchone():
                            cursor.execute(
                                f"INSERT INTO game_profiles (name, slug, filter_rules) VALUES ({_PH},{_PH},{_PH})",
                                (_name, _slug, _rules)
                            )
                    except Exception:
                        pass

                # Audit log centralizado v2
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS audit_log_v2 (
                        id BIGSERIAL PRIMARY KEY,
                        timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                        user_id INTEGER,
                        session_id TEXT,
                        action TEXT NOT NULL,
                        resource_type TEXT,
                        resource_id TEXT,
                        details TEXT,
                        ip_address TEXT,
                        user_agent TEXT
                    )
                """)
                try:
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_v2_ts ON audit_log_v2(timestamp DESC)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_v2_action ON audit_log_v2(action)")
                except Exception:
                    pass

                # Columnas adicionales en scan_tokens â€” solo ALTER si no existen
                _migrations = [
                    ('plugin_key_id', "ALTER TABLE scan_tokens ADD COLUMN plugin_key_id INTEGER"),
                    ('minecraft_staff', "ALTER TABLE scan_tokens ADD COLUMN minecraft_staff VARCHAR(160)"),
                    ('minecraft_target', "ALTER TABLE scan_tokens ADD COLUMN minecraft_target VARCHAR(160)"),
                    ('source', "ALTER TABLE scan_tokens ADD COLUMN source VARCHAR(32) DEFAULT 'web'"),
                ]
                for col_name, alter_sql in _migrations:
                    if _column_exists(cursor, 'scan_tokens', col_name):
                        continue
                    # Lock timeout corto: si hay un SELECT concurrente sosteniendo
                    # share lock sobre scan_tokens, no nos quedamos esperando para
                    # siempre y evitamos meter al request en deadlock.
                    try:
                        cursor.execute("SET LOCAL lock_timeout = '3s'")
                    except Exception:
                        pass
                    try:
                        cursor.execute(alter_sql)
                    except Exception as _e_alter:
                        print(f"[plugin_keys] no se pudo agregar columna {col_name}: {_e_alter}")
        except Exception as e:
            print(f"[plugin_keys] error en _ensure_plugin_keys_schema: {e}")


def _plugin_schema_guard():
    """Verifica que el schema de plugin keys este listo.

    En produccion ya se ejecuta UNA VEZ desde init_db_async() al boot, asi que
    aqui es solo un fallback para entornos donde init_db_async no haya corrido
    o haya fallado. Es no-op si ya esta listo."""
    global _PLUGIN_SCHEMA_READY, _SOFT_DELETE_READY
    if _PLUGIN_SCHEMA_READY:
        if not _SOFT_DELETE_READY:
            _ensure_soft_delete_schema()
            _SOFT_DELETE_READY = True
        return
    _ensure_plugin_keys_schema()
    _PLUGIN_SCHEMA_READY = True
    if not _SOFT_DELETE_READY:
        _ensure_soft_delete_schema()
        _SOFT_DELETE_READY = True


def _ensure_soft_delete_schema():
    """Agrega columnas deleted_at en tablas clave (migración no destructiva)."""
    targets = ['scans', 'users', 'companies', 'ai_decisions_log', 'ban_history', 'game_profiles', 'shared_filter_rules']
    try:
        with get_api_db_cursor() as cursor:
            for table in targets:
                try:
                    if not _column_exists(cursor, table, 'deleted_at'):
                        cursor.execute(f"ALTER TABLE {table} ADD COLUMN deleted_at TIMESTAMP NULL")
                except Exception:
                    # tabla puede no existir en algunos entornos
                    pass
    except Exception as e:
        print(f"[soft_delete] schema error: {e}")


def _ensure_dual_scanner_schema():
    """Migrations no destructivas para dual-scanner."""
    try:
        with get_api_db_cursor() as cursor:
            # scans.is_baseline
            if not _column_exists(cursor, 'scans', 'is_baseline'):
                try:
                    cursor.execute("ALTER TABLE scans ADD COLUMN is_baseline BOOLEAN DEFAULT FALSE")
                except Exception as e:
                    print(f"[dual_scanner] no se pudo agregar is_baseline: {e}")
            try:
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_scans_baseline ON scans(is_baseline)")
            except Exception:
                pass

            # Programación de rescans
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scan_schedules (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    host VARCHAR(255) NOT NULL,
                    frequency_hours INTEGER NOT NULL DEFAULT 24,
                    last_run TIMESTAMP,
                    next_run TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    enabled BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            try:
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_sched_next ON scan_schedules(next_run)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_sched_user ON scan_schedules(user_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_sched_host ON scan_schedules(host)")
            except Exception:
                pass
    except Exception as e:
        print(f"[dual_scanner] schema error: {e}")


def _build_scan_diff(cursor, scan_a: int, scan_b: int) -> dict:
    def _fetch_scan(sid):
        cursor.execute(
            f"SELECT id, machine_name, minecraft_username, started_at, risk_score, verdict, issues_found, "
            f"COALESCE(is_baseline, FALSE) AS is_baseline "
            f"FROM scans WHERE id = {_PH}",
            (sid,)
        )
        r = cursor.fetchone()
        if not r:
            return None
        return {
            'id': _row_get(r, 0, 'id'),
            'machine': _row_get(r, 1, 'machine_name') or '',
            'username': _row_get(r, 2, 'minecraft_username') or '',
            'date': str(_row_get(r, 3, 'started_at') or '')[:19],
            'risk': int(_row_get(r, 4, 'risk_score') or 0),
            'verdict': _row_get(r, 5, 'verdict') or 'pending',
            'total': int(_row_get(r, 6, 'issues_found') or 0),
            'is_baseline': bool(_row_get(r, 7, 'is_baseline') or False),
        }

    def _fetch_results(sid):
        cursor.execute(
            f"SELECT issue_type, issue_name, alert_level, confidence, issue_category "
            f"FROM scan_results WHERE scan_id = {_PH}",
            (sid,)
        )
        out = {}
        for r in (cursor.fetchall() or []):
            tipo = str(_row_get(r, 0, 'issue_type') or 'unknown')
            out[tipo] = {
                'name': str(_row_get(r, 1, 'issue_name') or '')[:100],
                'alert': str(_row_get(r, 2, 'alert_level') or ''),
                'confidence': float(_row_get(r, 3, 'confidence') or 0),
                'category': str(_row_get(r, 4, 'issue_category') or 'misc'),
            }
        return out

    meta_a = _fetch_scan(scan_a)
    meta_b = _fetch_scan(scan_b)
    if not meta_a or not meta_b:
        raise ValueError('Uno o ambos scans no existen')
    res_a = _fetch_results(scan_a)
    res_b = _fetch_results(scan_b)
    types_a = set(res_a.keys())
    types_b = set(res_b.keys())
    new_in_b = sorted(types_b - types_a)
    gone_from_b = sorted(types_a - types_b)
    common = sorted(types_a & types_b)
    persistent = []
    for t in common:
        cur = dict(res_b[t])
        cur['type'] = t
        cur['conf_delta'] = round((res_b[t].get('confidence') or 0) - (res_a[t].get('confidence') or 0), 3)
        cur['changed'] = (
            (res_b[t].get('alert') != res_a[t].get('alert')) or
            abs(cur['conf_delta']) >= 0.2
        )
        persistent.append(cur)
    items_added = [{**res_b[t], 'type': t} for t in new_in_b]
    items_removed = [{**res_a[t], 'type': t} for t in gone_from_b]
    sectors = {}
    for bucket, items in (('added', items_added), ('removed', items_removed), ('changed', [p for p in persistent if p.get('changed')])):
        for it in items:
            sec = str(it.get('category') or 'misc').strip().lower()[:48]
            sectors.setdefault(sec, {'added': [], 'removed': [], 'changed': []})
            sectors[sec][bucket].append(it)
    return {
        'scan_a': meta_a,
        'scan_b': meta_b,
        'risk_delta': meta_b['risk'] - meta_a['risk'],
        'verdict_change': meta_a['verdict'] != meta_b['verdict'],
        'new_findings': items_added,
        'resolved_findings': items_removed,
        'persistent_findings': persistent,
        'summary': {
            'new_count': len(items_added),
            'resolved_count': len(items_removed),
            'persistent_count': len(persistent),
            'changed_count': len([p for p in persistent if p.get('changed')]),
        },
        'sectors': sectors,
    }


def detect_suspicious_changes(scan_diff: dict) -> bool:
    """True si hay >5 hallazgos HIGH/CRITICAL nuevos."""
    added = scan_diff.get('new_findings') or []
    count_high = 0
    for it in added:
        lvl = str(it.get('alert') or '').upper()
        if lvl in ('HIGH', 'CRITICAL', 'SOSPECHOSO', 'MUY_SOSPECHOSO'):
            count_high += 1
    return count_high > 5


def _notify_suspicious_scan_diff(cursor, company_id: int, scan_id: int, diff: dict) -> None:
    try:
        if not detect_suspicious_changes(diff):
            return
        cursor.execute(
            f"SELECT type, webhook_url, enabled FROM company_notification_settings "
            f"WHERE company_id = {_PH} AND enabled = TRUE",
            (company_id,)
        )
        rows = cursor.fetchall() or []
        if not rows:
            return
        msg = (
            f"⚠️ Dual-scan suspicious changes\n"
            f"Scan #{scan_id}: +{(diff.get('summary') or {}).get('new_count', 0)} new findings, "
            f"{(diff.get('summary') or {}).get('changed_count', 0)} changed."
        )
        for r in rows:
            d = dict(r) if not isinstance(r, dict) else r
            webhook = str(d.get('webhook_url') or '').strip()
            if not webhook:
                continue
            ntype = str(d.get('type') or '').lower()
            try:
                if ntype == 'discord':
                    requests.post(webhook, json={'content': msg}, timeout=4)
                elif ntype == 'telegram':
                    requests.post(webhook, json={'text': msg}, timeout=4)
                else:
                    requests.post(webhook, json={'message': msg}, timeout=4)
            except Exception:
                pass
        _emit_realtime_notification(company_id=company_id, payload={
            'kind': 'security_alert',
            'scan_id': scan_id,
            'message': f'Cambios sospechosos detectados en scan #{scan_id}',
        })
        dispatch_webhook('scan.suspicious', {
            'scan_id': scan_id,
            'summary': diff.get('summary') if isinstance(diff, dict) else {},
            'company_id': company_id,
        }, company_id=company_id)
    except Exception as e:
        print(f"[dual_scanner] suspicious notify error: {e}")


def _resolve_company_id_for_user(user):
    """Devuelve el company_id del usuario o None si no aplica."""
    if not user:
        return None
    return user.get('company_id') or None


@app.route('/api/admin/plugin-keys', methods=['GET'])
@login_required
def api_list_plugin_keys():
    """Lista las plugin keys del usuario.
    - Owner / Admin global: ve TODAS las keys de todas las empresas.
    - Admin de empresa:     ve solo las de su empresa.
    - Usuario normal:       no tiene acceso (403)."""
    _plugin_schema_guard()
    try:
        user = get_user_by_id(session.get('user_id'))
        if not user:
            return jsonify({'success': False, 'error': 'No autenticado'}), 401

        roles = user.get('roles') or []
        if isinstance(roles, str):
            try: roles = json.loads(roles)
            except Exception: roles = [roles]
        roles_lower = {str(r).lower() for r in roles}
        is_global_admin = bool(roles_lower & {'admin', 'owner', 'super_admin'})
        company_id = _resolve_company_id_for_user(user)

        if not is_global_admin and not (company_id and ('company_admin' in roles_lower)):
            return jsonify({'success': False, 'error': 'No tienes permisos para listar plugin keys'}), 403

        with get_api_db_cursor() as cursor:
            if is_global_admin:
                cursor.execute(
                    "SELECT id, company_id, label, created_at, created_by, last_used_at, "
                    "last_used_ip, is_active, daily_quota, used_today, "
                    "SUBSTRING(api_key, 1, 8) || '...' AS api_key_preview "
                    "FROM company_plugin_keys ORDER BY created_at DESC"
                )
            else:
                cursor.execute(
                    f"SELECT id, company_id, label, created_at, created_by, last_used_at, "
                    f"last_used_ip, is_active, daily_quota, used_today, "
                    f"SUBSTRING(api_key, 1, 8) || '...' AS api_key_preview "
                    f"FROM company_plugin_keys WHERE company_id = {_PH} ORDER BY created_at DESC",
                    (company_id,)
                )
            rows = cursor.fetchall()

        keys = []
        for r in rows:
            d = dict(r) if not isinstance(r, dict) else r
            for k, v in list(d.items()):
                if hasattr(v, 'isoformat'):
                    d[k] = v.isoformat()
            keys.append(d)
        return jsonify({'success': True, 'keys': keys}), 200
    except Exception as e:
        print(f"ERROR api_list_plugin_keys: {type(e).__name__}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/plugin-keys', methods=['POST'])
@login_required
def api_create_plugin_key():
    """Crea una nueva plugin key. Devuelve la key COMPLETA una sola vez.
    Body: {"label": "Server Hispano", "company_id": 1, "daily_quota": 300}"""
    _plugin_schema_guard()
    try:
        user = get_user_by_id(session.get('user_id'))
        if not user:
            return jsonify({'success': False, 'error': 'No autenticado'}), 401

        roles = user.get('roles') or []
        if isinstance(roles, str):
            try: roles = json.loads(roles)
            except Exception: roles = [roles]
        roles_lower = {str(r).lower() for r in roles}
        is_global_admin = bool(roles_lower & {'admin', 'owner', 'super_admin'})

        body = request.get_json(silent=True) or {}
        label = (body.get('label') or '').strip()[:160]
        daily_quota = int(body.get('daily_quota') or 200)
        target_company_id = body.get('company_id')

        if is_global_admin:
            if not target_company_id:
                return jsonify({'success': False, 'error': 'company_id requerido para admin global'}), 400
        else:
            if 'company_admin' not in roles_lower:
                return jsonify({'success': False, 'error': 'No tienes permisos para crear plugin keys'}), 403
            target_company_id = _resolve_company_id_for_user(user)
            if not target_company_id:
                return jsonify({'success': False, 'error': 'Tu cuenta no tiene empresa asignada'}), 400

        # API key: prefijo `argus_pk_` + 56 chars urlsafe (~ 42 bytes de entropia)
        api_key = 'argus_pk_' + secrets.token_urlsafe(42)
        with get_api_db_cursor() as cursor:
            new_id = _insert_id(
                cursor,
                f"INSERT INTO company_plugin_keys (company_id, api_key, label, created_by, daily_quota) "
                f"VALUES ({_PH}, {_PH}, {_PH}, {_PH}, {_PH})",
                (target_company_id, api_key, label or None, user.get('username'), daily_quota)
            )

        return jsonify({
            'success': True,
            'key_id': new_id,
            'api_key': api_key,            # FULL key â€” solo se muestra esta vez
            'label': label,
            'company_id': target_company_id,
            'daily_quota': daily_quota,
            'usage_note': 'Guarda esta API key, NO se mostrara de nuevo. Configurala en config.yml del plugin Minecraft.',
        }), 201
    except Exception as e:
        print(f"ERROR api_create_plugin_key: {type(e).__name__}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/plugin-keys/<int:key_id>', methods=['DELETE'])
@login_required
def api_delete_plugin_key(key_id):
    """Revoca permanentemente una plugin key."""
    _plugin_schema_guard()
    try:
        user = get_user_by_id(session.get('user_id'))
        if not user:
            return jsonify({'success': False, 'error': 'No autenticado'}), 401

        roles = user.get('roles') or []
        if isinstance(roles, str):
            try: roles = json.loads(roles)
            except Exception: roles = [roles]
        roles_lower = {str(r).lower() for r in roles}
        is_global_admin = bool(roles_lower & {'admin', 'owner', 'super_admin'})
        company_id = _resolve_company_id_for_user(user)

        with get_api_db_cursor() as cursor:
            cursor.execute(f"SELECT company_id FROM company_plugin_keys WHERE id = {_PH}", (key_id,))
            row = cursor.fetchone()
            if not row:
                return jsonify({'success': False, 'error': 'Key no encontrada'}), 404

            row_company = dict(row).get('company_id') if not isinstance(row, dict) else row.get('company_id')
            if not is_global_admin:
                if 'company_admin' not in roles_lower or row_company != company_id:
                    return jsonify({'success': False, 'error': 'No puedes eliminar esta key'}), 403

            cursor.execute(f"DELETE FROM company_plugin_keys WHERE id = {_PH}", (key_id,))

        return jsonify({'success': True, 'deleted': key_id}), 200
    except Exception as e:
        print(f"ERROR api_delete_plugin_key: {type(e).__name__}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/plugin/issue-token', methods=['POST'])
def api_plugin_issue_token():
    """Endpoint llamado por el plugin Minecraft cuando un staff ejecuta /ss.
    Auth: header `X-Argus-Plugin-Key`.
    Body: {"staff": "<staff_mc_name>", "target": "<player_mc_name>", "reason": "..."}.
    Genera un short_code de 6 chars, 1 uso, 30 min, marcado con minecraft_staff.

    Multi-tenant: cada empresa tiene sus keys; los tokens emitidos por una key
    quedan asociados a su empresa via `created_by` y `plugin_key_id`."""
    _plugin_schema_guard()
    try:
        api_key = (
            request.headers.get('X-Argus-Plugin-Key')
            or request.headers.get('Authorization', '').replace('Bearer ', '').strip()
        )
        if not api_key:
            return jsonify({'success': False, 'error': 'Falta header X-Argus-Plugin-Key'}), 401

        # Validar key y rate limit
        client_ip = request.headers.get('CF-Connecting-IP') or request.headers.get('X-Forwarded-For', '').split(',')[0].strip() or request.remote_addr
        with get_api_db_cursor() as cursor:
            cursor.execute(
                f"SELECT id, company_id, label, is_active, daily_quota, used_today, quota_reset_at "
                f"FROM company_plugin_keys WHERE api_key = {_PH}",
                (api_key,)
            )
            row = cursor.fetchone()
            if not row:
                return jsonify({'success': False, 'error': 'API key invalida'}), 401
            row = dict(row) if not isinstance(row, dict) else row
            if not row.get('is_active'):
                return jsonify({'success': False, 'error': 'API key revocada'}), 403

            # Reset diario de quota
            today = datetime.date.today()
            quota_reset_at = row.get('quota_reset_at')
            if quota_reset_at != today:
                cursor.execute(
                    f"UPDATE company_plugin_keys SET used_today = 0, quota_reset_at = {_PH} WHERE id = {_PH}",
                    (today, row['id'])
                )
                row['used_today'] = 0

            if (row.get('used_today') or 0) >= (row.get('daily_quota') or 200):
                return jsonify({
                    'success': False,
                    'error': 'Quota diaria excedida',
                    'daily_quota': row.get('daily_quota'),
                }), 429

        body = request.get_json(silent=True) or {}
        staff = (body.get('staff') or '').strip()[:120]
        target = (body.get('target') or '').strip()[:120]
        reason = (body.get('reason') or '').strip()[:500]
        if not staff:
            return jsonify({'success': False, 'error': 'Falta staff (nombre del staff que ejecuto /ss)'}), 400

        # Generacion del short_code (mismo charset y politica que el endpoint web)
        _CODE_CHARS = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'
        scan_token = secrets.token_urlsafe(32)
        expires_at = (datetime.datetime.now() + datetime.timedelta(minutes=30)).isoformat()
        max_uses = 1

        # short_code unico
        short_code = ''
        with get_api_db_cursor() as cursor:
            for _ in range(20):
                short_code = ''.join(secrets.choice(_CODE_CHARS) for _ in range(6))
                cursor.execute(f'SELECT 1 FROM scan_tokens WHERE short_code = {_PH}', (short_code,))
                if not cursor.fetchone():
                    break

        created_by_label = f"mc:{staff}"
        if row.get('label'):
            created_by_label += f"@{row['label']}"

        with get_api_db_cursor() as cursor:
            token_id = _insert_id(
                cursor,
                f"INSERT INTO scan_tokens (token, expires_at, max_uses, created_by, short_code, "
                f"plugin_key_id, minecraft_staff, minecraft_target, source, description) "
                f"VALUES ({_PH},{_PH},{_PH},{_PH},{_PH},{_PH},{_PH},{_PH},{_PH},{_PH})",
                (
                    scan_token, expires_at, max_uses, created_by_label, short_code,
                    row['id'], staff, target or None,
                    'minecraft_plugin',
                    f"reason: {reason}" if reason else None
                )
            )
            # Bump usage
            cursor.execute(
                f"UPDATE company_plugin_keys SET used_today = used_today + 1, "
                f"last_used_at = CURRENT_TIMESTAMP, last_used_ip = {_PH} WHERE id = {_PH}",
                (client_ip, row['id'])
            )

        base_url = os.environ.get('RENDER_EXTERNAL_URL', request.host_url).rstrip('/')
        return jsonify({
            'success': True,
            'short_code': short_code,
            'token': scan_token,        # full token (el plugin normalmente solo usa short_code)
            'token_id': token_id,
            'expires_at': expires_at,
            'expires_in_seconds': 30 * 60,
            'max_uses': max_uses,
            'staff': staff,
            'target': target or None,
            'download_url': f"{base_url}/descargar/exe",
            'download_page_url': f"{base_url}/descargar",
            'company_id': row.get('company_id'),
            'remaining_quota_today': max(0, (row.get('daily_quota') or 200) - (row.get('used_today') or 0) - 1),
        }), 201

    except Exception as e:
        print(f"ERROR api_plugin_issue_token: {type(e).__name__}: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': f'Error interno: {str(e)}'}), 500


@app.route('/api/plugin/violation', methods=['POST'])
def api_plugin_violation():
    """Recibe una violation del anti-cheat del plugin Bukkit.

    Body JSON:
      - player_uuid (str)
      - player_name (str)
      - check_name (str): "reach", "fly", etc.
      - level (str): "LOW" / "MID" / "HIGH" / "CRITICAL"
      - details (str): texto humano legible
      - ts_ms (str/int): timestamp del lado del server MC

    Auth via header X-Argus-Plugin-Key. Devuelve 200 con id de la violation.
    Es fire-and-forget: el plugin ignora errores 5xx (gameplay no se rompe).
    """
    _plugin_schema_guard()
    api_key = (
        request.headers.get('X-Argus-Plugin-Key')
        or request.headers.get('Authorization', '').replace('Bearer ', '').strip()
    )
    if not api_key:
        return jsonify({'success': False, 'error': 'API key requerida'}), 401

    body = request.get_json(silent=True) or {}
    player_uuid = (body.get('player_uuid') or '')[:40]
    player_name = (body.get('player_name') or '')[:64]
    check_name  = (body.get('check_name') or 'unknown')[:64]
    level       = (body.get('level') or 'LOW').upper()[:16]
    details     = (body.get('details') or '')[:500]

    if level not in ('LOW', 'MID', 'HIGH', 'CRITICAL'):
        level = 'LOW'

    try:
        with get_api_db_cursor() as cursor:
            cursor.execute(
                f"SELECT id, company_id, label, is_active "
                f"FROM company_plugin_keys WHERE api_key = {_PH}",
                (api_key,)
            )
            row = cursor.fetchone()
            if not row:
                return jsonify({'success': False, 'error': 'API key invalida'}), 401
            row = dict(row) if not isinstance(row, dict) else row
            if not row.get('is_active'):
                return jsonify({'success': False, 'error': 'API key revocada'}), 403

            new_id = _insert_id(
                cursor,
                f"INSERT INTO plugin_violations "
                f"(plugin_key_id, company_id, player_uuid, player_name, check_name, level, details, server_label) "
                f"VALUES ({_PH}, {_PH}, {_PH}, {_PH}, {_PH}, {_PH}, {_PH}, {_PH})",
                (row['id'], row['company_id'], player_uuid, player_name,
                 check_name, level, details, row.get('label'))
            )
            return jsonify({
                'success': True,
                'violation_id': new_id,
                'level': level,
            }), 201
    except Exception as e:
        print(f"ERROR api_plugin_violation: {type(e).__name__}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/plugin/violations', methods=['GET'])
@login_required
def api_list_violations():
    """Lista violations del anti-cheat para el panel staff.

    Query params:
      - limit (int, default 100, max 500)
      - offset (int, default 0)
      - player (str): filtrar por nombre exacto
      - check (str): filtrar por check_name (reach, fly, ...)
      - level (str): LOW/MID/HIGH/CRITICAL
      - since_minutes (int): ultimos N minutos

    Aislamiento:
      - Owner / admin global: ve TODAS las violations.
      - Staff de empresa: solo ve las de su empresa.
    """
    _plugin_schema_guard()
    try:
        user = get_user_by_id(session.get('user_id'))
        if not user:
            return jsonify({'success': False, 'error': 'No autenticado'}), 401

        roles = user.get('roles') or []
        if isinstance(roles, str):
            try: roles = json.loads(roles)
            except Exception: roles = [roles]
        roles_lower = {str(r).lower() for r in roles}
        is_global_admin = bool(roles_lower & {'admin', 'owner', 'super_admin'})
        company_id = _resolve_company_id_for_user(user)

        limit  = max(1, min(500, int(request.args.get('limit', 100))))
        offset = max(0, int(request.args.get('offset', 0)))
        player = (request.args.get('player') or '').strip()[:64]
        check  = (request.args.get('check') or '').strip()[:64]
        level  = (request.args.get('level') or '').strip().upper()[:16]
        since_min = request.args.get('since_minutes')

        where = []
        params = []
        if not is_global_admin:
            if not company_id:
                return jsonify({'success': True, 'violations': [], 'total': 0}), 200
            where.append(f"company_id = {_PH}")
            params.append(company_id)
        if player:
            where.append(f"LOWER(player_name) = LOWER({_PH})")
            params.append(player)
        if check:
            where.append(f"check_name = {_PH}")
            params.append(check)
        if level in ('LOW', 'MID', 'HIGH', 'CRITICAL'):
            where.append(f"level = {_PH}")
            params.append(level)
        if since_min:
            try:
                since_int = max(1, min(43200, int(since_min)))
                where.append(f"created_at >= NOW() - INTERVAL '{since_int} minutes'")
            except Exception:
                pass

        where_sql = ('WHERE ' + ' AND '.join(where)) if where else ''
        with get_api_db_cursor() as cursor:
            cursor.execute(
                f"SELECT id, plugin_key_id, company_id, player_uuid, player_name, "
                f"check_name, level, details, server_label, related_token_id, created_at "
                f"FROM plugin_violations {where_sql} "
                f"ORDER BY created_at DESC LIMIT {_PH} OFFSET {_PH}",
                tuple(params + [limit, offset])
            )
            rows = cursor.fetchall()
            cursor.execute(
                f"SELECT COUNT(*) AS c FROM plugin_violations {where_sql}",
                tuple(params)
            )
            total_row = cursor.fetchone()
            total = (dict(total_row) if not isinstance(total_row, dict) else total_row).get('c', 0)

        violations = []
        for r in rows:
            d = dict(r) if not isinstance(r, dict) else r
            for k, v in list(d.items()):
                if hasattr(v, 'isoformat'):
                    d[k] = v.isoformat()
            violations.append(d)
        return jsonify({'success': True, 'violations': violations, 'total': total}), 200
    except Exception as e:
        print(f"ERROR api_list_violations: {type(e).__name__}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/plugin/violations/stats', methods=['GET'])
@login_required
def api_violations_stats():
    """Stats agregados para el panel: total por nivel, top players, top checks."""
    _plugin_schema_guard()
    try:
        user = get_user_by_id(session.get('user_id'))
        if not user:
            return jsonify({'success': False, 'error': 'No autenticado'}), 401
        roles = user.get('roles') or []
        if isinstance(roles, str):
            try: roles = json.loads(roles)
            except Exception: roles = [roles]
        roles_lower = {str(r).lower() for r in roles}
        is_global_admin = bool(roles_lower & {'admin', 'owner', 'super_admin'})
        company_id = _resolve_company_id_for_user(user)

        since_min = max(1, min(43200, int(request.args.get('since_minutes', 1440))))
        scope_clause = ''
        params = []
        if not is_global_admin:
            if not company_id:
                return jsonify({'success': True, 'by_level': {}, 'top_players': [], 'top_checks': []}), 200
            scope_clause = f"company_id = {_PH} AND "
            params.append(company_id)

        time_clause = f"created_at >= NOW() - INTERVAL '{since_min} minutes'"
        where = scope_clause + time_clause

        with get_api_db_cursor() as cursor:
            cursor.execute(
                f"SELECT level, COUNT(*) AS c FROM plugin_violations WHERE {where} GROUP BY level",
                tuple(params)
            )
            by_level = {}
            for r in cursor.fetchall():
                d = dict(r) if not isinstance(r, dict) else r
                by_level[d.get('level')] = d.get('c')
            cursor.execute(
                f"SELECT player_name, COUNT(*) AS c FROM plugin_violations "
                f"WHERE {where} GROUP BY player_name ORDER BY c DESC LIMIT 10",
                tuple(params)
            )
            top_players = [dict(r) if not isinstance(r, dict) else r for r in cursor.fetchall()]
            cursor.execute(
                f"SELECT check_name, COUNT(*) AS c FROM plugin_violations "
                f"WHERE {where} GROUP BY check_name ORDER BY c DESC LIMIT 10",
                tuple(params)
            )
            top_checks = [dict(r) if not isinstance(r, dict) else r for r in cursor.fetchall()]

        return jsonify({
            'success': True,
            'since_minutes': since_min,
            'by_level': by_level,
            'top_players': top_players,
            'top_checks': top_checks,
        }), 200
    except Exception as e:
        print(f"ERROR api_violations_stats: {type(e).__name__}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
#  Pack 44: Argus AI Oracle
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

# Cache de pesos por company_id para no machacar la BD en cada eval.
_AI_WEIGHTS_CACHE: dict = {}
_AI_WEIGHTS_TTL_S = 60.0


def _get_ai_weights(company_id: int) -> dict:
    """Obtiene los pesos del Oracle para una empresa, con cache 60s.

    Si la empresa no tiene pesos custom, usa los globales (company_id=0).
    Si tampoco hay globales en BD, usa los hardcoded de argus_ai_oracle."""
    import argus_ai_oracle as _oracle
    cache_key = f"ai_weights:{int(company_id or 0)}"
    cached = _app_cache.get(cache_key)
    if cached:
        return cached
    try:
        with get_api_db_cursor() as cursor:
            cursor.execute(
                f"SELECT weights_json FROM ai_weights WHERE company_id = {_PH}",
                (company_id,)
            )
            row = cursor.fetchone()
            if not row and company_id != 0:
                cursor.execute(
                    f"SELECT weights_json FROM ai_weights WHERE company_id = {_PH}",
                    (0,)
                )
                row = cursor.fetchone()
            if row:
                d = dict(row) if not isinstance(row, dict) else row
                weights = json.loads(d['weights_json'])
            else:
                weights = _oracle.get_default_weights()
    except Exception as e:
        print(f"[ai_weights] fallback a defaults: {e}")
        weights = _oracle.get_default_weights()
    # Ajustes agregados de feedback FP recientes (#178)
    try:
        with get_api_db_cursor() as cursor:
            cursor.execute(
                f"SELECT feature_name, weight_adjustment FROM ai_feedback_aggregations "
                f"WHERE agg_date >= CURRENT_DATE - INTERVAL '30 days' ORDER BY agg_date DESC LIMIT 200"
            )
            rows = cursor.fetchall() or []
        mult = ((weights.get('multipliers') or {}).copy())
        for r in rows:
            d = dict(r) if not isinstance(r, dict) else r
            fn = str(d.get('feature_name') or '')
            adj = float(d.get('weight_adjustment') or 0.0)
            if not fn:
                continue
            current = float(mult.get(fn, 1.0))
            mult[fn] = max(0.35, min(1.35, current + adj))
        weights = dict(weights)
        weights['multipliers'] = mult
    except Exception:
        pass
    _app_cache.set(cache_key, weights, ttl=300)
    return weights


def _get_company_game_profile_rules(company_id: int) -> dict:
    cache_key = f"company_game_profile_rules:{int(company_id or 0)}"
    c = _app_cache.get(cache_key)
    if c:
        return c
    default_rules = {'whitelist_checks': [], 'allow_legit_clients': True}
    if int(company_id or 0) <= 0:
        return default_rules
    try:
        with get_api_db_cursor() as cursor:
            cursor.execute(
                f"SELECT gp.filter_rules FROM company_game_profile cgp "
                f"JOIN game_profiles gp ON gp.id = cgp.game_profile_id "
                f"WHERE cgp.company_id = {_PH} LIMIT 1",
                (int(company_id),)
            )
            row = cursor.fetchone()
            if row:
                d = dict(row) if not isinstance(row, dict) else row
                rules = json.loads(d.get('filter_rules') or '{}')
                if isinstance(rules, dict):
                    out = {
                        'whitelist_checks': list(rules.get('whitelist_checks') or []),
                        'allow_legit_clients': bool(rules.get('allow_legit_clients', True)),
                    }
                    _app_cache.set(cache_key, out, ttl=60)
                    return out
    except Exception:
        pass
    _app_cache.set(cache_key, default_rules, ttl=60)
    return default_rules


def _build_ai_evidence(cursor, company_id: int, player_uuid: str, player_name: str,
                       new_violation: dict | None = None) -> dict:
    """Junta toda la evidencia disponible sobre un jugador para el Oracle.

    Lee:
      - violations recientes (ultima hora) de plugin_violations
      - estado actual de ai_player_scores (current_score + decay)
      - SS pasados via scan_tokens.minecraft_target (cuantos limpios, ultimo resultado)
      - reports recientes (no implementado aun, defaults a 0)
    """
    profile_rules = _get_company_game_profile_rules(company_id)
    evidence: dict = {
        'violations': [],
        'current_score': 0.0,
        'last_evaluated_at_age_seconds': None,
        'first_seen_now': False,
        'account_age_hours': None,
        'playtime_hours': None,
        'prior_clean_scans': 0,
        'scan_detected_hacks_recent': False,
        'reports_in_chat': 0,
        'game_profile_rules': profile_rules,
    }
    # Estado previo
    try:
        cursor.execute(
            f"SELECT score, last_evaluated_at FROM ai_player_scores "
            f"WHERE company_id = {_PH} AND player_uuid = {_PH}",
            (company_id, player_uuid)
        )
        row = cursor.fetchone()
        if row:
            d = dict(row) if not isinstance(row, dict) else row
            evidence['current_score'] = float(d.get('score') or 0.0)
            le = d.get('last_evaluated_at')
            if le:
                from datetime import datetime as _dt, timezone as _tz
                if isinstance(le, str):
                    try:
                        le = _dt.fromisoformat(le.replace('Z', '+00:00'))
                    except Exception:
                        le = None
                if le:
                    le_aware = le if le.tzinfo else le.replace(tzinfo=_tz.utc)
                    evidence['last_evaluated_at_age_seconds'] = max(
                        0.0, (_dt.now(_tz.utc) - le_aware).total_seconds())
        else:
            evidence['first_seen_now'] = True
    except Exception as e:
        print(f"[ai_evidence] error leyendo ai_player_scores: {e}")

    # Violations recientes (ultima hora)
    try:
        cursor.execute(
            f"SELECT check_name, level, "
            f"EXTRACT(EPOCH FROM (NOW() - created_at))::INT AS age_s "
            f"FROM plugin_violations "
            f"WHERE company_id = {_PH} AND player_uuid = {_PH} "
            f"AND created_at > NOW() - INTERVAL '60 minutes' "
            f"ORDER BY created_at DESC LIMIT 50",
            (company_id, player_uuid)
        )
        whitelist_checks = {str(x).strip().lower() for x in (profile_rules.get('whitelist_checks') or [])}
        for r in cursor.fetchall():
            d = dict(r) if not isinstance(r, dict) else r
            ckn = str(d.get('check_name') or '')
            if ckn.split(':', 1)[0].strip().lower() in whitelist_checks:
                continue
            evidence['violations'].append({
                'check_name': ckn,
                'level': d.get('level'),
                'age_seconds': d.get('age_s') or 0,
            })
    except Exception as e:
        print(f"[ai_evidence] error leyendo violations: {e}")

    # Si nos pasan una violation NUEVA (la que acaba de disparar la eval), la
    # incluimos manualmente con age=0 (puede no haber llegado al SELECT por
    # carrera transaccional).
    if new_violation:
        evidence['violations'].insert(0, {
            'check_name': new_violation.get('check_name'),
            'level': new_violation.get('level', 'LOW'),
            'age_seconds': 0,
        })

    # Historial de scans (Argus Windows scanner)
    try:
        cursor.execute(
            f"SELECT COUNT(*) AS c FROM scan_tokens "
            f"WHERE LOWER(minecraft_target) = LOWER({_PH}) AND completed = TRUE "
            f"AND created_at > NOW() - INTERVAL '90 days'",
            (player_name,)
        )
        cr = cursor.fetchone()
        if cr:
            evidence['prior_clean_scans'] = int(
                (dict(cr) if not isinstance(cr, dict) else cr).get('c') or 0)
    except Exception:
        pass

    return evidence


def _persist_ai_decision(cursor, company_id: int, plugin_key_id: int | None,
                         player_uuid: str, player_name: str, decision,
                         triggered_by: str = 'auto') -> int | None:
    """Guarda la decision en ai_decisions_log + actualiza ai_player_scores.

    Devuelve el id de la decision insertada (o None si fallo).
    """
    decision_id: int | None = None
    try:
        if _USE_PG:
            cursor.execute(
                f"INSERT INTO ai_decisions_log "
                f"(company_id, plugin_key_id, player_uuid, player_name, score, confidence, "
                f"action, reasoning, evidence_json, triggered_by) "
                f"VALUES ({_PH},{_PH},{_PH},{_PH},{_PH},{_PH},{_PH},{_PH},{_PH},{_PH}) "
                f"RETURNING id",
                (company_id, plugin_key_id, player_uuid, player_name,
                 decision.score, decision.confidence, decision.action,
                 decision.reasoning, json.dumps({
                     'top_factor': decision.top_factor,
                     'evidence_used': decision.evidence_used,
                     'multipliers_applied': decision.multipliers_applied,
                 }), triggered_by)
            )
            r = cursor.fetchone()
            if r:
                decision_id = int(r[0] if isinstance(r, (tuple, list)) else r.get('id'))
        else:
            cursor.execute(
                f"INSERT INTO ai_decisions_log "
                f"(company_id, plugin_key_id, player_uuid, player_name, score, confidence, "
                f"action, reasoning, evidence_json, triggered_by) "
                f"VALUES ({_PH},{_PH},{_PH},{_PH},{_PH},{_PH},{_PH},{_PH},{_PH},{_PH})",
                (company_id, plugin_key_id, player_uuid, player_name,
                 decision.score, decision.confidence, decision.action,
                 decision.reasoning, json.dumps({
                     'top_factor': decision.top_factor,
                     'evidence_used': decision.evidence_used,
                     'multipliers_applied': decision.multipliers_applied,
                 }), triggered_by)
            )
            try:
                decision_id = int(getattr(cursor, 'lastrowid', None) or 0) or None
            except Exception:
                decision_id = None
    except Exception as e:
        print(f"[ai_persist] error en log insert: {e}")

    try:
        # UPSERT compatible con ambos dialectos (postgres ON CONFLICT, sqlite IGNORE+UPDATE)
        cursor.execute(
            f"SELECT id FROM ai_player_scores WHERE company_id = {_PH} AND player_uuid = {_PH}",
            (company_id, player_uuid)
        )
        existing = cursor.fetchone()
        if existing:
            cursor.execute(
                f"UPDATE ai_player_scores SET "
                f"player_name = {_PH}, score = {_PH}, confidence = {_PH}, "
                f"last_action = {_PH}, last_reasoning = {_PH}, last_evidence_json = {_PH}, "
                f"evaluations_count = evaluations_count + 1, "
                f"last_evaluated_at = CURRENT_TIMESTAMP "
                f"WHERE company_id = {_PH} AND player_uuid = {_PH}",
                (player_name, decision.score, decision.confidence,
                 decision.action, decision.reasoning,
                 json.dumps(decision.evidence_used),
                 company_id, player_uuid)
            )
        else:
            cursor.execute(
                f"INSERT INTO ai_player_scores "
                f"(company_id, player_uuid, player_name, score, confidence, "
                f"last_action, last_reasoning, last_evidence_json, evaluations_count) "
                f"VALUES ({_PH},{_PH},{_PH},{_PH},{_PH},{_PH},{_PH},{_PH},1)",
                (company_id, player_uuid, player_name, decision.score, decision.confidence,
                 decision.action, decision.reasoning, json.dumps(decision.evidence_used))
            )
    except Exception as e:
        print(f"[ai_persist] error en upsert score: {e}")

    try:
        _dispatch_oracle_webhook_notifications(
            cursor=cursor,
            company_id=company_id,
            player_name=player_name,
            action=str(getattr(decision, 'action', '') or ''),
            confidence=float(getattr(decision, 'confidence', 0.0) or 0.0),
            score=float(getattr(decision, 'score', 0.0) or 0.0),
            decision_id=decision_id,
            reasoning=str(getattr(decision, 'reasoning', '') or ''),
        )
    except Exception as e:
        print(f"[oracle_notify] error dispatch: {e}")
    try:
        dispatch_webhook('oracle.decision', {
            'decision_id': decision_id,
            'company_id': company_id,
            'player_name': player_name,
            'action': str(getattr(decision, 'action', '') or ''),
            'score': float(getattr(decision, 'score', 0.0) or 0.0),
            'confidence': float(getattr(decision, 'confidence', 0.0) or 0.0),
        }, company_id=company_id)
        if str(getattr(decision, 'action', '') or '').lower() == 'ban':
            dispatch_webhook('ban.created', {
                'decision_id': decision_id,
                'company_id': company_id,
                'player_name': player_name,
            }, company_id=company_id)
    except Exception:
        pass

    return decision_id


_NOTIF_LEVEL_MAP = {
    'LOW': 1,
    'MID': 2,
    'MEDIUM': 2,
    'HIGH': 3,
    'CRITICAL': 4,
}


def _action_to_level(action: str, confidence: float = 0.0) -> str:
    a = (action or '').strip().lower()
    if a == 'ban':
        return 'CRITICAL'
    if a in ('kick', 'ss'):
        return 'HIGH'
    if a in ('watch', 'warn'):
        return 'MID'
    if confidence >= 0.85:
        return 'HIGH'
    return 'LOW'


def _dispatch_oracle_webhook_notifications(cursor, company_id: int, player_name: str,
                                           action: str, confidence: float, score: float,
                                           decision_id: int | None, reasoning: str = '') -> None:
    level = _action_to_level(action, confidence)
    if _NOTIF_LEVEL_MAP.get(level, 0) < _NOTIF_LEVEL_MAP['HIGH']:
        return
    cursor.execute(
        f"SELECT type, webhook_url, enabled, filter_min_level "
        f"FROM company_notification_settings WHERE company_id = {_PH} AND enabled = TRUE",
        (int(company_id),)
    )
    rows = cursor.fetchall() or []
    if not rows:
        return
    payload_base = {
        'event': 'oracle_decision',
        'company_id': int(company_id),
        'decision_id': decision_id,
        'player_name': player_name,
        'action': action,
        'level': level,
        'confidence': round(float(confidence or 0.0), 4),
        'score': round(float(score or 0.0), 4),
        'reasoning': (reasoning or '')[:600],
        'ts': datetime.datetime.utcnow().isoformat() + 'Z',
    }
    for r in rows:
        d = dict(r) if not isinstance(r, dict) else r
        min_level = str(d.get('filter_min_level') or 'HIGH').upper()
        if _NOTIF_LEVEL_MAP.get(level, 0) < _NOTIF_LEVEL_MAP.get(min_level, 3):
            continue
        webhook = str(d.get('webhook_url') or '').strip()
        if not webhook:
            continue
        ntype = str(d.get('type') or '').strip().lower()
        try:
            if ntype == 'discord':
                content = (
                    f"🚨 Oracle {action.upper()} · {level}\n"
                    f"Jugador: **{player_name}**\n"
                    f"Confianza: {payload_base['confidence']:.2f} · Score: {payload_base['score']:.2f}\n"
                    f"Decision ID: {decision_id or '-'}"
                )
                requests.post(webhook, json={'content': content}, timeout=4)
            elif ntype == 'telegram':
                txt = (
                    f"🚨 Oracle {action.upper()} · {level}\n"
                    f"Jugador: {player_name}\n"
                    f"Confianza: {payload_base['confidence']:.2f} | Score: {payload_base['score']:.2f}\n"
                    f"Decision ID: {decision_id or '-'}"
                )
                requests.post(webhook, json={'text': txt}, timeout=4)
            else:
                requests.post(webhook, json=payload_base, timeout=4)
        except Exception as _e:
            print(f"[oracle_notify] webhook error type={ntype}: {_e}")


def generate_daily_digest(company_id: int) -> dict:
    """Arma resumen diario de métricas Oracle para una empresa."""
    out = {
        'company_id': int(company_id),
        'date': datetime.date.today().isoformat(),
        'scans_today': 0,
        'violations': {'low': 0, 'mid': 0, 'high': 0, 'critical': 0},
        'top_violators': [],
        'ai_accuracy': 0.0,
    }
    try:
        with get_api_db_cursor() as cur:
            cur.execute(
                f"SELECT COUNT(*) AS c FROM scans WHERE company_id = {_PH} "
                f"AND started_at >= CURRENT_DATE",
                (int(company_id),)
            )
            r = cur.fetchone()
            out['scans_today'] = int((dict(r) if r and not isinstance(r, dict) else (r or {})).get('c') or 0)
            cur.execute(
                f"SELECT UPPER(COALESCE(level,'LOW')) AS lvl, COUNT(*) AS c "
                f"FROM plugin_violations WHERE company_id = {_PH} "
                f"AND created_at >= CURRENT_DATE GROUP BY UPPER(COALESCE(level,'LOW'))",
                (int(company_id),)
            )
            for row in (cur.fetchall() or []):
                rr = dict(row) if not isinstance(row, dict) else row
                lvl = str(rr.get('lvl') or '').lower()
                key = 'mid' if lvl == 'medium' else lvl
                if key in out['violations']:
                    out['violations'][key] = int(rr.get('c') or 0)
            cur.execute(
                f"SELECT player_name, COUNT(*) AS c FROM plugin_violations "
                f"WHERE company_id = {_PH} AND created_at >= CURRENT_DATE "
                f"GROUP BY player_name ORDER BY c DESC LIMIT 5",
                (int(company_id),)
            )
            out['top_violators'] = [
                {
                    'player_name': (dict(rw) if not isinstance(rw, dict) else rw).get('player_name') or '?',
                    'count': int((dict(rw) if not isinstance(rw, dict) else rw).get('c') or 0),
                }
                for rw in (cur.fetchall() or [])
            ]
            try:
                cur.execute(
                    f"SELECT COALESCE(SUM(agreements),0) AS a, COALESCE(SUM(disagreements),0) AS d, "
                    f"COALESCE(SUM(confirmed_correct),0) AS cc, COALESCE(SUM(confirmed_wrong),0) AS cw "
                    f"FROM staff_trust_metrics WHERE company_id = {_PH}",
                    (int(company_id),)
                )
                m = cur.fetchone()
                m = dict(m) if m and not isinstance(m, dict) else (m or {})
                a = int(m.get('a') or 0) + 2 * int(m.get('cc') or 0)
                d = int(m.get('d') or 0) + 2 * int(m.get('cw') or 0)
                out['ai_accuracy'] = round((a / (a + d)) * 100.0, 2) if (a + d) > 0 else 0.0
            except Exception:
                out['ai_accuracy'] = 0.0
    except Exception as e:
        print(f"[digest] generate error: {e}")
    return out


def _digest_to_text_html(digest: dict) -> tuple[str, str]:
    top_rows = '\n'.join(
        [f"- {x.get('player_name')}: {x.get('count')}" for x in (digest.get('top_violators') or [])]
    ) or "- Sin datos"
    text = (
        f"Argus Daily Digest ({digest.get('date')})\n"
        f"Company: {digest.get('company_id')}\n"
        f"Scans hoy: {digest.get('scans_today')}\n"
        f"Violations: LOW {digest['violations']['low']} | MID {digest['violations']['mid']} | "
        f"HIGH {digest['violations']['high']} | CRITICAL {digest['violations']['critical']}\n"
        f"Top violators:\n{top_rows}\n"
        f"AI accuracy: {digest.get('ai_accuracy')}%\n"
    )
    html = (
        "<h2>Argus Daily Digest</h2>"
        f"<p><b>Fecha:</b> {digest.get('date')}<br><b>Company:</b> {digest.get('company_id')}</p>"
        f"<p><b>Scans hoy:</b> {digest.get('scans_today')}</p>"
        f"<p><b>Violations:</b> LOW {digest['violations']['low']} · MID {digest['violations']['mid']} · "
        f"HIGH {digest['violations']['high']} · CRITICAL {digest['violations']['critical']}</p>"
        "<p><b>Top violators</b></p><ul>"
        + ''.join([f"<li>{x.get('player_name')}: {x.get('count')}</li>" for x in (digest.get('top_violators') or [])])
        + "</ul>"
        f"<p><b>AI accuracy:</b> {digest.get('ai_accuracy')}%</p>"
    )
    return text, html


def _send_daily_digest_emails():
    """Job diario: genera digest por company y envía a admins con email."""
    smtp_host = os.environ.get('SMTP_HOST', '').strip()
    smtp_user = os.environ.get('SMTP_USER', '').strip()
    smtp_pass = os.environ.get('SMTP_PASS', '').strip()
    smtp_from = os.environ.get('SMTP_FROM', 'argus@aspers.gg').strip()
    smtp_port = int(os.environ.get('SMTP_PORT', '587') or 587)
    if not smtp_host:
        print('[digest] SMTP_HOST no configurado, se omite envío diario')
        return
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    try:
        with get_api_db_cursor() as cur:
            cur.execute("SELECT DISTINCT company_id FROM users WHERE company_id IS NOT NULL")
            companies = [int((dict(r) if not isinstance(r, dict) else r).get('company_id') or 0) for r in (cur.fetchall() or [])]
        companies = [c for c in companies if c > 0]
        for cid in companies:
            digest = generate_daily_digest(cid)
            text, html = _digest_to_text_html(digest)
            with get_api_db_cursor() as cur:
                cur.execute(
                    f"SELECT email FROM users WHERE company_id = {_PH} "
                    f"AND email IS NOT NULL AND email != ''",
                    (cid,)
                )
                recipients = [str((dict(r) if not isinstance(r, dict) else r).get('email') or '').strip() for r in (cur.fetchall() or [])]
            recipients = [e for e in recipients if '@' in e]
            if not recipients:
                continue
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"Argus Daily Digest · Company {cid}"
            msg['From'] = smtp_from
            msg['To'] = ', '.join(recipients[:20])
            msg.attach(MIMEText(text, 'plain', 'utf-8'))
            msg.attach(MIMEText(html, 'html', 'utf-8'))
            with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as srv:
                srv.starttls()
                if smtp_user:
                    srv.login(smtp_user, smtp_pass)
                srv.sendmail(smtp_from, recipients, msg.as_string())
    except Exception as e:
        print(f"[digest] send error: {e}")


def _can_manage_company_notifications(user: dict | None, requested_company_id: int) -> bool:
    if not user:
        return False
    roles = user.get('roles') or []
    if isinstance(roles, str):
        try:
            roles = json.loads(roles)
        except Exception:
            roles = [roles]
    roles = {str(r).lower() for r in roles}
    if roles & {'admin', 'owner', 'super_admin'}:
        return True
    my_company = int(_resolve_company_id_for_user(user) or 0)
    return my_company > 0 and my_company == int(requested_company_id)


@app.route('/api/companies/<int:company_id>/notifications', methods=['GET', 'PUT'])
@login_required
@audit_action('company.notifications.update', 'company')
def api_company_notifications(company_id: int):
    _plugin_schema_guard()
    user = get_user_by_id(session.get('user_id'))
    if not _can_manage_company_notifications(user, company_id):
        return jsonify({'success': False, 'error': 'No autorizado'}), 403
    if request.method == 'GET':
        try:
            with get_api_db_cursor() as cur:
                cur.execute(
                    f"SELECT type, webhook_url, enabled, filter_min_level "
                    f"FROM company_notification_settings WHERE company_id = {_PH}",
                    (company_id,)
                )
                rows = []
                for r in (cur.fetchall() or []):
                    d = dict(r) if not isinstance(r, dict) else r
                    rows.append({
                        'type': d.get('type'),
                        'webhook_url': d.get('webhook_url') or '',
                        'enabled': bool(d.get('enabled')),
                        'filter_min_level': (d.get('filter_min_level') or 'HIGH'),
                    })
            return jsonify({'success': True, 'items': rows}), 200
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    data = request.json or {}
    items = data.get('items') or []
    if not isinstance(items, list):
        return jsonify({'success': False, 'error': 'items inválido'}), 400
    try:
        with get_api_db_cursor() as cur:
            cur.execute(f"DELETE FROM company_notification_settings WHERE company_id = {_PH}", (company_id,))
            for it in items[:8]:
                ntype = str((it or {}).get('type') or '').strip().lower()
                if ntype not in ('telegram', 'discord'):
                    continue
                url = str((it or {}).get('webhook_url') or '').strip()
                if not url:
                    continue
                en = bool((it or {}).get('enabled', True))
                lvl = str((it or {}).get('filter_min_level') or 'HIGH').upper()
                if lvl not in _NOTIF_LEVEL_MAP:
                    lvl = 'HIGH'
                cur.execute(
                    f"INSERT INTO company_notification_settings "
                    f"(company_id, type, webhook_url, enabled, filter_min_level, updated_at) "
                    f"VALUES ({_PH},{_PH},{_PH},{_PH},{_PH},CURRENT_TIMESTAMP)",
                    (company_id, ntype, url, en, lvl)
                )
        return jsonify({'success': True}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/digest/preview', methods=['GET'])
@login_required
def api_admin_digest_preview():
    _plugin_schema_guard()
    user = get_user_by_id(session.get('user_id'))
    if not user:
        return jsonify({'success': False, 'error': 'No autenticado'}), 401
    requested = int(request.args.get('company_id') or 0)
    if requested <= 0:
        requested = int(_resolve_company_id_for_user(user) or 0)
    if requested <= 0 or not _can_manage_company_notifications(user, requested):
        return jsonify({'success': False, 'error': 'No autorizado para esa company'}), 403
    digest = generate_daily_digest(requested)
    text, html = _digest_to_text_html(digest)
    return jsonify({'success': True, 'digest': digest, 'text_preview': text, 'html_preview': html}), 200


@app.route('/api/game-profiles', methods=['GET', 'POST', 'PUT', 'DELETE'])
@login_required
def api_game_profiles():
    _plugin_schema_guard()
    user = get_user_by_id(session.get('user_id'))
    if not user:
        return jsonify({'success': False, 'error': 'No autenticado'}), 401
    roles = user.get('roles') or []
    if isinstance(roles, str):
        try:
            roles = json.loads(roles)
        except Exception:
            roles = [roles]
    roles = {str(r).lower() for r in roles}
    is_admin = bool(roles & {'admin', 'owner', 'super_admin'})
    if request.method == 'GET':
        with get_api_db_cursor() as cur:
            cur.execute("SELECT id, name, slug, filter_rules, default_for_company FROM game_profiles ORDER BY name ASC")
            items = []
            for r in (cur.fetchall() or []):
                d = dict(r) if not isinstance(r, dict) else r
                items.append({
                    'id': d.get('id'),
                    'name': d.get('name'),
                    'slug': d.get('slug'),
                    'filter_rules': json.loads(d.get('filter_rules') or '{}'),
                    'default_for_company': d.get('default_for_company'),
                })
        return jsonify({'success': True, 'items': items}), 200
    if not is_admin:
        return jsonify({'success': False, 'error': 'No autorizado'}), 403
    data = request.json or {}
    try:
        with get_api_db_cursor() as cur:
            if request.method == 'POST':
                name = str(data.get('name') or '').strip()[:80]
                slug = str(data.get('slug') or '').strip().lower()[:60]
                rules = data.get('filter_rules') or {}
                if not name or not slug:
                    return jsonify({'success': False, 'error': 'name/slug requeridos'}), 400
                sid = _insert_id(cur, f"INSERT INTO game_profiles (name, slug, filter_rules) VALUES ({_PH},{_PH},{_PH})",
                                 (name, slug, json.dumps(rules)))
                return jsonify({'success': True, 'id': sid}), 200
            if request.method == 'PUT':
                pid = int(data.get('id') or 0)
                if pid <= 0:
                    return jsonify({'success': False, 'error': 'id requerido'}), 400
                cur.execute(
                    f"UPDATE game_profiles SET name = {_PH}, slug = {_PH}, filter_rules = {_PH}, updated_at = CURRENT_TIMESTAMP "
                    f"WHERE id = {_PH}",
                    (str(data.get('name') or '')[:80], str(data.get('slug') or '').lower()[:60],
                     json.dumps(data.get('filter_rules') or {}), pid)
                )
                return jsonify({'success': True}), 200
            pid = int(data.get('id') or request.args.get('id') or 0)
            if pid <= 0:
                return jsonify({'success': False, 'error': 'id requerido'}), 400
            cur.execute(f"DELETE FROM game_profiles WHERE id = {_PH}", (pid,))
            return jsonify({'success': True}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/companies/<int:company_id>/game-profile', methods=['GET', 'PUT'])
@login_required
def api_company_game_profile(company_id: int):
    _plugin_schema_guard()
    user = get_user_by_id(session.get('user_id'))
    if not _can_manage_company_notifications(user, company_id):
        return jsonify({'success': False, 'error': 'No autorizado'}), 403
    if request.method == 'GET':
        with get_api_db_cursor() as cur:
            cur.execute(
                f"SELECT cgp.game_profile_id, gp.slug, gp.name, gp.filter_rules "
                f"FROM company_game_profile cgp JOIN game_profiles gp ON gp.id = cgp.game_profile_id "
                f"WHERE cgp.company_id = {_PH} LIMIT 1",
                (company_id,)
            )
            row = cur.fetchone()
        if not row:
            return jsonify({'success': True, 'profile': None}), 200
        d = dict(row) if not isinstance(row, dict) else row
        return jsonify({'success': True, 'profile': {
            'game_profile_id': d.get('game_profile_id'),
            'slug': d.get('slug'),
            'name': d.get('name'),
            'filter_rules': json.loads(d.get('filter_rules') or '{}'),
        }}), 200
    data = request.json or {}
    pid = int(data.get('game_profile_id') or 0)
    if pid <= 0:
        return jsonify({'success': False, 'error': 'game_profile_id requerido'}), 400
    with get_api_db_cursor() as cur:
        cur.execute(f"SELECT company_id FROM company_game_profile WHERE company_id = {_PH}", (company_id,))
        if cur.fetchone():
            cur.execute(
                f"UPDATE company_game_profile SET game_profile_id = {_PH}, updated_at = CURRENT_TIMESTAMP "
                f"WHERE company_id = {_PH}",
                (pid, company_id)
            )
        else:
            cur.execute(
                f"INSERT INTO company_game_profile (company_id, game_profile_id, updated_at) VALUES ({_PH},{_PH},CURRENT_TIMESTAMP)",
                (company_id, pid)
            )
    _app_cache.delete(f"company_game_profile_rules:{company_id}")
    return jsonify({'success': True}), 200


@app.route('/api/shared-rules', methods=['GET', 'POST'])
@login_required
def api_shared_rules():
    _plugin_schema_guard()
    user = get_user_by_id(session.get('user_id'))
    if not user:
        return jsonify({'success': False, 'error': 'No autenticado'}), 401
    company_id = int(_resolve_company_id_for_user(user) or 0)
    if request.method == 'GET':
        page = max(1, int(request.args.get('page', 1) or 1))
        per_page = max(1, min(50, int(request.args.get('per_page', 20) or 20)))
        off = (page - 1) * per_page
        with get_api_db_cursor() as cur:
            cur.execute(
                f"SELECT id, source_company_id, name, description, rules_json, downloads_count, rating_avg "
                f"FROM shared_filter_rules WHERE public = TRUE ORDER BY rating_avg DESC, downloads_count DESC LIMIT {_PH} OFFSET {_PH}",
                (per_page, off)
            )
            rows = cur.fetchall() or []
        items = []
        for r in rows:
            d = dict(r) if not isinstance(r, dict) else r
            items.append({
                'id': d.get('id'),
                'source_company_id': d.get('source_company_id'),
                'name': d.get('name'),
                'description': d.get('description'),
                'rules': json.loads(d.get('rules_json') or '{}'),
                'downloads_count': int(d.get('downloads_count') or 0),
                'rating_avg': float(d.get('rating_avg') or 0.0),
            })
        return jsonify({'success': True, 'items': items, 'page': page, 'per_page': per_page}), 200
    data = request.json or {}
    if company_id <= 0:
        return jsonify({'success': False, 'error': 'Usuario sin company'}), 400
    with get_api_db_cursor() as cur:
        rid = _insert_id(
            cur,
            f"INSERT INTO shared_filter_rules (source_company_id, name, description, rules_json, public, updated_at) "
            f"VALUES ({_PH},{_PH},{_PH},{_PH},{_PH},CURRENT_TIMESTAMP)",
            (
                company_id,
                str(data.get('name') or 'Rule set')[:120],
                str(data.get('description') or '')[:500],
                json.dumps(data.get('rules') or {}),
                bool(data.get('public', True)),
            )
        )
    return jsonify({'success': True, 'id': rid}), 200


@app.route('/api/shared-rules/<int:rule_id>/use', methods=['POST'])
@login_required
def api_shared_rules_use(rule_id: int):
    user = get_user_by_id(session.get('user_id'))
    company_id = int(_resolve_company_id_for_user(user) or 0) if user else 0
    if company_id <= 0:
        return jsonify({'success': False, 'error': 'Usuario sin company'}), 400
    with get_api_db_cursor() as cur:
        cur.execute(
            f"INSERT INTO company_shared_rules (company_id, shared_rule_id) VALUES ({_PH},{_PH})",
            (company_id, rule_id)
        )
        cur.execute(
            f"UPDATE shared_filter_rules SET downloads_count = COALESCE(downloads_count,0)+1, updated_at = CURRENT_TIMESTAMP "
            f"WHERE id = {_PH}",
            (rule_id,)
        )
    return jsonify({'success': True}), 200


@app.route('/api/shared-rules/<int:rule_id>/rate', methods=['POST'])
@login_required
def api_shared_rules_rate(rule_id: int):
    data = request.json or {}
    rating = max(1, min(5, int(data.get('rating') or 0)))
    with get_api_db_cursor() as cur:
        cur.execute(
            f"SELECT rating_avg, rating_count FROM shared_filter_rules WHERE id = {_PH}",
            (rule_id,)
        )
        row = cur.fetchone()
        if not row:
            return jsonify({'success': False, 'error': 'Regla no encontrada'}), 404
        d = dict(row) if not isinstance(row, dict) else row
        cur_avg = float(d.get('rating_avg') or 0.0)
        cur_n = int(d.get('rating_count') or 0)
        new_n = cur_n + 1
        new_avg = ((cur_avg * cur_n) + rating) / new_n
        cur.execute(
            f"UPDATE shared_filter_rules SET rating_avg = {_PH}, rating_count = {_PH}, updated_at = CURRENT_TIMESTAMP "
            f"WHERE id = {_PH}",
            (new_avg, new_n, rule_id)
        )
    return jsonify({'success': True, 'rating_avg': round(new_avg, 3), 'rating_count': new_n}), 200


def dispatch_webhook(event_type: str, payload: dict, company_id: int | None = None):
    try:
        if not company_id:
            company_id = int(payload.get('company_id') or 0)
        if not company_id:
            return
        with get_api_db_cursor() as cur:
            cur.execute(
                f"SELECT id, url, secret, events, is_active FROM webhook_subscriptions "
                f"WHERE company_id = {_PH} AND is_active = TRUE",
                (company_id,)
            )
            rows = cur.fetchall() or []
            for r in rows:
                d = dict(r) if not isinstance(r, dict) else r
                events = []
                try:
                    events = json.loads(d.get('events') or '[]')
                except Exception:
                    events = []
                if events and event_type not in events:
                    continue
                sub_id = int(d.get('id') or 0)
                def _send_one(sid=sub_id, ev=event_type, pld=dict(payload), url=str(d.get('url') or ''), sec=str(d.get('secret') or '')):
                    ok, status_code = _deliver_webhook(
                        url=url,
                        secret=sec,
                        payload={'event_type': ev, 'payload': pld}
                    )
                    try:
                        with get_api_db_cursor() as _c:
                            _c.execute(
                                f"INSERT INTO webhook_deliveries (subscription_id, event_type, payload, status, response_code, attempts) "
                                f"VALUES ({_PH},{_PH},{_PH},{_PH},{_PH},{_PH})",
                                (sid, ev, json.dumps(pld), 'ok' if ok else 'failed', int(status_code or 0), 1)
                            )
                    except Exception:
                        pass
                threading.Thread(target=_send_one, daemon=True).start()
    except Exception as e:
        print(f"[webhooks] dispatch error: {e}")


@app.route('/api/webhooks/subscriptions', methods=['GET', 'POST', 'PUT', 'DELETE'])
@login_required
@audit_action('webhooks.subscriptions.mutate', 'webhook_subscription')
def api_webhook_subscriptions():
    user = get_user_by_id(session.get('user_id'))
    company_id = int(_resolve_company_id_for_user(user) or 0)
    if company_id <= 0:
        return jsonify({'success': False, 'error': 'Sin company_id'}), 400
    if request.method == 'GET':
        with get_api_db_cursor() as cur:
            cur.execute(
                f"SELECT id, company_id, url, events, is_active, created_at FROM webhook_subscriptions "
                f"WHERE company_id = {_PH} ORDER BY id DESC",
                (company_id,)
            )
            rows = cur.fetchall() or []
        items = []
        for r in rows:
            d = dict(r) if not isinstance(r, dict) else r
            items.append({
                'id': d.get('id'),
                'company_id': d.get('company_id'),
                'url': d.get('url'),
                'events': json.loads(d.get('events') or '[]'),
                'is_active': bool(d.get('is_active')),
                'created_at': str(d.get('created_at') or ''),
            })
        return jsonify({'success': True, 'items': items}), 200
    data = request.json or {}
    with get_api_db_cursor() as cur:
        if request.method == 'POST':
            sid = _insert_id(
                cur,
                f"INSERT INTO webhook_subscriptions (company_id, url, secret, events, is_active) "
                f"VALUES ({_PH},{_PH},{_PH},{_PH},{_PH})",
                (company_id, str(data.get('url') or '').strip(), str(data.get('secret') or '').strip(),
                 json.dumps(data.get('events') or []), bool(data.get('is_active', True)))
            )
            return jsonify({'success': True, 'id': sid}), 200
        if request.method == 'PUT':
            sid = int(data.get('id') or 0)
            cur.execute(
                f"UPDATE webhook_subscriptions SET url = {_PH}, secret = {_PH}, events = {_PH}, is_active = {_PH} "
                f"WHERE id = {_PH} AND company_id = {_PH}",
                (str(data.get('url') or '').strip(), str(data.get('secret') or '').strip(),
                 json.dumps(data.get('events') or []), bool(data.get('is_active', True)), sid, company_id)
            )
            return jsonify({'success': True}), 200
        sid = int(data.get('id') or request.args.get('id') or 0)
        cur.execute(f"DELETE FROM webhook_subscriptions WHERE id = {_PH} AND company_id = {_PH}", (sid, company_id))
        return jsonify({'success': True}), 200


@app.route('/api/webhooks/deliveries', methods=['GET'])
@login_required
def api_webhook_deliveries():
    sub_id = int(request.args.get('subscription_id') or 0)
    if sub_id <= 0:
        return jsonify({'success': False, 'error': 'subscription_id requerido'}), 400
    with get_api_db_cursor() as cur:
        cur.execute(
            f"SELECT id, subscription_id, event_type, status, response_code, attempts, created_at "
            f"FROM webhook_deliveries WHERE subscription_id = {_PH} ORDER BY id DESC LIMIT 200",
            (sub_id,)
        )
        rows = cur.fetchall() or []
    return jsonify({'success': True, 'items': [dict(r) if not isinstance(r, dict) else r for r in rows]}), 200


@app.route('/api/keys', methods=['GET', 'POST'])
@login_required
@audit_action('api_keys.manage', 'api_key')
def api_keys_list_create():
    uid = int(session.get('user_id') or 0)
    user = get_user_by_id(uid)
    company_id = int(_resolve_company_id_for_user(user) or 0) if user else 0
    if request.method == 'GET':
        with get_api_db_cursor() as cur:
            cur.execute(
                f"SELECT id, name, scopes, last_used_at, revoked_at, created_at FROM api_keys "
                f"WHERE user_id = {_PH} ORDER BY id DESC",
                (uid,)
            )
            rows = cur.fetchall() or []
        out = []
        for r in rows:
            d = dict(r) if not isinstance(r, dict) else r
            out.append({
                'id': d.get('id'),
                'name': d.get('name'),
                'scopes': json.loads(d.get('scopes') or '[]'),
                'last_used_at': str(d.get('last_used_at') or ''),
                'revoked_at': str(d.get('revoked_at') or '') if d.get('revoked_at') else None,
                'created_at': str(d.get('created_at') or ''),
            })
        return jsonify({'success': True, 'items': out}), 200
    data = request.json or {}
    name = str(data.get('name') or 'default')[:120]
    scopes = data.get('scopes') or ['read:scans']
    plain = _gen_api_key('argus')
    key_hash = _hash_api_key(plain)
    with get_api_db_cursor() as cur:
        kid = _insert_id(
            cur,
            f"INSERT INTO api_keys (user_id, company_id, name, key_hash, scopes) VALUES ({_PH},{_PH},{_PH},{_PH},{_PH})",
            (uid, company_id or None, name, key_hash, json.dumps(scopes))
        )
    _write_audit('api_key.created', 'api_key', str(kid or ''), {'name': name, 'scopes': scopes})
    return jsonify({'success': True, 'id': kid, 'api_key': plain}), 200


@app.route('/api/keys/<int:key_id>', methods=['DELETE'])
@login_required
@audit_action('api_key.revoked', 'api_key')
def api_keys_delete(key_id: int):
    uid = int(session.get('user_id') or 0)
    with get_api_db_cursor() as cur:
        cur.execute(
            f"UPDATE api_keys SET revoked_at = CURRENT_TIMESTAMP WHERE id = {_PH} AND user_id = {_PH}",
            (key_id, uid)
        )
    return jsonify({'success': True}), 200


@app.route('/api/me/notifications/prefs', methods=['GET', 'PUT'])
@login_required
def api_me_notification_prefs():
    uid = int(session.get('user_id') or 0)
    if request.method == 'GET':
        with get_api_db_cursor() as cur:
            cur.execute(
                f"SELECT channel, event_type, enabled FROM user_notification_prefs WHERE user_id = {_PH}",
                (uid,)
            )
            rows = cur.fetchall() or []
        return jsonify({'success': True, 'items': [dict(r) if not isinstance(r, dict) else r for r in rows]}), 200
    data = request.json or {}
    items = data.get('items') or []
    with get_api_db_cursor() as cur:
        cur.execute(f"DELETE FROM user_notification_prefs WHERE user_id = {_PH}", (uid,))
        for it in items[:200]:
            ch = str((it or {}).get('channel') or '').strip().lower()
            ev = str((it or {}).get('event_type') or '').strip().lower()
            en = bool((it or {}).get('enabled', True))
            if not ch or not ev:
                continue
            cur.execute(
                f"INSERT INTO user_notification_prefs (user_id, channel, event_type, enabled, updated_at) "
                f"VALUES ({_PH},{_PH},{_PH},{_PH},CURRENT_TIMESTAMP)",
                (uid, ch, ev, en)
            )
    _write_audit('notification_prefs.updated', 'user', str(uid), {'count': len(items)})
    return jsonify({'success': True}), 200


@app.route('/api/search', methods=['GET'])
@login_required
@audit_action('search.global', 'search')
def api_search_global():
    q = str(request.args.get('q') or '').strip()
    types = str(request.args.get('types') or 'scans,users,companies,violations').strip().lower().split(',')
    if len(q) < 2:
        return jsonify({'success': True, 'query': q, 'results': []}), 200
    user = get_user_by_id(session.get('user_id'))
    company_id = int(_resolve_company_id_for_user(user) or 0) if user else 0
    results = []
    with get_api_db_cursor() as cur:
        if 'scans' in types:
            cur.execute(
                f"SELECT id, machine_name, minecraft_username, started_at FROM scans "
                f"WHERE deleted_at IS NULL AND company_id = {_PH} AND (machine_name ILIKE {_PH} OR minecraft_username ILIKE {_PH}) "
                f"ORDER BY id DESC LIMIT 20",
                (company_id, f"%{q}%", f"%{q}%")
            )
            for r in (cur.fetchall() or []):
                d = dict(r) if not isinstance(r, dict) else r
                label = f"Scan #{d.get('id')} · {(d.get('machine_name') or '')} · {(d.get('minecraft_username') or '')}"
                results.append({'type': 'scan', 'id': d.get('id'), 'label': label, 'highlight': q})
        if 'users' in types:
            cur.execute(
                f"SELECT id, username, email FROM users WHERE deleted_at IS NULL AND company_id = {_PH} "
                f"AND (username ILIKE {_PH} OR email ILIKE {_PH}) ORDER BY id DESC LIMIT 20",
                (company_id, f"%{q}%", f"%{q}%")
            )
            for r in (cur.fetchall() or []):
                d = dict(r) if not isinstance(r, dict) else r
                results.append({'type': 'user', 'id': d.get('id'), 'label': f"{d.get('username')} <{d.get('email')}>", 'highlight': q})
        if 'companies' in types and is_admin(user):
            cur.execute(
                f"SELECT id, name FROM companies WHERE deleted_at IS NULL AND name ILIKE {_PH} ORDER BY id DESC LIMIT 20",
                (f"%{q}%",)
            )
            for r in (cur.fetchall() or []):
                d = dict(r) if not isinstance(r, dict) else r
                results.append({'type': 'company', 'id': d.get('id'), 'label': d.get('name'), 'highlight': q})
        if 'violations' in types:
            cur.execute(
                f"SELECT id, check_name, level, player_name FROM plugin_violations "
                f"WHERE company_id = {_PH} AND (check_name ILIKE {_PH} OR player_name ILIKE {_PH}) "
                f"ORDER BY id DESC LIMIT 20",
                (company_id, f"%{q}%", f"%{q}%")
            )
            for r in (cur.fetchall() or []):
                d = dict(r) if not isinstance(r, dict) else r
                results.append({'type': 'violation', 'id': d.get('id'), 'label': f"{d.get('player_name')} · {d.get('check_name')} · {d.get('level')}", 'highlight': q})
    return jsonify({'success': True, 'query': q, 'results': results[:100]}), 200


@app.route('/api/invitations', methods=['GET', 'POST'])
@login_required
@audit_action('invitations.manage', 'invitation')
def api_invitations():
    user = get_user_by_id(session.get('user_id'))
    company_id = int(_resolve_company_id_for_user(user) or 0) if user else 0
    if company_id <= 0:
        return jsonify({'success': False, 'error': 'Sin company'}), 400
    if request.method == 'GET':
        with get_api_db_cursor() as cur:
            cur.execute(
                f"SELECT id, email, role, token, expires_at, accepted_at, created_at FROM invitations "
                f"WHERE company_id = {_PH} ORDER BY id DESC LIMIT 200",
                (company_id,)
            )
            rows = cur.fetchall() or []
        return jsonify({'success': True, 'items': [dict(r) if not isinstance(r, dict) else r for r in rows]}), 200
    data = request.json or {}
    email = str(data.get('email') or '').strip().lower()
    role = str(data.get('role') or 'staff').strip().lower()
    if '@' not in email:
        return jsonify({'success': False, 'error': 'email inválido'}), 400
    token = secrets.token_urlsafe(24)
    expires_at = (datetime.datetime.utcnow() + datetime.timedelta(days=7)).isoformat()
    with get_api_db_cursor() as cur:
        iid = _insert_id(
            cur,
            f"INSERT INTO invitations (email, company_id, role, token, expires_at, created_by) "
            f"VALUES ({_PH},{_PH},{_PH},{_PH},{_PH},{_PH})",
            (email, company_id, role, token, expires_at, int(session.get('user_id') or 0))
        )
    print(f"[invitation] send placeholder email={email} token={token}")
    return jsonify({'success': True, 'id': iid, 'token': token}), 200


@app.route('/api/invitations/accept/<token>', methods=['POST'])
def api_invitations_accept(token: str):
    with get_api_db_cursor() as cur:
        cur.execute(
            f"SELECT id, email, company_id, role, expires_at, accepted_at FROM invitations WHERE token = {_PH} LIMIT 1",
            (token,)
        )
        row = cur.fetchone()
        if not row:
            return jsonify({'success': False, 'error': 'Invitación no encontrada'}), 404
        d = dict(row) if not isinstance(row, dict) else row
        if d.get('accepted_at'):
            return jsonify({'success': False, 'error': 'Invitación ya usada'}), 400
        try:
            if str(d.get('expires_at')) < datetime.datetime.utcnow().isoformat():
                return jsonify({'success': False, 'error': 'Invitación expirada'}), 400
        except Exception:
            pass
        cur.execute(f"UPDATE invitations SET accepted_at = CURRENT_TIMESTAMP WHERE id = {_PH}", (int(d.get('id') or 0),))
    return jsonify({'success': True, 'company_id': d.get('company_id'), 'role': d.get('role'), 'email': d.get('email')}), 200


def recalc_all_trust_scores():
    try:
        with get_api_db_cursor() as cur:
            cur.execute("SELECT id, company_id, created_at, COALESCE(totp_enabled,FALSE) AS totp_enabled FROM users WHERE deleted_at IS NULL")
            users = cur.fetchall() or []
            for u in users:
                d = dict(u) if not isinstance(u, dict) else u
                uid = int(d.get('id') or 0)
                cid = int(d.get('company_id') or 0)
                created_at = d.get('created_at')
                try:
                    age_days = max(0.0, (datetime.datetime.utcnow() - (created_at if isinstance(created_at, datetime.datetime) else datetime.datetime.utcnow())).total_seconds() / 86400.0)
                except Exception:
                    age_days = 0.0
                cur.execute(f"SELECT COUNT(*) AS c FROM scans WHERE deleted_at IS NULL AND company_id = {_PH} AND created_by = {_PH}", (cid, str(uid)))
                scans_count = int((dict(cur.fetchone() or {}).get('c') or 0))
                cur.execute(f"SELECT COUNT(*) AS c FROM ai_decisions_log WHERE company_id = {_PH} AND action IN ('ban','kick')", (cid,))
                oracle_flags = int((dict(cur.fetchone() or {}).get('c') or 0))
                score, factors = _calculate_trust_score({
                    'account_age_days': age_days,
                    'scans_count': scans_count,
                    'oracle_flags': oracle_flags,
                    'mfa_enabled': bool(d.get('totp_enabled') or False),
                    'profile_complete': True,
                })
                cur.execute(f"SELECT id FROM user_trust_scores WHERE user_id = {_PH}", (uid,))
                if cur.fetchone():
                    cur.execute(
                        f"UPDATE user_trust_scores SET score = {_PH}, factors_json = {_PH}, updated_at = CURRENT_TIMESTAMP WHERE user_id = {_PH}",
                        (score, json.dumps(factors), uid)
                    )
                else:
                    cur.execute(
                        f"INSERT INTO user_trust_scores (user_id, score, factors_json, updated_at) VALUES ({_PH},{_PH},{_PH},CURRENT_TIMESTAMP)",
                        (uid, score, json.dumps(factors))
                    )
    except Exception as e:
        print(f"[trust_score] recalc error: {e}")


@app.route('/api/users/<int:user_id>/trust-score', methods=['GET'])
@login_required
@admin_required
def api_user_trust_score(user_id: int):
    with get_api_db_cursor() as cur:
        cur.execute(
            f"SELECT user_id, score, factors_json, updated_at FROM user_trust_scores WHERE user_id = {_PH} LIMIT 1",
            (user_id,)
        )
        row = cur.fetchone()
    if not row:
        return jsonify({'success': False, 'error': 'Trust score no disponible'}), 404
    d = dict(row) if not isinstance(row, dict) else row
    try:
        factors = json.loads(d.get('factors_json') or '{}')
    except Exception:
        factors = {}
    return jsonify({'success': True, 'user_id': d.get('user_id'), 'score': d.get('score'), 'factors': factors, 'updated_at': str(d.get('updated_at') or '')}), 200


@app.route('/api/admin/backup/create', methods=['POST'])
@login_required
@require_superadmin
@audit_action('admin.backup.create', 'backup')
def api_admin_backup_create():
    data = request.json or {}
    password = str(data.get('password') or '').strip()
    if len(password) < 8:
        return jsonify({'success': False, 'error': 'password requerido (>=8 chars)'}), 400
    with get_api_db_cursor() as cur:
        cur.execute("SELECT id, username, email, company_id FROM users WHERE deleted_at IS NULL")
        users = [dict(r) if not isinstance(r, dict) else r for r in (cur.fetchall() or [])]
        cur.execute("SELECT id, machine_name, minecraft_username, company_id, started_at FROM scans WHERE deleted_at IS NULL ORDER BY id DESC LIMIT 5000")
        scans = [dict(r) if not isinstance(r, dict) else r for r in (cur.fetchall() or [])]
    payload = {'users': users, 'scans': scans}
    doc = _encrypt_backup_payload(payload, password)
    backup_id = _save_backup(doc)
    _rotate_backups(30)
    return jsonify({'success': True, 'backup_id': backup_id}), 200


@app.route('/api/admin/backup/list', methods=['GET'])
@login_required
@require_superadmin
def api_admin_backup_list():
    return jsonify({'success': True, 'items': _list_backups()}), 200


@app.route('/api/admin/backup/restore/<backup_id>', methods=['POST'])
@login_required
@require_superadmin
@audit_action('admin.backup.restore', 'backup')
def api_admin_backup_restore(backup_id: str):
    data = request.json or {}
    confirm = str(data.get('confirm_code') or '').strip()
    if confirm != 'RESTORE_CONFIRM':
        return jsonify({'success': False, 'error': 'confirm_code inválido'}), 400
    doc = _read_backup(backup_id)
    if not doc:
        return jsonify({'success': False, 'error': 'backup no encontrado'}), 404
    # Restauración real peligrosa: en esta fase devolvemos dry-run summary.
    return jsonify({'success': True, 'mode': 'dry-run', 'backup_id': backup_id, 'keys': list(doc.keys())}), 200


@app.route('/api/gdpr/export', methods=['POST'])
@login_required
@audit_action('gdpr.export', 'user')
def api_gdpr_export():
    uid = int(session.get('user_id') or 0)
    user = get_user_by_id(uid)
    company_id = int(_resolve_company_id_for_user(user) or 0) if user else 0
    with get_api_db_cursor() as cur:
        cur.execute(f"SELECT id, username, email, company_id FROM users WHERE id = {_PH}", (uid,))
        user_rows = [dict(r) if not isinstance(r, dict) else r for r in (cur.fetchall() or [])]
        cur.execute(f"SELECT id, machine_name, minecraft_username, started_at FROM scans WHERE company_id = {_PH} AND deleted_at IS NULL ORDER BY id DESC LIMIT 5000", (company_id,))
        scan_rows = [dict(r) if not isinstance(r, dict) else r for r in (cur.fetchall() or [])]
        cur.execute(f"SELECT id, timestamp, action, resource_type, details FROM audit_log_v2 WHERE user_id = {_PH} ORDER BY id DESC LIMIT 5000", (uid,))
        audit_rows = [dict(r) if not isinstance(r, dict) else r for r in (cur.fetchall() or [])]
    z = _build_user_export_zip({'user': user_rows, 'scans': scan_rows, 'audit': audit_rows})
    return Response(z, mimetype='application/zip', headers={'Content-Disposition': 'attachment; filename=gdpr-export.zip'})


@app.route('/api/gdpr/delete-request', methods=['POST'])
@login_required
@audit_action('gdpr.delete_request', 'user')
def api_gdpr_delete_request():
    uid = int(session.get('user_id') or 0)
    with get_api_db_cursor() as cur:
        cur.execute(
            f"UPDATE users SET deleted_at = CURRENT_TIMESTAMP + INTERVAL '30 days' WHERE id = {_PH}",
            (uid,)
        )
    return jsonify({'success': True, 'message': 'Delete request programada (30 días)'}), 200


@app.route('/api/gdpr/cancel-delete', methods=['POST'])
@login_required
@audit_action('gdpr.cancel_delete', 'user')
def api_gdpr_cancel_delete():
    uid = int(session.get('user_id') or 0)
    with get_api_db_cursor() as cur:
        cur.execute(
            f"UPDATE users SET deleted_at = NULL WHERE id = {_PH} AND deleted_at > CURRENT_TIMESTAMP",
            (uid,)
        )
    return jsonify({'success': True}), 200


@app.route('/api/filters/export', methods=['GET'])
@login_required
def api_filters_export():
    user = get_user_by_id(session.get('user_id'))
    req_company = int(request.args.get('company_id') or 0)
    company_id = req_company if req_company > 0 else int(_resolve_company_id_for_user(user) or 0)
    if company_id <= 0:
        return jsonify({'success': False, 'error': 'company_id inválido'}), 400
    if not _can_manage_company_notifications(user, company_id):
        return jsonify({'success': False, 'error': 'No autorizado'}), 403
    with get_api_db_cursor() as cur:
        cur.execute(
            f"SELECT gp.id, gp.name, gp.slug, gp.filter_rules "
            f"FROM company_game_profile cgp JOIN game_profiles gp ON gp.id = cgp.game_profile_id "
            f"WHERE cgp.company_id = {_PH} LIMIT 1",
            (company_id,)
        )
        gp = cur.fetchone()
        cur.execute(
            f"SELECT feature_name, false_positive_count, true_positive_count, weight_adjustment, agg_date "
            f"FROM ai_feedback_aggregations WHERE agg_date >= CURRENT_DATE - INTERVAL '30 days'",
        )
        aggs = cur.fetchall() or []
        cur.execute(
            f"SELECT shared_rule_id FROM company_shared_rules WHERE company_id = {_PH}",
            (company_id,)
        )
        shared = [int(_row_get(r, 0, 'shared_rule_id') or 0) for r in (cur.fetchall() or [])]
    out = {
        'company_id': company_id,
        'exported_at': datetime.datetime.utcnow().isoformat() + 'Z',
        'game_profile': None,
        'fp_feedback_aggregations': [dict(r) if not isinstance(r, dict) else r for r in aggs],
        'shared_rule_ids': shared,
    }
    if gp:
        d = dict(gp) if not isinstance(gp, dict) else gp
        out['game_profile'] = {
            'id': d.get('id'),
            'name': d.get('name'),
            'slug': d.get('slug'),
            'filter_rules': json.loads(d.get('filter_rules') or '{}'),
        }
    return jsonify({'success': True, 'data': out}), 200


@app.route('/api/filters/import', methods=['POST'])
@login_required
def api_filters_import():
    user = get_user_by_id(session.get('user_id'))
    data = request.json or {}
    company_id = int(data.get('company_id') or _resolve_company_id_for_user(user) or 0)
    if company_id <= 0:
        return jsonify({'success': False, 'error': 'company_id inválido'}), 400
    if not _can_manage_company_notifications(user, company_id):
        return jsonify({'success': False, 'error': 'No autorizado'}), 403
    payload = data.get('data') or {}
    gp = payload.get('game_profile') or {}
    aggs = payload.get('fp_feedback_aggregations') or []
    shared_ids = payload.get('shared_rule_ids') or []
    try:
        with get_api_db_cursor() as cur:
            if gp and gp.get('slug'):
                cur.execute(f"SELECT id FROM game_profiles WHERE slug = {_PH} LIMIT 1", (str(gp.get('slug')),))
                row = cur.fetchone()
                gid = int(_row_get(row, 0, 'id') or 0) if row else 0
                if gid <= 0:
                    gid = _insert_id(
                        cur,
                        f"INSERT INTO game_profiles (name, slug, filter_rules) VALUES ({_PH},{_PH},{_PH})",
                        (str(gp.get('name') or gp.get('slug')), str(gp.get('slug')), json.dumps(gp.get('filter_rules') or {}))
                    ) or 0
                cur.execute(f"DELETE FROM company_game_profile WHERE company_id = {_PH}", (company_id,))
                cur.execute(f"INSERT INTO company_game_profile (company_id, game_profile_id, updated_at) VALUES ({_PH},{_PH},CURRENT_TIMESTAMP)",
                            (company_id, gid))
            for a in aggs[:200]:
                cur.execute(
                    f"INSERT INTO ai_feedback_aggregations (agg_date, feature_name, false_positive_count, true_positive_count, weight_adjustment) "
                    f"VALUES ({_PH},{_PH},{_PH},{_PH},{_PH})",
                    (
                        str((a or {}).get('agg_date') or datetime.date.today().isoformat()),
                        str((a or {}).get('feature_name') or '')[:80],
                        int((a or {}).get('false_positive_count') or 0),
                        int((a or {}).get('true_positive_count') or 0),
                        float((a or {}).get('weight_adjustment') or 0.0),
                    )
                )
            for rid in shared_ids[:200]:
                try:
                    cur.execute(f"INSERT INTO company_shared_rules (company_id, shared_rule_id) VALUES ({_PH},{_PH})",
                                (company_id, int(rid)))
                except Exception:
                    pass
        _app_cache.delete(f"company_game_profile_rules:{company_id}")
        _app_cache.delete(f"ai_weights:{company_id}")
        return jsonify({'success': True}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/audit/search', methods=['GET'])
@login_required
@require_superadmin
@_limit("30 per minute")
def api_audit_search():
    limit = max(1, min(200, int(request.args.get('limit', 50) or 50)))
    cursor_id = int(request.args.get('cursor_id', 0) or 0)
    cursor_token = str(request.args.get('cursor') or '').strip()
    if cursor_id <= 0 and cursor_token and _Paginator is not None:
        payload = _Paginator.decode_cursor(cursor_token)
        cursor_id = int(payload.get('last_id') or 0)
    user_id = int(request.args.get('user_id', 0) or 0)
    action = str(request.args.get('action') or '').strip()
    resource_type = str(request.args.get('resource_type') or '').strip()
    where = ["1=1"]
    params: list = []
    if cursor_id > 0:
        where.append(f"id < {_PH}")
        params.append(cursor_id)
    if user_id > 0:
        where.append(f"user_id = {_PH}")
        params.append(user_id)
    if action:
        where.append(f"action = {_PH}")
        params.append(action)
    if resource_type:
        where.append(f"resource_type = {_PH}")
        params.append(resource_type)
    where_sql = " AND ".join(where)
    with get_api_db_cursor() as cur:
        cur.execute(
            f"SELECT id, timestamp, user_id, action, resource_type, resource_id, details, ip_address, user_agent "
            f"FROM audit_log_v2 WHERE {where_sql} ORDER BY id DESC LIMIT {_PH}",
            tuple(params + [limit])
        )
        rows = cur.fetchall() or []
    items = []
    for r in rows:
        d = dict(r) if not isinstance(r, dict) else r
        details_raw = d.get('details')
        try:
            details = json.loads(details_raw) if isinstance(details_raw, str) else details_raw
        except Exception:
            details = {'raw': str(details_raw)}
        items.append({
            'id': d.get('id'),
            'timestamp': str(d.get('timestamp') or ''),
            'user_id': d.get('user_id'),
            'action': d.get('action'),
            'resource_type': d.get('resource_type'),
            'resource_id': d.get('resource_id'),
            'details': details,
            'ip_address': d.get('ip_address'),
            'user_agent': d.get('user_agent'),
        })
    next_cursor_id = items[-1]['id'] if items else None
    next_cursor = _Paginator.encode_cursor({'last_id': next_cursor_id}) if (next_cursor_id and _Paginator is not None) else None
    return jsonify({'success': True, 'items': items, 'next_cursor_id': next_cursor_id, 'next_cursor': next_cursor}), 200


@app.route('/api/openapi.json', methods=['GET'])
def api_openapi_json():
    try:
        with open(os.path.join(os.path.dirname(__file__), 'static', 'openapi.json'), 'r', encoding='utf-8') as f:
            spec = json.load(f)
        return jsonify(spec), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/docs', methods=['GET'])
def api_docs():
    html = """
    <!doctype html><html><head><meta charset="utf-8"><title>Argus API Docs</title></head>
    <body style="margin:0"><div id="swagger-ui"></div>
    <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
    <script>window.ui = SwaggerUIBundle({url:'/api/openapi.json',dom_id:'#swagger-ui'});</script>
    </body></html>
    """
    return Response(html, mimetype='text/html')


def aggregate_fp_feedback():
    """Agrega feedback del último mes y guarda ajustes de multiplicadores."""
    try:
        with get_api_db_cursor() as cur:
            cur.execute(
                f"SELECT COALESCE(reasoning,''), COUNT(*) AS c "
                f"FROM ai_feedback WHERE created_at >= CURRENT_DATE - INTERVAL '30 days' "
                f"GROUP BY COALESCE(reasoning,'')"
            )
            rows = cur.fetchall() or []
            for r in rows:
                d = dict(r) if not isinstance(r, dict) else r
                reason = str(d.get('coalesce') or d.get('reasoning') or '').lower()
                cnt = int(d.get('c') or 0)
                feature_name = ''
                if 'legit' in reason or 'false positive' in reason or 'fp' in reason:
                    feature_name = 'legitimate_client_detected'
                if not feature_name:
                    continue
                adj = -min(0.25, 0.02 * cnt)
                cur.execute(
                    f"INSERT INTO ai_feedback_aggregations (agg_date, feature_name, false_positive_count, true_positive_count, weight_adjustment) "
                    f"VALUES (CURRENT_DATE, {_PH}, {_PH}, 0, {_PH})",
                    (feature_name, cnt, adj)
                )
        _app_cache.delete("ai_weights:0")
    except Exception as e:
        print(f"[fp_aggregation] error: {e}")


def audit_retention_cleanup():
    try:
        with get_api_db_cursor() as cur:
            cur.execute("DELETE FROM audit_log_v2 WHERE timestamp < CURRENT_TIMESTAMP - INTERVAL '365 days'")
    except Exception as e:
        print(f"[audit_v2] cleanup error: {e}")


@app.route('/api/me/preferences', methods=['GET', 'PUT'])
@login_required
def api_me_preferences():
    _plugin_schema_guard()
    uid = int(session.get('user_id') or 0)
    if uid <= 0:
        return jsonify({'success': False, 'error': 'No autenticado'}), 401
    if request.method == 'GET':
        cache_key = f"user_prefs:{uid}"
        hit = _app_cache.get(cache_key)
        if isinstance(hit, dict):
            return jsonify({'success': True, 'preferences': hit}), 200
        with get_api_db_cursor() as cur:
            cur.execute(
                f"SELECT pref_key, pref_value FROM user_preferences WHERE user_id = {_PH}",
                (uid,)
            )
            prefs = {}
            for r in (cur.fetchall() or []):
                d = dict(r) if not isinstance(r, dict) else r
                prefs[str(d.get('pref_key') or '')] = d.get('pref_value')
        _app_cache.set(cache_key, prefs, ttl=300)
        return jsonify({'success': True, 'preferences': prefs}), 200
    data = request.json or {}
    prefs = data.get('preferences') or {}
    if not isinstance(prefs, dict):
        return jsonify({'success': False, 'error': 'preferences inválido'}), 400
    try:
        with get_api_db_cursor() as cur:
            for k, v in list(prefs.items())[:30]:
                key = str(k or '').strip()[:64]
                if not key:
                    continue
                val = str(v)[:300]
                cur.execute(
                    f"SELECT id FROM user_preferences WHERE user_id = {_PH} AND pref_key = {_PH}",
                    (uid, key)
                )
                ex = cur.fetchone()
                if ex:
                    cur.execute(
                        f"UPDATE user_preferences SET pref_value = {_PH}, updated_at = CURRENT_TIMESTAMP "
                        f"WHERE user_id = {_PH} AND pref_key = {_PH}",
                        (val, uid, key)
                    )
                else:
                    cur.execute(
                        f"INSERT INTO user_preferences (user_id, pref_key, pref_value, updated_at) "
                        f"VALUES ({_PH},{_PH},{_PH},CURRENT_TIMESTAMP)",
                        (uid, key, val)
                    )
        _app_cache.delete(f"user_prefs:{uid}")
        return jsonify({'success': True}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ──────────────────────────────────────────────────────────────────────
#  Pack 45: ML model helpers (load/save/train)
# ──────────────────────────────────────────────────────────────────────

# Cache simple en memoria de modelos cargados (TTL 60s)
_ML_MODEL_CACHE: dict[tuple[int, str], tuple[float, object]] = {}
_ML_MODEL_CACHE_TTL_S = 60.0


def _load_ml_model(cursor, company_id: int, model_kind: str):
    """Carga modelo desde ai_model_state. Fallback global (company_id=0).
    None si no existe entrenado todavia.
    """
    import time as _t
    key = (company_id, model_kind)
    now = _t.time()
    cached = _ML_MODEL_CACHE.get(key)
    if cached and (now - cached[0]) < _ML_MODEL_CACHE_TTL_S:
        return cached[1]
    state_json = None
    try:
        cursor.execute(
            f"SELECT state_json FROM ai_model_state "
            f"WHERE company_id = {_PH} AND model_kind = {_PH}",
            (company_id, model_kind)
        )
        row = cursor.fetchone()
        if row:
            row = dict(row) if not isinstance(row, dict) else row
            state_json = row.get('state_json')
        if not state_json:
            cursor.execute(
                f"SELECT state_json FROM ai_model_state "
                f"WHERE company_id = 0 AND model_kind = {_PH}",
                (model_kind,)
            )
            row = cursor.fetchone()
            if row:
                row = dict(row) if not isinstance(row, dict) else row
                state_json = row.get('state_json')
    except Exception as e:
        print(f"[ml_load] error consultando ai_model_state {model_kind}: {e}")
        return None
    if not state_json:
        _ML_MODEL_CACHE[key] = (now, None)
        return None
    try:
        if model_kind == 'logreg':
            import argus_ai_trainer as _t
            m = _t.LogisticRegression.from_json(state_json)
        elif model_kind == 'knn':
            import argus_ai_trainer as _t
            m = _t.KNNCheaterClassifier.from_json(state_json)
        elif model_kind == 'temporal':
            import argus_ai_trainer as _t
            m = _t.TemporalPatternDetector.from_json(state_json)
        else:
            m = None
    except Exception as e:
        print(f"[ml_load] error deserializando {model_kind}: {e}")
        m = None
    _ML_MODEL_CACHE[key] = (now, m)
    return m


def _save_ml_model(cursor, company_id: int, model_kind: str, model) -> bool:
    """Persiste un modelo entrenado en ai_model_state (UPSERT)."""
    try:
        state_json = model.to_json()
        version       = getattr(model, 'version', 1)
        samples       = getattr(model, 'samples_trained', 0)
        accuracy      = getattr(model, 'last_accuracy', 0.0)
        precision_v   = getattr(model, 'last_precision', 0.0)
        recall        = getattr(model, 'last_recall', 0.0)
        f1            = getattr(model, 'last_f1', 0.0)
        loss          = getattr(model, 'last_loss', 0.0)
        cursor.execute(
            f"SELECT id FROM ai_model_state WHERE company_id = {_PH} AND model_kind = {_PH}",
            (company_id, model_kind)
        )
        row = cursor.fetchone()
        if row:
            cursor.execute(
                f"UPDATE ai_model_state SET state_json = {_PH}, version = {_PH}, "
                f"samples_trained = {_PH}, accuracy = {_PH}, precision = {_PH}, "
                f"recall = {_PH}, f1 = {_PH}, last_loss = {_PH}, "
                f"trained_at = CURRENT_TIMESTAMP "
                f"WHERE company_id = {_PH} AND model_kind = {_PH}",
                (state_json, version, samples, accuracy, precision_v,
                 recall, f1, loss, company_id, model_kind)
            )
        else:
            cursor.execute(
                f"INSERT INTO ai_model_state "
                f"(company_id, model_kind, state_json, version, samples_trained, "
                f"accuracy, precision, recall, f1, last_loss) "
                f"VALUES ({_PH},{_PH},{_PH},{_PH},{_PH},{_PH},{_PH},{_PH},{_PH},{_PH})",
                (company_id, model_kind, state_json, version, samples,
                 accuracy, precision_v, recall, f1, loss)
            )
        # Invalidar cache
        _ML_MODEL_CACHE.pop((company_id, model_kind), None)
        return True
    except Exception as e:
        print(f"[ml_save] error guardando {model_kind}: {e}")
        return False


def _upsert_player_profile(cursor, company_id: int, player_uuid: str,
                            player_name: str, feature_vector: list[float],
                            label: float | None = None,
                            label_confidence: float = 0.0,
                            label_source: str | None = None) -> None:
    """Guarda o actualiza el perfil de feature vector del jugador."""
    fv_json = json.dumps(feature_vector)
    cursor.execute(
        f"SELECT id FROM ai_player_profiles "
        f"WHERE company_id = {_PH} AND player_uuid = {_PH}",
        (company_id, player_uuid)
    )
    row = cursor.fetchone()
    if row:
        if label is not None:
            cursor.execute(
                f"UPDATE ai_player_profiles SET "
                f"player_name = {_PH}, feature_vector_json = {_PH}, "
                f"last_label = {_PH}, last_label_confidence = {_PH}, "
                f"last_label_source = {_PH}, "
                f"last_updated_at = CURRENT_TIMESTAMP "
                f"WHERE company_id = {_PH} AND player_uuid = {_PH}",
                (player_name, fv_json, label, label_confidence, label_source,
                 company_id, player_uuid)
            )
        else:
            cursor.execute(
                f"UPDATE ai_player_profiles SET "
                f"player_name = {_PH}, feature_vector_json = {_PH}, "
                f"last_updated_at = CURRENT_TIMESTAMP "
                f"WHERE company_id = {_PH} AND player_uuid = {_PH}",
                (player_name, fv_json, company_id, player_uuid)
            )
    else:
        cursor.execute(
            f"INSERT INTO ai_player_profiles "
            f"(company_id, player_uuid, player_name, feature_vector_json, "
            f"last_label, last_label_confidence, last_label_source) "
            f"VALUES ({_PH},{_PH},{_PH},{_PH},{_PH},{_PH},{_PH})",
            (company_id, player_uuid, player_name, fv_json,
             label, label_confidence, label_source)
        )


def _collect_training_dataset(cursor, company_id: int,
                              include_synthetic: bool = True,
                              min_confidence: float = 0.45):
    """
    Junta todos los samples disponibles para training:
      - feedback explicito del staff (weight = 1.0 * confidence)
      - auto-labels combinados (weight = 0.6 * confidence)
      - synthetic bootstrap (weight = 0.4)

    Cada sample = (feature_vector, label, weight). Si un (company, player_uuid)
    tiene MULTIPLES labels, se usa el agregado weighted.

    Devuelve (X, y, weights, n_real, n_synthetic).
    """
    import argus_ai_features as F
    import argus_ai_trainer as T

    X: list[list[float]] = []
    y: list[float] = []
    w: list[float] = []
    n_real = 0
    n_synthetic = 0

    # 1. Cargar feedback explicito
    try:
        cursor.execute(
            f"SELECT decision_id, player_uuid, player_name, label, confidence "
            f"FROM ai_feedback WHERE company_id = {_PH}",
            (company_id,)
        )
        feedback_rows = cursor.fetchall() or []
    except Exception as e:
        print(f"[ml_train] error fetching feedback: {e}")
        feedback_rows = []

    # 2. Cargar auto-labels (combined)
    try:
        cursor.execute(
            f"SELECT decision_id, player_uuid, player_name, label, confidence, source "
            f"FROM ai_auto_labels WHERE company_id = {_PH} AND confidence >= {_PH}",
            (company_id, min_confidence)
        )
        auto_rows = cursor.fetchall() or []
    except Exception as e:
        print(f"[ml_train] error fetching auto-labels: {e}")
        auto_rows = []

    # Mapear (decision_id | player_uuid) → label/conf
    # feedback explicito siempre wins sobre auto-label
    samples_by_key: dict[str, dict] = {}

    for row in auto_rows:
        row = dict(row) if not isinstance(row, dict) else row
        key = f"d:{row.get('decision_id')}" if row.get('decision_id') else f"p:{row.get('player_uuid')}"
        prev = samples_by_key.get(key)
        if prev and prev.get('source') == 'feedback':
            continue
        if prev and prev.get('confidence', 0) > float(row.get('confidence') or 0):
            continue
        samples_by_key[key] = {
            'decision_id': row.get('decision_id'),
            'player_uuid': row.get('player_uuid'),
            'player_name': row.get('player_name'),
            'label': float(row.get('label') or 0),
            'confidence': float(row.get('confidence') or 0),
            'source': 'auto',
        }

    for row in feedback_rows:
        row = dict(row) if not isinstance(row, dict) else row
        key = f"d:{row.get('decision_id')}" if row.get('decision_id') else f"p:{row.get('player_uuid')}"
        samples_by_key[key] = {
            'decision_id': row.get('decision_id'),
            'player_uuid': row.get('player_uuid'),
            'player_name': row.get('player_name'),
            'label': float(row.get('label') or 0),
            'confidence': float(row.get('confidence') or 1.0),
            'source': 'feedback',
        }

    # 3. Recuperar feature_vector para cada sample usando ai_player_profiles
    #    o ai_decisions_log.evidence_json
    decision_ids = [s['decision_id'] for s in samples_by_key.values() if s.get('decision_id')]
    decisions_features: dict[int, list[float]] = {}
    if decision_ids:
        ph_list = ','.join([_PH] * len(decision_ids))
        try:
            cursor.execute(
                f"SELECT id, evidence_json FROM ai_decisions_log "
                f"WHERE id IN ({ph_list})",
                tuple(decision_ids)
            )
            for r in cursor.fetchall() or []:
                r = dict(r) if not isinstance(r, dict) else r
                try:
                    ev = json.loads(r.get('evidence_json') or '{}')
                    eu = ev.get('evidence_used') or ev
                    # evidence_used no tiene un raw evidence — para reentrenar
                    # confiable, mejor extraer del player profile si esta.
                    decisions_features[int(r['id'])] = None  # placeholder, usaremos profile
                except Exception:
                    pass
        except Exception:
            pass

    # Cargar profiles de los uuids relevantes
    uuids = [s['player_uuid'] for s in samples_by_key.values() if s.get('player_uuid')]
    profiles_by_uuid: dict[str, list[float]] = {}
    if uuids:
        unique_uuids = list(set(uuids))
        ph_list = ','.join([_PH] * len(unique_uuids))
        try:
            cursor.execute(
                f"SELECT player_uuid, feature_vector_json FROM ai_player_profiles "
                f"WHERE company_id = {_PH} AND player_uuid IN ({ph_list})",
                (company_id, *unique_uuids)
            )
            for r in cursor.fetchall() or []:
                r = dict(r) if not isinstance(r, dict) else r
                try:
                    profiles_by_uuid[r['player_uuid']] = json.loads(r['feature_vector_json'])
                except Exception:
                    pass
        except Exception:
            pass

    for s in samples_by_key.values():
        fv = None
        if s.get('player_uuid') and s['player_uuid'] in profiles_by_uuid:
            fv = profiles_by_uuid[s['player_uuid']]
        if fv is None or len(fv) != F.n_features():
            continue
        weight = s['confidence'] * (1.0 if s['source'] == 'feedback' else 0.65)
        if weight < 0.15:
            continue
        X.append(fv)
        y.append(float(s['label']))
        w.append(weight)
        n_real += 1

    # 4. Synthetic bootstrap si esta habilitado y no tenemos suficiente data real
    if include_synthetic:
        # Si tenemos POCOS samples reales, hacer bootstrap completo (480 samples)
        # Si tenemos MUCHOS reales, agregar bootstrap reducido para regularizar
        if n_real < 50:
            sx, sy, sw = T.generate_bootstrap_dataset(
                F.extract_features,
                n_cheaters=200, n_clean=200, n_borderline=80,
                seed=42
            )
        else:
            sx, sy, sw = T.generate_bootstrap_dataset(
                F.extract_features,
                n_cheaters=50, n_clean=50, n_borderline=20,
                seed=42
            )
        X.extend(sx); y.extend(sy); w.extend(sw)
        n_synthetic = len(sx)

    return X, y, w, n_real, n_synthetic


def _train_models_for(company_id: int = 0, triggered_by: str = 'cron') -> dict:
    """
    Re-entrena los 3 modelos (logreg, knn, temporal) para una company.
    company_id=0 entrena modelos globales (defaults).

    Retorna dict con metricas + flag de cuales modelos se actualizaron.
    """
    import time as _t
    import argus_ai_features as F
    import argus_ai_trainer as T

    t0 = _t.time()
    result = {
        'company_id': company_id,
        'started_at': t0,
        'logreg': None, 'knn': None, 'temporal': None,
        'samples_real': 0, 'samples_synthetic': 0,
        'duration_ms': 0,
    }

    try:
        with get_api_db_cursor() as cursor:
            X, y, w, n_real, n_syn = _collect_training_dataset(cursor, company_id)
            result['samples_real'] = n_real
            result['samples_synthetic'] = n_syn
            if len(X) < 20:
                result['error'] = f'datos insuficientes: {len(X)} samples'
                return result

            # ── LogReg ─────────────────────────────────────────────
            lr = T.LogisticRegression(feature_names=F.FEATURE_NAMES,
                                       lr=0.05, l2=1e-4, seed=42)
            metrics = lr.fit(X, y, sample_weights=w, epochs=40, verbose=False)
            _save_ml_model(cursor, company_id, 'logreg', lr)
            result['logreg'] = metrics

            # Insertar history
            try:
                cursor.execute(
                    f"INSERT INTO ai_training_history "
                    f"(company_id, model_kind, samples_used, samples_synthetic, "
                    f"samples_real, epochs, loss, accuracy, precision, recall, f1, "
                    f"duration_ms, triggered_by) "
                    f"VALUES ({_PH},{_PH},{_PH},{_PH},{_PH},{_PH},{_PH},{_PH},{_PH},{_PH},{_PH},{_PH},{_PH})",
                    (company_id, 'logreg', len(X), n_syn, n_real, 40,
                     metrics.get('loss', 0), metrics.get('accuracy', 0),
                     metrics.get('precision', 0), metrics.get('recall', 0),
                     metrics.get('f1', 0),
                     int((_t.time() - t0) * 1000), triggered_by)
                )
            except Exception:
                pass

            # ── KNN ────────────────────────────────────────────────
            knn = T.KNNCheaterClassifier(feature_names=F.FEATURE_NAMES, k=7)
            for i in range(len(X)):
                if w[i] < 0.3:  # solo ejemplos con peso decente
                    continue
                knn.add_example(T.KNNExample(
                    player_uuid=f'sample_{i}',
                    player_name=f'sample_{i}',
                    feature_vector=X[i],
                    label=y[i],
                    weight=w[i],
                    source='training_set',
                ))
            _save_ml_model(cursor, company_id, 'knn', knn)
            result['knn'] = {'size': knn.size(), **knn.class_counts()}

            # ── Temporal Markov ────────────────────────────────────
            tpd = T.TemporalPatternDetector()
            # Observar secuencias del bootstrap (las sintéticas tienen sequence)
            import random as _r
            rng = _r.Random(42)
            for _ in range(150):
                ev = T._synth_cheater(rng)
                seq = F.extract_sequence(ev)
                tpd.observe(seq, 1.0)
            for _ in range(150):
                ev = T._synth_clean(rng)
                seq = F.extract_sequence(ev)
                tpd.observe(seq, 0.0)
            _save_ml_model(cursor, company_id, 'temporal', tpd)
            result['temporal'] = {
                'samples': tpd.samples_observed,
                'cheater_vocab': len(tpd.cheater_counts),
                'clean_vocab': len(tpd.clean_counts),
            }
    except Exception as e:
        result['error'] = f'{type(e).__name__}: {e}'
        print(f"[ml_train] error: {e}")

    result['duration_ms'] = int((_t.time() - t0) * 1000)
    return result


@app.route('/api/plugin/ai-evaluate', methods=['POST'])
def api_plugin_ai_evaluate():
    """El plugin Bukkit envia evidencia, recibe veredicto del Oracle.

    Body JSON:
      - player_uuid (str)
      - player_name (str)
      - violation: dict opcional con la nueva violation que dispara la eval
      - plugin_action: str opcional con la accion que el ViolationManager
        del plugin ya tomaria (none/watch/ss/kick/ban). El Oracle puede
        sobreescribirla a algo mas severo.

    Auth via X-Argus-Plugin-Key.

    Devuelve: {success, score, confidence, action, reasoning, top_factor,
                merged_action}.
    """
    _plugin_schema_guard()
    api_key = (
        request.headers.get('X-Argus-Plugin-Key')
        or request.headers.get('Authorization', '').replace('Bearer ', '').strip()
    )
    if not api_key:
        return jsonify({'success': False, 'error': 'API key requerida'}), 401

    body = request.get_json(silent=True) or {}
    player_uuid = (body.get('player_uuid') or '')[:40]
    player_name = (body.get('player_name') or '')[:64]
    if not player_uuid or not player_name:
        return jsonify({'success': False, 'error': 'player_uuid y player_name requeridos'}), 400
    new_violation = body.get('violation')
    plugin_action = body.get('plugin_action')

    try:
        import argus_ai_oracle as _oracle
        with get_api_db_cursor() as cursor:
            cursor.execute(
                f"SELECT id, company_id, label, is_active "
                f"FROM company_plugin_keys WHERE api_key = {_PH}",
                (api_key,)
            )
            row = cursor.fetchone()
            if not row:
                return jsonify({'success': False, 'error': 'API key invalida'}), 401
            row = dict(row) if not isinstance(row, dict) else row
            if not row.get('is_active'):
                return jsonify({'success': False, 'error': 'API key revocada'}), 403
            company_id = row['company_id']
            plugin_key_id = row['id']

            evidence = _build_ai_evidence(cursor, company_id, player_uuid, player_name, new_violation)
            weights = _get_ai_weights(company_id)

            # Pack 45: cargar modelos ML entrenados (si existen) para
            # evaluacion hybrid. Si no estan entrenados, degrada a heuristica.
            log_reg = _load_ml_model(cursor, company_id, 'logreg')
            knn     = _load_ml_model(cursor, company_id, 'knn')
            temporal = _load_ml_model(cursor, company_id, 'temporal')

            try:
                # Computar feature vector y secuencia ANTES de la evaluacion
                # para persistirlos junto al log de decision (sirven para
                # training futuro sin recomputar).
                from argus_ai_features import extract_features, extract_sequence
                ev_with_h = dict(evidence)
                # heuristic_score sera completado tras evaluacion base
                feature_vector = None
                sequence = extract_sequence(evidence)
            except Exception:
                feature_vector = None
                sequence = None

            decision = _oracle.evaluate_hybrid(
                evidence, weights,
                log_reg=log_reg, knn=knn, temporal=temporal,
                feature_vector=None,  # se computa adentro con heuristic_score correcto
                sequence=sequence,
            )

            # Re-extraer feature vector con heuristic_score real para persistencia
            try:
                from argus_ai_features import extract_features
                ev_with_h = dict(evidence)
                ev_with_h['heuristic_score'] = decision.evidence_used.get('heuristic_score', decision.score)
                feature_vector = extract_features(ev_with_h)
            except Exception:
                feature_vector = None

            merged_action = _oracle.merge_action_with_existing(decision.action, plugin_action)

            decision_id = _persist_ai_decision(cursor, company_id, plugin_key_id,
                                 player_uuid, player_name, decision,
                                 triggered_by=new_violation.get('check_name') if new_violation else 'manual')

            # Actualizar player profile con el feature vector mas reciente
            if feature_vector is not None:
                try:
                    _upsert_player_profile(cursor, company_id, player_uuid, player_name,
                                           feature_vector)
                except Exception as _e_pp:
                    print(f"[ai_profile] error upsert: {_e_pp}")

        return jsonify({
            'success': True,
            'score': decision.score,
            'confidence': decision.confidence,
            'action': decision.action,
            'merged_action': merged_action,
            'reasoning': decision.reasoning,
            'top_factor': decision.top_factor,
            'decision_id': decision_id,
            'evidence_used': decision.evidence_used,
        }), 200
    except Exception as e:
        print(f"ERROR api_plugin_ai_evaluate: {type(e).__name__}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/ai/scores', methods=['GET'])
@login_required
def api_ai_scores():
    """Lista de jugadores con su score actual del Oracle (top sospechosos).

    Aislamiento: super-admin global ve todo, staff de empresa solo su empresa.
    """
    _plugin_schema_guard()
    try:
        user = get_user_by_id(session.get('user_id'))
        if not user:
            return jsonify({'success': False, 'error': 'No autenticado'}), 401
        roles = user.get('roles') or []
        if isinstance(roles, str):
            try: roles = json.loads(roles)
            except Exception: roles = [roles]
        roles_lower = {str(r).lower() for r in roles}
        is_global_admin = bool(roles_lower & {'admin', 'owner', 'super_admin'})
        company_id = _resolve_company_id_for_user(user)
        limit = max(1, min(200, int(request.args.get('limit', 50))))
        min_score = float(request.args.get('min_score', 0.0))

        where = [f"score >= {_PH}"]
        params: list = [min_score]
        if not is_global_admin:
            if not company_id:
                return jsonify({'success': True, 'scores': []}), 200
            where.append(f"company_id = {_PH}")
            params.append(company_id)
        where_sql = 'WHERE ' + ' AND '.join(where)

        with get_api_db_cursor() as cursor:
            cursor.execute(
                f"SELECT id, company_id, player_uuid, player_name, score, confidence, "
                f"last_action, last_reasoning, evaluations_count, last_evaluated_at "
                f"FROM ai_player_scores {where_sql} "
                f"ORDER BY score DESC, last_evaluated_at DESC LIMIT {_PH}",
                tuple(params + [limit])
            )
            rows = cursor.fetchall()

        scores = []
        for r in rows:
            d = dict(r) if not isinstance(r, dict) else r
            for k, v in list(d.items()):
                if hasattr(v, 'isoformat'):
                    d[k] = v.isoformat()
            scores.append(d)
        return jsonify({'success': True, 'scores': scores}), 200
    except Exception as e:
        print(f"ERROR api_ai_scores: {type(e).__name__}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/ai/evaluate-batch', methods=['POST'])
@login_required
@_limit("30 per minute")
@audit_action('oracle.evaluate_batch', 'oracle')
def api_ai_evaluate_batch():
    """Evalúa N jugadores en una sola request usando Oracle hybrid."""
    data = request.get_json(silent=True) or {}
    players = data.get('players') or []
    if not isinstance(players, list) or not players:
        return jsonify({'success': False, 'error': 'players debe ser un array no vacío'}), 400
    if len(players) > 50:
        return jsonify({'success': False, 'error': 'Máximo 50 jugadores por lote'}), 400

    try:
        user = get_user_by_id(session.get('user_id'))
        if not user:
            return jsonify({'success': False, 'error': 'No autenticado'}), 401
        company_id = 0 if user.get('is_super_admin') else int(user.get('company_id') or 0)
        import argus_ai_oracle as _oracle

        out: list[dict] = []
        with get_api_db_cursor() as cursor:
            weights = _get_ai_weights(company_id)
            log_reg = _load_ml_model(cursor, company_id, 'logreg')
            knn = _load_ml_model(cursor, company_id, 'knn')
            temporal = _load_ml_model(cursor, company_id, 'temporal')
            for p in players:
                if not isinstance(p, dict):
                    continue
                player_uuid = (p.get('player_uuid') or '').strip()[:40]
                player_name = (p.get('player_name') or '').strip()[:64]
                violation = p.get('violation') if isinstance(p.get('violation'), dict) else None
                if not player_uuid or not player_name:
                    out.append({
                        'player_uuid': player_uuid,
                        'player_name': player_name,
                        'error': 'player_uuid y player_name requeridos',
                    })
                    continue
                evidence = _build_ai_evidence(cursor, company_id, player_uuid, player_name, violation)
                decision = _oracle.evaluate_hybrid(
                    evidence, weights,
                    log_reg=log_reg, knn=knn, temporal=temporal,
                    feature_vector=None, sequence=None,
                )
                out.append({
                    'player_uuid': player_uuid,
                    'player_name': player_name,
                    'score': decision.score,
                    'confidence': decision.confidence,
                    'action': decision.action,
                    'reasoning': decision.reasoning,
                    'top_factor': decision.top_factor,
                    'evidence_used': decision.evidence_used,
                })
        return jsonify({'success': True, 'count': len(out), 'results': out}), 200
    except Exception as e:
        print(f"ERROR api_ai_evaluate_batch: {type(e).__name__}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/ai/decisions', methods=['GET'])
@login_required
def api_ai_decisions():
    """Log de decisiones recientes del Oracle (auditoria + apelaciones)."""
    _plugin_schema_guard()
    try:
        user = get_user_by_id(session.get('user_id'))
        if not user:
            return jsonify({'success': False, 'error': 'No autenticado'}), 401
        roles = user.get('roles') or []
        if isinstance(roles, str):
            try: roles = json.loads(roles)
            except Exception: roles = [roles]
        roles_lower = {str(r).lower() for r in roles}
        is_global_admin = bool(roles_lower & {'admin', 'owner', 'super_admin'})
        company_id = _resolve_company_id_for_user(user)
        limit = max(1, min(200, int(request.args.get('limit', 100))))
        player = (request.args.get('player') or '').strip()[:64]
        action = (request.args.get('action') or '').strip()[:32]

        where = []
        params: list = []
        if not is_global_admin:
            if not company_id:
                return jsonify({'success': True, 'decisions': []}), 200
            where.append(f"company_id = {_PH}")
            params.append(company_id)
        if player:
            where.append(f"LOWER(player_name) = LOWER({_PH})")
            params.append(player)
        if action:
            where.append(f"action = {_PH}")
            params.append(action)
        where_sql = ('WHERE ' + ' AND '.join(where)) if where else ''
        with get_api_db_cursor() as cursor:
            cursor.execute(
                f"SELECT id, company_id, player_uuid, player_name, score, confidence, "
                f"action, reasoning, evidence_json, triggered_by, created_at "
                f"FROM ai_decisions_log {where_sql} "
                f"ORDER BY created_at DESC LIMIT {_PH}",
                tuple(params + [limit])
            )
            rows = cursor.fetchall()

        decisions = []
        for r in rows:
            d = dict(r) if not isinstance(r, dict) else r
            for k, v in list(d.items()):
                if hasattr(v, 'isoformat'):
                    d[k] = v.isoformat()
            decisions.append(d)
        return jsonify({'success': True, 'decisions': decisions}), 200
    except Exception as e:
        print(f"ERROR api_ai_decisions: {type(e).__name__}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/ai/decisions/<int:decision_id>/explain', methods=['GET'])
@login_required
def api_ai_explain_decision(decision_id: int):
    """Explicación detallada de una decisión del Oracle para auditoría staff."""
    _plugin_schema_guard()
    try:
        user = get_user_by_id(session.get('user_id'))
        if not user:
            return jsonify({'success': False, 'error': 'No autenticado'}), 401
        roles = user.get('roles') or []
        if isinstance(roles, str):
            try:
                roles = json.loads(roles)
            except Exception:
                roles = [roles]
        roles_lower = {str(r).lower() for r in roles}
        is_global_admin = bool(roles_lower & {'admin', 'owner', 'super_admin'})
        company_id = _resolve_company_id_for_user(user)

        with get_api_db_cursor() as cursor:
            cursor.execute(
                f"SELECT id, company_id, player_uuid, player_name, score, confidence, "
                f"action, reasoning, evidence_json, triggered_by, created_at "
                f"FROM ai_decisions_log WHERE id = {_PH}",
                (decision_id,)
            )
            row = cursor.fetchone()
            if not row:
                return jsonify({'success': False, 'error': 'Decisión no encontrada'}), 404
            d = dict(row) if not isinstance(row, dict) else row
            if (not is_global_admin) and int(d.get('company_id') or 0) != int(company_id or 0):
                return jsonify({'success': False, 'error': 'No autorizado para esta decisión'}), 403

        evidence = {}
        try:
            evidence = json.loads(d.get('evidence_json') or '{}')
            if not isinstance(evidence, dict):
                evidence = {}
        except Exception:
            evidence = {}

        top_checks = []
        by_check = evidence.get('by_check') or {}
        if isinstance(by_check, dict):
            for check_name, lvls in by_check.items():
                total = int(sum(int(v or 0) for v in (lvls or {}).values())) if isinstance(lvls, dict) else 0
                top_checks.append({'check': check_name, 'count': total})
            top_checks.sort(key=lambda x: x['count'], reverse=True)

        return jsonify({
            'success': True,
            'decision': {
                'id': d.get('id'),
                'company_id': d.get('company_id'),
                'player_uuid': d.get('player_uuid'),
                'player_name': d.get('player_name'),
                'score': d.get('score'),
                'confidence': d.get('confidence'),
                'action': d.get('action'),
                'reasoning': d.get('reasoning'),
                'triggered_by': d.get('triggered_by'),
                'created_at': str(d.get('created_at')) if d.get('created_at') else None,
            },
            'evidence': evidence,
            'summary': {
                'total_violations': int(evidence.get('total_violations') or 0),
                'distinct_checks': int(evidence.get('distinct_checks') or 0),
                'top_checks': top_checks[:5],
                'ensemble_components': evidence.get('ensemble_components') or {},
                'ensemble_weights': evidence.get('ensemble_weights') or {},
                'ml_score': evidence.get('ml_score'),
            },
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/ai/weights', methods=['GET'])
@login_required
def api_ai_weights_get():
    """Devuelve los pesos vigentes para la empresa del usuario (o globales)."""
    _plugin_schema_guard()
    try:
        user = get_user_by_id(session.get('user_id'))
        if not user:
            return jsonify({'success': False, 'error': 'No autenticado'}), 401
        company_id = _resolve_company_id_for_user(user) or 0
        weights = _get_ai_weights(company_id)
        return jsonify({'success': True, 'company_id': company_id, 'weights': weights}), 200
    except Exception as e:
        print(f"ERROR api_ai_weights_get: {type(e).__name__}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/ai/weights', methods=['PUT'])
@admin_required
def api_ai_weights_set():
    """Solo SUPER-ADMIN. Guarda pesos custom (puede ser por company_id o globales)."""
    _plugin_schema_guard()
    try:
        body = request.get_json(silent=True) or {}
        company_id = int(body.get('company_id') or 0)
        weights = body.get('weights')
        if not isinstance(weights, dict):
            return jsonify({'success': False, 'error': 'weights debe ser un dict'}), 400
        weights_json = json.dumps(weights)
        user = get_user_by_id(session.get('user_id'))
        username = (user or {}).get('username') or 'unknown'
        with get_api_db_cursor() as cursor:
            cursor.execute(
                f"SELECT id FROM ai_weights WHERE company_id = {_PH}",
                (company_id,)
            )
            existing = cursor.fetchone()
            if existing:
                cursor.execute(
                    f"UPDATE ai_weights SET weights_json = {_PH}, updated_by = {_PH}, "
                    f"updated_at = CURRENT_TIMESTAMP WHERE company_id = {_PH}",
                    (weights_json, username, company_id)
                )
            else:
                cursor.execute(
                    f"INSERT INTO ai_weights (company_id, weights_json, updated_by) "
                    f"VALUES ({_PH}, {_PH}, {_PH})",
                    (company_id, weights_json, username)
                )
        # Invalidar cache para que la proxima eval lea los nuevos pesos
        _AI_WEIGHTS_CACHE.pop(company_id, None)
        return jsonify({'success': True, 'company_id': company_id}), 200
    except Exception as e:
        print(f"ERROR api_ai_weights_set: {type(e).__name__}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ──────────────────────────────────────────────────────────────────────
#  Pack 45: Endpoints ML — feedback, training, stats, profiles
# ──────────────────────────────────────────────────────────────────────

@app.route('/api/ai/feedback', methods=['POST'])
@login_required
def api_ai_feedback():
    """Staff marca una decision como correcta/incorrecta.

    Body: {decision_id, label: 0/0.5/1, reasoning?: str}
    Label: 1 = era cheater, 0 = falso positivo / limpio, 0.5 = incierto
    """
    _plugin_schema_guard()
    try:
        body = request.get_json(silent=True) or {}
        decision_id = body.get('decision_id')
        try:
            label = float(body.get('label'))
        except Exception:
            return jsonify({'success': False, 'error': 'label requerido (0..1)'}), 400
        label = max(0.0, min(1.0, label))
        reasoning = (body.get('reasoning') or '')[:500]

        user = get_user_by_id(session.get('user_id'))
        if not user:
            return jsonify({'success': False, 'error': 'No autenticado'}), 401
        username = (user.get('username') or 'unknown')[:255]
        # Si no es admin, solo puede marcar decisiones de su company
        user_company = user.get('company_id') or 0

        with get_api_db_cursor() as cursor:
            # Validar que la decision existe y pertenece a la company
            if decision_id:
                cursor.execute(
                    f"SELECT company_id, player_uuid, player_name "
                    f"FROM ai_decisions_log WHERE id = {_PH}",
                    (int(decision_id),)
                )
                row = cursor.fetchone()
                if not row:
                    return jsonify({'success': False, 'error': 'decision no existe'}), 404
                row = dict(row) if not isinstance(row, dict) else row
                if (not user.get('is_super_admin')
                    and row.get('company_id') != user_company):
                    return jsonify({'success': False, 'error': 'sin permisos'}), 403
                target_company = row.get('company_id') or 0
                player_uuid = row.get('player_uuid')
                player_name = row.get('player_name')
            else:
                player_uuid = (body.get('player_uuid') or '')[:40]
                player_name = (body.get('player_name') or '')[:64]
                if not player_uuid:
                    return jsonify({'success': False, 'error': 'decision_id o player_uuid requerido'}), 400
                target_company = user_company

            cursor.execute(
                f"INSERT INTO ai_feedback "
                f"(company_id, decision_id, player_uuid, player_name, label, "
                f"confidence, source, staff_username, reasoning) "
                f"VALUES ({_PH},{_PH},{_PH},{_PH},{_PH},{_PH},'staff',{_PH},{_PH})",
                (target_company, int(decision_id) if decision_id else None,
                 player_uuid, player_name, label, 1.0, username, reasoning)
            )
            # Si el profile del jugador existe, marcarlo con este label
            if player_uuid:
                try:
                    cursor.execute(
                        f"UPDATE ai_player_profiles SET last_label = {_PH}, "
                        f"last_label_confidence = {_PH}, last_label_source = 'staff' "
                        f"WHERE company_id = {_PH} AND player_uuid = {_PH}",
                        (label, 1.0, target_company, player_uuid)
                    )
                except Exception:
                    pass
        return jsonify({'success': True}), 200
    except Exception as e:
        print(f"ERROR api_ai_feedback: {type(e).__name__}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/ai/model-stats', methods=['GET'])
@login_required
def api_ai_model_stats():
    """Devuelve estado actual del modelo ML: accuracy, samples, last train, etc."""
    _plugin_schema_guard()
    try:
        user = get_user_by_id(session.get('user_id'))
        if not user:
            return jsonify({'success': False, 'error': 'No autenticado'}), 401
        company_id = 0 if user.get('is_super_admin') else int(user.get('company_id') or 0)
        try:
            company_id = int(request.args.get('company_id', company_id))
        except Exception:
            pass

        with get_api_db_cursor() as cursor:
            cursor.execute(
                f"SELECT model_kind, version, samples_trained, accuracy, precision, "
                f"recall, f1, last_loss, trained_at "
                f"FROM ai_model_state WHERE company_id = {_PH} OR company_id = 0 "
                f"ORDER BY company_id DESC",
                (company_id,)
            )
            rows = cursor.fetchall() or []
            models: dict[str, dict] = {}
            for r in rows:
                r = dict(r) if not isinstance(r, dict) else r
                kind = r['model_kind']
                if kind not in models:  # company-specific first (descending order)
                    models[kind] = {
                        'kind': kind,
                        'version': r.get('version'),
                        'samples_trained': r.get('samples_trained'),
                        'accuracy': r.get('accuracy'),
                        'precision': r.get('precision'),
                        'recall': r.get('recall'),
                        'f1': r.get('f1'),
                        'last_loss': r.get('last_loss'),
                        'trained_at': str(r.get('trained_at')) if r.get('trained_at') else None,
                    }

            # Counts de feedback + auto-labels
            cursor.execute(
                f"SELECT COUNT(*) AS c FROM ai_feedback WHERE company_id = {_PH}",
                (company_id,)
            )
            r = cursor.fetchone()
            r = dict(r) if not isinstance(r, dict) else r
            feedback_count = int(r.get('c') or 0) if r else 0

            cursor.execute(
                f"SELECT source, COUNT(*) AS c FROM ai_auto_labels "
                f"WHERE company_id = {_PH} GROUP BY source",
                (company_id,)
            )
            auto_counts = {}
            for r in cursor.fetchall() or []:
                r = dict(r) if not isinstance(r, dict) else r
                auto_counts[r['source']] = int(r['c'])

            # Decisions sin label
            cursor.execute(
                f"SELECT COUNT(*) AS c FROM ai_decisions_log d "
                f"WHERE d.company_id = {_PH} AND NOT EXISTS ("
                f"  SELECT 1 FROM ai_feedback f WHERE f.decision_id = d.id"
                f") AND NOT EXISTS ("
                f"  SELECT 1 FROM ai_auto_labels al WHERE al.decision_id = d.id"
                f")",
                (company_id,)
            )
            r = cursor.fetchone()
            r = dict(r) if not isinstance(r, dict) else r
            pending_count = int(r.get('c') or 0) if r else 0

            # Top features (de logreg) si esta cargado
            top_features = []
            log_reg = _load_ml_model(cursor, company_id, 'logreg')
            if log_reg:
                top_features = [
                    {'name': n, 'weight': round(w, 4)}
                    for n, w in log_reg.feature_importance(top_k=15)
                ]

            # Training history (last 10)
            cursor.execute(
                f"SELECT model_kind, samples_used, samples_real, samples_synthetic, "
                f"loss, accuracy, precision, recall, f1, duration_ms, "
                f"triggered_by, created_at "
                f"FROM ai_training_history WHERE company_id = {_PH} "
                f"ORDER BY created_at DESC LIMIT 10",
                (company_id,)
            )
            history = []
            for r in cursor.fetchall() or []:
                r = dict(r) if not isinstance(r, dict) else r
                history.append({
                    **{k: r.get(k) for k in ('model_kind', 'samples_used', 'samples_real',
                                              'samples_synthetic', 'loss', 'accuracy',
                                              'precision', 'recall', 'f1',
                                              'duration_ms', 'triggered_by')},
                    'created_at': str(r.get('created_at')) if r.get('created_at') else None,
                })

        return jsonify({
            'success': True,
            'company_id': company_id,
            'models': models,
            'feedback_count': feedback_count,
            'auto_label_counts': auto_counts,
            'auto_label_total': sum(auto_counts.values()),
            'decisions_pending_review': pending_count,
            'top_features': top_features,
            'training_history': history,
        }), 200
    except Exception as e:
        print(f"ERROR api_ai_model_stats: {type(e).__name__}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/ai/agreement-rate', methods=['GET'])
@login_required
def api_ai_agreement_rate():
    """KPI de acuerdo IA vs decisiones confirmadas por staff."""
    if not _AI_TRUST_AVAILABLE:
        return jsonify({'success': False, 'error': 'ai_trust no disponible'}), 503
    try:
        user = get_user_by_id(session.get('user_id'))
        if not user:
            return jsonify({'success': False, 'error': 'No autenticado'}), 401
        company_id = 0 if user.get('is_super_admin') else int(user.get('company_id') or 0)
        with get_api_db_cursor() as cursor:
            if company_id > 0:
                cursor.execute(
                    f"SELECT COALESCE(SUM(agreements),0) AS a, "
                    f"       COALESCE(SUM(disagreements),0) AS d, "
                    f"       COALESCE(SUM(confirmed_correct),0) AS cc, "
                    f"       COALESCE(SUM(confirmed_wrong),0) AS cw "
                    f"FROM staff_trust WHERE user_id IN ("
                    f"  SELECT id FROM users WHERE company_id = {_PH}"
                    f")",
                    (company_id,)
                )
            else:
                cursor.execute(
                    "SELECT COALESCE(SUM(agreements),0) AS a, "
                    "       COALESCE(SUM(disagreements),0) AS d, "
                    "       COALESCE(SUM(confirmed_correct),0) AS cc, "
                    "       COALESCE(SUM(confirmed_wrong),0) AS cw "
                    "FROM staff_trust"
                )
            row = cursor.fetchone()
            agreements = int(_row_get(row, 0, 'a') or 0)
            disagreements = int(_row_get(row, 1, 'd') or 0)
            confirmed_correct = int(_row_get(row, 2, 'cc') or 0)
            confirmed_wrong = int(_row_get(row, 3, 'cw') or 0)
            weighted_ok = agreements + (2 * confirmed_correct)
            weighted_bad = disagreements + (2 * confirmed_wrong)
            sample_size = weighted_ok + weighted_bad
            agreement_rate = round((weighted_ok / sample_size) * 100.0, 2) if sample_size > 0 else 0.0
        return jsonify({
            'success': True,
            'company_id': company_id,
            'agreement_rate': agreement_rate,
            'sample_size': sample_size,
            'agreements': agreements,
            'disagreements': disagreements,
            'confirmed_correct': confirmed_correct,
            'confirmed_wrong': confirmed_wrong,
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/ai/confidence-histogram', methods=['GET'])
@login_required
def api_ai_confidence_histogram():
    """Histograma de confianza de decisiones IA para panel de salud."""
    _plugin_schema_guard()
    try:
        user = get_user_by_id(session.get('user_id'))
        if not user:
            return jsonify({'success': False, 'error': 'No autenticado'}), 401
        company_id = 0 if user.get('is_super_admin') else int(user.get('company_id') or 0)
        days = max(1, min(180, int(request.args.get('days', 30))))
        bins = [0] * 10  # 0-9 => [0.0-0.1), ..., [0.9-1.0]

        with get_api_db_cursor() as cursor:
            try:
                if company_id > 0:
                    cursor.execute(
                        f"SELECT confidence FROM ai_decisions_log "
                        f"WHERE company_id = {_PH} "
                        f"  AND created_at >= CURRENT_TIMESTAMP - INTERVAL '{days} days'",
                        (company_id,)
                    )
                else:
                    cursor.execute(
                        f"SELECT confidence FROM ai_decisions_log "
                        f"WHERE created_at >= CURRENT_TIMESTAMP - INTERVAL '{days} days'"
                    )
            except Exception:
                if company_id > 0:
                    cursor.execute(
                        f"SELECT confidence FROM ai_decisions_log "
                        f"WHERE company_id = {_PH} "
                        f"  AND created_at >= datetime('now', '-{days} days')",
                        (company_id,)
                    )
                else:
                    cursor.execute(
                        f"SELECT confidence FROM ai_decisions_log "
                        f"WHERE created_at >= datetime('now', '-{days} days')"
                    )
            rows = cursor.fetchall() or []

        total = 0
        for r in rows:
            c = float(_row_get(r, 0, 'confidence') or 0.0)
            c = max(0.0, min(1.0, c))
            idx = min(9, int(c * 10))
            bins[idx] += 1
            total += 1

        labels = [f"{i/10:.1f}-{(i+1)/10:.1f}" for i in range(10)]
        return jsonify({
            'success': True,
            'company_id': company_id,
            'days': days,
            'labels': labels,
            'bins': bins,
            'total': total,
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/ai/retrain', methods=['POST'])
@admin_required
def api_ai_retrain():
    """Super-admin fuerza un retraining de modelos."""
    _plugin_schema_guard()
    try:
        body = request.get_json(silent=True) or {}
        company_id = int(body.get('company_id') or 0)
        result = _train_models_for(company_id, triggered_by='manual')
        return jsonify({'success': True, **result}), 200
    except Exception as e:
        print(f"ERROR api_ai_retrain: {type(e).__name__}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/ai/decisions-pending-review', methods=['GET'])
@login_required
def api_ai_decisions_pending_review():
    """Lista decisiones sin label todavia (priorizadas por uncertainty)."""
    _plugin_schema_guard()
    try:
        user = get_user_by_id(session.get('user_id'))
        if not user:
            return jsonify({'success': False, 'error': 'No autenticado'}), 401
        company_id = int(user.get('company_id') or 0)
        if user.get('is_super_admin'):
            company_id = int(request.args.get('company_id', company_id))
        limit = min(50, int(request.args.get('limit', 25)))

        with get_api_db_cursor() as cursor:
            cursor.execute(
                f"SELECT d.id, d.player_name, d.player_uuid, d.score, d.confidence, "
                f"d.action, d.reasoning, d.triggered_by, d.created_at "
                f"FROM ai_decisions_log d "
                f"WHERE d.company_id = {_PH} AND d.action IN ('ss', 'kick', 'ban') "
                f"AND NOT EXISTS (SELECT 1 FROM ai_feedback f WHERE f.decision_id = d.id) "
                f"AND NOT EXISTS (SELECT 1 FROM ai_auto_labels al WHERE al.decision_id = d.id) "
                f"ORDER BY d.confidence ASC, d.created_at DESC "
                f"LIMIT {limit}",
                (company_id,)
            )
            out = []
            for r in cursor.fetchall() or []:
                r = dict(r) if not isinstance(r, dict) else r
                out.append({
                    'id': r['id'],
                    'player_name': r.get('player_name'),
                    'player_uuid': r.get('player_uuid'),
                    'score': r.get('score'),
                    'confidence': r.get('confidence'),
                    'action': r.get('action'),
                    'reasoning': r.get('reasoning'),
                    'triggered_by': r.get('triggered_by'),
                    'created_at': str(r.get('created_at')) if r.get('created_at') else None,
                })
        return jsonify({'success': True, 'decisions': out, 'count': len(out)}), 200
    except Exception as e:
        print(f"ERROR api_ai_decisions_pending: {type(e).__name__}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/ai/player-profile/<player_uuid>', methods=['GET'])
@login_required
def api_ai_player_profile(player_uuid: str):
    """Devuelve perfil completo de un jugador para que el panel lo muestre."""
    _plugin_schema_guard()
    try:
        user = get_user_by_id(session.get('user_id'))
        if not user:
            return jsonify({'success': False, 'error': 'No autenticado'}), 401
        company_id = int(user.get('company_id') or 0)
        if user.get('is_super_admin'):
            company_id = int(request.args.get('company_id', company_id))
        with get_api_db_cursor() as cursor:
            cursor.execute(
                f"SELECT * FROM ai_player_profiles "
                f"WHERE company_id = {_PH} AND player_uuid = {_PH}",
                (company_id, player_uuid[:40])
            )
            row = cursor.fetchone()
            if not row:
                return jsonify({'success': False, 'error': 'sin perfil'}), 404
            row = dict(row) if not isinstance(row, dict) else row

            # KNN neighbors si esta cargado
            neighbors = []
            try:
                knn = _load_ml_model(cursor, company_id, 'knn')
                if knn:
                    fv = json.loads(row.get('feature_vector_json') or '[]')
                    r = knn.predict(fv)
                    neighbors = r.get('neighbors') or []
            except Exception:
                pass

            # Recent violations del player
            cursor.execute(
                f"SELECT check_name, level, details, created_at "
                f"FROM plugin_violations "
                f"WHERE company_id = {_PH} AND player_uuid = {_PH} "
                f"ORDER BY created_at DESC LIMIT 30",
                (company_id, player_uuid[:40])
            )
            violations = []
            for v in cursor.fetchall() or []:
                v = dict(v) if not isinstance(v, dict) else v
                violations.append({
                    'check_name': v.get('check_name'),
                    'level': v.get('level'),
                    'details': v.get('details'),
                    'created_at': str(v.get('created_at')) if v.get('created_at') else None,
                })

            # Ultima score / action del jugador
            cursor.execute(
                f"SELECT score, confidence, last_action, last_reasoning, "
                f"evaluations_count, last_evaluated_at "
                f"FROM ai_player_scores "
                f"WHERE company_id = {_PH} AND player_uuid = {_PH}",
                (company_id, player_uuid[:40])
            )
            score_row = cursor.fetchone()
            current_score = None
            if score_row:
                sr = dict(score_row) if not isinstance(score_row, dict) else score_row
                current_score = {
                    'score': sr.get('score'),
                    'confidence': sr.get('confidence'),
                    'last_action': sr.get('last_action'),
                    'last_reasoning': sr.get('last_reasoning'),
                    'evaluations_count': sr.get('evaluations_count'),
                    'last_evaluated_at': str(sr.get('last_evaluated_at')) if sr.get('last_evaluated_at') else None,
                }

        return jsonify({
            'success': True,
            'profile': {
                'player_uuid': row.get('player_uuid'),
                'player_name': row.get('player_name'),
                'last_label': row.get('last_label'),
                'last_label_confidence': row.get('last_label_confidence'),
                'last_label_source': row.get('last_label_source'),
                'last_updated_at': str(row.get('last_updated_at')) if row.get('last_updated_at') else None,
            },
            'current_score': current_score,
            'recent_violations': violations,
            'similar_players': neighbors[:5],
        }), 200
    except Exception as e:
        print(f"ERROR api_ai_player_profile: {type(e).__name__}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/ai/auto-label-run', methods=['POST'])
@admin_required
def api_ai_auto_label_run():
    """Ejecuta los 12 pipelines de auto-labeling sobre decisiones pendientes."""
    _plugin_schema_guard()
    try:
        body = request.get_json(silent=True) or {}
        company_id = int(body.get('company_id') or 0)
        limit = min(500, int(body.get('limit') or 200))
        result = _run_auto_labeling_for(company_id, limit=limit)
        return jsonify({'success': True, **result}), 200
    except Exception as e:
        print(f"ERROR api_ai_auto_label_run: {type(e).__name__}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


def _run_auto_labeling_for(company_id: int, limit: int = 200) -> dict:
    """Ejecuta los pipelines de auto-labeling y persiste resultados.

    Solo se evalua sobre decisiones SIN feedback explicito ni auto-label previo
    (para no contaminar el training set con duplicados).
    """
    import time as _t
    import argus_ai_labeler as _L

    t0 = _t.time()
    out = {
        'company_id': company_id,
        'decisions_processed': 0,
        'labels_created': 0,
        'by_source': {},
    }
    try:
        with get_api_db_cursor() as cursor:
            # 1. Cargar decisiones pendientes (sin feedback ni auto-label)
            cursor.execute(
                f"SELECT d.id, d.player_uuid, d.player_name, d.score, d.confidence, "
                f"d.action, d.evidence_json, d.created_at "
                f"FROM ai_decisions_log d "
                f"WHERE d.company_id = {_PH} "
                f"AND NOT EXISTS (SELECT 1 FROM ai_feedback f WHERE f.decision_id = d.id) "
                f"AND NOT EXISTS (SELECT 1 FROM ai_auto_labels al WHERE al.decision_id = d.id) "
                f"ORDER BY d.created_at DESC LIMIT {limit}",
                (company_id,)
            )
            decisions = []
            for r in cursor.fetchall() or []:
                r = dict(r) if not isinstance(r, dict) else r
                ev_json = r.get('evidence_json') or '{}'
                try:
                    ev = json.loads(ev_json)
                except Exception:
                    ev = {}
                # Convert created_at a timestamp
                ct = r.get('created_at')
                created_ts = 0
                try:
                    if hasattr(ct, 'timestamp'):
                        created_ts = ct.timestamp()
                    elif ct:
                        # tratar como string YYYY-MM-DD HH:MM:SS
                        import datetime as _dt
                        created_ts = _dt.datetime.fromisoformat(str(ct)).timestamp()
                except Exception:
                    pass
                evidence_used = ev.get('evidence_used') or {}
                # Necesitamos sintetizar parte del evidence_summary
                # con scoresprev / counts / etc. para los pipelines.
                violation_summary = evidence_used.get('violation_summary') or {}
                distinct = evidence_used.get('distinct_checks') or len(violation_summary)
                total = evidence_used.get('total_violations') or sum(violation_summary.values())
                decisions.append({
                    'id': r['id'],
                    'player_uuid': r.get('player_uuid'),
                    'player_name': r.get('player_name'),
                    'action': r.get('action'),
                    'score': r.get('score'),
                    'confidence': r.get('confidence'),
                    'created_at': created_ts,
                    'evidence_summary': {
                        'v_lows': 0, 'v_mids': 0, 'v_highs': 0, 'v_criticals': 0,
                        'distinct_checks': distinct,
                        'total_violations': total,
                        'cluster_density': 0.0,
                        **evidence_used,
                    },
                })
            out['decisions_processed'] = len(decisions)
            if not decisions:
                out['duration_ms'] = int((_t.time() - t0) * 1000)
                return out

            # 2. Fetch contexto adicional para pipelines

            # ss_results: scan_tokens.scan_at + did detect
            uuids = list({d['player_uuid'] for d in decisions if d.get('player_uuid')})
            ss_results: dict[str, dict] = {}
            if uuids:
                ph = ','.join([_PH] * len(uuids))
                try:
                    # Buscar la mas reciente por uuid (con minecraft_target = name)
                    # Como scan_tokens es por NAME y no UUID, intentamos hacer match por name.
                    names = list({d['player_name'] for d in decisions if d.get('player_name')})
                    if names:
                        ph_n = ','.join([_PH] * len(names))
                        cursor.execute(
                            f"SELECT minecraft_target, created_at, used_at, result_count "
                            f"FROM scan_tokens "
                            f"WHERE minecraft_target IN ({ph_n}) AND used_at IS NOT NULL",
                            tuple(names)
                        )
                        # result_count > 0 = detecciones positivas
                        for r in cursor.fetchall() or []:
                            r = dict(r) if not isinstance(r, dict) else r
                            tgt = r.get('minecraft_target')
                            # Encontrar uuid asociado al name
                            for d in decisions:
                                if d.get('player_name') == tgt:
                                    used_at = r.get('used_at')
                                    used_ts = 0
                                    try:
                                        if hasattr(used_at, 'timestamp'):
                                            used_ts = used_at.timestamp()
                                    except Exception:
                                        pass
                                    ss_results[d['player_uuid']] = {
                                        'scan_at': used_ts,
                                        'detected_hacks': int(r.get('result_count') or 0) > 0,
                                    }
                                    break
                except Exception as e:
                    print(f"[auto_label] ss_results lookup failed: {e}")

            # cross_server: violations del jugador en OTRAS companies
            cross_server: dict[str, dict] = {}
            for d in decisions:
                uuid = d.get('player_uuid')
                if not uuid:
                    continue
                try:
                    cursor.execute(
                        f"SELECT COUNT(*) AS c, COUNT(DISTINCT company_id) AS s "
                        f"FROM plugin_violations "
                        f"WHERE player_uuid = {_PH} AND level IN ('HIGH','CRITICAL') "
                        f"AND company_id != {_PH}",
                        (uuid, company_id)
                    )
                    r = cursor.fetchone()
                    if r:
                        r = dict(r) if not isinstance(r, dict) else r
                        cnt = int(r.get('c') or 0)
                        srv = int(r.get('s') or 0)
                        if srv >= 2:
                            cross_server[uuid] = {
                                'banned_in_servers': [f'srv_{i}' for i in range(srv)],
                                'clean_streak_days': 0,
                            }
                        elif cnt == 0 and srv > 0:
                            cross_server[uuid] = {
                                'banned_in_servers': [],
                                'clean_streak_days': 60,
                            }
                except Exception:
                    pass

            # activity: last_seen_at / last_violation_at — del scan / violations
            activity: dict[str, dict] = {}
            for d in decisions:
                uuid = d.get('player_uuid')
                if not uuid:
                    continue
                try:
                    cursor.execute(
                        f"SELECT MAX(created_at) AS last_v FROM plugin_violations "
                        f"WHERE player_uuid = {_PH} AND company_id = {_PH}",
                        (uuid, company_id)
                    )
                    r = cursor.fetchone()
                    last_v_ts = 0
                    if r:
                        r = dict(r) if not isinstance(r, dict) else r
                        lv = r.get('last_v')
                        try:
                            if hasattr(lv, 'timestamp'):
                                last_v_ts = lv.timestamp()
                        except Exception:
                            pass
                    activity[uuid] = {
                        'last_seen_at': last_v_ts or _t.time(),
                        'last_violation_at': last_v_ts,
                    }
                except Exception:
                    pass

            # KNN para propagacion
            knn = _load_ml_model(cursor, company_id, 'knn')
            # Para usar KNN, necesitamos feature_vector en cada decision
            # Cargamos profiles
            if knn:
                profiles_uuid = list({d['player_uuid'] for d in decisions if d.get('player_uuid')})
                if profiles_uuid:
                    ph = ','.join([_PH] * len(profiles_uuid))
                    try:
                        cursor.execute(
                            f"SELECT player_uuid, feature_vector_json "
                            f"FROM ai_player_profiles "
                            f"WHERE company_id = {_PH} AND player_uuid IN ({ph})",
                            (company_id, *profiles_uuid)
                        )
                        prof_map = {}
                        for r in cursor.fetchall() or []:
                            r = dict(r) if not isinstance(r, dict) else r
                            try:
                                prof_map[r['player_uuid']] = json.loads(r['feature_vector_json'])
                            except Exception:
                                pass
                        for d in decisions:
                            if d['player_uuid'] in prof_map:
                                d['feature_vector'] = prof_map[d['player_uuid']]
                    except Exception:
                        pass

            # 3. Ejecutar pipelines
            all_labels: list = []
            try:
                all_labels.extend(_L.label_from_ss_outcomes(decisions, ss_results))
            except Exception as e: print(f"[auto_label] ss_outcomes failed: {e}")
            try:
                all_labels.extend(_L.label_from_clean_history(decisions, activity))
            except Exception as e: print(f"[auto_label] clean_history failed: {e}")
            try:
                all_labels.extend(_L.label_from_violation_clusters(decisions))
            except Exception as e: print(f"[auto_label] clusters failed: {e}")
            try:
                if knn:
                    all_labels.extend(_L.label_from_knn_propagation(decisions, knn))
            except Exception as e: print(f"[auto_label] knn failed: {e}")
            try:
                all_labels.extend(_L.label_from_yaw_consistency(decisions))
            except Exception as e: print(f"[auto_label] yaw failed: {e}")
            try:
                all_labels.extend(_L.label_from_age_stats_mismatch(decisions))
            except Exception as e: print(f"[auto_label] age_stats failed: {e}")
            try:
                all_labels.extend(_L.label_from_hit_accept_rate(decisions))
            except Exception as e: print(f"[auto_label] hit_rate failed: {e}")
            try:
                all_labels.extend(_L.label_from_cross_server_history(decisions, cross_server))
            except Exception as e: print(f"[auto_label] cross_server failed: {e}")

            # 4. Combinar (dedup por decision_id)
            combined = _L.combine_labels(all_labels)

            # 5. Persistir cada label combinado
            for did, lbl in combined.items():
                try:
                    cursor.execute(
                        f"INSERT INTO ai_auto_labels "
                        f"(company_id, decision_id, player_uuid, player_name, "
                        f"label, confidence, source, reasoning) "
                        f"VALUES ({_PH},{_PH},{_PH},{_PH},{_PH},{_PH},{_PH},{_PH})",
                        (company_id, did, lbl.player_uuid, lbl.player_name,
                         lbl.label, lbl.confidence, lbl.source, lbl.reasoning[:500])
                    )
                    out['labels_created'] += 1
                    out['by_source'][lbl.source] = out['by_source'].get(lbl.source, 0) + 1
                    # Si el label es muy seguro (>0.85), actualizar el profile
                    if lbl.confidence > 0.85 and lbl.player_uuid:
                        try:
                            cursor.execute(
                                f"UPDATE ai_player_profiles SET last_label = {_PH}, "
                                f"last_label_confidence = {_PH}, last_label_source = {_PH} "
                                f"WHERE company_id = {_PH} AND player_uuid = {_PH}",
                                (lbl.label, lbl.confidence, lbl.source,
                                 company_id, lbl.player_uuid)
                            )
                        except Exception:
                            pass
                except Exception as e:
                    print(f"[auto_label] error insert: {e}")
    except Exception as e:
        out['error'] = f'{type(e).__name__}: {e}'

    out['duration_ms'] = int((_t.time() - t0) * 1000)
    return out


# ──────────────────────────────────────────────────────────────────────
#  Pack 46: Assistant — chat conversacional + briefs + msgs in-game
# ──────────────────────────────────────────────────────────────────────

def _build_assistant_player_ctx(cursor, company_id: int, player_name: str) -> dict | None:
    """
    Resuelve un nombre de jugador a un context dict para el assistant.
    Busca por player_name en ai_player_scores. Si no encuentra, fallback
    a búsqueda fuzzy (LIKE) en plugin_violations.
    """
    if not player_name:
        return None
    try:
        cursor.execute(
            f"SELECT player_uuid, player_name, score, confidence, last_action, "
            f"last_reasoning, last_evidence_json, evaluations_count, "
            f"last_evaluated_at "
            f"FROM ai_player_scores "
            f"WHERE company_id = {_PH} AND LOWER(player_name) = LOWER({_PH}) "
            f"ORDER BY last_evaluated_at DESC LIMIT 1",
            (company_id, player_name)
        )
        row = cursor.fetchone()
        if not row:
            # Fuzzy fallback
            cursor.execute(
                f"SELECT player_uuid, player_name, score, confidence, last_action, "
                f"last_reasoning, last_evidence_json, evaluations_count, "
                f"last_evaluated_at "
                f"FROM ai_player_scores "
                f"WHERE company_id = {_PH} AND LOWER(player_name) LIKE LOWER({_PH}) "
                f"ORDER BY last_evaluated_at DESC LIMIT 1",
                (company_id, f"%{player_name}%")
            )
            row = cursor.fetchone()
        if not row:
            return None
        row = dict(row) if not isinstance(row, dict) else row

        # Violations stats
        viol_stats = {'total': 0, 'distinct': 0,
                      'low': 0, 'mid': 0, 'high': 0, 'critical': 0,
                      'top_check': ''}
        try:
            cursor.execute(
                f"SELECT level, COUNT(*) AS c, COUNT(DISTINCT check_name) AS dc "
                f"FROM plugin_violations "
                f"WHERE company_id = {_PH} AND player_uuid = {_PH} "
                f"AND created_at > CURRENT_TIMESTAMP - INTERVAL '7 days' "
                f"GROUP BY level"
                if _USE_PG else
                f"SELECT level, COUNT(*) AS c, COUNT(DISTINCT check_name) AS dc "
                f"FROM plugin_violations "
                f"WHERE company_id = {_PH} AND player_uuid = {_PH} "
                f"AND created_at > datetime('now', '-7 days') "
                f"GROUP BY level",
                (company_id, row['player_uuid'])
            )
            for vr in cursor.fetchall() or []:
                vr = dict(vr) if not isinstance(vr, dict) else vr
                lvl = (vr.get('level') or '').upper()
                cnt = int(vr.get('c') or 0)
                viol_stats['total'] += cnt
                if lvl == 'LOW': viol_stats['low'] = cnt
                elif lvl == 'MID': viol_stats['mid'] = cnt
                elif lvl == 'HIGH': viol_stats['high'] = cnt
                elif lvl == 'CRITICAL': viol_stats['critical'] = cnt
                viol_stats['distinct'] = max(viol_stats['distinct'], int(vr.get('dc') or 0))
            # Top check name
            cursor.execute(
                f"SELECT check_name, COUNT(*) AS c FROM plugin_violations "
                f"WHERE company_id = {_PH} AND player_uuid = {_PH} "
                f"GROUP BY check_name ORDER BY c DESC LIMIT 1",
                (company_id, row['player_uuid'])
            )
            tc = cursor.fetchone()
            if tc:
                tc = dict(tc) if not isinstance(tc, dict) else tc
                viol_stats['top_check'] = tc.get('check_name') or ''
        except Exception:
            pass

        # Top factor + ml_components from last evidence_json
        top_factor = ''
        ml_components = {}
        try:
            ej = json.loads(row.get('last_evidence_json') or '{}')
            top_factor = ej.get('top_factor', '') or ''
            ml_components = ej.get('ensemble_components') or {}
        except Exception:
            pass

        # last_evaluated_at -> timestamp
        last_eval_ts = 0.0
        try:
            le = row.get('last_evaluated_at')
            if hasattr(le, 'timestamp'):
                last_eval_ts = le.timestamp()
            elif le:
                import datetime as _dt
                last_eval_ts = _dt.datetime.fromisoformat(str(le)).timestamp()
        except Exception:
            pass

        # Neighbors via KNN si disponible
        neighbors = []
        try:
            knn = _load_ml_model(cursor, company_id, 'knn')
            if knn:
                cursor.execute(
                    f"SELECT feature_vector_json FROM ai_player_profiles "
                    f"WHERE company_id = {_PH} AND player_uuid = {_PH}",
                    (company_id, row['player_uuid'])
                )
                pr = cursor.fetchone()
                if pr:
                    pr = dict(pr) if not isinstance(pr, dict) else pr
                    fv = json.loads(pr.get('feature_vector_json') or '[]')
                    pred = knn.predict(fv)
                    neighbors = pred.get('neighbors') or []
        except Exception:
            pass

        return {
            'player_uuid': row.get('player_uuid'),
            'player_name': row.get('player_name'),
            'score': float(row.get('score') or 0),
            'confidence': float(row.get('confidence') or 0),
            'last_action': row.get('last_action') or 'none',
            'reasoning': row.get('last_reasoning') or '',
            'top_factor': top_factor,
            'top_check': viol_stats['top_check'] or top_factor,
            'violations_total': viol_stats['total'],
            'distinct_checks': viol_stats['distinct'],
            'low_count': viol_stats['low'],
            'mid_count': viol_stats['mid'],
            'high_count': viol_stats['high'],
            'critical_count': viol_stats['critical'],
            'evaluations_count': int(row.get('evaluations_count') or 0),
            'last_evaluated_at_ts': last_eval_ts,
            'ml_components': ml_components,
            'neighbors_list': neighbors,
        }
    except Exception as e:
        print(f"[assistant_ctx] error: {e}")
        return None


def _list_top_suspects_for_assistant(cursor, company_id: int, limit: int = 5) -> list[dict]:
    try:
        cursor.execute(
            f"SELECT player_name, score FROM ai_player_scores "
            f"WHERE company_id = {_PH} AND score > 0.3 "
            f"ORDER BY score DESC LIMIT {int(limit)}",
            (company_id,)
        )
        out = []
        for r in cursor.fetchall() or []:
            r = dict(r) if not isinstance(r, dict) else r
            out.append({'player_name': r.get('player_name'), 'score': r.get('score')})
        return out
    except Exception:
        return []


def _get_daily_stats_for_assistant(cursor, company_id: int, days: int = 1) -> dict:
    """Stats agregadas para daily_brief / weekly_brief."""
    out: dict = {
        'date': time.strftime('%Y-%m-%d'),
        'evaluations_count': 0, 'bans_count': 0, 'kicks_count': 0,
        'ss_count': 0, 'watch_count': 0,
        'top_player': None, 'ml_samples': 0, 'ml_accuracy': 0,
        'pending_count': 0,
    }
    interval_sql = (f"CURRENT_TIMESTAMP - INTERVAL '{int(days)} days'"
                    if _USE_PG else f"datetime('now', '-{int(days)} days')")
    try:
        cursor.execute(
            f"SELECT action, COUNT(*) AS c FROM ai_decisions_log "
            f"WHERE company_id = {_PH} AND created_at > {interval_sql} "
            f"GROUP BY action",
            (company_id,)
        )
        for r in cursor.fetchall() or []:
            r = dict(r) if not isinstance(r, dict) else r
            a = (r.get('action') or '').lower()
            c = int(r.get('c') or 0)
            out['evaluations_count'] += c
            if a == 'ban': out['bans_count'] = c
            elif a == 'kick': out['kicks_count'] = c
            elif a == 'ss': out['ss_count'] = c
            elif a == 'watch': out['watch_count'] = c
        # Top player
        cursor.execute(
            f"SELECT player_name, score FROM ai_decisions_log "
            f"WHERE company_id = {_PH} AND created_at > {interval_sql} "
            f"AND action IN ('ban','kick','ss') "
            f"ORDER BY score DESC LIMIT 1",
            (company_id,)
        )
        r = cursor.fetchone()
        if r:
            r = dict(r) if not isinstance(r, dict) else r
            out['top_player'] = {
                'player_name': r.get('player_name'),
                'score': float(r.get('score') or 0),
                'top_check': '',
            }
            # Top check para ese player
            try:
                cursor.execute(
                    f"SELECT check_name FROM plugin_violations "
                    f"WHERE company_id = {_PH} AND player_name = {_PH} "
                    f"GROUP BY check_name ORDER BY COUNT(*) DESC LIMIT 1",
                    (company_id, r.get('player_name'))
                )
                tc = cursor.fetchone()
                if tc:
                    tc = dict(tc) if not isinstance(tc, dict) else tc
                    out['top_player']['top_check'] = tc.get('check_name') or ''
            except Exception:
                pass
        # ML stats
        cursor.execute(
            f"SELECT accuracy, samples_trained FROM ai_model_state "
            f"WHERE model_kind = 'logreg' AND (company_id = {_PH} OR company_id = 0) "
            f"ORDER BY company_id DESC LIMIT 1",
            (company_id,)
        )
        r = cursor.fetchone()
        if r:
            r = dict(r) if not isinstance(r, dict) else r
            out['ml_samples'] = int(r.get('samples_trained') or 0)
            out['ml_accuracy'] = float(r.get('accuracy') or 0)
        # Pending count
        cursor.execute(
            f"SELECT COUNT(*) AS c FROM ai_decisions_log d "
            f"WHERE d.company_id = {_PH} AND d.action IN ('ss','kick','ban') "
            f"AND d.created_at > {interval_sql} "
            f"AND NOT EXISTS (SELECT 1 FROM ai_feedback f WHERE f.decision_id = d.id) "
            f"AND NOT EXISTS (SELECT 1 FROM ai_auto_labels al WHERE al.decision_id = d.id)",
            (company_id,)
        )
        r = cursor.fetchone()
        if r:
            r = dict(r) if not isinstance(r, dict) else r
            out['pending_count'] = int(r.get('c') or 0)
    except Exception as e:
        print(f"[assistant_stats] error: {e}")
    return out


@app.route('/api/ai/assistant/ask', methods=['POST'])
@login_required
def api_ai_assistant_ask():
    """
    Chat conversacional con el Oracle. Body: {text: str, tone?: 'neutral'|'sarcastic'}.
    Devuelve: {intent, answer, missing_data}.
    """
    _plugin_schema_guard()
    try:
        body = request.get_json(silent=True) or {}
        text = (body.get('text') or '').strip()[:500]
        tone = body.get('tone') or 'neutral'
        if not text:
            return jsonify({'success': False, 'error': 'text requerido'}), 400
        user = get_user_by_id(session.get('user_id'))
        if not user:
            return jsonify({'success': False, 'error': 'No autenticado'}), 401
        company_id = int(user.get('company_id') or 0)

        import argus_ai_assistant as A
        with get_api_db_cursor() as cursor:
            def resolver(name: str):
                return _build_assistant_player_ctx(cursor, company_id, name)
            def top_susp():
                return _list_top_suspects_for_assistant(cursor, company_id)
            def daily_stats(days: int = 1):
                return _get_daily_stats_for_assistant(cursor, company_id, days)

            result = A.ask(text, resolver, top_susp, daily_stats, tone=tone)

        # Polish con LLM si hay key configurada
        if result.get('answer') and result.get('intent') not in (
            'daily_summary', 'weekly_summary', 'help'  # estos ya están bien formados
        ):
            try:
                result['answer'] = A.llm_polish(result['answer'])
            except Exception:
                pass

        return jsonify({'success': True, **result}), 200
    except Exception as e:
        print(f"ERROR api_ai_assistant_ask: {type(e).__name__}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/ai/assistant/daily-brief', methods=['GET'])
@login_required
def api_ai_assistant_daily_brief():
    """Brief narrativo del día (últimas 24h)."""
    _plugin_schema_guard()
    try:
        user = get_user_by_id(session.get('user_id'))
        if not user:
            return jsonify({'success': False, 'error': 'No autenticado'}), 401
        company_id = int(user.get('company_id') or 0)
        if user.get('is_super_admin'):
            company_id = int(request.args.get('company_id', company_id))
        days = max(1, min(30, int(request.args.get('days', 1))))
        tone = request.args.get('tone', 'neutral')

        import argus_ai_assistant as A
        with get_api_db_cursor() as cursor:
            stats = _get_daily_stats_for_assistant(cursor, company_id, days)
        if days == 7:
            answer = A.weekly_brief(stats, tone=tone)
        else:
            answer = A.daily_brief(stats, tone=tone)
        return jsonify({'success': True, 'answer': answer, 'stats': stats, 'days': days}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/ai/assistant/warn-message', methods=['POST'])
@login_required
def api_ai_assistant_warn_message():
    """Genera texto humanizado para warn/kick/ban a un jugador."""
    _plugin_schema_guard()
    try:
        body = request.get_json(silent=True) or {}
        player = (body.get('player_name') or '').strip()[:64]
        kind = (body.get('kind') or 'warn').lower()
        if not player:
            return jsonify({'success': False, 'error': 'player_name requerido'}), 400
        user = get_user_by_id(session.get('user_id'))
        company_id = int(user.get('company_id') or 0)

        import argus_ai_assistant as A
        with get_api_db_cursor() as cursor:
            ctx = _build_assistant_player_ctx(cursor, company_id, player)
            if not ctx:
                # Sin data, generar mensaje genérico con player_name only
                ctx = {'player_name': player, 'top_check': 'patrón genérico',
                       'score': 0.5, 'confidence': 0.4}

        if kind == 'kick':
            answer = A.generate_kick_message(ctx)
        elif kind == 'ban':
            answer = A.generate_ban_message(ctx)
        else:
            answer = A.generate_warning(ctx)
        return jsonify({'success': True, 'message': answer, 'kind': kind}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/ai/assistant/compare/<player_uuid>', methods=['GET'])
@login_required
def api_ai_assistant_compare(player_uuid: str):
    """Narrativa: compara este jugador con perfiles confirmados (vía KNN)."""
    _plugin_schema_guard()
    try:
        user = get_user_by_id(session.get('user_id'))
        if not user:
            return jsonify({'success': False, 'error': 'No autenticado'}), 401
        company_id = int(user.get('company_id') or 0)

        import argus_ai_assistant as A
        with get_api_db_cursor() as cursor:
            # Resolver feature vector
            cursor.execute(
                f"SELECT player_name, feature_vector_json FROM ai_player_profiles "
                f"WHERE company_id = {_PH} AND player_uuid = {_PH}",
                (company_id, player_uuid[:40])
            )
            row = cursor.fetchone()
            if not row:
                return jsonify({'success': False, 'error': 'sin perfil'}), 404
            row = dict(row) if not isinstance(row, dict) else row
            fv = json.loads(row.get('feature_vector_json') or '[]')
            knn = _load_ml_model(cursor, company_id, 'knn')
            if not knn:
                return jsonify({
                    'success': True,
                    'answer': 'El modelo KNN aún no está entrenado.',
                    'neighbors': [],
                }), 200
            pred = knn.predict(fv)
            neighbors = pred.get('neighbors') or []
            ctx = {'player_name': row.get('player_name')}
        answer = A.compare_with_neighbors(ctx, neighbors)
        return jsonify({
            'success': True,
            'answer': answer,
            'neighbors': neighbors,
            'score': pred.get('score'),
            'confidence': pred.get('confidence'),
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/ai/assistant/proactive', methods=['GET'])
@login_required
def api_ai_assistant_proactive():
    """
    Lista alertas proactivas: jugadores que escalaron rápido en última hora
    y vecinos KNN con label=cheater de alta similitud.
    """
    _plugin_schema_guard()
    try:
        user = get_user_by_id(session.get('user_id'))
        if not user:
            return jsonify({'success': False, 'error': 'No autenticado'}), 401
        company_id = int(user.get('company_id') or 0)
        if user.get('is_super_admin'):
            company_id = int(request.args.get('company_id', company_id))

        import argus_ai_assistant as A
        alerts: list[dict] = []
        with get_api_db_cursor() as cursor:
            # 1. Escalation: jugadores que tuvieron >= 3 violations en última hora
            #    y score subió en últimas evaluaciones
            interval_sql = ("CURRENT_TIMESTAMP - INTERVAL '60 minutes'"
                            if _USE_PG else "datetime('now', '-60 minutes')")
            cursor.execute(
                f"SELECT player_name, player_uuid, score, last_evaluated_at "
                f"FROM ai_player_scores "
                f"WHERE company_id = {_PH} AND score > 0.35 "
                f"AND last_evaluated_at > {interval_sql} "
                f"ORDER BY score DESC LIMIT 5",
                (company_id,)
            )
            for r in cursor.fetchall() or []:
                r = dict(r) if not isinstance(r, dict) else r
                # Violations en 5min
                interval_short = ("CURRENT_TIMESTAMP - INTERVAL '5 minutes'"
                                  if _USE_PG else "datetime('now', '-5 minutes')")
                cursor.execute(
                    f"SELECT check_name, COUNT(*) AS c FROM plugin_violations "
                    f"WHERE company_id = {_PH} AND player_uuid = {_PH} "
                    f"AND created_at > {interval_short} "
                    f"GROUP BY check_name ORDER BY c DESC LIMIT 1",
                    (company_id, r.get('player_uuid'))
                )
                tc = cursor.fetchone()
                if not tc:
                    continue
                tc = dict(tc) if not isinstance(tc, dict) else tc
                cnt = int(tc.get('c') or 0)
                if cnt < 3:
                    continue
                msg = A.proactive_alert({
                    'player_name': r.get('player_name'),
                    'top_check': tc.get('check_name'),
                    'violations_recent': cnt,
                    'window_min': 5,
                    'prev_score': max(0, float(r.get('score') or 0) - 0.2),
                    'new_score': float(r.get('score') or 0),
                }, urgency='escalation')
                alerts.append({
                    'kind': 'escalation',
                    'player_name': r.get('player_name'),
                    'player_uuid': r.get('player_uuid'),
                    'score': float(r.get('score') or 0),
                    'message': msg,
                })
            # 2. KNN confirmed-neighbor: profiles cuyo vecino más cercano es cheater con sim > 0.92
            knn = _load_ml_model(cursor, company_id, 'knn')
            if knn:
                cursor.execute(
                    f"SELECT player_name, player_uuid, feature_vector_json "
                    f"FROM ai_player_profiles "
                    f"WHERE company_id = {_PH} AND (last_label IS NULL OR last_label < 0.5) "
                    f"AND last_updated_at > {interval_sql} "
                    f"ORDER BY last_updated_at DESC LIMIT 30",
                    (company_id,)
                )
                for r in cursor.fetchall() or []:
                    r = dict(r) if not isinstance(r, dict) else r
                    try:
                        fv = json.loads(r.get('feature_vector_json') or '[]')
                        pred = knn.predict(fv)
                        neigh = (pred.get('neighbors') or [])
                        if not neigh:
                            continue
                        top = neigh[0]
                        if top.get('similarity', 0) >= 0.92 and top.get('label', 0) >= 0.7:
                            msg = A.proactive_alert({
                                'player_name': r.get('player_name'),
                                'similarity': top['similarity'],
                                'neighbor_name': top.get('player_name', '?'),
                            }, urgency='confirmed_neighbor')
                            alerts.append({
                                'kind': 'confirmed_neighbor',
                                'player_name': r.get('player_name'),
                                'player_uuid': r.get('player_uuid'),
                                'similarity': top['similarity'],
                                'neighbor_name': top.get('player_name'),
                                'message': msg,
                            })
                    except Exception:
                        continue
        return jsonify({'success': True, 'alerts': alerts, 'count': len(alerts)}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# Endpoint plugin: el plugin manda texto del usuario in-game, recibe respuesta
@app.route('/api/plugin/assistant/query', methods=['POST'])
def api_plugin_assistant_query():
    """Plugin in-game pregunta al Oracle. Auth via X-Argus-Plugin-Key."""
    _plugin_schema_guard()
    api_key = (
        request.headers.get('X-Argus-Plugin-Key')
        or request.headers.get('Authorization', '').replace('Bearer ', '').strip()
    )
    if not api_key:
        return jsonify({'success': False, 'error': 'API key requerida'}), 401
    try:
        body = request.get_json(silent=True) or {}
        text = (body.get('text') or '').strip()[:500]
        if not text:
            return jsonify({'success': False, 'error': 'text requerido'}), 400

        import argus_ai_assistant as A
        with get_api_db_cursor() as cursor:
            cursor.execute(
                f"SELECT company_id, is_active FROM company_plugin_keys WHERE api_key = {_PH}",
                (api_key,)
            )
            row = cursor.fetchone()
            if not row:
                return jsonify({'success': False, 'error': 'API key invalida'}), 401
            row = dict(row) if not isinstance(row, dict) else row
            if not row.get('is_active'):
                return jsonify({'success': False, 'error': 'API key revocada'}), 403
            company_id = int(row['company_id'])

            def resolver(name: str):
                return _build_assistant_player_ctx(cursor, company_id, name)
            def top_susp():
                return _list_top_suspects_for_assistant(cursor, company_id)
            def daily_stats(days: int = 1):
                return _get_daily_stats_for_assistant(cursor, company_id, days)

            result = A.ask(text, resolver, top_susp, daily_stats, tone='neutral')
        return jsonify({'success': True, **result}), 200
    except Exception as e:
        print(f"ERROR api_plugin_assistant_query: {type(e).__name__}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/plugin/assistant/proactive-suggestions', methods=['GET'])
def api_plugin_assistant_proactive_suggestions():
    """
    Plugin pide sugerencias proactivas (las que el Oracle quiere comunicar a
    staff conectado). Auth via plugin key. Devuelve max 3 alertas activas
    para que el plugin las whisper al staff.
    """
    _plugin_schema_guard()
    api_key = (
        request.headers.get('X-Argus-Plugin-Key')
        or request.headers.get('Authorization', '').replace('Bearer ', '').strip()
    )
    if not api_key:
        return jsonify({'success': False, 'error': 'API key requerida'}), 401
    try:
        import argus_ai_assistant as A
        with get_api_db_cursor() as cursor:
            cursor.execute(
                f"SELECT company_id, is_active FROM company_plugin_keys WHERE api_key = {_PH}",
                (api_key,)
            )
            row = cursor.fetchone()
            if not row:
                return jsonify({'success': False, 'error': 'API key invalida'}), 401
            row = dict(row) if not isinstance(row, dict) else row
            if not row.get('is_active'):
                return jsonify({'success': False, 'error': 'API key revocada'}), 403
            company_id = int(row['company_id'])

            # Reuse la logica del endpoint /api/ai/assistant/proactive
            interval_sql = ("CURRENT_TIMESTAMP - INTERVAL '15 minutes'"
                            if _USE_PG else "datetime('now', '-15 minutes')")
            cursor.execute(
                f"SELECT player_name, player_uuid, score "
                f"FROM ai_player_scores "
                f"WHERE company_id = {_PH} AND score > 0.45 "
                f"AND last_evaluated_at > {interval_sql} "
                f"ORDER BY score DESC LIMIT 3",
                (company_id,)
            )
            suggestions = []
            for r in cursor.fetchall() or []:
                r = dict(r) if not isinstance(r, dict) else r
                interval_short = ("CURRENT_TIMESTAMP - INTERVAL '10 minutes'"
                                  if _USE_PG else "datetime('now', '-10 minutes')")
                cursor.execute(
                    f"SELECT check_name, COUNT(*) AS c FROM plugin_violations "
                    f"WHERE company_id = {_PH} AND player_uuid = {_PH} "
                    f"AND created_at > {interval_short} "
                    f"GROUP BY check_name ORDER BY c DESC LIMIT 1",
                    (company_id, r.get('player_uuid'))
                )
                tc = cursor.fetchone()
                if not tc:
                    continue
                tc = dict(tc) if not isinstance(tc, dict) else tc
                msg = A.proactive_alert({
                    'player_name': r.get('player_name'),
                    'top_check': tc.get('check_name'),
                    'violations_recent': int(tc.get('c') or 0),
                    'window_min': 10,
                    'prev_score': max(0, float(r.get('score') or 0) - 0.2),
                    'new_score': float(r.get('score') or 0),
                }, urgency='escalation')
                suggestions.append({
                    'player_name': r.get('player_name'),
                    'score': float(r.get('score') or 0),
                    'message': msg,
                })
        return jsonify({'success': True, 'suggestions': suggestions}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/ai/feature-importance', methods=['GET'])
@login_required
def api_ai_feature_importance():
    """Top features con sus pesos absolutos del modelo LogReg actual."""
    _plugin_schema_guard()
    try:
        user = get_user_by_id(session.get('user_id'))
        if not user:
            return jsonify({'success': False, 'error': 'No autenticado'}), 401
        company_id = 0 if user.get('is_super_admin') else int(user.get('company_id') or 0)
        with get_api_db_cursor() as cursor:
            lr = _load_ml_model(cursor, company_id, 'logreg')
            if not lr:
                return jsonify({'success': True, 'features': [], 'note': 'modelo no entrenado'}), 200
            top = lr.feature_importance(top_k=int(request.args.get('top_k', 25)))
        return jsonify({
            'success': True,
            'features': [{'name': n, 'weight': round(w, 4)} for n, w in top],
            'samples_trained': lr.samples_trained,
            'last_trained_at': lr.last_trained_at,
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/plugin/health', methods=['GET'])
def api_plugin_health():
    """Health check para que el plugin valide la conectividad y la key."""
    _plugin_schema_guard()
    api_key = (
        request.headers.get('X-Argus-Plugin-Key')
        or request.headers.get('Authorization', '').replace('Bearer ', '').strip()
    )
    if not api_key:
        return jsonify({'success': True, 'status': 'ok', 'authenticated': False, 'argus_version': _ARGUS_VERSION}), 200

    try:
        with get_api_db_cursor() as cursor:
            cursor.execute(
                f"SELECT id, company_id, label, is_active, daily_quota, used_today "
                f"FROM company_plugin_keys WHERE api_key = {_PH}",
                (api_key,)
            )
            row = cursor.fetchone()
            if not row:
                return jsonify({'success': False, 'authenticated': False, 'error': 'API key invalida'}), 401
            row = dict(row) if not isinstance(row, dict) else row
            return jsonify({
                'success': True,
                'authenticated': True,
                'status': 'active' if row.get('is_active') else 'revoked',
                'company_id': row.get('company_id'),
                'label': row.get('label'),
                'daily_quota': row.get('daily_quota'),
                'used_today': row.get('used_today'),
                'argus_version': _ARGUS_VERSION,
            }), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


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

# ============================================================
# Licencia de escaneo firmada (reemplaza el token manual de 6 chars)
# ------------------------------------------------------------
# Una "licencia" es un blob firmado (itsdangerous) que un staff logueado
# y con suscripcion activa mina al descargar el scanner. Viaja embebida en
# el config.json del .exe (campo scan_token) y se verifica en
# /api/validate-token y /api/scans. No necesita fila en scan_tokens: la
# atribucion a empresa sale del propio blob (company + staff username), y
# la prueba de "soy staff que paga" la da la firma + el chequeo de
# suscripcion. Asi nadie tiene que tipear un codigo a mano.
# ============================================================
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

_LICENSE_PREFIX = 'argus_lic_'
_LICENSE_SALT = 'argus-scan-license-v1'
# Ventana de validez del blob (segundos). Por defecto 6h: cubre un SS largo
# y un par de descargas, sin volverse un token permanente.
_LICENSE_MAX_AGE = int(os.environ.get('ARGUS_LICENSE_MAX_AGE', str(6 * 3600)))


def _license_serializer():
    return URLSafeTimedSerializer(app.secret_key, salt=_LICENSE_SALT)


def _mint_scan_license(company_id, username):
    """Firma una licencia de escaneo para una empresa/staff concretos."""
    payload = {'c': int(company_id or 0), 'u': (username or '')[:64]}
    return _LICENSE_PREFIX + _license_serializer().dumps(payload)


def _parse_sub_end_date(raw):
    if not raw:
        return None
    try:
        if isinstance(raw, str):
            return datetime.datetime.fromisoformat(raw.replace('Z', '+00:00')).replace(tzinfo=None)
        if hasattr(raw, 'tzinfo'):
            return raw.replace(tzinfo=None)
        return raw
    except Exception:
        return None


def _company_subscription_active(company_id):
    """True si la empresa existe, esta activa y su suscripcion no vencio."""
    if not company_id:
        return False
    try:
        comp = get_company_by_id(company_id)
    except Exception:
        comp = None
    if not comp:
        return False
    if not comp.get('is_active', True):
        return False
    status = (comp.get('subscription_status') or '').strip().lower()
    if status not in ('active', 'trial', 'trialing'):
        return False
    end = _parse_sub_end_date(comp.get('subscription_end_date'))
    if end is not None and datetime.datetime.now() > end:
        return False
    return True


def _verify_scan_license(raw):
    """Devuelve None si 'raw' no es una licencia firmada (para que caiga al
    flujo de token clasico). Si lo es, devuelve dict con created_by/company_id
    o {'error': ...} cuando la firma/expiracion/suscripcion no validan."""
    if not raw or not isinstance(raw, str) or not raw.startswith(_LICENSE_PREFIX):
        return None
    blob = raw[len(_LICENSE_PREFIX):]
    try:
        data = _license_serializer().loads(blob, max_age=_LICENSE_MAX_AGE)
    except SignatureExpired:
        return {'error': 'Licencia expirada. Descargá el scanner de nuevo desde tu panel.'}
    except (BadSignature, Exception):
        return {'error': 'Licencia inválida.'}
    company_id = data.get('c')
    username = data.get('u') or ''
    if not _company_subscription_active(company_id):
        return {'error': 'Suscripción inactiva o vencida. Renová para usar el scanner.'}
    return {'company_id': company_id, 'created_by': username, 'is_license': True}


def _notify_company_scan_started(company_id, who, country, scan_id, launcher=None):
    """Ping a los webhooks (Discord/Telegram) de la empresa cuando arranca un SS.
    Best-effort: cualquier fallo se ignora para no romper el inicio del scan."""
    if not company_id:
        return
    try:
        with get_api_db_cursor() as cur:
            cur.execute(
                f"SELECT type, webhook_url, enabled FROM company_notification_settings "
                f"WHERE company_id = {_PH} AND enabled = TRUE",
                (int(company_id),)
            )
            rows = cur.fetchall() or []
    except Exception:
        rows = []
    if not rows:
        return
    _loc = f" · {country}" if country else ''
    _lz = f" · {launcher}" if launcher else ''
    for r in rows:
        d = dict(r) if not isinstance(r, dict) else r
        url = str(d.get('webhook_url') or '').strip()
        if not url:
            continue
        ntype = str(d.get('type') or '').strip().lower()
        try:
            if ntype == 'discord':
                requests.post(url, json={'content': f"🛰️ **SS iniciado** · {who}{_loc}{_lz} · scan #{scan_id}"}, timeout=4)
            elif ntype == 'telegram':
                requests.post(url, json={'text': f"🛰️ SS iniciado: {who}{_loc}{_lz} (scan #{scan_id})"}, timeout=4)
            else:
                requests.post(url, json={'event': 'scan_started', 'who': who, 'country': country,
                                         'scan_id': scan_id, 'company_id': int(company_id)}, timeout=4)
        except Exception as _e:
            print(f"[ss_notify] webhook error type={ntype}: {_e}")


def _validate_scan_token_direct(token):
    """Valida un token de escaneo en la BD. Retorna (token_id, error_msg, created_by, allowed_mods).

    Primero intenta interpretar 'token' como una licencia firmada
    (argus_lic_...). Si no lo es, cae al flujo clasico de scan_tokens.
    Para licencias, token_id es None (no hay fila): el resto del pipeline
    (start_scan) deriva la empresa desde created_by."""
    lic = _verify_scan_license(token)
    if lic is not None:
        if lic.get('error'):
            return None, lic['error'], None, None
        return None, None, lic.get('created_by'), []
    try:
        # CÃ³digos cortos (â‰¤8 chars) se buscan en short_code; tokens largos en token
        use_short = len(token) <= 8
        with get_api_db_cursor() as cursor:
            col = 'short_code' if use_short else 'token'
            try:
                cursor.execute(
                    f'SELECT id, expires_at, used_count, max_uses, is_active, created_by, allowed_mods FROM scan_tokens WHERE {col} = {_PH}',
                    (token.upper() if use_short else token,)
                )
            except Exception:
                cursor.execute(
                    f'SELECT id, expires_at, used_count, max_uses, is_active, created_by FROM scan_tokens WHERE {col} = {_PH}',
                    (token.upper() if use_short else token,)
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


@app.route('/setup-admin-aspers2024', methods=['POST'])
def setup_admin():
    """Bootstrap one-shot de admin inicial protegido por token de entorno."""
    ip = (request.headers.get('X-Forwarded-For', request.remote_addr or '') or '').split(',')[0].strip()
    supplied = (
        request.headers.get('X-Argus-Bootstrap-Token')
        or (request.get_json(silent=True) or {}).get('token')
        or request.form.get('token')
        or ''
    )
    expected = os.environ.get('ARGUS_BOOTSTRAP_TOKEN', '').strip()
    if not expected:
        app.logger.error('[security] bootstrap_admin intento sin ARGUS_BOOTSTRAP_TOKEN configurado ip=%s', ip)
        return jsonify({'status': 'disabled', 'message': 'Bootstrap deshabilitado'}), 403
    if not secrets.compare_digest(str(supplied), expected):
        app.logger.warning('[security] bootstrap_admin token inválido ip=%s', ip)
        return jsonify({'status': 'forbidden', 'message': 'Token inválido'}), 403

    try:
        with get_api_db_cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) AS count FROM users "
                "WHERE LOWER(COALESCE(roles,'')) LIKE '%admin%' "
                "   OR LOWER(COALESCE(roles,'')) LIKE '%owner%' "
                "   OR LOWER(COALESCE(roles,'')) LIKE '%super%'"
            )
            row = cursor.fetchone()
            count = _row_get(row, 0, 'count')
            if count > 0:
                app.logger.warning('[security] bootstrap_admin rechazado: ya existe admin ip=%s', ip)
                return jsonify({'status': 'already_exists', 'message': 'Ya existe un administrador'}), 409

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
            username = os.environ.get('ARGUS_BOOTSTRAP_USER', 'arefy_admin').strip() or 'arefy_admin'
            email = os.environ.get('ARGUS_BOOTSTRAP_EMAIL', 'admin@arefy.com').strip() or 'admin@arefy.com'
            temp_password = secrets.token_urlsafe(18)
            _insert_id(cursor,
                f'INSERT INTO users (username, email, password_hash, roles, company_id, created_by) VALUES ({_PH},{_PH},{_PH},{_PH},{_PH},{_PH})',
                (username, email, hash_password(temp_password), '["admin", "empresa", "administrador"]', company_id, 'system')
            )
        app.logger.warning('[security] bootstrap_admin exitoso user=%s ip=%s', username, ip)
        return jsonify({'status': 'ok', 'username': username, 'temporary_password': temp_password}), 201
    except Exception as e:
        app.logger.exception('[security] bootstrap_admin error ip=%s', ip)
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/db-status', methods=['GET'])
@login_required
@require_superadmin
def api_db_status():
    """Muestra quÃ© backend de BD estÃ¡ activo â€” Ãºtil para verificar deploys"""
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
    """Valida un token de escaneo (usado por el cliente .exe) â€” sin login requerido"""
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
@login_required
@require_superadmin
def debug_last_scan():
    """Endpoint de diagnÃ³stico â€” muestra el Ãºltimo scan en bruto desde la BD"""
    try:
        with get_api_db_cursor() as cursor:
            # Estado de columnas disponibles en la tabla scans
            cursor.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'scans' ORDER BY ordinal_position
            """)
            cols = [r['column_name'] if hasattr(r, 'keys') else r[0] for r in cursor.fetchall()]

            # Ãšltimo scan
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

            # Resultados del Ãºltimo scan
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


# Current released scanner version â€” update this when distributing a new build
CURRENT_SCANNER_VERSION = "1.6.58"

@app.route('/sw.js')
def service_worker():
    """Serve service worker from root scope so it can control the full origin."""
    resp = make_response(app.send_static_file('sw.js'))
    resp.headers['Content-Type'] = 'application/javascript'
    resp.headers['Service-Worker-Allowed'] = '/'
    resp.headers['Cache-Control'] = 'no-cache'
    return resp


# â”€â”€ P5 #16 â€” Web Push Notifications â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _get_vapid_keys():
    """Returns (private_key_b64, public_key_b64) from env or generates them."""
    priv = os.environ.get('VAPID_PRIVATE_KEY', '')
    pub  = os.environ.get('VAPID_PUBLIC_KEY', '')
    if priv and pub:
        return priv, pub
    # Try to load from DB
    try:
        conn = get_db_connection()
        cur  = conn.cursor()
        cur.execute("SELECT value FROM app_settings WHERE key = 'vapid_private_key'")
        row_priv = cur.fetchone()
        cur.execute("SELECT value FROM app_settings WHERE key = 'vapid_public_key'")
        row_pub  = cur.fetchone()
        cur.close()
        conn.close()
        if row_priv and row_pub:
            pv = row_priv[0] if isinstance(row_priv, (list, tuple)) else row_priv.get('value', '')
            pk = row_pub[0] if isinstance(row_pub, (list, tuple)) else row_pub.get('value', '')
            if pv and pk:
                return pv, pk
    except Exception:
        pass
    # Generate new keys using py_vapid if available
    try:
        from py_vapid import Vapid
        v = Vapid()
        v.generate_keys()
        priv_b64 = v.private_key_urlsafe_base64()
        pub_b64  = v.public_key_urlsafe_base64()
        # Persist to DB
        try:
            conn = get_db_connection()
            cur  = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS app_settings (key TEXT PRIMARY KEY, value TEXT)
            """)
            cur.execute("INSERT INTO app_settings (key, value) VALUES ('vapid_private_key', %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value", (priv_b64,))
            cur.execute("INSERT INTO app_settings (key, value) VALUES ('vapid_public_key', %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value", (pub_b64,))
            conn.commit()
            cur.close()
            conn.close()
        except Exception:
            pass
        return priv_b64, pub_b64
    except ImportError:
        return '', ''


def _send_push_to_all(title: str, body: str, url: str = '/panel'):
    """Sends a Web Push notification to all stored subscriptions. Fire-and-forget."""
    try:
        from pywebpush import webpush, WebPushException
        priv_key, pub_key = _get_vapid_keys()
        if not priv_key:
            return
        conn = get_db_connection()
        cur  = conn.cursor()
        cur.execute("SELECT endpoint, p256dh, auth FROM push_subscriptions")
        subs = cur.fetchall()
        cur.close()
        conn.close()
        payload = json.dumps({'title': title, 'body': body, 'url': url})
        vapid_claims = {'sub': f'mailto:{os.environ.get("VAPID_EMAIL","argus@aspers.gg")}'}
        for sub in subs:
            ep   = sub[0] if isinstance(sub, (list, tuple)) else sub.get('endpoint', '')
            p256 = sub[1] if isinstance(sub, (list, tuple)) else sub.get('p256dh', '')
            auth = sub[2] if isinstance(sub, (list, tuple)) else sub.get('auth', '')
            try:
                webpush(
                    subscription_info={'endpoint': ep, 'keys': {'p256dh': p256, 'auth': auth}},
                    data=payload,
                    vapid_private_key=priv_key,
                    vapid_claims=vapid_claims,
                )
            except WebPushException as e:
                if '410' in str(e) or '404' in str(e):
                    # Remove expired subscription
                    try:
                        conn2 = get_db_connection(); cur2 = conn2.cursor()
                        cur2.execute("DELETE FROM push_subscriptions WHERE endpoint = %s", (ep,))
                        conn2.commit(); cur2.close(); conn2.close()
                    except Exception:
                        pass
            except Exception:
                pass
    except ImportError:
        pass
    except Exception:
        pass


@app.route('/api/push/vapid-public-key', methods=['GET'])
@login_required
def push_vapid_public_key():
    """Returns the VAPID public key for browser push subscription."""
    _, pub = _get_vapid_keys()
    if not pub:
        return jsonify({'error': 'Web Push no configurado en este servidor'}), 501
    return jsonify({'public_key': pub})


@app.route('/api/push/subscribe', methods=['POST'])
@login_required
def push_subscribe():
    """Saves a push subscription from the browser."""
    data = request.json or {}
    endpoint = data.get('endpoint', '')
    keys     = data.get('keys', {})
    p256dh   = keys.get('p256dh', '')
    auth     = keys.get('auth', '')
    if not endpoint or not p256dh or not auth:
        return jsonify({'error': 'Subscription incompleta'}), 400
    try:
        conn = get_db_connection()
        cur  = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS push_subscriptions (
                id SERIAL PRIMARY KEY,
                endpoint TEXT UNIQUE NOT NULL,
                p256dh TEXT NOT NULL,
                auth TEXT NOT NULL,
                user_id INTEGER,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        cur.execute("""
            INSERT INTO push_subscriptions (endpoint, p256dh, auth, user_id)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (endpoint) DO UPDATE SET p256dh = EXCLUDED.p256dh, auth = EXCLUDED.auth
        """, (endpoint, p256dh, auth, session.get('user_id')))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/push/unsubscribe', methods=['POST'])
@login_required
def push_unsubscribe():
    """Removes a push subscription."""
    data = request.json or {}
    endpoint = data.get('endpoint', '')
    if not endpoint:
        return jsonify({'error': 'endpoint requerido'}), 400
    try:
        conn = get_db_connection()
        cur  = conn.cursor()
        cur.execute("DELETE FROM push_subscriptions WHERE endpoint = %s", (endpoint,))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/scanner/version', methods=['GET'])
def scanner_version():
    """Returns latest scanner version info so the .exe can self-update.
    Reads from app_versions table if available; falls back to CURRENT_SCANNER_VERSION."""
    base_url = request.host_url.rstrip('/')
    version  = CURRENT_SCANNER_VERSION
    changelog = ''
    try:
        with get_api_db_cursor() as cur:
            cur.execute(
                'SELECT version, changelog FROM app_versions ORDER BY id DESC LIMIT 1'
            )
            row = cur.fetchone()
            if row:
                v = _row_get(row, 0, 'version') or ''
                if v:
                    version   = v
                    changelog = _row_get(row, 1, 'changelog') or ''
    except Exception:
        pass
    return jsonify({
        'version':      version,
        'download_url': f'{base_url}/descargar/exe',
        'changelog':    changelog,
    })


@app.route('/api/scans', methods=['POST'])
@_limit("60 per hour")
@audit_action('scan.create', 'scan')
def start_scan():
    """Inicia un nuevo escaneo (usado por el cliente .exe) â€” sin login requerido"""
    try:
        _flags = _sa_imperial_flags()
        if _flags.get('maintenance_mode'):
            return jsonify({
                'error': 'Argus en mantenimiento. Reintentá en unos minutos.',
                'maintenance_mode': True,
            }), 503
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
            print(f"[DEBUG start_scan] token invÃ¡lido: {error}")
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
            company_id = None
            try:
                if _created_by:
                    cursor.execute(
                        f"SELECT company_id FROM users WHERE LOWER(username) = LOWER({_PH}) LIMIT 1",
                        (_created_by,)
                    )
                    _urow = cursor.fetchone()
                    company_id = int(_row_get(_urow, 0, 'company_id') or 0) or None
            except Exception:
                company_id = None
            cursor.execute(
                f'UPDATE scan_tokens SET used_count = used_count + 1,'
                f' is_active = CASE WHEN max_uses > 0 AND (used_count + 1) >= max_uses THEN FALSE ELSE is_active END'
                f' WHERE id = {_PH}',
                (token_id,)
            )
            scan_id = _insert_id(
                cursor,
                f'INSERT INTO scans (token_id, scan_token, status, machine_id, machine_name, ip_address, country, minecraft_username, company_id)'
                f" VALUES ({_PH},{_PH},'running',{_PH},{_PH},{_PH},{_PH},{_PH},{_PH})",
                (token_id, scan_token, machine_id, machine_name, ip_address, country, mc_username, company_id)
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
            # Visual #50 â€” guardar la versiÃ³n del scanner que generÃ³ este scan
            scanner_ver = (data.get('scanner_version') or '')[:40]
            if scanner_ver:
                try:
                    cursor.execute('SAVEPOINT scnv_save')
                    cursor.execute(f'UPDATE scans SET scanner_version = {_PH} WHERE id = {_PH}', (scanner_ver, scan_id))
                    cursor.execute('RELEASE SAVEPOINT scnv_save')
                except Exception:
                    try:
                        cursor.execute('ROLLBACK TO SAVEPOINT scnv_save')
                    except Exception:
                        pass

        print(f"[DEBUG start_scan] scan_id={scan_id} creado OK")

        # SS en vivo: avisar al staff (room de empresa) que el jugador ya
        # ejecuto el scanner. Llega como toast + sonido en el panel.
        if company_id:
            _who = (mc_username or machine_name or 'PC sin nombre')
            _loc = f" · {country}" if country else ''
            _launcher = (data.get('mc_launcher') or '') if isinstance(data, dict) else ''
            try:
                _emit_realtime_notification(company_id=company_id, payload={
                    'kind': 'scan_started',
                    'message': f"🛰️ SS en vivo: {_who} empezó a escanear{_loc}",
                    'scan_id': scan_id,
                    'machine_name': machine_name,
                    'minecraft_username': mc_username,
                    'country': country,
                    'launcher': _launcher,
                    'ip_address': ip_address,
                    'started_at': datetime.datetime.utcnow().isoformat() + 'Z',
                })
            except Exception as _ws_e:
                print(f"[ws] no se pudo emitir scan_started: {_ws_e}")
            try:
                _notify_company_scan_started(company_id, _who, country, scan_id, _launcher)
            except Exception as _wh_e:
                print(f"[ss_notify] {_wh_e}")

        return jsonify({'success': True, 'scan_id': scan_id, 'status': 'running', 'message': 'Escaneo iniciado'}), 201
    except Exception as e:
        print(f"[DEBUG start_scan] ERROR: {e}\n{traceback.format_exc()}")
        return jsonify({'error': f'Error iniciando escaneo: {str(e)}'}), 500


# Rutas/nombres de software legÃ­timo que el scanner client puede mandar como falsos positivos.
# Aplicado server-side para que funcione con cualquier versiÃ³n del exe.
_SERVER_FP_FRAGMENTS = [
    # Sistema Windows
    'windows\\system32', 'windows\\syswow64', 'windows\\winsxs',
    'windows\\servicing', 'windows\\inf', 'windows\\panther',
    'windows\\softwaredistribution', 'windows\\assembly',
    'program files\\microsoft', 'program files (x86)\\microsoft',
    'program files\\windowsapps', 'program files\\common files',
    'program files (x86)\\common files',
    'programdata\\microsoft', 'programdata\\package cache',
    'programdata\\windows', 'programdata\\nvidia',
    # AppData â€” apps legÃ­timas
    'webview2runtime', 'trust protection lists', 'pspc_sdk',
    'appdata\\local\\packages',        # Windows Store apps (firmadas, sandboxed)
    'appdata\\local\\origin',          # EA Origin
    'appdata\\local\\nvidia',
    'appdata\\local\\nvidia corporation',
    'appdata\\local\\amd', 'appdata\\local\\intel',
    'appdata\\local\\temp\\nv',         # NVIDIA temp installers
    'appdata\\roaming\\opera software',
    'appdata\\roaming\\microsoft\\windows',
    'appdata\\local\\microsoft\\windows',
    'appdata\\local\\microsoft\\onedrive',
    'appdata\\local\\microsoft\\teams',
    'appdata\\local\\microsoft\\office',
    'appdata\\local\\microsoft\\powertoys',
    'electronic arts\\ea desktop',
    'site-packages',                   # librerÃ­as Python instaladas
    'node_modules',                    # mÃ³dulos JS de proyectos
    # Windows AppRepository â€” paquetes firmados del sistema, jamÃ¡s hacks
    'apprepository\\packages', 'microsoft\\windows\\apprepository',
    'activationstore.dat', 'credentialstore', '.pckgdep',
    # Navegadores â€” rutas de datos del perfil
    'appdata\\local\\google\\chrome',
    'appdata\\local\\microsoft\\edge',
    'appdata\\local\\brave-browser',
    'appdata\\local\\vivaldi',
    'appdata\\local\\chromium',
    'appdata\\local\\opera software\\opera',
    'appdata\\roaming\\mozilla\\firefox',
    'appdata\\roaming\\waterfox', 'appdata\\roaming\\librewolf',
    # Launchers / clientes legÃ­timos de Minecraft
    'lunar client', 'lunarclient',
    'steam\\steamapps', 'epicgames', 'origin games',
    'tlauncher', 'prismlauncher', 'badlion client',
    'gdlauncher', 'multimc', 'atlauncher', 'curseforgeapp',
    'feather launcher', 'feathermc',   # Feather â€” launcher legÃ­timo
    'modrinth-app', 'modrinth.app',    # Modrinth official launcher
    'minecraftlauncher.exe',           # launcher oficial Mojang
    'xboxlivegames', 'minecraft launcher\\',
    # Anti-cheats y herramientas de seguridad legÃ­timas
    'easyanticheat',                   # anti-cheat de juegos (EAC)
    'battleye', 'vanguard', 'faceit',  # otros anti-cheats
    'riot vanguard', 'riotclientservices',
    # Herramientas del sistema Windows que aparecen en prefetch
    'screenclippinghost',              # captura de pantalla nativa de Windows
    'snippingtool', 'snipping tool',
    'magnify.exe', 'narrator.exe', 'osk.exe',
    'taskmgr.exe', 'mmc.exe', 'compmgmt.msc',
    'svchost.exe', 'lsass.exe', 'csrss.exe',
    'dwm.exe', 'explorer.exe', 'fontdrvhost.exe',
    'searchapp.exe', 'searchhost.exe', 'startmenuexperiencehost',
    'shellexperiencehost', 'runtimebroker.exe',
    'wmiprvse.exe', 'audiodg.exe', 'winlogon.exe',
    # El propio scanner â€” no flaggear sus propias copias borradas
    'argusscanner', 'minecraftsstool',
    # Java oficial / OpenJDK / temurin â€” runtime legÃ­timo
    'java\\jdk', 'java\\jre', 'temurin', 'corretto',
    'eclipse adoptium', 'openjdk',
    'oracle\\java', 'azul zulu',
    # Dominios seguros en URLs de historial/descargas de navegador
    'github.com', 'modrinth.com', 'curseforge.com', 'files.minecraftforge.net',
    'spigotmc.org', 'papermc.io', 'fabricmc.net', 'quiltmc.org',
    'optifine.net', 'minecraftforge.net', 'cdn.modrinth.com',
    'minecraft.net', 'mojang.com', 'minecraftjava.com',
    'lifehacker.com', 'lifehack.org', 'medium.com',
    'stackoverflow.com', 'reddit.com', 'youtube.com',
    'google.com', 'bing.com', 'wikipedia.org',
    'discord.com', 'discord.gg', 'discordapp.com',
    'twitch.tv', 'twitter.com', 'x.com', 'facebook.com',
    'amazon.com', 'amazonaws.com', 'cloudflare.com',
    'office.com', 'microsoft.com', 'live.com',
    'nvidia.com', 'amd.com', 'intel.com',
    'mediafire.com', 'mega.nz', 'drive.google.com',
    'docs.google.com', 'gmail.com',
    # Mods / datapacks legÃ­timos conocidos
    'optifine', 'fabricmc', 'quiltmc', 'sodium', 'lithium', 'phosphor',
    'iris', 'indium', 'ferritecore', 'lazydfu', 'starlight',
    'journeymap', 'just enough items', 'jei-', 'rei-',
    'terralith', 'amplified_nether', 'william_wythers',  # datapacks populares
    'create-', 'botania-', 'waystones-', 'appleskin-',   # mods comunes
    'modmenu-', 'cloth-config-', 'architectury-',
    'fabric-api-', 'forgeconfigapiport-', 'jade-',
    'distanthorizons', 'embeddium-', 'rubidium-',
    'oculus-', 'continuity-', 'lambdynamiclights-',
    'voicechat-', 'simplevoicechat-',
    # JNA â€” archivos temporales normales de Java/Minecraft
    'jna', 'jna-',
    # Otros programas legÃ­timos
    'voicemod',
    # Drivers y software de hardware
    'nvidia corporation', 'amd\\radeon', 'intel corporation',
    'discord\\app-', 'teamspeak 3 client',
    'logitech\\logi options', 'razer\\synapse',
    'wallpaperservice32',              # servicio Windows de fondos (FP: matcheaba ce32)
    'appdata\\local\\crashdumps\\',    # dumps de apps legítimas (ASUS, Steam, etc.)
    '\\temp\\lwjgl',                   # natives LWJGL extraídos por Minecraft
    'feather\\sidebar.json', '.minecraft\\feather\\',
    'corsair\\icue', 'steelseries\\engine',
    # LabyMod â€” cliente legÃ­timo de Minecraft
    'labymod', 'labymodlauncher', 'labymod-neo',
    # Fabric API processed mods y librerÃ­as de Minecraft
    '.fabric\\processedmods', '.minecraft\\.fabric', '.minecraft\\libraries',
    '.minecraft\\assets', '.minecraft\\versions',
    '.minecraft\\bin\\natives', '.minecraft\\natives',
    '.minecraft\\crash-reports', '.minecraft\\logs\\debug',
    # Grabadores de clips
    'medal\\', 'medal.tv',
    # Emuladores — carpetas "Cheats" y "Mods" son funcionalidades del emulador
    'cemu\\', 'yuzu\\', 'ryujinx\\', 'dolphin\\', 'citra\\',
    'rpcs3\\', 'ppsspp\\', 'desmume\\', 'melonds\\',
    'retroarch\\', 'mame\\', 'pcsx2\\', 'xenia\\',
    'graphicpacks\\', 'graphic packs\\',
    # Juegos y apps legÃ­timas
    'roblox\\', 'innersloth', 'vseeface',
    'epic games\\launcher', 'riot games\\',
    'ubisoft connect', 'gog galaxy',
    # Overwolf
    'ow-electron', 'overwolf',
    # Conexiones de red internas de Minecraft
    '127.0.0.1', 'connection to addr(ip=\'127.0.0.1\'',
    '::1', '0.0.0.0', 'localhost',
    # Servidores Minecraft populares (no son C2)
    '.hypixel.net', 'mc.hypixel.net', 'mineplex.com',
    'cubecraft.net', '.cubecraft.net',
    # IDE y herramientas de desarrollo (modders legÃ­timos)
    'jetbrains\\intellij', 'jetbrains\\toolbox', 'pycharm',
    'visual studio code', 'microsoft vs code', 'cursor\\',
    'eclipse\\', 'netbeans\\',
    '.gradle\\caches', '.gradle\\wrapper', '.m2\\repository',
    # OBS y streaming (no es evidencia per se, salvo que se grabe el SS)
    'obs-studio\\bin', 'streamlabs',

    # â”€â”€ Filter #13 â€” Discord (todas las variantes oficiales y forks comunes) â”€â”€
    # Discord original + canales beta + mods de cliente. Estos hookean overlay,
    # captura de ventana, etc â€” heurÃ­sticas viejas los confunden con inyectores.
    'discord.exe', 'discordptb.exe', 'discordcanary.exe',
    'discord_voice.exe', 'discord_overlay', 'discord_overlay2',
    'discordoverlay.exe', 'discord_helper', 'discord_crashhandler',
    'discord-crash', 'discord_setup',
    'appdata\\local\\discord',
    'appdata\\roaming\\discord',
    'appdata\\local\\discordptb',
    'appdata\\local\\discordcanary',
    'discord\\modules', 'discord\\resources', 'discord\\update.exe',
    # Mods de cliente Discord â€” son legÃ­timos pero hookean el client local
    'betterdiscord', 'better-discord', 'bdpluginlibrary',
    'vencord', 'arrpc.exe', 'replugged',
    'discord_arrpc', 'discord_rpc', 'discord rich presence',

    # â”€â”€ Filter #14 â€” PerifÃ©ricos: software oficial de mouse/teclado/audio â”€â”€â”€â”€
    # Estos tools capturan teclas / mueven el mouse / cargan profiles, lo que
    # se confunde con macros de hack. Whitelist por path y por nombre.
    # Razer
    'razer\\cortex', 'razer\\synapse 3', 'razer central',
    'razercentralservice', 'razersynapseservice',
    'razer\\gameinstaller', 'razer chroma',
    # Logitech
    'logitech\\g hub', 'logitech\\ghub', 'lghub.exe', 'lghub_agent.exe',
    'logitech gaming framework', 'logioptionsplus', 'logi options',
    'logitech connection utility',
    # Corsair
    'corsair\\icue', 'icue.exe', 'icuedevicecontrol', 'icue4service',
    'corsair gaming\\corsair utility',
    # SteelSeries
    'steelseries\\engine 3', 'steelseries gg',
    'steelseriesengine.exe', 'sonarsuite.exe',
    # HyperX
    'hyperx\\ngenuity', 'hyperxngenuity',
    # ASUS / EVGA / MSI
    'asus\\armoury crate', 'armourycrate.exe',
    'evga\\precision x1', 'precisionx1.exe',
    'msi\\dragon center', 'msi\\center', 'msicentral.exe',
    'gigabyte\\rgb fusion', 'rgbfusion.exe',
    # Mouse misc
    'glorious\\glorious core', 'gloriouscore',
    'pulsar\\pulsar driver', 'lamzu\\lamzu config',
    'finalmouse\\flux',
    # Audio peripherals
    'nahimic\\nahimic 3', 'realtek\\audio console',
    'sonar.exe',  # SteelSeries Sonar
    'discord_voice', 'voicemeeter',

    # â”€â”€ Filter #15 â€” Macros legales firmados â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # JoyToKey, Xpadder, AntiMicro/AntiMicroX (gamepad â†’ keyboard mappers).
    # Son legÃ­timos pero generan eventos de input sintÃ©ticos que parecen macros.
    'joytokey', 'joy2key', 'xpadder.exe',
    'antimicro', 'antimicrox',
    'controllercompanion', 'rewasd.exe',  # reWASD â€” gamepad mapper firmado
    'ds4windows', 'ds4-windows',          # DualShock 4 driver popular

    # â”€â”€ Filter #16 â€” AutoHotkey â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # AutoHotkey runtime y compiler. Los .ahk en sÃ­ podrÃ­an ser hack, pero el
    # runtime ".exe" del propio AHK no es la evidencia.
    'autohotkey\\autohotkey.exe', 'autohotkey64.exe', 'autohotkey32.exe',
    'autohotkeyu64.exe', 'autohotkeyu32.exe', 'ahk2exe.exe',
    'autohotkey\\compiler', 'autohotkey\\autohotkey.chm',

    # â”€â”€ Filter #17 â€” OBS Studio + plugins legÃ­timos â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # OBS hookea captura de ventanas (game capture), su plugin loader y
    # plugins firmados como StreamFX, NDI, advanced-scene-switcher.
    'obs-studio\\obs64.exe', 'obs-studio\\obs32.exe',
    'obs-studio\\obs-plugins',
    'obs-studio\\data\\obs-plugins',
    'streamfx', 'ndi.dll', 'libndi',
    'advanced-scene-switcher', 'obs-websocket',
    'obs-virtualcam', 'obs-vkcapture',
    'obs-streamfx', 'obs-multi-rtmp',
    'streamlabs obs', 'slobs', 'streamelements',
    'xsplit\\broadcaster',

    # Capturadoras alternativas firmadas
    'shadowplay', 'nvidia\\nvshadowplay', 'nvidia\\geforce experience',
    'nvcontainer.exe', 'nvgameshare.exe',
    'amd\\rxoverlay', 'amd\\amf',
    'xbox game bar', 'gamebar.exe', 'gamebarpresencewriter',
    'screen recorder', 'bandicam', 'fraps.exe',
    'lossless cut', 'shotcut',

    # â”€â”€ Bonus: emuladores firmados â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # Algunos hacks se han camuflado como emus. Los oficiales son seguros.
    'parsec\\parsec', 'parsecd.exe',         # remote play
    'moonlight\\moonlight', 'moonlight-qt',  # game streaming
    'sunshine\\sunshine.exe',                # host de moonlight

    # â”€â”€ Filter #23 â€” UWP / MSIX (Microsoft Store apps firmadas) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # WindowsApps/ ya estaba parcial. AcÃ¡ aÃ±adimos rutas mÃ¡s explÃ­citas y
    # patrones del AppRepository/StateRepository que aparecen como fp.
    'program files\\windowsapps\\microsoft.',
    'program files\\windowsapps\\xbox',
    'program files\\windowsapps\\spotifyab.spotifymusic',
    'program files\\windowsapps\\discord',
    'appdata\\local\\packages\\microsoft.',
    'appdata\\local\\packages\\xbox',
    'appdata\\local\\packages\\spotifyab.',
    'appdata\\local\\packages\\netflix.',
    'staterepository-machine.srd', 'staterepository-app.srd',
    'apprepositorystatemachine', 'msixrepository',
    'windowsstore-msixappfilegateway',
    # Components silenciosos del runtime UWP
    'microsoft.vclibs', 'microsoft.netnative',
    'microsoft.ui.xaml', 'microsoft.windowsappruntime',
    'microsoft.dxruntime', 'microsoft.gamingservices',
    'microsoft.xboxgamingoverlay', 'microsoft.xboxidentityprovider',
    'microsoft.xboxlive.', 'microsoft.gamebar',

    # â”€â”€ Filter #56 â€” Remote support tools autorizados â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # TeamViewer / AnyDesk / Chrome Remote / Splashtop. Estos hookean
    # input y captura, lo que las heurÃ­sticas viejas marcaban como cheat
    # backdoor. Si estÃ¡n en su carpeta canÃ³nica (Program Files), legit.
    # NOTA: tambiÃ©n podrÃ­an usarse en ataques sociales â€” el staff debe
    # cruzar este FP filter con el contexto del scan (lo dejamos como
    # whitelist de path para reducir ruido, no un absuelve total).
    'teamviewer.exe', 'tv_w32.exe', 'tv_x64.exe',
    'program files\\teamviewer', 'program files (x86)\\teamviewer',
    'anydesk.exe', 'program files (x86)\\anydesk',
    'program files\\anydesk',
    'chrome remote desktop', 'remoting_host.exe',
    'splashtop\\splashtop business', 'srservice.exe',
    'remotepc.exe', 'rustdesk.exe',  # RustDesk â€” open source remote
    'logmein\\logmein hamachi', 'logmein\\logmeinrescue',
    'gotomypc', 'gotomeeting',
    # Microsoft propio para soporte
    'quickassist.exe',                       # Quick Assist (Windows 11)
    'microsoft\\windows\\quickassist',
    'remoteassistance.exe', 'msra.exe',
    # Atajos de gestiÃ³n empresarial
    'connectwise control', 'screenconnect.client',
    'kaseya', 'ninja-remote', 'ninjaremote',
    'datto.rmm', 'syncro.live',

    # â”€â”€ Filter #29 â€” TLauncher contextual (advisory, no FP duro) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # TLauncher es FP recurrente en zonas de bajo poder adquisitivo. Sus
    # binarios y carpetas se whitelist por path; si el filename es hack
    # explÃ­cito, igual reportamos (no se arriesga falso negativo).
    'tlauncher.exe', 'tlauncher\\bin', 'tlauncher\\game',
    'tlauncher\\properties', 'tlauncher_repo',

    # â”€â”€ Filter #34 â€” Mods en folders de launchers (CurseForge, Lunar...) â”€â”€
    # Ampliamos el whitelist existente: las carpetas mods/cache/instances
    # de los launchers mÃ¡s comunes. F#53 ya cubre paths de update â€”
    # esto cubre el storage estÃ¡tico.
    'curseforge\\minecraft\\instances', 'curseforge\\minecraft\\install',
    'overwolf\\packages\\extensions',
    'multimc\\instances', 'prismlauncher\\instances',
    'gdlauncher\\instances', 'gdlauncher\\datastore',
    'atlauncher\\instances', 'atlauncher\\downloads',
    'lunarclient\\game-cache', 'lunarclient\\offline',
    'lunarclient\\settings\\game', 'lunarclient\\profiles',
    'lunarclient\\jre', 'lunar client\\jre',
    'badlion client\\bcc', 'badlionclient\\bcc',
    'badlion client\\cache', 'badlion client\\logs\\launcher',
    'modrinth-app\\meta', 'modrinth.app\\profiles',

    # â”€â”€ Filter #47 â€” Steam Workshop subscriptions â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    'steam\\steamapps\\workshop', 'steam\\workshop',
    'steam\\steamapps\\common',          # juegos instalados (no son hack)
    'steam\\steamapps\\downloading',     # downloads en curso
    'steam\\appcache', 'steam\\config',

    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    # PACK 29 â€” Lote masivo de whitelists server-side adicionales.
    # Aplicado retroactivamente a scans antiguos via _scrub_results_for_display.
    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

    # â”€â”€ Filter #5 (extensiÃ³n) â€” Launchers MC oficiales/third-party adicionales
    'xmcl-launcher', 'x minecraft launcher',  # XMCL â€” open-source, popular en CN
    'hmcl', 'hmcl-launcher', 'huangminecraftlauncher',  # HMCL Java (no Android variant)
    'magiclauncher', 'magic launcher',
    'fjordlauncher', 'fjord launcher',
    'technic launcher', 'technicpack',
    'mclauncher\\', 'mclauncher.exe',
    'voidclient', 'voidlauncher',
    'salwyrr', 'salwyrr launcher',
    'pcl2\\', 'pcl-launcher',         # Plain Craft Launcher 2 â€” popular CN
    'cmclauncher\\', 'cmcl',
    'easymc',
    'pojavlauncher\\',                 # Pojav (tambiÃ©n usado en desktop por algunos)
    'tlauncher 2',                     # TLauncher v2 modern
    'novalauncher\\', 'nova launcher minecraft',
    # Forks legÃ­timos abiertos
    'siged-launcher', 'olive launcher', 'olivelauncher',

    # â”€â”€ Filter #7 â€” ReputaciÃ³n por path: rutas inherentemente firmadas â”€â”€â”€â”€â”€
    'program files\\windowsapps\\microsoft.',    # UWP firmados Microsoft
    'program files\\windowsapps\\xboxgaming',    # Xbox apps
    'program files\\windowsapps\\spotifyab.',    # Spotify UWP
    'program files\\windowsapps\\discordinc.',   # Discord UWP (raro pero existe)
    'program files\\common files\\microsoft shared\\',
    'program files (x86)\\common files\\microsoft shared\\',
    'program files\\common files\\system\\',
    'windowsapps\\runtime',                       # runtime files UWP
    'windowsapps\\sdk',
    # Microsoft Store SDK / runtime
    'microsoft.vclibs.140', 'microsoft.netnative',
    'microsoft.ui.xaml', 'microsoft.windowsappruntime',

    # â”€â”€ Filter #10 â€” Patrones genÃ©ricos test/demo/sample en filename â”€â”€â”€â”€â”€â”€â”€
    # Si el path/nombre contiene estos tokens, MUY probable que sea archivo
    # de prueba personal del usuario, no un cheat real (los cheats no se
    # llaman a sÃ­ mismos "test"). Solo aplica como segmento de path â€”
    # si el filename completo es 'test.exe' aÃºn se reporta porque puede
    # ser un binario malicioso renombrado.
    '\\demos\\', '\\demo\\', '\\samples\\', '\\examples\\',
    '\\tests\\', '\\test_', '\\proyectos demo\\',
    '\\tutorial\\', '\\tutoriales\\',

    # â”€â”€ Filter #28 â€” Paths localizados (es-AR/es-MX/es-ES) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # Windows con idioma espaÃ±ol traduce "Documents" a "Documentos", etc.
    # Estos paths son carpetas del usuario, no instalaciones de cheats.
    'usuarios\\public\\', 'usuarios\\publico\\',
    '\\mis documentos\\', '\\documentos\\favoritos\\',
    '\\descargas\\drivers',
    '\\escritorio\\backups',
    '\\imagenes\\', '\\videos\\', '\\musica\\',

    # â”€â”€ Filter #32 â€” Caches de package managers (no contienen ejecutables â”€â”€
    # propios; son cachÃ©s de Maven/Gradle/npm/pip/cargo/yarn).
    '\\.gradle\\caches', '\\.gradle\\wrapper\\dists',
    '\\.m2\\repository', '\\.ivy2\\cache',
    'appdata\\local\\npm-cache',
    'appdata\\roaming\\npm', 'appdata\\local\\yarn',
    'appdata\\local\\pip\\cache', 'appdata\\local\\pypoetry\\cache',
    '\\.cargo\\registry', '\\.cargo\\git',
    '\\.cache\\pip', '\\.cache\\yarn', '\\.cache\\go-build',
    '\\.nuget\\packages', '\\packages\\.nuget',

    # â”€â”€ Filter #35 â€” Cache de modpacks de CurseForge / Modrinth â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # Mods descargados auto por el launcher cuando el usuario suscribe a un
    # modpack. Mismos archivos en N PCs, no cuenta como "hack instalado".
    '.minecraft\\mods\\caches', '.minecraft\\modpacks\\',
    'curseforge\\install\\', 'curseforge\\downloads\\',
    'modrinth\\downloads\\', 'modrinth\\cache\\',
    'feathermc\\modpacks\\', 'feather launcher\\modpacks\\',
    'lunarclient\\modpacks\\',
    'gdlauncher\\downloads', 'gdlauncher\\packs',
    'multimc\\meta\\', 'prismlauncher\\meta\\',
    'overwolf\\packages\\extensions\\onjbihaipdjlphmlpedhdpgpaihjeofg\\',  # CurseForge ext stable id

    # â”€â”€ Filter #52 â€” Reinstalaciones legÃ­timas (cache/installer paths) â”€â”€â”€â”€â”€
    # Carpetas de instaladores tÃ­picos. Si un mismo binario aparece en N
    # scans del mismo usuario, es reinstalaciÃ³n, no nuevo evento.
    '\\appdata\\local\\package cache\\',     # Visual Studio installer cache
    '\\package cache\\{',                    # GUID-based installer cache
    'softwaredistribution\\download',        # Windows Update
    'wuredist\\', 'wuredownloads\\',
    '\\msocache\\', 'mshtmedit',

    # â”€â”€ Filter #60 â€” Cooldown markers: paths donde la empresa ya marcÃ³ FP â”€â”€
    # Soportado a nivel de fragmento aprendido (learned_legit_paths) â€”
    # solo agregamos aquÃ­ defaults globales para acelerar. La lÃ³gica de
    # cooldown por empresa va en el endpoint /api/staff/learn-fp ya existente.

    # â”€â”€ Bonus extra: programas legÃ­timos comunes mal-flageados â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    'jdownloader', 'jdownloader2',           # download manager
    'qbittorrent', 'utorrent',               # torrent (legal o no, no es MC hack)
    'transmission-qt',
    '7-zip\\', '7z.exe', '7za.exe',
    'winrar\\', 'winrar.exe',
    'notepad++', 'sublime text', 'vscode',
    'audacity\\', 'davinci resolve\\',
    'unity hub', 'unityhub.exe',
    'godot\\', 'godot.exe',
    'blender\\', 'blender.exe',
    'autodesk\\fusion 360',
    'docker desktop\\', 'wsl\\',
    'powertoys\\',
    'flow.launcher', 'powerToys.exe',
    'wechat\\', 'qqlive\\', 'tencent\\',
    'dropbox\\', 'box drive', 'mega.nz',
    'putty.exe', 'mobaxterm', 'winscp',
    'filezilla\\',
    'spotify.exe', 'apple music\\', 'apple\\itunes',
    # Repos de scripts personales del usuario (proyectos legÃ­timos suyos)
    '\\onedrive\\documents\\github\\',
    '\\users\\public\\desktop\\',
    '\\projects\\', '\\proyectos\\',
    '\\repositories\\', '\\repos\\',
]


# â”€â”€ Filter #43, #44 â€” Settings por empresa (threshold dinÃ¡mico + modo) â”€â”€â”€â”€â”€â”€
# Permite que cada empresa configure su polÃ­tica:
#   * mode: 'tournament' (mÃ¡s estricto, threshold default -10), 'normal',
#           'casual' (mÃ¡s permisivo, threshold default +10).
#   * threshold_critical / threshold_suspicious: umbrales custom (override
#           del default {70, 30}).
# Cargado on-demand con cache 60s por empresa. Si la empresa no configurÃ³
# nada, devuelve los defaults.
_company_settings_cache = {}    # {company_id: (settings_dict, ts)}
_COMPANY_SETTINGS_TTL = 60.0     # 1 min â€” staff verÃ¡ los cambios pronto

def _get_company_settings(company_id):
    if not company_id:
        return {'mode': 'normal', 'threshold_critical': 70, 'threshold_suspicious': 30}
    import time as _time
    cached = _company_settings_cache.get(company_id)
    if cached and (_time.time() - cached[1]) < _COMPANY_SETTINGS_TTL:
        return cached[0]
    settings = {'mode': 'normal', 'threshold_critical': 70, 'threshold_suspicious': 30}
    try:
        with get_api_db_cursor() as cur:
            cur.execute('''
                CREATE TABLE IF NOT EXISTS company_settings (
                    company_id          INTEGER PRIMARY KEY,
                    mode                VARCHAR(20)  DEFAULT 'normal',
                    threshold_critical  INTEGER      DEFAULT 70,
                    threshold_suspicious INTEGER     DEFAULT 30,
                    updated_at          TIMESTAMP DEFAULT NOW(),
                    updated_by          INTEGER
                )
            ''')
            cur.execute(
                f'SELECT mode, threshold_critical, threshold_suspicious '
                f'FROM company_settings WHERE company_id = {_PH}',
                (company_id,)
            )
            row = cur.fetchone()
            if row:
                if isinstance(row, dict):
                    settings['mode'] = row.get('mode') or 'normal'
                    settings['threshold_critical'] = int(row.get('threshold_critical') or 70)
                    settings['threshold_suspicious'] = int(row.get('threshold_suspicious') or 30)
                else:
                    settings['mode'] = row[0] or 'normal'
                    settings['threshold_critical'] = int(row[1] or 70)
                    settings['threshold_suspicious'] = int(row[2] or 30)
    except Exception as e:
        print(f'[CompanySettings] error: {e}')

    # Pack 32 F#60 â€” Aplicar threshold_bump del cooldown si existe.
    # No mutamos los valores guardados en BD; sumamos en memoria por
    # request. Si la empresa hizo muchos overturns o learn-fp, sus
    # thresholds suben para forzar revisiÃ³n mÃ¡s estricta.
    if _AI_TRUST_AVAILABLE:
        try:
            with get_api_db_cursor() as _ccur:
                cd = _ai_trust.get_company_cooldown(_ccur, company_id)
                bump = int(cd.get('threshold_bump') or 0)
                if bump > 0:
                    settings['threshold_critical'] = min(
                        99, settings['threshold_critical'] + bump
                    )
                    settings['threshold_suspicious'] = min(
                        settings['threshold_critical'] - 1,
                        settings['threshold_suspicious'] + bump
                    )
                    settings['cooldown_active']  = True
                    settings['cooldown_bump']    = bump
                    settings['cooldown_reason']  = (
                        f"FP={cd.get('fp_count_24h',0)} "
                        f"overturns={cd.get('overturn_count_24h',0)}"
                    )
                else:
                    settings['cooldown_active'] = False
        except Exception as _e_cd:
            print(f'[CompanySettings.cooldown] {_e_cd}')

    _company_settings_cache[company_id] = (settings, _time.time())
    return settings


@app.route('/api/company/settings', methods=['GET'])
@login_required
def get_company_settings_endpoint():
    company_id = session.get('company_id')
    if not company_id:
        return jsonify({'error': 'Sin empresa asignada'}), 400
    return jsonify(_get_company_settings(company_id)), 200


@app.route('/api/company/settings', methods=['POST'])
@login_required
def set_company_settings_endpoint():
    user_id = session.get('user_id')
    company_id = session.get('company_id')
    if not company_id:
        return jsonify({'error': 'Sin empresa asignada'}), 400
    if not (is_admin(user_id) or is_company_admin(user_id, company_id)):
        return jsonify({'error': 'Solo admins de empresa pueden cambiar settings'}), 403
    data = request.get_json(silent=True) or {}
    mode = (data.get('mode') or 'normal').lower()
    if mode not in ('tournament', 'normal', 'casual'):
        return jsonify({'error': "mode debe ser tournament|normal|casual"}), 400
    try:
        crit = int(data.get('threshold_critical', 70))
        susp = int(data.get('threshold_suspicious', 30))
    except (TypeError, ValueError):
        return jsonify({'error': 'thresholds invÃ¡lidos'}), 400
    if not (1 <= susp < crit <= 99):
        return jsonify({'error': 'thresholds: suspicious < critical, ambos 1..99'}), 400
    try:
        with get_api_db_cursor() as cur:
            cur.execute('''
                CREATE TABLE IF NOT EXISTS company_settings (
                    company_id          INTEGER PRIMARY KEY,
                    mode                VARCHAR(20)  DEFAULT 'normal',
                    threshold_critical  INTEGER      DEFAULT 70,
                    threshold_suspicious INTEGER     DEFAULT 30,
                    updated_at          TIMESTAMP DEFAULT NOW(),
                    updated_by          INTEGER
                )
            ''')
            # UPSERT manual: PostgreSQL soporta ON CONFLICT, MySQL ON DUPLICATE KEY.
            try:
                cur.execute(
                    f'INSERT INTO company_settings (company_id, mode, threshold_critical, threshold_suspicious, updated_at, updated_by) '
                    f'VALUES ({_PH}, {_PH}, {_PH}, {_PH}, NOW(), {_PH}) '
                    f'ON CONFLICT (company_id) DO UPDATE SET '
                    f'mode = EXCLUDED.mode, threshold_critical = EXCLUDED.threshold_critical, '
                    f'threshold_suspicious = EXCLUDED.threshold_suspicious, updated_at = NOW(), updated_by = EXCLUDED.updated_by',
                    (company_id, mode, crit, susp, user_id)
                )
            except Exception:
                # Fallback DELETE + INSERT
                cur.execute(f'DELETE FROM company_settings WHERE company_id = {_PH}', (company_id,))
                cur.execute(
                    f'INSERT INTO company_settings (company_id, mode, threshold_critical, threshold_suspicious, updated_by) '
                    f'VALUES ({_PH}, {_PH}, {_PH}, {_PH}, {_PH})',
                    (company_id, mode, crit, susp, user_id)
                )
        # Invalidar cachÃ©
        _company_settings_cache.pop(company_id, None)
        try:
            _log_staff_action('company_settings_update',
                              detail=f'mode={mode} crit={crit} susp={susp}')
        except Exception:
            pass
        return jsonify({'ok': True, 'mode': mode,
                        'threshold_critical': crit, 'threshold_suspicious': susp}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Tipos de issue que nunca deben guardarse (FP estructural, no por ruta)
_ZERO_RISK_ISSUE_TYPES = {
    'texture_pack', 'texture_pack_xray', 'texture_pack_analysis',
    'resource_pack', 'resource_pack_xray',
    'event_logs',   # cambios fecha/hora: los dispara Windows NTP automÃ¡ticamente
}


_lp_cache: dict = {'paths': [], 'ts': 0.0}
_LP_CACHE_TTL = 300  # 5 minutos


def _get_learned_legit_paths() -> list:
    """Devuelve lista de rutas legÃ­timas aprendidas por el staff (cachÃ© 5 min)."""
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
        pass  # si falla la BD usamos la cachÃ© vieja o lista vacÃ­a
    return _lp_cache['paths']


import re as _re_fp
# CategorÃ­as que solo existÃ­an en EXEs viejos con parsers buggeados â€” 100% FP
# APPCOMPAT y USN_FORENSICS ya no se filtran: el nuevo scanner los usa correctamente
_LEGACY_FP_CATEGORIES = {'EXECUTED_DELETED'}
# Patrones de basura binaria en nombres â€” parser viejo decodificaba .pf como UTF-16
_BINARY_GARBAGE_RE = _re_fp.compile(
    r'\bLMEM\b|Windows\.Data\.|Matrix3x2|\.CenterX|\.CenterY|'
    r'ItemReference|MEOW\b|CloudData|RevealBrush|XamlAnim|'
    r'BaseM\s+I&|BorderBrush\s+[A-Z]|\bMEM\s+[A-Z]|\bLE[A-Z]\b|'
    r'D2D1\.|DCompositionBrush|DXGI_|\\u[0-9a-f]{4}|'
    r'^[\x00-\x08\x0b\x0c\x0e-\x1f]{2,}|[\xc0-\xff]{6,}',
    _re_fp.IGNORECASE
)
# Strings de control / no-imprimibles tÃ­picos de basura binaria
_NONPRINTABLE_RE = _re_fp.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')
# Caracteres "raros" no-ASCII que aparecen al decodificar UTF-16 incorrectamente
_HIGH_BYTE_RUN_RE = _re_fp.compile(r'[\u0080-\uFFFF]{4,}')


def _normalize_path(p: str) -> str:
    """Normaliza una ruta para comparaciÃ³n robusta:
       - lowercase
       - separadores unificados a '\\'
       - quitar prefijos extendidos '\\\\?\\' y '\\\\.\\'
       - colapsar separadores duplicados.
    """
    if not p:
        return ''
    s = str(p).lower().strip()
    # Algunos scanners reportan barras escapadas o URL-encoded (%5C).
    s = s.replace('%5c', '\\').replace('%2f', '/')
    s = s.replace('/', '\\')
    if s.startswith('\\\\?\\') or s.startswith('\\\\.\\'):
        s = s[4:]
    while '\\\\' in s:
        s = s.replace('\\\\', '\\')
    return s


def _is_garbage_string(s: str) -> bool:
    """True si el string parece basura binaria (parser viejo, encoding roto)."""
    if not s:
        return False
    s_str = str(s)
    if len(s_str) > 600:
        return True  # nombres absurdamente largos = basura
    # Caracteres de control no-imprimibles
    if len(_NONPRINTABLE_RE.findall(s_str)) >= 2:
        return True
    # Run largo de caracteres no-ASCII (tÃ­pico de UTF-16 mal decodificado)
    if _HIGH_BYTE_RUN_RE.search(s_str):
        return True
    if _BINARY_GARBAGE_RE.search(s_str):
        return True
    # Ratio de caracteres alfanumÃ©ricos: si <30% es probable basura
    alnum = sum(1 for c in s_str if c.isalnum() or c in ' .\\/_-:()[]')
    if len(s_str) >= 12 and alnum / max(1, len(s_str)) < 0.30:
        return True
    return False


def _is_server_false_positive(result: dict) -> bool:
    """Devuelve True si el resultado es un falso positivo conocido y debe descartarse.
    Mejorado: normaliza paths, detecta basura binaria en cualquier campo,
    descarta confidence cero, y aplica matching robusto contra fragmentos seguros.
    """
    # FILE_ACTIVITY (tab Logs del Explore): historial informacional
    # de archivos creados/modificados/borrados/ejecutados desde el Ãºltimo boot.
    # NUNCA aplicar el filtro de FPs aquÃ­ â€” pueden caer perfectamente en
    # rutas de "fragmentos seguros" (AppData, Windows, etc.) y eso NO las
    # convierte en FPs: son justamente lo que queremos mostrar como historial.
    categoria = (result.get('categoria') or result.get('issue_category') or '').upper()
    if categoria == 'FILE_ACTIVITY':
        # Solo descartar basura binaria (parsers rotos), nada mÃ¡s
        ruta_raw = result.get('ruta', '') or result.get('issue_path', '') or ''
        nombre = (result.get('nombre', '') or result.get('archivo', '')
                  or result.get('issue_name', '') or '')
        if _is_garbage_string(nombre) or _is_garbage_string(ruta_raw):
            return True
        return False

    # El propio scanner jamás es un hallazgo real
    ruta_raw = result.get('ruta', '') or result.get('issue_path', '') or ''
    nombre   = (result.get('nombre', '') or result.get('archivo', '')
                or result.get('issue_name', '') or '')
    _self = (ruta_raw + '|' + nombre).lower()
    if 'argusscanner' in _self or 'minecraftsstool' in _self:
        return True

    # Tipos que son FP estructural independientemente de la ruta
    tipo = (result.get('tipo') or result.get('issue_type') or '').lower().replace(' ', '_')
    _NEVER_SCRUB_TYPES = {
        'blacklisted_mod', 'dll_injection_java', 'injected_dll', 'javaagent_injection',
        'injector_process', 'ghost_client_config', 'ghost_client_registry',
        'browser_visited_hack', 'browser_download_hack', 'modified_minecraft_jar',
        'hack_string_in_loaded_jar', 'weave_loader', 'prefetch_hack', 'kill_chain',
        'registry_run_hack', 'registry_userassist_hack', 'cloud_hash_match',
    }
    if tipo in _NEVER_SCRUB_TYPES:
        return False
    if tipo in _ZERO_RISK_ISSUE_TYPES:
        return True

    # CategorÃ­as de EXE antiguo con parsers buggeados
    if categoria in _LEGACY_FP_CATEGORIES:
        return True

    ruta     = _normalize_path(ruta_raw)
    combined = ruta + '|' + (nombre or '').lower()

    # Confidence numÃ©ricamente nula y sin patrones detectados â†’ ruido
    try:
        c = float(result.get('confidence', 0) or 0)
        if c > 1.0:
            c = c / 100.0
    except (TypeError, ValueError):
        c = 0.0
    patterns = result.get('detected_patterns') or []
    has_evidence = bool(patterns) or bool(result.get('file_hash'))
    nivel = (result.get('alerta') or result.get('alert_level') or '').upper()
    if c <= 0.05 and not has_evidence and nivel not in ('CRITICAL', 'SOSPECHOSO', 'MUY_SOSPECHOSO'):
        return True

    # Basura binaria en nombre o ruta (parser viejo decodificaba .pf como UTF-16)
    if _is_garbage_string(nombre) or _is_garbage_string(ruta_raw):
        return True

    # Hallazgos sin nombre y sin ruta no son procesables
    if not (nombre or '').strip() and not (ruta or '').strip():
        return True

    # Hallazgos con descripciÃ³n genÃ©rica de fecha/hora del sistema (NTP) â€” FP histÃ³rico
    desc = (result.get('descripcion') or result.get('issue_description') or '').lower()
    if 'cambio de hora' in desc or 'time-service' in desc or 'w32time' in desc:
        return True

    if any(frag in combined for frag in _SERVER_FP_FRAGMENTS):
        return True

    # Filter #37 â€” `.rise` extensiÃ³n vs folder.
    # Rise client tiene su carpeta de config en %appdata%\.rise (o similar).
    # Si el path es una CARPETA `.rise\` (no termina en .rise como extensiÃ³n
    # real de archivo), descartar â€” solo el archivo con extensiÃ³n .rise
    # cuenta como evidencia (raro de ver fuera del cheat real).
    # HeurÃ­stica: si '.rise' aparece como segmento de directorio (con
    # separador despuÃ©s), es config folder; si es la extensiÃ³n final del
    # archivo (nombre.rise) o nombre completo, sigue evaluÃ¡ndose.
    try:
        # Nombre de archivo (Ãºltimo segmento de la ruta)
        last_seg = (nombre or '').lower().strip()
        # Si es CARPETA .rise (tÃ­pico de Rise/Vape config legÃ­tima del propio
        # usuario que ya desinstalÃ³ y solo dejÃ³ la config) â†’ soft FP.
        # Solo skipea si el filename NO termina en .rise como extensiÃ³n
        # real (Ãºltimo .rise antes del fin del string).
        is_rise_folder_path = (
            ('\\.rise\\' in combined) or ('/.rise/' in combined) or
            ('\\.rise/' in combined) or ('/.rise\\' in combined)
        )
        ends_in_rise_ext = last_seg.endswith('.rise') and last_seg != '.rise'
        if is_rise_folder_path and not ends_in_rise_ext:
            return True
    except Exception:
        pass

    # Filter #11 â€” Aprendizaje incremental por feedback. Las rutas marcadas
    # como 'legitimate_path' por el staff (vÃ­a learned_patterns) se aplican
    # ahora retroactivamente a TODOS los scans servidos. La funciÃ³n ya
    # existÃ­a pero no se llamaba. Cache de 5 min en _get_learned_legit_paths
    # evita el round-trip a BD por cada result.
    try:
        learned = _get_learned_legit_paths()
        if learned and any(frag in combined for frag in learned):
            return True
    except Exception:
        pass

    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    # PACK 29 â€” heurÃ­sticas inline (sin tabla / sin red) que filtran
    # categorÃ­as obvias de FP que no se pueden capturar solo con fragmentos.
    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    try:
        name_lower = (nombre or '').lower().strip()

        # Filter #3 â€” "killaura" / "aimbot" / etc como nombre LITERAL del archivo
        # en path de usuario (Documents/Escritorio/Downloads), con extensiÃ³n
        # de imagen/texto/video/pdf â†’ es nota personal o screenshot, no el
        # cheat real. Los cheats reales SIEMPRE son .exe/.jar/.dll en paths
        # de instalaciÃ³n (no en Documents).
        _user_path_segs = (
            '\\desktop\\', '\\downloads\\', '\\documents\\',
            '\\documentos\\', '\\descargas\\', '\\escritorio\\',
            '\\users\\public\\', '\\users\\publico\\',
            '\\imagenes\\', '\\pictures\\', '\\my pictures\\',
            '\\videos\\', '\\music\\', '\\musica\\',
        )
        _mc_install_segs = (
            '\\.minecraft\\mods', '\\.minecraft\\bin',
            'lunarclient\\offline', 'feathermc\\mods',
            'curseforge\\minecraft\\instances\\',
            'multimc\\instances\\', 'prismlauncher\\instances\\',
            'gdlauncher\\instances\\', 'atlauncher\\instances\\',
            'modrinth-app\\profiles\\',
        )
        _harmless_extensions = (
            '.txt', '.md', '.rtf', '.docx', '.doc', '.pdf', '.html', '.htm',
            '.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.svg', '.ico',
            '.mp4', '.avi', '.mov', '.mkv', '.webm', '.mp3', '.wav', '.ogg', '.flac',
            '.json', '.xml', '.yaml', '.yml', '.csv', '.log', '.ini', '.cfg',
        )
        in_user_path = any(seg in combined for seg in _user_path_segs)
        in_mc_install = any(seg in combined for seg in _mc_install_segs)
        ends_harmless = name_lower.endswith(_harmless_extensions)
        if in_user_path and not in_mc_install and ends_harmless:
            # Ej: "killaura tutorial.txt", "vape_screenshot.png" en Downloads
            return True

        # Filter #10 â€” patrones test/demo/sample/example/tutorial/proyecto en
        # nombre del archivo (no solo path) y en path de usuario. Estos suelen
        # ser proyectos personales/test del usuario, no cheats reales.
        _self_test_tokens = (
            'sample_', 'example_', 'demo_', 'test_', 'prueba_', 'pruebas_',
            'tutorial_', 'tutoriales_', 'proyecto_', 'proyectos_',
            'mi proyecto', 'mi prueba', 'mi test',
        )
        if in_user_path and any(tok in name_lower for tok in _self_test_tokens):
            # Solo descarta si el alert es bajo o es archivo benigno
            if nivel not in ('CRITICAL',):
                return True

        # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
        # PACK 40 â€” Filter F#1 cierre (instaladores legÃ­timos por filename
        # + publisher pattern). Server-side, sin DB de hashes externa.
        # Cubre el Ãºltimo 30% que faltaba despuÃ©s del path-whitelist Pack 29.
        # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
        if is_known_legit_installer(name_lower, combined):
            return True

        # PACK 55 — ruido típico en PCs de staff/dev (audit scan #110)
        _pat_raw = result.get('detected_patterns') or []
        if isinstance(_pat_raw, str):
            try:
                _pat_raw = json.loads(_pat_raw)
            except Exception:
                _pat_raw = [_pat_raw]
        _pat_s = ' '.join(str(p).lower() for p in (_pat_raw if isinstance(_pat_raw, list) else []))

        if tipo == 'crash_dump' or '\\crashdumps\\' in combined:
            return True
        if tipo == 'defender_health_event' or 'defender_health' in _pat_s:
            return True
        if tipo == 'razer_installed' or 'razer_macros' in _pat_s or 'razer_installed' in _pat_s:
            return True
        if 'wallpaperservice32' in combined:
            return True
        if name_lower == 'sidebar.json' and (
            'feather' in combined or 'feathermc' in combined or '\\.minecraft\\feather' in combined
        ):
            return True
        if '\\temp\\lwjgl' in combined or (
            'lwjgl' in combined and '\\appdata\\local\\temp\\' in combined
        ):
            return True
        if tipo == 'ghost_client_config' and (
            'versiones de minecraft' in desc or 'no-vanilla' in desc
            or ('sin metadata' in desc and 'companyname' in desc)
        ):
            return True
        if tipo == 'ghost_client_config' and 'config_tfidf' in _pat_s and (
            'feather' in combined or 'sidebar.json' in name_lower
        ):
            return True
        if tipo == 'javaagent_injection' and 'rwx_large_regions' in _pat_s:
            return True
        if 'multiple_javaw' in _pat_s or tipo == 'multiple_javaw':
            return True
    except Exception:
        pass

    return False


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Filter F#1 â€” Whitelist de instaladores legÃ­timos por filename pattern
# (server-side, sin VirusTotal Intelligence ni Microsoft Catalog).
#
# Estrategia: en lugar de mantener una tabla de hashes (carÃ­simo de poblar
# y mantener), reconocemos el filename + estructura tÃ­pica de los instaladores
# de software popular. Los cheats reales NO se distribuyen como
# "EpicGamesLauncherInstaller.exe" en Downloads â€” vienen como `vape.jar`
# en `.minecraft\mods` o `client.exe` en una carpeta sin firma.
#
# Reglas:
#   1. Filename matchea uno de los patterns conocidos.
#   2. Path tÃ­pico de instalador (Downloads, Temp, %TEMP%, Cache, AppData,
#      Program Files, Recycle, MSOCache, package cache...).
#   3. ExtensiÃ³n .exe o .msi (los cheats raramente usan .msi).
#
# Si los 3 se cumplen â†’ es un instalador reconocido y se descarta como FP.
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
import re as _re_legit_installer

_KNOWN_INSTALLER_PATTERNS = [
    # NVIDIA
    _re_legit_installer.compile(r'(?:^|\W)nvidia[-_ ]?(?:geforce|game|app|experience|driver|broadcast|inspector|control[-_ ]?panel)?[-_ ]?(?:setup|installer|update)?[-_ \d\.\w]*\.exe$'),
    _re_legit_installer.compile(r'^geforce[-_ ]?experience[-_ ]?(?:setup|installer|update|app)[-_ \d\.\w]*\.exe$'),
    _re_legit_installer.compile(r'^nvgflashwindows.*\.exe$'),
    # AMD
    _re_legit_installer.compile(r'^(?:amd|radeon)[-_ ]?software[-_ ]?(?:adrenalin|crimson)?[-_ \d\.\w]*\.exe$'),
    _re_legit_installer.compile(r'^amd[-_ ]?(?:chipset|driver|cleanup[-_ ]?utility)[-_ \d\.\w]*\.exe$'),
    # Intel
    _re_legit_installer.compile(r'^intel[-_ ]?(?:driver|graphics|wireless|chipset|arc|installation)[-_ ]?(?:assistant|setup|installer)?[-_ \d\.\w]*\.exe$'),
    _re_legit_installer.compile(r'^igfxsetup[-_ \d\.\w]*\.exe$'),
    _re_legit_installer.compile(r'^wirelesssetup[-_ \d\.\w]*\.exe$'),
    # Microsoft Visual C++ Redistributables / .NET / Edge / Office / Visual Studio
    _re_legit_installer.compile(r'^vc(?:_|-)redist[-_\.\w]*\.(?:exe|msi)$'),
    _re_legit_installer.compile(r'^(?:vc(?:pp|\+\+))[-_ ]?\d{4}[-_ ]?redist.*\.(?:exe|msi)$'),
    _re_legit_installer.compile(r'^(?:dotnet|netcore|net[-_]framework)[-_ ]?(?:runtime|sdk|installer)?[-_ \d\.\w]*\.(?:exe|msi)$'),
    _re_legit_installer.compile(r'^windowsdesktop[-_ ]?runtime[-_ \d\.\w]*\.exe$'),
    _re_legit_installer.compile(r'^aspnetcore[-_ ]?runtime[-_ \d\.\w]*\.exe$'),
    _re_legit_installer.compile(r'^(?:office|o365|microsoft365)[-_ ]?(?:setup|installer|home|business|pro)?[-_ \d\.\w]*\.exe$'),
    _re_legit_installer.compile(r'^(?:officesetup|onenotesetup|teamssetup|outlooksetup|wordsetup|excelsetup|powerpointsetup)[-_ \d\.\w]*\.exe$'),
    _re_legit_installer.compile(r'^(?:edge|microsoftedge|edgewebview)[-_ ]?(?:setup|installer|update)?[-_ \d\.\w]*\.exe$'),
    _re_legit_installer.compile(r'^(?:visualstudio|vs[-_ ]?(?:code|community|pro|enterprise))[-_ ]?(?:setup|installer|bootstrapper)?[-_ \d\.\w]*\.exe$'),
    _re_legit_installer.compile(r'^vssetup[-_ \d\.\w]*\.(?:exe|msi)$'),
    _re_legit_installer.compile(r'^(?:powershell|wt|windowsterminal)[-_ ]?(?:setup|installer|preview)?[-_ \d\.\w]*\.(?:exe|msi|msix)$'),
    _re_legit_installer.compile(r'^(?:directx|dxsetup|d3dx9_redist).*\.exe$'),
    _re_legit_installer.compile(r'^(?:winget|appinstaller|app[-_ ]?installer).*\.(?:exe|msi|msix|msixbundle)$'),
    # Browsers
    _re_legit_installer.compile(r'^(?:chrome|google[-_ ]?chrome)[-_ ]?(?:setup|installer)?[-_ \d\.\w]*\.exe$'),
    _re_legit_installer.compile(r'^firefox[-_ ]?(?:setup|installer|esr)?[-_ \d\.\w]*\.exe$'),
    _re_legit_installer.compile(r'^(?:brave|bravebrowser)[-_ ]?(?:setup|installer)?[-_ \d\.\w]*\.exe$'),
    _re_legit_installer.compile(r'^(?:opera|opera[-_ ]?gx|operasetup)[-_ ]?(?:setup|installer)?[-_ \d\.\w]*\.exe$'),
    _re_legit_installer.compile(r'^(?:vivaldi|vivaldi[-_ ]?installer)[-_ \d\.\w]*\.exe$'),
    # Discord, Spotify, Slack, Telegram
    _re_legit_installer.compile(r'^discordsetup[-_ \d\.\w]*\.exe$'),
    _re_legit_installer.compile(r'^discord(?:[-_ ]?canary|[-_ ]?ptb)?[-_ ]?setup[-_ \d\.\w]*\.exe$'),
    _re_legit_installer.compile(r'^spotifysetup[-_ \d\.\w]*\.exe$'),
    _re_legit_installer.compile(r'^slacksetup[-_ \d\.\w]*\.exe$'),
    _re_legit_installer.compile(r'^telegram[-_ ]?(?:setup|desktop|installer)?[-_ \d\.\w]*\.exe$'),
    _re_legit_installer.compile(r'^zoom(?:installer|setup|launcher)?[-_ \d\.\w]*\.exe$'),
    _re_legit_installer.compile(r'^teamssetup[-_ \d\.\w]*\.exe$'),
    # Steam, Epic, Riot, Battle.net, GOG, Origin, Ubisoft, Rockstar
    _re_legit_installer.compile(r'^steamsetup[-_ \d\.\w]*\.exe$'),
    _re_legit_installer.compile(r'^epicgameslauncherinstaller[-_ \d\.\w]*\.msi$'),
    _re_legit_installer.compile(r'^epicgameslauncher[-_ ]?(?:installer|setup)?[-_ \d\.\w]*\.(?:exe|msi)$'),
    _re_legit_installer.compile(r'^riotclient(?:installer|setup)?[-_ \d\.\w]*\.exe$'),
    _re_legit_installer.compile(r'^battle[-_ ]?net[-_ ]?(?:setup|installer)[-_ \d\.\w]*\.exe$'),
    _re_legit_installer.compile(r'^(?:gog|gog[-_ ]?galaxy)[-_ ]?(?:setup|installer|update)?[-_ \d\.\w]*\.(?:exe|msi)$'),
    _re_legit_installer.compile(r'^origin(?:setup|installer|launcher|update)?[-_ \d\.\w]*\.exe$'),
    _re_legit_installer.compile(r'^(?:ubisoft|uplay)[-_ ]?(?:connect|launcher|installer|setup)?[-_ \d\.\w]*\.exe$'),
    _re_legit_installer.compile(r'^(?:rockstar|socialclub)[-_ ]?(?:games[-_ ]?launcher)?[-_ ]?(?:setup|installer)?[-_ \d\.\w]*\.exe$'),
    _re_legit_installer.compile(r'^playstation(?:[-_ ]?launcher)?[-_ \d\.\w]*\.exe$'),
    # OBS, Streamlabs, capture tools
    _re_legit_installer.compile(r'^obs[-_ ]?studio[-_ ]?[-_ \d\.\w]*(?:full[-_ ]?installer|setup|installer)?[-_ \d\.\w]*\.exe$'),
    _re_legit_installer.compile(r'^streamlabs[-_ ]?(?:obs|desktop|setup|installer)?[-_ \d\.\w]*\.exe$'),
    # Java JDK / JRE / OpenJDK
    _re_legit_installer.compile(r'^(?:jdk|jre|openjdk|java)[-_ ]?(?:setup|installer|win|x64|x86)?[-_ \d\.\w]*\.(?:exe|msi)$'),
    _re_legit_installer.compile(r'^(?:adoptopenjdk|adoptium|temurin|corretto|liberica|zulu|microsoft[-_ ]?build[-_ ]?of[-_ ]?openjdk)[-_ ]?[-_ \d\.\w]*\.(?:exe|msi)$'),
    # Razer, Logitech, Corsair, SteelSeries, HyperX
    _re_legit_installer.compile(r'^(?:razer)[-_ ]?(?:synapse|cortex|chroma|installer|setup)?[-_ \d\.\w]*\.exe$'),
    _re_legit_installer.compile(r'^(?:logitech|lghub)[-_ ]?(?:installer|setup|gaming|update)?[-_ \d\.\w]*\.exe$'),
    _re_legit_installer.compile(r'^lghub_installer[-_ \d\.\w]*\.exe$'),
    _re_legit_installer.compile(r'^(?:icue|corsair[-_ ]?icue)[-_ ]?(?:installer|setup)?[-_ \d\.\w]*\.exe$'),
    _re_legit_installer.compile(r'^(?:steelseries|sse|ss[-_ ]?engine)[-_ ]?(?:gg|installer|setup)?[-_ \d\.\w]*\.exe$'),
    _re_legit_installer.compile(r'^(?:hyperx|ngenuity)[-_ ]?(?:installer|setup)?[-_ \d\.\w]*\.exe$'),
    # 7-Zip, WinRAR, NotePad++, Git
    _re_legit_installer.compile(r'^7z[-_ \d\.\w]*\.(?:exe|msi)$'),
    _re_legit_installer.compile(r'^winrar[-_ ]?(?:x64|x86)?[-_ \d\.\w]*\.exe$'),
    _re_legit_installer.compile(r'^npp[-_ ]?(?:installer|setup)?[-_ \d\.\w]*\.exe$'),
    _re_legit_installer.compile(r'^git[-_ ]?(?:bash|cmd|installer|setup|for[-_ ]?windows)?[-_ \d\.\w]*\.exe$'),
    _re_legit_installer.compile(r'^github[-_ ]?desktop[-_ ]?(?:setup|installer)?[-_ \d\.\w]*\.exe$'),
    # Antivirus (instaladores oficiales)
    _re_legit_installer.compile(r'^(?:malwarebytes|mbam|mb3|mb4)[-_ ]?(?:installer|setup)?[-_ \d\.\w]*\.exe$'),
    _re_legit_installer.compile(r'^(?:avast|avg|kaspersky|bitdefender|eset|norton|mcafee|sophos)[-_ ]?(?:setup|installer|free|antivirus)?[-_ \d\.\w]*\.exe$'),
    # Drivers genÃ©ricos (HID, audio realtek, etc.)
    _re_legit_installer.compile(r'^realtek[-_ ]?(?:audio|hd|wireless|setup)?[-_ \d\.\w]*\.exe$'),
    # NVidia/AMD legacy DCH installers
    _re_legit_installer.compile(r'^\d{3,4}\.\d{1,3}[-_ ]?(?:desktop|notebook|game|studio|dch)[-_ ]?(?:notebook|win\d+|x64|us|setup|international)?[-_ \d\.\w]*\.exe$'),
]

_INSTALLER_PATH_HINTS = (
    '\\downloads\\', '\\descargas\\', '\\desktop\\', '\\escritorio\\',
    '\\temp\\', '\\tmp\\', '\\appdata\\local\\temp\\',
    '\\windows\\softwaredistribution\\', '\\windows\\installer\\',
    '\\msocache\\', '\\windows\\winsxs\\',
    '\\packagecache\\', '\\package cache\\', '\\packages\\',
    '\\program files\\', '\\program files (x86)\\',
    '\\appdata\\local\\packages\\', '\\appdata\\local\\microsoft\\',
    '\\appdata\\roaming\\microsoft\\',
    '\\$recycle.bin\\', '\\recycle.bin\\',
    '\\nvidia\\', '\\amd\\', '\\intel\\',
    '\\squirreltemp\\', '\\update\\packages\\',
)


def is_known_legit_installer(name_lower: str, combined_lower: str) -> bool:
    """True si el filename matchea un installer reconocido Y estÃ¡ en path
    tÃ­pico de instalador. DiseÃ±ado para tener 0 FN sobre instaladores reales
    populares y ~0 FP sobre cheats (los cheats no se llaman como installers
    de NVIDIA / Office).

    Args:
        name_lower:     nombre del archivo en lowercase (sin path)
        combined_lower: path|name completo en lowercase
    """
    if not name_lower or not name_lower.endswith(('.exe', '.msi', '.msix', '.msixbundle')):
        return False
    # Match contra patterns
    matched_pattern = False
    for pat in _KNOWN_INSTALLER_PATTERNS:
        try:
            if pat.match(name_lower):
                matched_pattern = True
                break
        except Exception:
            continue
    if not matched_pattern:
        return False
    # Confirmar con un path hint razonable (los cheats tÃ­picos aparecen en
    # .minecraft/mods, no en C:\Windows\Installer ni en Downloads como
    # GeForceExperience-Setup.exe). Si el path es ambiguo (sin ningÃºn hint),
    # SOLO descartamos si el filename es muy especÃ­fico de installer
    # (contiene "setup" / "installer" / "redist" / "runtime").
    path_ok = any(hint in combined_lower for hint in _INSTALLER_PATH_HINTS)
    explicit_installer_token = any(
        tok in name_lower for tok in (
            'setup', 'installer', 'redist', 'runtime', 'update',
            'bootstrapper', 'webview', 'distribut', 'installation'
        )
    )
    return path_ok or explicit_installer_token


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Filter #42 â€” HeurÃ­stica "Primera vez visto" (first-seen tracking).
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Cada evidencia (file_hash o name_norm+tipo) se trackea en evidence_fingerprints
# con contador acumulado. Cuando un scan llega:
#   - Si el fingerprint no existe â†’ first_seen=true (revisiÃ³n humana sugerida).
#   - Si seen_count crece â†’ ya fue visto antes en otros scans/empresas.
# El panel muestra badge "ðŸ†• Primera vez visto" o "ðŸ‘ Visto Nx" en cada hallazgo.
# Auditable y NO destructivo: nunca cambia el verdict, solo decora metadata.
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
import re as _re_fp42
_NAME_NORM_RE = _re_fp42.compile(r'[\d\s_\-\.\(\)\[\]\{\}]+')


def _compute_evidence_fingerprint(r: dict) -> str | None:
    """Genera un fingerprint estable para un result de scan.
    Prioridad: file_hash (sha256 real del binario) â†’ name_norm+tipo.
    Devuelve None si no hay datos suficientes para identificar la evidencia.
    """
    if not r or not isinstance(r, dict):
        return None
    fh = (r.get('file_hash') or '').strip().lower()
    if fh and len(fh) >= 16 and all(c in '0123456789abcdef' for c in fh[:64]):
        return f"hash:{fh[:64]}"
    name = (r.get('nombre') or r.get('archivo') or r.get('issue_name') or '').lower().strip()
    if not name:
        return None
    name_norm = _NAME_NORM_RE.sub('', name)[:64]
    if len(name_norm) < 3:
        return None
    tipo = (r.get('tipo') or r.get('issue_type') or '').lower()[:32]
    return f"name:{name_norm}|tipo:{tipo}"


def _ensure_evidence_fingerprints_table(cur) -> bool:
    """Crea evidence_fingerprints si no existe. Idempotente, seguro de llamar
    mÃºltiples veces. Devuelve True si la tabla estÃ¡ disponible.
    """
    try:
        cur.execute(
            "CREATE TABLE IF NOT EXISTS evidence_fingerprints ("
            " fingerprint TEXT PRIMARY KEY,"
            " sample_name TEXT,"
            " sample_tipo TEXT,"
            " sample_categoria TEXT,"
            " seen_count INTEGER NOT NULL DEFAULT 1,"
            " first_seen_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,"
            " last_seen_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,"
            " hack_count    INTEGER NOT NULL DEFAULT 0,"
            " clean_count   INTEGER NOT NULL DEFAULT 0,"
            " sample_scan_id INTEGER"
            ")"
        )
        return True
    except Exception:
        return False


def _upsert_evidence_fingerprints(cur, scan_id: int, results: list) -> dict:
    """UPSERT por cada result en evidence_fingerprints. Devuelve dict
    {fingerprint: {'seen_count': N, 'was_first': bool}} para que el caller
    pueda decorar la respuesta con esa info.
    Idempotente, tolera fallos de BD (devuelve dict vacÃ­o si la tabla cae).
    """
    out: dict = {}
    if not results:
        return out
    if not _ensure_evidence_fingerprints_table(cur):
        return out
    seen_in_batch: set = set()
    for r in results:
        fp = _compute_evidence_fingerprint(r)
        if not fp or fp in seen_in_batch:
            continue
        seen_in_batch.add(fp)
        try:
            cur.execute('SAVEPOINT efp_save')
            cur.execute(
                f"SELECT seen_count FROM evidence_fingerprints WHERE fingerprint = {_PH}",
                (fp,)
            )
            row = cur.fetchone()
            existing_count = None
            if row:
                existing_count = row[0] if not isinstance(row, dict) else row.get('seen_count')
            if existing_count is None:
                # Primera vez visto a nivel global
                cur.execute(
                    f"INSERT INTO evidence_fingerprints "
                    f" (fingerprint, sample_name, sample_tipo, sample_categoria, "
                    f"  seen_count, first_seen_at, last_seen_at, sample_scan_id) "
                    f" VALUES ({_PH},{_PH},{_PH},{_PH},1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,{_PH})",
                    (
                        fp,
                        ((r.get('nombre') or r.get('archivo') or r.get('issue_name') or '')[:255]),
                        ((r.get('tipo') or r.get('issue_type') or '')[:64]),
                        ((r.get('categoria') or r.get('issue_category') or '')[:64]),
                        scan_id,
                    )
                )
                out[fp] = {'seen_count': 1, 'was_first': True}
            else:
                cur.execute(
                    f"UPDATE evidence_fingerprints "
                    f" SET seen_count = seen_count + 1, last_seen_at = CURRENT_TIMESTAMP "
                    f" WHERE fingerprint = {_PH}",
                    (fp,)
                )
                out[fp] = {'seen_count': int(existing_count) + 1, 'was_first': False}
            cur.execute('RELEASE SAVEPOINT efp_save')
        except Exception:
            try:
                cur.execute('ROLLBACK TO SAVEPOINT efp_save')
            except Exception:
                pass
            # Si la tabla falla a nivel filo, salimos en silencio
            return out
    return out


def _query_evidence_seen_counts(cur, results: list) -> dict:
    """Variante read-only para GET: devuelve dict {fingerprint: seen_count}
    sin escribir. Si la tabla no existe, devuelve dict vacÃ­o (decorate falla
    silenciosamente y todos quedan como first_seen=true, lo cual es seguro).
    """
    out: dict = {}
    if not results:
        return out
    fps: list = []
    for r in results:
        fp = _compute_evidence_fingerprint(r)
        if fp and fp not in out:
            fps.append(fp)
            out[fp] = 0  # default
    if not fps:
        return out
    try:
        # Construimos un IN (...) con placeholders dinÃ¡micos
        placeholders = ','.join([_PH] * len(fps))
        cur.execute(
            f"SELECT fingerprint, seen_count FROM evidence_fingerprints "
            f"WHERE fingerprint IN ({placeholders})",
            fps
        )
        rows = cur.fetchall() or []
        for row in rows:
            if isinstance(row, dict):
                out[row.get('fingerprint')] = int(row.get('seen_count') or 0)
            else:
                out[row[0]] = int(row[1] or 0)
    except Exception:
        # Tabla aÃºn no existe (deploys nuevos), todos quedan en 0 â†’ first_seen
        return {fp: 0 for fp in fps}
    return out


def _decorate_results_with_first_seen(results: list, seen_map: dict) -> list:
    """Inyecta 'first_seen' (bool), 'seen_count' (int) y 'globally_common'
    (bool) en cada result. Mutates en sitio y devuelve la misma lista.
    Conserva resultados sin fingerprint (los marca como first_seen=False).

    Filter #12 â€” Consenso global: si un fingerprint apareciÃ³ >=50 veces
    sin que se haya verificado como hack en histÃ³rico, lo marcamos como
    'globally_common' para que el panel ofrezca al staff aprenderlo
    como FP de un solo click. NO degrada el verdict automÃ¡ticamente.
    """
    if not results:
        return results
    for r in results:
        try:
            fp = _compute_evidence_fingerprint(r)
            if not fp:
                r['first_seen'] = False
                r['seen_count'] = 0
                r['globally_common'] = False
                continue
            n = int(seen_map.get(fp) or 0)
            r['seen_count'] = n
            r['first_seen'] = (n <= 1)
            r['globally_common'] = (n >= 50)
        except Exception:
            r.setdefault('first_seen', False)
            r.setdefault('seen_count', 0)
            r.setdefault('globally_common', False)
    return results


def _scrub_results_for_display(results: list) -> list:
    """Aplica el filtro server-side a una lista de resultados ya almacenados,
    devolviendo solo los que NO son FP. Ãštil para sanear scans antiguos al servirlos.
    Conserva el orden original y nunca elimina mÃ¡s de un 95% de los resultados como
    medida de seguridad (evita ocultar todos los hallazgos por un bug del filtro).
    """
    if not results:
        return results
    keep = []
    for r in results:
        try:
            if not _is_server_false_positive(r):
                keep.append(r)
        except Exception:
            keep.append(r)  # ante error, conservar
    if len(keep) == 0 and len(results) > 0:
        return results  # safety: nunca devolver lista vacÃ­a si habÃ­a datos
    if len(results) >= 6 and len(keep) / len(results) < 0.05:
        return results  # safety: filtro demasiado agresivo, devolver original
    return keep


def _calculate_risk_score(results, return_breakdown=False):
    """Calcula el risk score de un scan segÃºn las evidencias encontradas.
    Retorna score 0â€“100. Con return_breakdown=True devuelve (score, breakdown_list).
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

    # Tipos/categorÃ­as que no aportan nada al risk score:
    # - texture_pack: muy fÃ¡cil de confundir, demasiados FPs
    # - event_logs de fecha/hora: lo dispara Windows NTP automÃ¡ticamente
    ZERO_RISK_TYPES = {
        'texture_pack', 'texture_pack_xray', 'texture_pack_analysis',
        'resource_pack', 'resource_pack_xray',
        'file_created', 'file_modified',
        'crash_dump', 'defender_health_event', 'razer_installed',
        'multiple_javaw',
    }
    ZERO_RISK_CATS = {'texture_packs', 'resource_packs', 'file_activity'}

    _alert_counted = set()

    for r in results:
        tipo   = (r.get('tipo') or r.get('issue_type') or '').lower().replace(' ', '_')
        cat    = (r.get('categoria') or r.get('issue_category') or '').lower().replace(' ', '_')
        alerta = (r.get('alerta') or r.get('alert_level') or '').upper()
        nombre = (r.get('issue_name') or r.get('nombre') or tipo)[:80]

        # Texture packs y cambios de fecha/hora: 0 riesgo
        if tipo in ZERO_RISK_TYPES or cat in ZERO_RISK_CATS:
            continue
        if tipo == 'event_logs' and 'fecha' in nombre.lower():
            continue

        # Bonus por categorÃ­a/tipo (una sola vez por categorÃ­a)
        for key, pts in CATEGORY_SCORES.items():
            if key in tipo or key in cat:
                if key not in _counted:
                    score += pts
                    _counted.add(key)
                    breakdown.append({'source': nombre, 'points': pts, 'reason': f'Tipo detectado: {key}'})
                break

        # Puntos por alerta: una vez por (tipo, nivel), no por cada fila duplicada
        alert_pts = ALERT_SCORES.get(alerta, 0)
        alert_key = (tipo or cat or 'unknown', alerta)
        if alert_pts > 0 and alert_key not in _alert_counted:
            _alert_counted.add(alert_key)
            score += alert_pts
            breakdown.append({'source': nombre, 'points': alert_pts, 'reason': f'Nivel de alerta: {alerta}'})

        # Pack 36 â€” Autolearn boost: si el result matchea un pattern
        # confirmado por staff con alto trust (Pack 36), suma puntos
        # extra escalados por la confidence del pattern (max +30).
        boost = float(r.get('_autolearn_boost') or 0.0)
        if boost > 0:
            extra = min(30, int(round(boost * 30)))
            score += extra
            breakdown.append({
                'source': nombre,
                'points': extra,
                'reason': f'Auto-aprendido (confidence {boost:.0%}, kind={r.get("_autolearn_kind")})'
            })

    final_score = min(score, 100)
    if return_breakdown:
        # Sort by points desc, only keep top contributors
        breakdown_sorted = sorted(breakdown, key=lambda x: x['points'], reverse=True)[:15]
        return final_score, breakdown_sorted
    return final_score


def _ensemble_risk_score(results):
    """Ensemble autÃ³nomo: 50% heurÃ­stico + 30% RF + 20% Isolation Forest.
    Si un modelo no estÃ¡ disponible, sus pesos se redistribuyen a heurÃ­stico.
    """
    heuristic = _calculate_risk_score(results)

    try:
        from ml_classifier import get_classifier
        clf = get_classifier()

        rf_score  = None
        iso_score = None

        # --- Random Forest (supervised / pseudo-supervised) ---
        if clf.is_available and results:
            hack_probs = []
            for r in results:
                features = {
                    'alert_level':          r.get('alerta') or r.get('alert_level') or 'NORMAL',
                    'issue_category':       r.get('categoria') or r.get('issue_category') or 'OTHER',
                    'confidence':           float(r.get('confidence') or 0.5),
                    'obfuscation_detected': int(bool(r.get('obfuscation_detected') or 0)),
                }
                pred = clf.predict(features)
                if pred.get('available'):
                    hack_probs.append(pred.get('hack_prob', 0.0))
            if hack_probs:
                rf_score = round(sum(hack_probs) / len(hack_probs) * 100)

        # --- Isolation Forest (unsupervised anomaly detection) ---
        if clf.iso_available and results:
            from ml_classifier import _ALERT_MAP, _CAT_MAP
            alert_nums = [_ALERT_MAP.get(str((r.get('alerta') or r.get('alert_level') or '')).upper(), 0) for r in results]
            cat_nums   = [_CAT_MAP.get(str((r.get('categoria') or r.get('issue_category') or '')).upper(), 1) for r in results]
            confs      = [float(r.get('confidence') or 0.5) for r in results]
            obfuscs    = [int(bool(r.get('obfuscation_detected') or 0)) for r in results]
            n = len(results)
            scan_feats = [
                n,
                sum(1 for a in alert_nums if a >= 4),
                max(alert_nums) if alert_nums else 0,
                sum(confs) / n,
                sum(obfuscs),
                len(set(cat_nums)),
                sum(1 for a in alert_nums if a >= 3),
            ]
            iso_pred = clf.predict_iso(scan_feats)
            if iso_pred.get('available'):
                # score_samples returns negative values near 0 for anomalies,
                # more negative = more anomalous. Normalize to 0â€“100 hack probability.
                raw = iso_pred.get('score', 0.0)
                # Typical range is roughly -0.20 (anomaly) to +0.10 (normal).
                # Map: -0.20 â†’ 100, 0.0 â†’ 50, +0.10 â†’ 0
                iso_hack = max(0, min(100, round((-raw / 0.20) * 50 + 50)))
                iso_score = iso_hack

        # --- Weighted ensemble ---
        if rf_score is None and iso_score is None:
            return heuristic                         # fallback: 100% heuristic
        elif rf_score is None:
            ensemble = round(heuristic * 0.70 + iso_score * 0.30)
        elif iso_score is None:
            ensemble = round(heuristic * 0.60 + rf_score * 0.40)
        else:
            ensemble = round(heuristic * 0.50 + rf_score * 0.30 + iso_score * 0.20)

        return min(100, ensemble)

    except Exception:
        return heuristic


# ---------------------------------------------------------------------------
# 6-system ensemble verdict
# ---------------------------------------------------------------------------
_ENSEMBLE_IN_INST_FRAGS = (
    '/.minecraft/mods/', '/.minecraft/versions/', '/.minecraft/resourcepacks/',
    '/.minecraft/shaderpacks/', '/.minecraft/saves/', '/.minecraft/config/',
    '.minecraft/mods', '.minecraft/versions', '.minecraft/resourcepacks',
    '.minecraft/shaderpacks', '.minecraft/saves', '.minecraft/config',
    'multimc/instances', 'prismlauncher/instances',
    'curseforge/minecraft/instances', 'gdlauncher/instances',
    'atlauncher/instances',
)

_ENSEMBLE_KNOWN_CLIENTS = [
    'vape', 'entropy', 'whiteout', 'liquidbounce', 'wurst', 'sigma', 'flux',
    'future', 'astolfo', 'ghost', 'rise', 'moon', 'drip', 'meteor', 'aristois',
    'tenacity', 'vertex', 'inertia', 'salhack', 'slinky', 'reflex', 'rage',
    'biscuit', 'thunder', 'autoclick', 'autoclicker',
]

_VERDICT_ORDER = ['LIMPIO', 'POCO_SOSPECHOSO', 'SOSPECHOSO', 'MUY_SOSPECHOSO', 'HACK_CONFIRMADO']


def _compute_ensemble_verdict(results, cursor=None, machine_id=None,
                              minecraft_username=None, exclude_scan_id=None):
    """6-system ensemble verdict with in-instance hard gate.

    Gate rule: without any in-instance evidence, max verdict = SOSPECHOSO (not sanctionable).
    Systems and weights:
      1. Risk Score          0.30
      2. Instance Layer      0.00  (gate, no contribuye al score)
      3. Signal Convergence  0.25
      4. Hash Reputation     0.20
      5. Temporality         0.10
      6. ML                  0.05
      7. Prior Consensus     0.10  (Pack 32 F#55 â€” verdicts previos del
                                   mismo machine_id/player). Solo se
                                   aplica si machine_id o
                                   minecraft_username estÃ¡n presentes.

    All systems return 0-4; final score is weighted average scaled to 0-100.
    """
    if not results:
        return {'verdict': 'LIMPIO', 'sanctionable': False, 'score': 0, 'systems': {}, 'reason': 'Sin hallazgos'}

    # -- System 2: Instance Layer (GATE) --
    in_inst_count = 0
    for r in results:
        path = (r.get('issue_path') or r.get('ruta') or r.get('archivo') or '').lower().replace('\\', '/')
        if any(f in path for f in _ENSEMBLE_IN_INST_FRAGS):
            in_inst_count += 1
    sanctionable = in_inst_count > 0
    s2 = 4 if in_inst_count >= 3 else 2 if in_inst_count >= 1 else 0

    # -- System 1: Risk Score --
    risk_score = _ensemble_risk_score(results)
    s1 = min(4, risk_score // 20)

    # -- System 3: Signal Convergence --
    _TYPE_TO_SIG = {
        'ghost_client': 'file', 'hack_client': 'file', 'hacks': 'file', 'mod': 'file',
        'proceso': 'process', 'process': 'process', 'processes': 'process',
        'network': 'network', 'red': 'network', 'network_forensics': 'network',
        'browser': 'browser', 'web': 'browser', 'forense': 'browser',
        'descarga': 'download', 'download': 'download',
    }
    client_signals = {}
    for r in results:
        r_text = ' '.join([
            r.get('issue_name') or r.get('nombre') or '',
            r.get('issue_type') or r.get('tipo') or '',
        ]).lower()
        r_type = (r.get('issue_type') or r.get('tipo') or '').lower()
        r_cat  = (r.get('issue_category') or r.get('categoria') or '').lower()
        sig_cat = next((v for k, v in _TYPE_TO_SIG.items() if k in r_type or k in r_cat), 'file')
        client = next((c for c in _ENSEMBLE_KNOWN_CLIENTS if c in r_text), None)
        if client:
            client_signals.setdefault(client, set()).add(sig_cat)
    max_convergence = max((len(v) for v in client_signals.values()), default=0)
    s3 = min(4, max_convergence)

    # -- System 4: Hash Reputation --
    s4 = 0
    if cursor:
        try:
            hashes = [r.get('file_hash') for r in results if r.get('file_hash') and len(r.get('file_hash', '')) > 8]
            if hashes:
                placeholders = ','.join([_PH] * len(hashes))
                cursor.execute(
                    f'SELECT COUNT(*) FROM scan_results sr '
                    f'JOIN scans s ON sr.scan_id = s.id '
                    f'WHERE sr.file_hash IN ({placeholders}) AND s.verdict = {_PH}',
                    hashes + ['hack']
                )
                row = cursor.fetchone()
                matches = int(_row_get(row, 0, 'count') or 0)
                s4 = 4 if matches >= 3 else 2 if matches >= 1 else 0
        except Exception:
            s4 = 0

    # -- System 5: Temporality --
    _TEMP_MAP = {
        'proceso': 4, 'process': 4, 'processes': 4,
        'descarga': 3, 'download': 3,
        'ghost_client': 2, 'hack_client': 2, 'hacks': 2, 'mod': 2,
        'browser': 1, 'web': 1, 'red': 1, 'network': 1,
    }
    max_temp = 0
    for r in results:
        r_type = (r.get('issue_type') or r.get('tipo') or '').lower()
        r_cat  = (r.get('issue_category') or r.get('categoria') or '').lower()
        t = next((v for k, v in _TEMP_MAP.items() if k in r_type or k in r_cat), 0)
        if t > max_temp:
            max_temp = t
    s5 = max_temp

    # -- System 6: ML (reuse existing risk_score proxy) --
    s6 = min(4, risk_score // 25)

    # -- System 7: Prior Consensus (Pack 32 F#55) --
    s7 = 2  # neutro
    s7_meta = {'verdicts': [], 'count': 0, 'reason': 'sin contexto'}
    if _AI_TRUST_AVAILABLE and cursor and (machine_id or minecraft_username):
        try:
            s7_data = _ai_trust.system7_prior_consensus(
                cursor, machine_id, minecraft_username,
                exclude_scan_id=exclude_scan_id,
            )
            s7 = int(s7_data.get('score', 2))
            s7_meta = {
                'verdicts': s7_data.get('verdicts', []),
                'count':    s7_data.get('count', 0),
                'hacks':    s7_data.get('hacks', 0),
                'cleans':   s7_data.get('cleans', 0),
                'reason':   s7_data.get('reason', ''),
            }
        except Exception as _e_s7:
            print(f'[ensemble.s7] {_e_s7}')

    # -- Weighted ensemble. Instance Layer es gate, no contribuye a la
    # suma. El System 7 entra con peso 0.10 cuando hay machine_id /
    # username, en cuyo caso se renormaliza el resto a 0.90.
    if _AI_TRUST_AVAILABLE and (machine_id or minecraft_username):
        # Pesos con S7 activo
        raw = (s1 * 0.30 + s3 * 0.25 + s4 * 0.20 +
               s5 * 0.10 + s6 * 0.05 + s7 * 0.10)
    else:
        # Pesos legacy (sin S7): renormalizo hacia 1.0 manteniendo
        # las proporciones originales.
        raw = s1 * 0.35 + s3 * 0.30 + s4 * 0.20 + s5 * 0.10 + s6 * 0.05
    score = min(100, round(raw / 4.0 * 100))

    # -- Verdict from score --
    if   score >= 75: verdict = 'HACK_CONFIRMADO'
    elif score >= 50: verdict = 'MUY_SOSPECHOSO'
    elif score >= 30: verdict = 'SOSPECHOSO'
    elif score >= 15: verdict = 'POCO_SOSPECHOSO'
    else:             verdict = 'LIMPIO'

    # -- Gate: no in-instance evidence â†’ cap at SOSPECHOSO, not sanctionable --
    gate_capped = not sanctionable and _VERDICT_ORDER.index(verdict) > _VERDICT_ORDER.index('SOSPECHOSO')
    if gate_capped:
        verdict = 'SOSPECHOSO'

    reasons = []
    if sanctionable:
        reasons.append(f'{in_inst_count} hallazgo(s) en instancia')
    else:
        reasons.append('Sin evidencia en instancia')
    if client_signals:
        top_client = max(client_signals, key=lambda k: len(client_signals[k]))
        reasons.append(f'{top_client} ({len(client_signals[top_client])} seÃ±al(es))')

    s7_active = _AI_TRUST_AVAILABLE and (machine_id or minecraft_username)
    if s7_active and s7_meta.get('count', 0) > 0:
        reasons.append(f"prior: {s7_meta['reason']}")

    return {
        'verdict': verdict,
        'sanctionable': sanctionable,
        'score': score,
        'gate_capped': gate_capped,
        'systems': {
            'risk_score':         {'score': s1, 'raw': risk_score, 'weight': 0.30 if s7_active else 0.35},
            'instance_layer':     {'score': s2, 'in_instance': in_inst_count, 'sanctionable': sanctionable, 'weight': 0},
            'signal_convergence': {'score': s3, 'clients': {k: list(v) for k, v in client_signals.items()}, 'weight': 0.25 if s7_active else 0.30},
            'hash_reputation':    {'score': s4, 'weight': 0.20},
            'temporality':        {'score': s5, 'weight': 0.10},
            'ml':                 {'score': s6, 'weight': 0.05},
            'prior_consensus':    {'score': s7, 'weight': 0.10 if s7_active else 0.0, 'active': bool(s7_active), **s7_meta},
        },
        'reason': ' Â· '.join(reasons) if reasons else '',
    }


def _compare_consecutive_scans(cursor, scan_id, machine_id, current_results):
    """P2 #43 â€” Compara scan actual con el anterior del mismo machine_id.
    Inserta notas de 'new_finding' en scan_results para hallazgos que no estaban antes.
    Devuelve (new_types, disappeared_types) para logging.
    """
    if not machine_id or not current_results:
        return [], []
    try:
        # Obtener el scan anterior completado del mismo machine
        cursor.execute(
            f'SELECT id FROM scans WHERE machine_id={_PH} AND status={_PH}'
            f' AND id != {_PH} ORDER BY id DESC LIMIT 1',
            (machine_id, 'completed', scan_id)
        )
        row = cursor.fetchone()
        if not row:
            return [], []
        prev_scan_id = _row_get(row, 0, 'id')

        # Tipos de hallazgos del scan anterior
        cursor.execute(
            f'SELECT DISTINCT issue_type FROM scan_results WHERE scan_id={_PH}',
            (prev_scan_id,)
        )
        prev_types = {
            (_row_get(r, 0, 'issue_type') or '').lower()
            for r in (cursor.fetchall() or [])
        } - {''}

        current_types = {
            (r.get('tipo') or r.get('issue_type') or '').lower()
            for r in current_results
        } - {''}

        new_types        = current_types - prev_types
        disappeared_types = prev_types - current_types

        if new_types:
            print(f"[consecutive] {len(new_types)} tipo(s) nuevos vs scan {prev_scan_id}: {new_types}")
        if disappeared_types:
            print(f"[consecutive] {len(disappeared_types)} tipo(s) desaparecidos: {disappeared_types}")

        # Marcar en scan_results los hallazgos que son nuevos respecto al anterior
        if new_types:
            cursor.execute(
                f'UPDATE scan_results SET detected_patterns = COALESCE(detected_patterns,{_PH}) || {_PH}'
                f' WHERE scan_id={_PH} AND LOWER(issue_type) = ANY({_PH})',
                ('[]', ',"new_vs_prev_scan"', scan_id, list(new_types))
            )

        return list(new_types), list(disappeared_types)
    except Exception as ex:
        print(f"[consecutive] Error: {ex}")
        return [], []


@app.route('/api/scans/<int:scan_id>/results', methods=['POST'])
def submit_scan_results(scan_id):
    """Recibe y almacena resultados de escaneo (usado por el cliente .exe) â€” sin login requerido"""
    _flags = _sa_imperial_flags()
    if _flags.get('scanner_uploads_paused') or _flags.get('maintenance_mode'):
        return jsonify({'error': 'Subida de resultados pausada temporalmente.', 'paused': True}), 503
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

    _ensure_dual_scanner_schema()
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
                print(f"[DEBUG] FP filter: {before} â†’ {len(results)} resultados ({before - len(results)} descartados)")
            # Pack 36 â€” Boost results con learned_hack_patterns (autolearn).
            # Inyecta `_autolearn_boost` en results que matchean patterns
            # confirmados por staff con alto trust. _calculate_risk_score
            # los considera para subir confidence efectivo.
            if _AI_AUTOLEARN_AVAILABLE:
                try:
                    cursor.execute('SAVEPOINT autolearn_boost_save')
                    _boosted = _ai_autolearn.boost_results_with_patterns(cursor, results)
                    if _boosted:
                        print(f'[DEBUG] autolearn boost: {_boosted}/{len(results)} results matched patterns aprendidos')
                    cursor.execute('RELEASE SAVEPOINT autolearn_boost_save')
                except Exception as _b_e:
                    try:
                        cursor.execute('ROLLBACK TO SAVEPOINT autolearn_boost_save')
                    except Exception:
                        pass
                    print(f'[DEBUG] autolearn boost fallÃ³: {_b_e}')
            # Filter #42 â€” Upsert evidence_fingerprints para tracking "first-seen"
            # Tolera fallos: si la tabla aÃºn no existe, simplemente no se decora.
            try:
                cursor.execute('SAVEPOINT efp_upsert_save')
                _upsert_evidence_fingerprints(cursor, scan_id, results)
                cursor.execute('RELEASE SAVEPOINT efp_upsert_save')
            except Exception as _efp_e:
                try:
                    cursor.execute('ROLLBACK TO SAVEPOINT efp_upsert_save')
                except Exception:
                    pass
                print(f"[DEBUG] evidence_fingerprints upsert fallÃ³ silenciosamente: {_efp_e}")
            # Deduplicar resultados antes de insertar (misma key = tipo+nombre+ruta)
            _seen_keys = set()
            _deduped = []
            for _r in results:
                _dk = (
                    (_r.get('tipo') or _r.get('issue_type') or ''),
                    (_r.get('nombre') or _r.get('issue_name') or _r.get('archivo') or '')[:200],
                    (_r.get('ruta') or _r.get('issue_path') or '')[:200],
                )
                if _dk not in _seen_keys:
                    _seen_keys.add(_dk)
                    _deduped.append(_r)
            if len(_deduped) < len(results):
                print(f"[DEBUG] Dedup: {len(results)} → {len(_deduped)} resultados ({len(results)-len(_deduped)} duplicados removidos)")
            results = _deduped

            print(f"[DEBUG] Insertando {len(results)} resultados en scan_results")
            if results:
                def _norm_conf(v):
                    """Normaliza confidence a rango 0-1 independientemente de si el exe lo mandÃ³ como 0-1 o 0-100."""
                    try:
                        f = float(v or 0)
                        return f / 100.0 if f > 1.0 else f
                    except (TypeError, ValueError):
                        return 0.0
                def _extra_json(r_dict):
                    """Serializa el campo 'extra' a JSON string, o None si no hay."""
                    raw = r_dict.get('extra')
                    if not raw or not isinstance(raw, dict):
                        return None
                    try:
                        return json.dumps(raw, ensure_ascii=False)[:4000]
                    except (TypeError, ValueError):
                        return None
                batch = [
                    (scan_id,
                     r.get('tipo', ''), r.get('nombre', '') or r.get('archivo', ''),
                     r.get('ruta', ''), r.get('categoria', ''), r.get('alerta', ''),
                     _norm_conf(r.get('confidence', 0)), json.dumps(r.get('detected_patterns', [])),
                     r.get('obfuscation', False), r.get('file_hash', ''),
                     r.get('ai_analysis', ''), _norm_conf(r.get('ai_confidence', 0)),
                     _extra_json(r))
                    for r in results
                ]
                if results:
                    print(f"[DEBUG] Primer resultado: tipo={results[0].get('tipo')}, "
                          f"nombre={results[0].get('nombre') or results[0].get('archivo')}, "
                          f"alerta={results[0].get('alerta')}")
                # Intento INSERT con columna 'extra'; si la columna aÃºn no existe en
                # esta DB (migraciÃ³n pendiente), reintenta sin ella.
                try:
                    cursor.execute('SAVEPOINT extra_save')
                    cursor.executemany(
                        f'INSERT INTO scan_results'
                        f' (scan_id, issue_type, issue_name, issue_path, issue_category,'
                        f'  alert_level, confidence, detected_patterns, obfuscation_detected,'
                        f'  file_hash, ai_analysis, ai_confidence, extra)'
                        f' VALUES ({_PH},{_PH},{_PH},{_PH},{_PH},{_PH},{_PH},{_PH},{_PH},{_PH},{_PH},{_PH},{_PH})',
                        batch
                    )
                    cursor.execute('RELEASE SAVEPOINT extra_save')
                except Exception as _e:
                    try:
                        cursor.execute('ROLLBACK TO SAVEPOINT extra_save')
                    except Exception:
                        pass
                    print(f"[DEBUG] INSERT con extra fallÃ³ ({_e}); reintentando sin columna extra")
                    fallback_batch = [row[:-1] for row in batch]
                    cursor.executemany(
                        f'INSERT INTO scan_results'
                        f' (scan_id, issue_type, issue_name, issue_path, issue_category,'
                        f'  alert_level, confidence, detected_patterns, obfuscation_detected,'
                        f'  file_hash, ai_analysis, ai_confidence)'
                        f' VALUES ({_PH},{_PH},{_PH},{_PH},{_PH},{_PH},{_PH},{_PH},{_PH},{_PH},{_PH},{_PH})',
                        fallback_batch
                    )
                print(f"[DEBUG] executemany completado")

            # Calcular y guardar risk_score (P3 #7 ensemble: heurÃ­stico + RF)
            try:
                cursor.execute('SAVEPOINT risk_score_save')
                risk_score = _ensemble_risk_score(results)
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

            # Recalcular issues_found basado en resultados reales insertados (excluir FILE_ACTIVITY)
            try:
                cursor.execute(
                    f"UPDATE scans SET issues_found = ("
                    f"  SELECT COUNT(*) FROM scan_results"
                    f"  WHERE scan_id = {_PH} AND COALESCE(issue_category,'') != 'FILE_ACTIVITY'"
                    f") WHERE id = {_PH}",
                    (scan_id, scan_id)
                )
            except Exception:
                pass

            # 7-system ensemble verdict (Pack 32 incluye Prior Consensus).
            # Leemos machine_id + minecraft_username del scan actual para
            # alimentar el sistema 7 con verdicts previos del mismo
            # cliente / jugador.
            _scan_machine_id = None
            _scan_username   = None
            try:
                cursor.execute(
                    f'SELECT machine_id, minecraft_username FROM scans WHERE id = {_PH}',
                    (scan_id,)
                )
                _row = cursor.fetchone()
                if _row:
                    _scan_machine_id = _row_get(_row, 0, 'machine_id')
                    _scan_username   = _row_get(_row, 1, 'minecraft_username')
            except Exception:
                pass
            try:
                cursor.execute('SAVEPOINT ensemble_save')
                _ens = _compute_ensemble_verdict(
                    results, cursor,
                    machine_id=_scan_machine_id,
                    minecraft_username=_scan_username,
                    exclude_scan_id=scan_id,
                )
                cursor.execute(
                    f'UPDATE scans SET ensemble_data = {_PH} WHERE id = {_PH}',
                    (json.dumps(_ens), scan_id)
                )
                cursor.execute('RELEASE SAVEPOINT ensemble_save')
                print(f"[DEBUG] ensemble verdict={_ens['verdict']} sanctionable={_ens['sanctionable']} score={_ens['score']}")
                # Si gate_capped (sin evidencia en instancia) ajustar risk_score para que
                # el gauge del panel sea coherente con el veredicto SOSPECHOSO.
                if _ens.get('gate_capped') and locals().get('risk_score', 0) > 50:
                    _capped_rs = min(locals().get('risk_score', 0), 45)
                    try:
                        cursor.execute(
                            f'UPDATE scans SET risk_score = {_PH} WHERE id = {_PH}',
                            (_capped_rs, scan_id)
                        )
                        risk_score = _capped_rs
                        print(f"[DEBUG] risk_score cappado por gate_capped â†’ {_capped_rs}")
                    except Exception:
                        pass
            except Exception:
                try:
                    cursor.execute('ROLLBACK TO SAVEPOINT ensemble_save')
                except Exception:
                    pass

            # P2 #43 â€” ComparaciÃ³n con scan anterior del mismo machine
            try:
                _compare_consecutive_scans(cursor, scan_id, data.get('machine_id', ''), results)
            except Exception:
                pass

            # #291 — alerta automática ante cambios sospechosos vs scan anterior
            try:
                cursor.execute(
                    f"SELECT id, company_id, machine_name, minecraft_username "
                    f"FROM scans WHERE id = {_PH}",
                    (scan_id,)
                )
                srow = cursor.fetchone()
                if srow:
                    srow = dict(srow) if not isinstance(srow, dict) else srow
                    company_id = int(srow.get('company_id') or 0)
                    host = str(srow.get('machine_name') or '').strip()
                    usern = str(srow.get('minecraft_username') or '').strip()
                    cursor.execute(
                        f"SELECT id FROM scans WHERE company_id = {_PH} AND machine_name = {_PH} "
                        f"AND minecraft_username = {_PH} AND id < {_PH} "
                        f"ORDER BY id DESC LIMIT 1",
                        (company_id, host, usern, scan_id)
                    )
                    prev = cursor.fetchone()
                    prev_id = int(_row_get(prev, 0, 'id') or 0) if prev else 0
                    if prev_id > 0:
                        diff = _build_scan_diff(cursor, prev_id, scan_id)
                        _notify_suspicious_scan_diff(cursor, company_id, scan_id, diff)
            except Exception as _e_ds:
                print(f"[dual_scanner] post-scan compare error: {_e_ds}")

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

        # P5 #16 â€” Web Push a todos los staff suscritos
        _rs = locals().get('risk_score', 0)
        _mn = data.get('machine_name', 'Jugador')
        _push_title = 'ðŸ”´ Argus â€” Nuevo scan con hacks' if _rs >= 70 else 'ðŸŸ¡ Argus â€” Nuevo scan' if _rs >= 30 else 'âœ… Argus â€” Scan limpio'
        _push_body  = f'{_mn} Â· Risk {_rs} Â· {len(results)} hallazgos'
        import threading as _pt
        _pt.Thread(target=_send_push_to_all, args=(_push_title, _push_body, f'/panel?scan={scan_id}'), daemon=True).start()
        try:
            with get_api_db_cursor() as _cws:
                _cws.execute(f"SELECT company_id FROM scans WHERE id = {_PH}", (scan_id,))
                _r = _cws.fetchone()
                _cid = int((_r.get('company_id') if isinstance(_r, dict) else (_r[0] if _r else 0)) or 0)
            dispatch_webhook('scan.completed', {
                'scan_id': scan_id,
                'risk_score': _rs,
                'issues_count': len(results),
                'company_id': _cid,
            }, company_id=_cid if _cid > 0 else None)
            _emit_realtime_notification(company_id=_cid if _cid > 0 else None, payload={
                'kind': 'scan_completed',
                'scan_id': scan_id,
                'risk_score': _rs,
                'issues_count': len(results),
                'message': f'Nuevo scan #{scan_id} completado',
            })
        except Exception:
            pass

        return jsonify({'success': True, 'message': 'Resultados almacenados'})
    except Exception as e:
        print(f"[DEBUG] ===== ERROR en submit_scan_results scan_id={scan_id} =====")
        print(f"[DEBUG] {e}")
        print(traceback.format_exc())
        return jsonify({'error': f'Error almacenando resultados: {str(e)}'}), 500


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# ENDPOINT TEMPORAL DE DIAGNOSTICO â€” sin login, replica TODA la logica de
# get_scan() paso a paso, devolviendo en que paso fallo si falla. Permite
# diagnosticar 500's del endpoint real sin acceso a logs.
# Eliminar cuando el bug este resuelto.
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.route('/api/debug/scan/<int:scan_id>', methods=['GET'])
def debug_scan_summary(scan_id):
    import traceback as _tb
    steps = []
    def _step(name, ok, info=None, err=None):
        steps.append({'name': name, 'ok': ok, 'info': info, 'err': err})

    payload = {'scan_id': scan_id, 'argus_version': _ARGUS_VERSION,
               'php_marker': _PH, 'steps': steps}

    try:
        with get_api_db_cursor() as cursor:
            try:
                cursor.execute(
                    f"SELECT id, token_id, scan_token, started_at, completed_at, status, "
                    f"total_files_scanned, issues_found, scan_duration, machine_id, "
                    f"machine_name, ip_address, country, minecraft_username "
                    f"FROM scans WHERE id = {_PH}", (scan_id,))
                row = cursor.fetchone()
                if not row:
                    _step('select_scans_base', False, err='no row')
                    payload['final'] = '404'
                    return jsonify(payload), 404
                _step('select_scans_base', True, info={'machine_name': _row_get(row, 10, 'machine_name')})
            except Exception as e:
                _step('select_scans_base', False, err=f'{type(e).__name__}: {e}')
                payload['final'] = '500'
                payload['traceback'] = _tb.format_exc()[:1500]
                return jsonify(payload), 500

            try:
                cursor.execute('SAVEPOINT opt_cols')
                cursor.execute(
                    f"SELECT total_dirs_scanned, verdict, verdict_reason, verdict_by, verdict_at, "
                    f"screenshot, mc_info, risk_score, ensemble_data "
                    f"FROM scans WHERE id = {_PH}", (scan_id,))
                vrow = cursor.fetchone()
                cursor.execute('RELEASE SAVEPOINT opt_cols')
                _step('select_scans_optional_cols', True, info={'has_vrow': vrow is not None})
            except Exception as e:
                _step('select_scans_optional_cols', False, err=f'{type(e).__name__}: {e}')
                try:
                    cursor.execute('ROLLBACK TO SAVEPOINT opt_cols')
                except Exception:
                    pass

            try:
                cursor.execute(
                    f"SELECT st.created_by FROM scans s "
                    f"LEFT JOIN scan_tokens st ON s.token_id = st.id "
                    f"WHERE s.id = {_PH}", (scan_id,))
                srow = cursor.fetchone()
                _step('select_scanned_by', True, info={'scanned_by': _row_get(srow, 0, 'created_by') if srow else None})
            except Exception as e:
                _step('select_scanned_by', False, err=f'{type(e).__name__}: {e}')

            _has_extra_col = True
            try:
                cursor.execute('SAVEPOINT extra_select')
                cursor.execute(
                    f"SELECT id, issue_type, issue_name, issue_path, issue_category, "
                    f"alert_level, confidence, detected_patterns, obfuscation_detected, "
                    f"file_hash, ai_analysis, ai_confidence, feedback_status, extra "
                    f"FROM scan_results WHERE scan_id = {_PH}", (scan_id,))
                rows = cursor.fetchall()
                cursor.execute('RELEASE SAVEPOINT extra_select')
                _step('select_results_with_extra', True, info={'rows': len(rows)})
            except Exception as e:
                _step('select_results_with_extra', False, err=f'{type(e).__name__}: {e}')
                try:
                    cursor.execute('ROLLBACK TO SAVEPOINT extra_select')
                except Exception:
                    pass
                _has_extra_col = False
                try:
                    cursor.execute(
                        f"SELECT id, issue_type, issue_name, issue_path, issue_category, "
                        f"alert_level, confidence, detected_patterns, obfuscation_detected, "
                        f"file_hash, ai_analysis, ai_confidence, feedback_status "
                        f"FROM scan_results WHERE scan_id = {_PH}", (scan_id,))
                    rows = cursor.fetchall()
                    _step('select_results_no_extra', True, info={'rows': len(rows)})
                except Exception as e2:
                    _step('select_results_no_extra', False, err=f'{type(e2).__name__}: {e2}')
                    rows = []

            # Procesar como hace get_scan
            try:
                results = []
                for r in rows:
                    raw_patterns = _row_get(r, 7, 'detected_patterns')
                    extra_obj = {}
                    if _has_extra_col:
                        raw_extra = _row_get(r, 13, 'extra')
                        if raw_extra:
                            try:
                                extra_obj = json.loads(raw_extra) if isinstance(raw_extra, str) else (raw_extra or {})
                                if not isinstance(extra_obj, dict):
                                    extra_obj = {}
                            except (TypeError, ValueError):
                                extra_obj = {}
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
                        'extra': extra_obj,
                    })
                _step('process_results', True, info={'processed': len(results)})
            except Exception as e:
                _step('process_results', False, err=f'{type(e).__name__}: {e}')
                payload['final'] = '500'
                payload['traceback'] = _tb.format_exc()[:1500]
                return jsonify(payload), 500

            try:
                results2 = _scrub_results_for_display(results)
                _step('scrub_results', True, info={'after_scrub': len(results2)})
            except Exception as e:
                _step('scrub_results', False, err=f'{type(e).__name__}: {e}')

            try:
                _ = json.dumps({'results': results}, default=str)
                _step('jsonify_test', True, info={'serializable': True})
            except Exception as e:
                _step('jsonify_test', False, err=f'{type(e).__name__}: {e}')

        payload['final'] = 'ok'
        return jsonify(payload), 200
    except Exception as e:
        payload['final'] = '500-outer'
        payload['error'] = f'{type(e).__name__}: {e}'
        payload['traceback'] = _tb.format_exc()[:2000]
        return jsonify(payload), 500


@app.route('/api/scans', methods=['GET'])
@login_required
def list_scans():
    """Lista escaneos - Usa BD directa si estÃ¡ disponible, sino HTTP"""
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

    # CachÃ© solo cuando no hay filtros activos
    cache_key = f'scans_list_{limit}_{offset}'
    if not has_filters and cache_key in _stats_cache:
        if time.time() - _stats_cache_time.get(cache_key, 0) < 10:
            return jsonify(_stats_cache[cache_key]), 200

    # Intentar acceso directo a BD primero (mÃ¡s rÃ¡pido) - BD unificada siempre disponible
    if API_DB_AVAILABLE_LOCALLY:
        try:
            print(f"ðŸ”„ Intentando obtener escaneos directamente de la BD local...")
            with get_api_db_cursor() as cursor:
                # Construir WHERE dinÃ¡mico
                conditions = ["s.deleted_at IS NULL"]
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

                # scanner_version puede no existir aÃºn en deploys viejos â€” fallback NULL.
                # IMPORTANTE: PostgreSQL aborta la TX entera si la query del try falla
                # (ej. UndefinedColumn). Sin SAVEPOINT, la query del except hereda la
                # TX aborted y revienta con "current transaction is aborted, commands
                # ignored until end of transaction block" â†’ list_scans cae a fallback
                # HTTP roto. Causa del 500 en Pack 25 cuando Render upgradeÃ³ Python.
                try:
                    cursor.execute('SAVEPOINT scn_ver_probe')
                except Exception:
                    pass
                try:
                    cursor.execute(f'''
                        SELECT s.id, s.scan_token, s.started_at, s.completed_at, s.status,
                               s.total_files_scanned, s.issues_found, s.scan_duration, s.machine_name,
                               s.minecraft_username, s.ip_address, s.country,
                               st.created_by AS scanned_by, s.risk_score, s.verdict, s.os,
                               s.scanner_version
                        FROM scans s
                        LEFT JOIN scan_tokens st ON s.token_id = st.id
                        {where}
                        ORDER BY s.started_at DESC
                        LIMIT {_PH} OFFSET {_PH}
                    ''', params)
                    _has_scn_ver = True
                    try:
                        cursor.execute('RELEASE SAVEPOINT scn_ver_probe')
                    except Exception:
                        pass
                except Exception as _scn_err:
                    print(f"âš ï¸ list_scans: probe scanner_version fallÃ³ ({_scn_err.__class__.__name__}: {_scn_err}); usando query sin esa columna")
                    try:
                        cursor.execute('ROLLBACK TO SAVEPOINT scn_ver_probe')
                    except Exception:
                        pass
                    _has_scn_ver = False
                    cursor.execute(f'''
                        SELECT s.id, s.scan_token, s.started_at, s.completed_at, s.status,
                               s.total_files_scanned, s.issues_found, s.scan_duration, s.machine_name,
                               s.minecraft_username, s.ip_address, s.country,
                               st.created_by AS scanned_by, s.risk_score, s.verdict, s.os
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
                    _os_raw = _row_get(row, 15, 'os')
                    _os_str = (str(_os_raw).strip() if _os_raw is not None else '') or ''
                    _los = _os_str.lower()
                    if _los.startswith('linux'):
                        _plat = 'linux'
                    elif 'windows' in _los or _los.startswith('win'):
                        _plat = 'windows'
                    elif _os_str:
                        _plat = 'other'
                    else:
                        _plat = 'windows'
                    _scn_ver = ''
                    if _has_scn_ver:
                        try:
                            _v = _row_get(row, 16, 'scanner_version')
                            _scn_ver = (str(_v).strip() if _v is not None else '') or ''
                        except Exception:
                            _scn_ver = ''
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
                        'os': _os_str,
                        'os_name': _os_str,
                        'scanner_platform': _plat,
                        'scanner_version': _scn_ver,
                    })
                
                print(f"ðŸ“Š Escaneos encontrados en BD local: {len(scans)}")
                
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
                
                # Guardar en cachÃ©
                _stats_cache[cache_key] = result
                _stats_cache_time[cache_key] = time.time()
                
                print(f"âœ… Escaneos obtenidos directamente de BD. Total: {len(scans)}")
                return jsonify(result), 200
        except Exception as e:
            print(f"âš ï¸ Error accediendo BD directamente en list_scans: {str(e)}")
            print(traceback.format_exc())
            print("Intentando via HTTP como fallback...")
    
    # Fallback: usar HTTP para obtener escaneos desde la API
    print(f"ðŸ”„ Obteniendo escaneos vÃ­a HTTP desde: {get_api_url('/api/scans')}")
    try:
        api_url = get_api_url('/api/scans')
        print(f"ðŸŒ URL completa: {api_url}")
        print(f"ðŸŒ ParÃ¡metros: limit={limit}, offset={offset}")
        
        headers = {}
        if API_KEY:
            headers['X-API-Key'] = API_KEY
            print(f"ðŸ”‘ Enviando API Key en headers")
        else:
            print(f"âš ï¸ No hay API_KEY configurada, la API puede rechazar la peticiÃ³n")
        
        response = requests.get(
            api_url,
            params={'limit': limit, 'offset': offset},
            headers=headers,
            timeout=15  # Aumentado timeout para Render
        )
        
        print(f"ðŸ“¡ Respuesta de API: Status {response.status_code}")
        print(f"ðŸ“¡ Headers de respuesta: {dict(response.headers)}")
        
        if response.status_code == 200:
            result = response.json()
            scans_count = len(result.get('scans', []))
            print(f"âœ… Obtenidos {scans_count} escaneos desde la API")
            
            # Log detallado de los primeros escaneos
            if scans_count > 0:
                print(f"ðŸ“‹ Primeros escaneos recibidos:")
                for i, scan in enumerate(result.get('scans', [])[:3]):
                    print(f"   [{i+1}] Scan ID: {scan.get('id')}, Machine: {scan.get('machine_name')}, Issues: {scan.get('issues_found')}, Status: {scan.get('status')}")
            else:
                print(f"âš ï¸ La API devolviÃ³ 200 pero sin escaneos en la respuesta")
                print(f"ðŸ“‹ Respuesta completa: {result}")
            
            # Guardar en cachÃ©
            _stats_cache[cache_key] = result
            _stats_cache_time[cache_key] = time.time()
            return jsonify(result), 200
        else:
            print(f"âŒ Error obteniendo escaneos: {response.status_code}")
            print(f"âŒ Respuesta completa: {response.text[:500]}")
            return jsonify({'error': f'Error obteniendo escaneos: {response.status_code}', 'scans': []}), response.status_code
    except requests.exceptions.Timeout as te:
        print(f"âŒ Timeout al obtener escaneos desde la API: {te}")
        return jsonify({'error': 'Timeout al conectar con la API', 'scans': []}), 504
    except requests.exceptions.ConnectionError as ce:
        print(f"âŒ Error de conexiÃ³n con la API: {ce}")
        return jsonify({'error': f'No se pudo conectar con la API: {str(ce)}', 'scans': []}), 503
    except Exception as e:
        print(f"âŒ Error inesperado en list_scans (HTTP): {str(e)}")
        print(f"âŒ Traceback:")
        print(traceback.format_exc())
        return jsonify({'error': f'Error inesperado: {str(e)}', 'scans': []}), 500

@app.route('/api/scans/<int:scan_id>', methods=['GET'])
@login_required
def get_scan(scan_id):
    """Obtiene un escaneo especÃ­fico - Usa BD directa si estÃ¡ disponible, sino HTTP"""
    import time
    
    # CachÃ© por scan_id (5 segundos TTL)
    cache_key = f'scan_{scan_id}'
    if cache_key in _stats_cache:
        if time.time() - _stats_cache_time.get(cache_key, 0) < 5:
            return jsonify(_stats_cache[cache_key]), 200
    
    # Intentar acceso directo a BD primero (mÃ¡s rÃ¡pido)
    if API_DB_AVAILABLE_LOCALLY:
        try:
            with get_api_db_cursor() as cursor:
                # Columnas base (siempre existen desde la primera versiÃ³n del schema)
                cursor.execute(f'''
                    SELECT id, token_id, scan_token, started_at, completed_at, status,
                           total_files_scanned, issues_found, scan_duration,
                           machine_id, machine_name, ip_address, country, minecraft_username
                    FROM scans
                    WHERE id = {_PH} AND deleted_at IS NULL
                ''', (scan_id,))

                row = cursor.fetchone()
                if not row:
                    return jsonify({'error': 'Escaneo no encontrado'}), 404

                _started_raw = _row_get(row, 3, 'started_at')
                _status_raw = _row_get(row, 5, 'status')
                # Scans colgados en running (>10 min sin submit) — el panel los trata como abandonados
                if _status_raw == 'running' and _started_raw:
                    try:
                        from datetime import datetime, timezone
                        if hasattr(_started_raw, 'isoformat'):
                            _started_dt = _started_raw
                            if getattr(_started_dt, 'tzinfo', None) is None:
                                _started_dt = _started_dt.replace(tzinfo=timezone.utc)
                        else:
                            _s = str(_started_raw).replace('Z', '+00:00')
                            _started_dt = datetime.fromisoformat(_s)
                        _age_s = (datetime.now(timezone.utc) - _started_dt.astimezone(timezone.utc)).total_seconds()
                        if _age_s > 600:
                            _status_raw = 'abandoned'
                    except Exception:
                        pass

                scan = {
                    'id': _row_get(row, 0, 'id'),
                    'token_id': _row_get(row, 1, 'token_id'),
                    'scan_token': _row_get(row, 2, 'scan_token'),
                    'started_at': str(_started_raw or ''),
                    'completed_at': str(_row_get(row, 4, 'completed_at') or ''),
                    'status': _status_raw,
                    'total_files_scanned': _row_get(row, 6, 'total_files_scanned') or 0,
                    'total_dirs_scanned': 0,
                    'issues_found': _row_get(row, 7, 'issues_found') or 0,
                    'scan_duration': _row_get(row, 8, 'scan_duration') or 0,
                    'machine_id': _row_get(row, 9, 'machine_id'),
                    'machine_name': _row_get(row, 10, 'machine_name'),
                    'ip_address': _row_get(row, 11, 'ip_address'),
                    'country': _row_get(row, 12, 'country'),
                    'minecraft_username': _row_get(row, 13, 'minecraft_username'),
                    'os': None,
                    'os_name': None,
                    'scanner_platform': None,
                    'verdict': None, 'verdict_reason': None,
                    'verdict_by': None, 'verdict_at': '',
                }

                # Columnas opcionales: total_dirs_scanned, verdict, screenshot, mc_info, ensemble_data
                # Usa SAVEPOINT para que un fallo (columna inexistente) no aborte la transacciÃ³n
                scan['screenshot'] = None
                scan['mc_info'] = None
                scan['risk_score'] = 0
                scan['ensemble_data'] = None
                scan['scanner_version'] = ''
                try:
                    cursor.execute('SAVEPOINT opt_cols')
                    # Visual #50 â€” leer scanner_version. Tolerante a deploys sin la columna.
                    try:
                        cursor.execute(f'''
                            SELECT total_dirs_scanned, verdict, verdict_reason, verdict_by, verdict_at,
                                   screenshot, mc_info, risk_score, ensemble_data, os, scanner_version
                            FROM scans WHERE id = {_PH} AND deleted_at IS NULL
                        ''', (scan_id,))
                        _has_scn_ver_col = True
                    except Exception:
                        _has_scn_ver_col = False
                        cursor.execute(f'''
                            SELECT total_dirs_scanned, verdict, verdict_reason, verdict_by, verdict_at,
                                   screenshot, mc_info, risk_score, ensemble_data, os
                            FROM scans WHERE id = {_PH} AND deleted_at IS NULL
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
                        raw_ens = _row_get(vrow, 8, 'ensemble_data')
                        if raw_ens:
                            try:
                                scan['ensemble_data'] = json.loads(raw_ens)
                            except Exception:
                                scan['ensemble_data'] = None
                        _os_v = _row_get(vrow, 9, 'os')
                        _os_s = (str(_os_v).strip() if _os_v is not None else '') or ''
                        scan['os'] = _os_s or None
                        scan['os_name'] = scan['os']
                        lowos = (_os_s or '').lower()
                        if lowos.startswith('linux'):
                            scan['scanner_platform'] = 'linux'
                        elif 'windows' in lowos or lowos.startswith('win'):
                            scan['scanner_platform'] = 'windows'
                        elif lowos:
                            scan['scanner_platform'] = 'other'
                        else:
                            scan['scanner_platform'] = 'windows'
                        if _has_scn_ver_col:
                            try:
                                _sv = _row_get(vrow, 10, 'scanner_version')
                                scan['scanner_version'] = (str(_sv).strip() if _sv is not None else '') or ''
                            except Exception:
                                scan['scanner_version'] = ''
                    cursor.execute('RELEASE SAVEPOINT opt_cols')
                except Exception:
                    try:
                        cursor.execute('ROLLBACK TO SAVEPOINT opt_cols')
                    except Exception:
                        pass
                
                # Staff que hizo el scan (via token)
                # Usamos SAVEPOINT para que un fallo (deadlock con ALTER TABLE de
                # _ensure_plugin_keys_schema, columna inexistente, etc.) no aborte
                # la transaccion entera y deje sin resultados al endpoint.
                scan['scanned_by'] = None
                try:
                    cursor.execute('SAVEPOINT scanned_by_save')
                    cursor.execute(f'''
                        SELECT st.created_by FROM scans s
                        LEFT JOIN scan_tokens st ON s.token_id = st.id
                        WHERE s.id = {_PH}
                    ''', (scan_id,))
                    srow = cursor.fetchone()
                    if srow:
                        # _row_get maneja tanto sqlite3.Row como RealDictCursor (PostgreSQL)
                        scan['scanned_by'] = _row_get(srow, 0, 'created_by')
                    cursor.execute('RELEASE SAVEPOINT scanned_by_save')
                except Exception as _e_sb:
                    print(f"âš ï¸ get_scan scanned_by query fallida (id={scan_id}): {type(_e_sb).__name__}: {_e_sb}")
                    try:
                        cursor.execute('ROLLBACK TO SAVEPOINT scanned_by_save')
                    except Exception:
                        pass

                # Obtener resultados (incluye feedback_status para mostrar veredicto del staff
                # y extra con la metadata adicional para FILE_ACTIVITY del tab Logs).
                # IMPORTANTE: hay que hacer fetchall() ANTES del RELEASE SAVEPOINT.
                # En psycopg2 cualquier cursor.execute() siguiente (incluido RELEASE)
                # descarta los resultados pendientes del SELECT y el fetchall posterior
                # tira "ProgrammingError: no results to fetch". Por eso guardamos los
                # rows en una variable local y recien despues hacemos RELEASE.
                _has_extra_col = True
                _result_rows = []
                try:
                    cursor.execute('SAVEPOINT extra_select')
                    cursor.execute(f'''
                        SELECT id, issue_type, issue_name, issue_path, issue_category,
                               alert_level, confidence, detected_patterns, obfuscation_detected,
                               file_hash, ai_analysis, ai_confidence, feedback_status, extra
                        FROM scan_results
                        WHERE scan_id = {_PH}
                    ''', (scan_id,))
                    _result_rows = cursor.fetchall()
                    cursor.execute('RELEASE SAVEPOINT extra_select')
                except Exception:
                    try:
                        cursor.execute('ROLLBACK TO SAVEPOINT extra_select')
                    except Exception:
                        pass
                    _has_extra_col = False
                    cursor.execute(f'''
                        SELECT id, issue_type, issue_name, issue_path, issue_category,
                               alert_level, confidence, detected_patterns, obfuscation_detected,
                               file_hash, ai_analysis, ai_confidence, feedback_status
                        FROM scan_results
                        WHERE scan_id = {_PH}
                    ''', (scan_id,))
                    _result_rows = cursor.fetchall()

                results = []
                for r in _result_rows:
                    raw_patterns = _row_get(r, 7, 'detected_patterns')
                    extra_obj = {}
                    if _has_extra_col:
                        raw_extra = _row_get(r, 13, 'extra')
                        if raw_extra:
                            try:
                                extra_obj = json.loads(raw_extra) if isinstance(raw_extra, str) else (raw_extra or {})
                                if not isinstance(extra_obj, dict):
                                    extra_obj = {}
                            except (TypeError, ValueError):
                                extra_obj = {}
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
                        'extra': extra_obj,
                    })

                # Saneo de display: filtrar FPs de scans antiguos al servirlos al panel
                # (no toca la BD, solo lo que ve el staff)
                results = _scrub_results_for_display(results)

                # Filter #42 â€” Decorar con first_seen + seen_count antes de servir.
                # 1 query para todo el scan (IN ...). Si la tabla cae, todos quedan
                # en first_seen=true que es "mÃ¡s alarmante" y por tanto seguro.
                try:
                    _seen_map = _query_evidence_seen_counts(cursor, results)
                    _decorate_results_with_first_seen(results, _seen_map)
                except Exception as _fs_e:
                    print(f"âš ï¸ first-seen decorate fallÃ³: {_fs_e}")

                scan['results'] = results

                # Risk visible = heurística sobre hallazgos ya saneados (FP filter).
                # Corrige scans con risk inflado (p. ej. miles de FILE_ACTIVITY).
                if results:
                    try:
                        _stored_before = int(scan.get('risk_score') or 0)
                        _recalc = _calculate_risk_score(results)
                        scan['risk_score'] = _recalc
                        if _recalc != _stored_before:
                            try:
                                cursor.execute(
                                    f'UPDATE scans SET risk_score = {_PH} WHERE id = {_PH}',
                                    (_recalc, scan_id)
                                )
                            except Exception:
                                pass
                    except Exception:
                        pass

                # Filter #43, #44 â€” incluir thresholds dinÃ¡micos de la
                # empresa del staff. El frontend los usa para colorear
                # el risk_score y para los filtros del listado. Si el
                # staff no tiene company_id (admin global), defaults.
                try:
                    _cs = _get_company_settings(session.get('company_id'))
                    scan['company_settings'] = _cs
                except Exception:
                    scan['company_settings'] = {
                        'mode': 'normal',
                        'threshold_critical': 70,
                        'threshold_suspicious': 30,
                    }

                # Guardar en cachÃ©
                _stats_cache[cache_key] = scan
                _stats_cache_time[cache_key] = time.time()
                
                return jsonify(scan), 200
        except Exception as e:
            # Logueamos el traceback completo (Render lo capta) y resetamos
            # la conexion thread-local si quedo en estado abortado para que el
            # proximo request del mismo worker no herede la transaccion rota.
            print(f"âš ï¸ Error accediendo BD directamente en get_scan({scan_id}): {type(e).__name__}: {e}")
            print(traceback.format_exc())
            try:
                from db_mysql import _local as _db_local
                if hasattr(_db_local, 'connection'):
                    try:
                        _db_local.connection.rollback()
                    except Exception:
                        pass
                    try:
                        _db_local.connection.close()
                    except Exception:
                        pass
                    try:
                        del _db_local.connection
                    except Exception:
                        pass
                    print(f"ðŸ” Conexion thread-local reseteada tras error en get_scan")
            except Exception as _re:
                print(f"âš ï¸ No se pudo resetear conexion: {_re}")
            # Devolvemos el error real al frontend (con 500) para diagnosticar
            # rapido sin tener que mirar logs de Render. Antes esto se iba a un
            # fallback HTTP que loopeaba contra la misma instancia.
            return jsonify({
                'error': 'Error interno consultando el escaneo',
                'detail': f'{type(e).__name__}: {e}',
                'scan_id': scan_id,
                'argus_version': _ARGUS_VERSION,
            }), 500
    # Si la BD local no esta disponible, devolvemos 503 (no hacemos loop HTTP)
    return jsonify({
        'error': 'Backend BD no disponible',
        'scan_id': scan_id,
    }), 503

@app.route('/api/feedback', methods=['POST'])
@login_required
def submit_feedback():
    return jsonify({'success': True, 'message': 'Feedback desactivado'}), 200

@app.route('/api/feedback/batch', methods=['POST'])
@login_required
def submit_feedback_batch():
    return jsonify({'success': True, 'processed_count': 0, 'message': 'Feedback desactivado'}), 200

@app.route('/api/feedback/<int:result_id>', methods=['GET'])
def get_feedback(result_id):
    return jsonify({'feedback': None}), 200

@app.route('/api/update-model', methods=['POST'])
def update_model():
    """Retorna estadÃ­sticas de patrones aprendidos directamente desde BD"""
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
            'message': 'Modelo actualizado. Los clientes descargarÃ¡n automÃ¡ticamente los nuevos patrones al iniciar.',
            'version': '1.0',
            'patterns_count': patterns_count,
            'hashes_count': hashes_count,
            'legit_paths_count': legit_paths_count,
        })
    except Exception as e:
        print(f"Error en update_model: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': f'Error inesperado: {str(e)}'}), 500


@app.route('/api/ml/trigger', methods=['POST'])
@admin_required
def trigger_autonomous_learning():
    """Dispara el pipeline de aprendizaje autÃ³nomo manualmente (sin esperar al cron)."""
    import threading
    def _run():
        _autonomous_daily_learning()
    threading.Thread(target=_run, daemon=True).start()
    return jsonify({'success': True, 'message': 'Pipeline autÃ³nomo iniciado en segundo plano'})

@app.route('/api/learning-stats', methods=['GET'])
def get_learning_stats():
    """EstadÃ­sticas del sistema de aprendizaje autÃ³nomo."""
    try:
        from ml_classifier import get_classifier
        clf = get_classifier()
        with get_api_db_cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM learned_patterns WHERE is_active = TRUE AND pattern_type != 'legitimate_path'")
            patterns_count = (_row_get(cursor.fetchone(), 0, 'count') or 0)
            cursor.execute("SELECT COUNT(*) FROM learned_hashes")
            hashes_count = (_row_get(cursor.fetchone(), 0, 'count') or 0)
            cursor.execute("SELECT COUNT(*) FROM staff_feedback")
            feedbacks_count = (_row_get(cursor.fetchone(), 0, 'count') or 0)
            auto_count = 0
            try:
                cursor.execute("SELECT COUNT(*) FROM auto_labels")
                auto_count = (_row_get(cursor.fetchone(), 0, 'count') or 0)
            except Exception:
                pass
        return jsonify({
            'patterns_count':   int(patterns_count),
            'hashes_count':     int(hashes_count),
            'feedbacks_count':  int(feedbacks_count),
            'auto_labels':      int(auto_count),
            'rf_trained_on':    clf._trained_on,
            'rf_available':     clf.is_available,
            'iso_available':    clf.iso_available,
            'iso_trained_on':   getattr(clf, '_iso_trained_on', 0),
        }), 200
    except Exception as e:
        return jsonify({'patterns_count': 0, 'hashes_count': 0, 'feedbacks_count': 0, 'error': str(e)}), 200


@app.route('/api/admin/scans/bulk-delete', methods=['POST'])
@login_required
@audit_action('scan.bulk_soft_delete', 'scan')
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
            cursor.execute(f'UPDATE scans SET deleted_at = CURRENT_TIMESTAMP WHERE id IN ({_ids_ph})', scan_ids)
        return jsonify({'deleted': len(scan_ids), 'message': f'{len(scan_ids)} scan(s) marcados como borrados'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/hard-delete/<resource>/<int:rid>', methods=['POST'])
@login_required
@require_superadmin
@audit_action('admin.hard_delete', 'resource')
def admin_hard_delete(resource: str, rid: int):
    table_map = {
        'scans': 'scans',
        'users': 'users',
        'companies': 'companies',
        'oracle_decisions': 'ai_decisions_log',
        'ban_history': 'ban_history',
        'game_profiles': 'game_profiles',
        'shared_filter_rules': 'shared_filter_rules',
    }
    table = table_map.get(resource)
    if not table:
        return jsonify({'success': False, 'error': 'resource inválido'}), 400
    try:
        with get_api_db_cursor() as cursor:
            cursor.execute(f"DELETE FROM {table} WHERE id = {_PH}", (rid,))
        return jsonify({'success': True, 'resource': resource, 'id': rid}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/restore/<resource>/<int:rid>', methods=['POST'])
@login_required
@require_superadmin
@audit_action('admin.restore_soft_deleted', 'resource')
def admin_restore_soft_deleted(resource: str, rid: int):
    table_map = {
        'scans': 'scans',
        'users': 'users',
        'companies': 'companies',
        'oracle_decisions': 'ai_decisions_log',
        'ban_history': 'ban_history',
        'game_profiles': 'game_profiles',
        'shared_filter_rules': 'shared_filter_rules',
    }
    table = table_map.get(resource)
    if not table:
        return jsonify({'success': False, 'error': 'resource inválido'}), 400
    try:
        with get_api_db_cursor() as cursor:
            cursor.execute(
                f"UPDATE {table} SET deleted_at = NULL "
                f"WHERE id = {_PH} AND deleted_at >= CURRENT_TIMESTAMP - INTERVAL '30 days'",
                (rid,)
            )
        return jsonify({'success': True, 'resource': resource, 'id': rid}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


def purge_soft_deleted_older_than_90d():
    targets = ['scans', 'users', 'companies', 'ai_decisions_log', 'ban_history', 'game_profiles', 'shared_filter_rules']
    try:
        with get_api_db_cursor() as cursor:
            for t in targets:
                try:
                    cursor.execute(f"DELETE FROM {t} WHERE deleted_at IS NOT NULL AND deleted_at < CURRENT_TIMESTAMP - INTERVAL '90 days'")
                except Exception:
                    pass
    except Exception as e:
        print(f"[soft_delete] purge error: {e}")


@app.route('/api/admin/purge-garbage-results', methods=['POST'])
@login_required
def purge_garbage_results():
    """Elimina resultados basura de EXEs viejos (EXECUTED_DELETED + nombres binarios). Solo admin."""
    current_user = get_user_by_id(session.get('user_id'))
    if not is_admin(current_user):
        return jsonify({'error': 'Se requiere rol admin'}), 403
    try:
        with get_api_db_cursor() as cursor:
            # Eliminar por categorÃ­a legacy
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
    
    # CachÃ© (60 segundos TTL - los patrones no cambian tan frecuentemente)
    cache_key = 'learned_patterns'
    if cache_key in _stats_cache:
        if time.time() - _stats_cache_time.get(cache_key, 0) < 60:
            return jsonify(_stats_cache[cache_key]), 200
    
    try:
        # Acceso directo a BD (SIN HTTP - MUCHO MÃS RÃPIDO)
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
                    # Si la tabla no existe, retornar vacÃ­o
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
            
            # Guardar en cachÃ©
            _stats_cache[cache_key] = result
            _stats_cache_time[cache_key] = time.time()
            
            return jsonify(result), 200
    except Exception as e:
        print(f"Error en get_learned_patterns: {str(e)}")
        print(traceback.format_exc())
        # Retornar respuesta vacÃ­a en lugar de error para no romper la app
        return jsonify({'patterns': [], 'total': 0, 'error': str(e)}), 200

@app.route('/api/ai-model/latest', methods=['GET'])
def get_latest_ai_model():
    """Obtiene el modelo de IA mÃ¡s reciente - OPTIMIZADO: Acceso directo a BD sin HTTP"""
    import time
    
    # CachÃ© (300 segundos TTL - el modelo no cambia tan frecuentemente)
    cache_key = 'ai_model_latest'
    if cache_key in _stats_cache:
        if time.time() - _stats_cache_time.get(cache_key, 0) < 300:
            return jsonify(_stats_cache[cache_key]), 200
    
    try:
        # Acceso directo a BD (SIN HTTP - MUCHO MÃS RÃPIDO)
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
            
            # Guardar en cachÃ©
            _stats_cache[cache_key] = result
            _stats_cache_time[cache_key] = time.time()
            
            return jsonify(result), 200
    except Exception as e:
        print(f"Error en get_latest_ai_model: {str(e)}")
        print(traceback.format_exc())
        # Retornar modelo vacÃ­o en lugar de error
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
    """Genera una nueva versiÃ³n de la aplicaciÃ³n.
    En Render: sirve el exe pre-compilado + muestra modelo actualizado.
    En local Windows: compila con PyInstaller.
    """
    # En Render no se puede compilar (Linux, sin PyInstaller).
    # En cambio, servimos el exe pre-compilado que viene en el repo
    # y mostramos las estadÃ­sticas del modelo (que el scanner descarga en runtime).
    if IS_RENDER:
        def generate_render():
            try:
                yield f"data: {json.dumps({'step': 'ðŸ” Verificando modelo de IA...', 'progress': 20})}\n\n"

                # Leer estadÃ­sticas del modelo
                try:
                    with get_api_db_cursor() as _cur:
                        _cur.execute('SELECT COUNT(*) as c FROM learned_patterns WHERE is_active = TRUE')
                        patterns_count = _row_get(_cur.fetchone(), 0, 'c') or 0
                        _cur.execute('SELECT COUNT(*) as c FROM learned_hashes')
                        hashes_count = _row_get(_cur.fetchone(), 0, 'c') or 0
                except Exception:
                    patterns_count = hashes_count = 0

                yield f"data: {json.dumps({'step': f'âœ… Modelo activo: {patterns_count} patrones aprendidos, {hashes_count} hashes confirmados', 'progress': 40})}\n\n"
                yield f"data: {json.dumps({'step': 'ðŸ“¡ El scanner descarga automÃ¡ticamente el modelo actualizado en cada inicio â€” no requiere recompilar.', 'progress': 60})}\n\n"

                # Buscar el exe pre-compilado en el repo
                project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                exe_candidates = [
                    os.path.join(project_root, 'source', 'dist', 'ArgusScanner.exe'),
                    os.path.join(project_root, 'source', 'dist', 'MinecraftSSTool.exe'),
                    os.path.join(project_root, 'ArgusScanner.exe'),
                ]
                exe_path = next((p for p in exe_candidates if os.path.exists(p)), None)

                if not exe_path:
                    _msg = ('âš ï¸ No se encontrÃ³ un ejecutable pre-compilado en el repositorio.\n\n'
                            'Para distribuir el scanner:\n1. Compila localmente: pyinstaller ArgusScanner.spec\n'
                            '2. Haz commit de source/dist/ArgusScanner.exe\n'
                            '3. Pushea a GitHub â€” Render lo incluirÃ¡ en el siguiente deploy.')
                    yield "data: " + json.dumps({'step': _msg, 'progress': 100, 'error': True}) + "\n\n"
                    return

                import hashlib
                file_size = os.path.getsize(exe_path)
                with open(exe_path, 'rb') as f:
                    file_hash = hashlib.sha256(f.read()).hexdigest()
                exe_name = os.path.basename(exe_path)

                yield f"data: {json.dumps({'step': f'âœ… Ejecutable listo: {exe_name} ({file_size / (1024*1024):.1f} MB)', 'progress': 90})}\n\n"

                # Registrar en BD como versiÃ³n disponible
                import datetime as _dt
                version = _dt.datetime.now().strftime('%Y%m%d_%H%M%S')
                try:
                    with get_api_db_cursor() as _cur:
                        _cur.execute(
                            f'INSERT INTO app_versions (version, download_url, changelog, file_size, file_hash) VALUES ({_PH},{_PH},{_PH},{_PH},{_PH}) ON CONFLICT (version) DO NOTHING',
                            (f'1.{version}', f'/download/{exe_name}',
                             f'Modelo: {patterns_count} patrones, {hashes_count} hashes. IA se actualiza automÃ¡ticamente en runtime.',
                             file_size, file_hash)
                        )
                except Exception:
                    pass

                _done_msg = (f'âœ… Listo para distribuir.\n\nArchivo: {exe_name}\n'
                             f'TamaÃ±o: {file_size / (1024*1024):.1f} MB\n'
                             f'Modelo: {patterns_count} patrones + {hashes_count} hashes\n\n'
                             'ðŸ’¡ El modelo de IA se actualiza automÃ¡ticamente sin recompilar.')
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
            
            # Obtener estadÃ­sticas del modelo directamente desde BD
            try:
                with get_api_db_cursor() as _cur:
                    _cur.execute('SELECT COUNT(*) as c FROM learned_patterns WHERE is_active = TRUE')
                    patterns_count = _row_get(_cur.fetchone(), 0, 'c') or 0
                    _cur.execute('SELECT COUNT(*) as c FROM learned_hashes')
                    hashes_count = _row_get(_cur.fetchone(), 0, 'c') or 0
                step_message = f'âœ… Modelo: {patterns_count} patrones, {hashes_count} hashes. Los clientes descargarÃ¡n automÃ¡ticamente.'
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
                yield f"data: {json.dumps({'step': 'ERROR: No se encontrÃ³ ArgusScanner.spec en source/', 'progress': 100, 'error': True})}\n\n"
                return

            yield f"data: {json.dumps({'step': f'âœ… Spec encontrado: {os.path.basename(spec_file)}', 'progress': 58})}\n\n"
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
                # Leer salida lÃ­nea por lÃ­nea
                line = process.stdout.readline()
                if line:
                    output_lines.append(line.strip())
                    # Mostrar Ãºltimas lÃ­neas importantes
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
                yield f"data: {json.dumps({'step': f'ERROR en compilaciÃ³n (cÃ³digo {return_code}): {error_msg}', 'progress': 100, 'error': True})}\n\n"
                return
            
            # Verificar si hay mensajes de error en la salida
            if 'error' in output_text.lower() or 'failed' in output_text.lower():
                error_msg = output_text[-500:] if len(output_text) > 500 else output_text
                yield f"data: {json.dumps({'step': f'Advertencia en compilaciÃ³n: {error_msg}', 'progress': 95})}\n\n"
            
            # Paso 3: Buscar ejecutable compilado
            yield f"data: {json.dumps({'step': 'Buscando ejecutable compilado...', 'progress': 92})}\n\n"
            time.sleep(0.5)

            exe_candidates_local = [
                os.path.join(project_root, 'source', 'dist', 'ArgusScanner.exe'),
                os.path.join(project_root, 'source', 'dist', 'MinecraftSSTool.exe'),
            ]
            exe_path = next((p for p in exe_candidates_local if os.path.exists(p)), None)
            if not exe_path:
                yield f"data: {json.dumps({'step': 'ERROR: Ejecutable no encontrado despuÃ©s de compilaciÃ³n', 'progress': 100, 'error': True})}\n\n"
                return
            
            # Paso 4: Calcular hash y tamaÃ±o
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
            
            # Paso 6: Registrar versiÃ³n en BD directamente
            try:
                with get_api_db_cursor() as _cur:
                    _cur.execute(
                        f'INSERT INTO app_versions (version, download_url, changelog, file_size, file_hash) VALUES ({_PH},{_PH},{_PH},{_PH},{_PH}) ON CONFLICT (version) DO NOTHING',
                        (f'1.{version}', f'/download/{download_filename}',
                         f'VersiÃ³n generada con {model_data.get("patterns_count", 0)} patrones aprendidos',
                         file_size, file_hash)
                    )
            except Exception:
                pass
            
            # Paso 7: Completado
            step_message = f'âœ… AplicaciÃ³n generada exitosamente.\n\nArchivo: {download_filename}\nTamaÃ±o: {file_size / (1024*1024):.1f} MB\nHash: {file_hash[:16]}...\n\nNOTA: Las actualizaciones de IA se descargan automÃ¡ticamente sin necesidad de recompilar.'
            yield f"data: {json.dumps({'step': step_message, 'progress': 100, 'success': True, 'download_url': f'/download/{download_filename}', 'filename': download_filename})}\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'step': f'ERROR: {str(e)}', 'progress': 100, 'error': True})}\n\n"
    
    return Response(generate(), mimetype='text/event-stream')

@app.route('/download/<filename>')
def download_file(filename):
    """Endpoint para descargar el ejecutable generado - Requiere autenticaciÃ³n o token"""
    import os
    from flask import send_file, request
    
    # Verificar si hay un token en la query string
    token = request.args.get('token')
    if token:
        # Usar el endpoint con token
        return download_with_token(token)
    
    # Si no hay token, requerir autenticaciÃ³n (comportamiento anterior)
    from auth import login_required
    return login_required(lambda: _send_file_download(filename))()

def _send_file_download(filename):
    """FunciÃ³n auxiliar para enviar el archivo"""
    import os
    from flask import send_file, jsonify
    
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Lista de ubicaciones posibles en orden de prioridad
    possible_paths = [
        os.path.join(project_root, 'dist', filename),
        os.path.join(project_root, 'downloads', filename),
        os.path.join(project_root, 'source', 'dist', filename),
        os.path.join(project_root, filename),
    ]
    
    # Buscar el primer archivo que exista (evita mÃºltiples checks)
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
    """Endpoint pÃºblico para descargar usando token temporal (similar a Ocean)"""
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
                return jsonify({'error': 'Enlace de descarga invÃ¡lido o expirado'}), 404

            link_id       = _row_get(link, 0, 'id')
            filename      = _row_get(link, 1, 'filename')
            expires_at    = _row_get(link, 2, 'expires_at')
            max_downloads = _row_get(link, 3, 'max_downloads')
            download_count= _row_get(link, 4, 'download_count')

            # Obtener el token de escaneo del parÃ¡metro de la URL (si existe)
            scan_token = request.args.get('token', None)

            try:
                max_downloads  = int(max_downloads)  if max_downloads  is not None else -1
                download_count = int(download_count) if download_count is not None else 0
            except (ValueError, TypeError):
                max_downloads = -1
                download_count = 0

            print(f"ðŸ” Verificando enlace: ID={link_id}, max={max_downloads}, count={download_count}")

            # Verificar expiraciÃ³n
            if expires_at:
                if isinstance(expires_at, str):
                    expires_dt = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                else:
                    expires_dt = expires_at  # psycopg2 ya devuelve datetime
                if datetime.now() > expires_dt.replace(tzinfo=None):
                    print(f"âŒ Enlace expirado: {expires_at}")
                    return jsonify({'error': 'Este enlace de descarga ha expirado'}), 410

            # Verificar lÃ­mite de descargas (-1 = ilimitado)
            if max_downloads != -1 and download_count >= max_downloads:
                print(f"âŒ LÃ­mite alcanzado: {download_count} >= {max_downloads}")
                return jsonify({'error': 'Este enlace ha alcanzado el lÃ­mite de descargas'}), 403

            print(f"âœ… Enlace vÃ¡lido, procediendo con descarga")

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
            # Fallback: buscar ArgusScanner.exe si se pidiÃ³ el nombre viejo
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
                    
                    print(f"âœ… ZIP creado con ejecutable y config.json: {zip_path}")
                    print(f"ðŸ”‘ Token incluido en config: {scan_token[:20]}...")
                    
                    # Enviar el ZIP
                    response = send_file(zip_path, as_attachment=True, download_name='ArgusScanner.zip', mimetype='application/zip')
                    
                    # Limpiar el archivo temporal despuÃ©s de enviarlo (en un thread separado)
                    def cleanup_temp_file():
                        import time
                        time.sleep(5)  # Esperar 5 segundos antes de eliminar
                        try:
                            if os.path.exists(zip_path):
                                os.remove(zip_path)
                                print(f"ðŸ—‘ï¸ Archivo temporal eliminado: {zip_path}")
                        except Exception as e:
                            print(f"âš ï¸ Error eliminando archivo temporal: {e}")
                    
                    import threading
                    threading.Thread(target=cleanup_temp_file, daemon=True).start()
                    
                    return response
                except Exception as e:
                    print(f"âš ï¸ Error creando ZIP con token: {e}")
                    traceback.print_exc()
                    # Continuar con la descarga normal si falla la creaciÃ³n del ZIP
            
            return send_file(file_path, as_attachment=True, download_name=filename)
        else:
            return jsonify({'error': f'Archivo no encontrado: {filename}'}), 404
    except Exception as e:
        print(f"âŒ Error en download_with_token: {e}")
        print(traceback.format_exc())
        return jsonify({'error': f'Error al procesar descarga: {str(e)}'}), 500

# Cache de metadatos del .exe (tamano + sha256). Se invalida si mtime cambia.
_EXE_META_CACHE: dict = {}

def _get_exe_metadata(exe_name: str = 'ArgusScanner.exe'):
    """Devuelve dict con {size_mb, size_bytes, sha256, mtime, exists, path}.
    Cachea el SHA-256 entre requests porque calcularlo es caro.
    Si el archivo no existe devuelve un dict 'best-effort' con exists=False."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidates = [
        os.path.join(project_root, 'dist', exe_name),
        os.path.join(project_root, 'downloads', exe_name),
    ]
    exe_path = next((p for p in candidates if os.path.exists(p)), None)
    if not exe_path:
        return {'exists': False, 'size_mb': None, 'size_bytes': 0, 'sha256': None, 'mtime': None, 'path': None}

    mtime = os.path.getmtime(exe_path)
    cached = _EXE_META_CACHE.get(exe_name)
    if cached and cached.get('mtime') == mtime and cached.get('data') is not None:
        return cached['data']

    try:
        import hashlib
        size_bytes = os.path.getsize(exe_path)
        h = hashlib.sha256()
        with open(exe_path, 'rb') as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b''):
                h.update(chunk)
        sha256 = h.hexdigest()
        data = {
            'exists': True,
            'size_bytes': size_bytes,
            'size_mb': round(size_bytes / (1024 * 1024), 1),
            'sha256': sha256,
            'mtime': mtime,
            'path': exe_path,
        }
        _EXE_META_CACHE[exe_name] = {'mtime': mtime, 'data': data}
        return data
    except Exception as exc:
        print(f"[descargar] error calculando metadata exe: {exc}")
        return {'exists': True, 'size_mb': None, 'size_bytes': 0, 'sha256': None, 'mtime': mtime, 'path': exe_path}


@app.route('/descargar')
def descargar_page():
    """Pagina publica de descarga de ArgusScanner."""
    base_url = os.environ.get('RENDER_EXTERNAL_URL', request.host_url).rstrip('/')
    exe_url = f"{base_url}/descargar/exe"
    lite_url = f"{base_url}/descargar/exe-lite"
    meta = _get_exe_metadata()
    lite_meta = _get_exe_metadata(exe_name='ArgusScannerLite.exe')
    return render_template(
        'descargar.html',
        exe_url=exe_url,
        exe_size_mb=meta.get('size_mb'),
        exe_sha256=meta.get('sha256'),
        exe_exists=meta.get('exists', False),
        lite_url=lite_url,
        lite_size_mb=lite_meta.get('size_mb'),
        lite_exists=lite_meta.get('exists', False),
    )


# â”€â”€ ReputaciÃ³n pÃºblica de jugadores (read-only, efecto de red cross-server) â”€â”€

def _rep_username_ok(u):
    """Valida un nombre de Minecraft: 1-32 chars alfanumÃ©ricos o guion bajo."""
    return bool(u) and 1 <= len(u) <= 32 and all(c.isalnum() or c == '_' for c in u)


def _rep_parse_dt(s):
    """Parsea started_at (datetime o string) de forma tolerante. None si no puede."""
    if isinstance(s, datetime.datetime):
        return s
    if not s:
        return None
    t = str(s).strip().replace(' ', 'T')
    t = t.split('+')[0].split('Z')[0]
    try:
        return datetime.datetime.fromisoformat(t)
    except Exception:
        try:
            return datetime.datetime.fromisoformat(t[:19])
        except Exception:
            return None


@app.route('/reputacion')
@app.route('/reputation')
def reputacion_page():
    """PÃ¡gina pÃºblica de reputaciÃ³n de jugadores (solo lectura)."""
    return render_template('reputacion.html')


_rep_cache = {}
_REP_CACHE_TTL = 60
_rep_rate = {}            # ip -> [timestamps] (throttle propio, independiente de Flask-Limiter)
_REP_RATE_MAX = 30
_REP_RATE_WINDOW = 60


@app.route('/api/public/reputation', methods=['GET'])
@_limit("40 per minute")
def api_public_reputation():
    """ReputaciÃ³n pÃºblica agregada de un jugador por minecraft_username.

    Solo expone agregados NO sensibles: conteos de scans, veredictos,
    risk_score promedio, etiqueta de reputaciÃ³n y un historial anonimizado
    (fecha + veredicto + risk). NUNCA devuelve IP, machine_id, empresa/servidor
    ni quiÃ©n hizo el scan.
    """
    username = (request.args.get('u') or request.args.get('user') or '').strip()
    if not _rep_username_ok(username):
        return jsonify({'error': 'username invalido'}), 400

    _key = username.lower()
    _now = _time_mod.time()

    # Throttle propio por IP (red de seguridad contra enumeracion/abuso)
    _ip = (request.headers.get('X-Forwarded-For', '').split(',')[0].strip()
           or request.remote_addr or 'unknown')
    _bucket = [t for t in _rep_rate.get(_ip, []) if _now - t < _REP_RATE_WINDOW]
    if len(_bucket) >= _REP_RATE_MAX:
        _rep_rate[_ip] = _bucket
        _r429 = jsonify({'error': 'demasiadas consultas, espera un momento'})
        return _r429, 429
    _bucket.append(_now)
    if len(_rep_rate) > 5000:
        _rep_rate.clear()
    _rep_rate[_ip] = _bucket

    _hit = _rep_cache.get(_key)
    if _hit and (_now - _hit[1]) < _REP_CACHE_TTL:
        _r = jsonify(_hit[0])
        _r.headers['Cache-Control'] = 'public, max-age=60'
        return _r

    out = {
        'username':    username,
        'scan_count':  0,
        'hack_count':  0,
        'clean_count': 0,
        'hack_rate':   0,
        'avg_risk':    0,
        'reputation':  None,
        'first_seen':  None,
        'last_seen':   None,
        'recent':      {'scans_7d': 0, 'hacks_7d': 0, 'hacks_30d': 0},
        'history':     [],
    }
    try:
        rows = []
        with get_api_db_cursor() as cur:
            try:
                cur.execute(
                    f"SELECT verdict, risk_score, started_at FROM scans"
                    f" WHERE LOWER(minecraft_username)=LOWER({_PH}) AND status={_PH}"
                    f" ORDER BY id DESC LIMIT 100",
                    (username, 'completed')
                )
                rows = cur.fetchall() or []
            except Exception:
                # Fallback defensivo si falta alguna columna (status/risk/verdict)
                try:
                    cur.execute(
                        f"SELECT verdict, risk_score, started_at FROM scans"
                        f" WHERE LOWER(minecraft_username)=LOWER({_PH})"
                        f" ORDER BY id DESC LIMIT 100",
                        (username,)
                    )
                    rows = cur.fetchall() or []
                except Exception:
                    rows = []

        verdicts = [(_row_get(r, 0, 'verdict') or '').lower() for r in rows]
        risks    = [int(_row_get(r, 1, 'risk_score') or 0) for r in rows]
        dates    = [_row_get(r, 2, 'started_at') for r in rows]

        total       = len(rows)
        hack_count  = verdicts.count('hack')
        clean_count = verdicts.count('clean')
        out['scan_count']  = total
        out['hack_count']  = hack_count
        out['clean_count'] = clean_count
        if total:
            out['hack_rate'] = round(hack_count / total, 3)
            out['avg_risk']  = round(sum(risks) / total, 1)
            out['reputation'] = ('ALTO_RIESGO' if out['hack_rate'] >= 0.5
                                 else 'SOSPECHOSO' if out['hack_rate'] >= 0.2
                                 else 'LIMPIO')
            _ds = [str(d) for d in dates if d]
            if _ds:
                out['last_seen']  = _ds[0]
                out['first_seen'] = _ds[-1]
            out['history'] = [
                {
                    'date':    str(_row_get(r, 2, 'started_at') or ''),
                    'verdict': (_row_get(r, 0, 'verdict') or 'pending').lower(),
                    'risk':    int(_row_get(r, 1, 'risk_score') or 0),
                }
                for r in rows[:25]
            ]
            _now_dt = datetime.datetime.utcnow()
            _rec = {'scans_7d': 0, 'hacks_7d': 0, 'hacks_30d': 0}
            for r in rows:
                _d = _rep_parse_dt(_row_get(r, 2, 'started_at'))
                if not _d:
                    continue
                _age = (_now_dt - _d).days
                _v = (_row_get(r, 0, 'verdict') or '').lower()
                if _age <= 7:
                    _rec['scans_7d'] += 1
                    if _v == 'hack':
                        _rec['hacks_7d'] += 1
                if _age <= 30 and _v == 'hack':
                    _rec['hacks_30d'] += 1
            out['recent'] = _rec
    except Exception:
        pass  # DB no disponible -> se devuelve out en cero

    if len(_rep_cache) > 1000:
        _rep_cache.clear()
    _rep_cache[_key] = (out, _now)
    resp = jsonify(out)
    resp.headers['Cache-Control'] = 'public, max-age=60'
    return resp


_wanted_cache = {'data': None, 'ts': 0}
_WANTED_TTL = 120


@app.route('/api/public/wanted', methods=['GET'])
@_limit("30 per minute")
def api_public_wanted():
    """Ranking publico de "mas buscados": jugadores con mas hacks confirmados.

    Solo expone username + conteos agregados (mismo principio de red que la
    reputacion individual). NUNCA expone IP, machine_id ni servidor/empresa.
    """
    _now = _time_mod.time()

    # Mismo throttle por IP que la reputacion (red de seguridad anti-abuso)
    _ip = (request.headers.get('X-Forwarded-For', '').split(',')[0].strip()
           or request.remote_addr or 'unknown')
    _bucket = [t for t in _rep_rate.get(_ip, []) if _now - t < _REP_RATE_WINDOW]
    if len(_bucket) >= _REP_RATE_MAX:
        _rep_rate[_ip] = _bucket
        return jsonify({'error': 'demasiadas consultas, espera un momento'}), 429
    _bucket.append(_now)
    if len(_rep_rate) > 5000:
        _rep_rate.clear()
    _rep_rate[_ip] = _bucket

    if _wanted_cache['data'] is not None and (_now - _wanted_cache['ts']) < _WANTED_TTL:
        _r = jsonify(_wanted_cache['data'])
        _r.headers['Cache-Control'] = 'public, max-age=120'
        return _r

    out = {'players': [], 'generated_at': int(_now)}
    try:
        rows = []
        with get_api_db_cursor() as cur:
            try:
                cur.execute(
                    f"SELECT minecraft_username,"
                    f" SUM(CASE WHEN LOWER(verdict)='hack' THEN 1 ELSE 0 END) AS hacks,"
                    f" COUNT(*) AS total"
                    f" FROM scans"
                    f" WHERE status={_PH} AND minecraft_username IS NOT NULL AND minecraft_username <> ''"
                    f" GROUP BY minecraft_username"
                    f" ORDER BY hacks DESC, total DESC"
                    f" LIMIT 30",
                    ('completed',)
                )
                rows = cur.fetchall() or []
            except Exception:
                try:
                    cur.execute(
                        f"SELECT minecraft_username,"
                        f" SUM(CASE WHEN LOWER(verdict)='hack' THEN 1 ELSE 0 END) AS hacks,"
                        f" COUNT(*) AS total"
                        f" FROM scans"
                        f" WHERE minecraft_username IS NOT NULL AND minecraft_username <> ''"
                        f" GROUP BY minecraft_username"
                        f" ORDER BY hacks DESC, total DESC"
                        f" LIMIT 30"
                    )
                    rows = cur.fetchall() or []
                except Exception:
                    rows = []

        players = []
        for r in rows:
            uname = _row_get(r, 0, 'minecraft_username') or ''
            hacks = int(_row_get(r, 1, 'hacks') or 0)
            total = int(_row_get(r, 2, 'total') or 0)
            if not uname or hacks < 1:
                continue
            players.append({
                'username':  uname,
                'hacks':     hacks,
                'scans':     total,
                'hack_rate': round(hacks / total, 3) if total else 0,
                'recent_hacks_7d': 0,
            })
            if len(players) >= 15:
                break

        # Recencia: hacks confirmados en los ultimos 7 dias (marca reincidencia activa)
        recent_map = {}
        try:
            with get_api_db_cursor() as cur2:
                try:
                    cur2.execute(
                        "SELECT minecraft_username, COUNT(*) AS cnt FROM scans"
                        " WHERE LOWER(verdict)='hack' AND started_at > NOW() - INTERVAL '7 days'"
                        " AND minecraft_username IS NOT NULL AND minecraft_username <> ''"
                        " GROUP BY minecraft_username"
                    )
                    rr = cur2.fetchall() or []
                except Exception:
                    cur2.execute(
                        "SELECT minecraft_username, COUNT(*) AS cnt FROM scans"
                        " WHERE LOWER(verdict)='hack' AND started_at > datetime('now', '-7 days')"
                        " AND minecraft_username IS NOT NULL AND minecraft_username <> ''"
                        " GROUP BY minecraft_username"
                    )
                    rr = cur2.fetchall() or []
            for r in rr:
                _u = (_row_get(r, 0, 'minecraft_username') or '').lower()
                if _u:
                    recent_map[_u] = int(_row_get(r, 1, 'cnt') or 0)
        except Exception:
            recent_map = {}

        for p in players:
            p['recent_hacks_7d'] = recent_map.get(p['username'].lower(), 0)

        out['players'] = players
    except Exception:
        pass  # DB no disponible -> ranking vacio

    _wanted_cache['data'] = out
    _wanted_cache['ts'] = _now
    resp = jsonify(out)
    resp.headers['Cache-Control'] = 'public, max-age=120'
    return resp


@app.route('/descargar/exe')
def descargar_exe():
    """Endpoint pÃºblico permanente para descargar ArgusScanner.exe sin autenticaciÃ³n."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    possible_paths = [
        os.path.join(project_root, 'dist', 'ArgusScanner.exe'),          # versiÃ³n compilada en git (prioridad)
        os.path.join(project_root, 'downloads', 'ArgusScanner.exe'),      # fallback: subida manual
        os.path.join(project_root, 'source', 'dist', 'ArgusScanner.exe'),
        os.path.join(project_root, 'ArgusScanner.exe'),
    ]
    for path in possible_paths:
        if os.path.exists(path):
            return send_file(path, as_attachment=True, download_name='ArgusScanner.exe')
    return jsonify({'error': 'Ejecutable no disponible aÃºn. Contacta a un administrador.'}), 404


def _locate_scanner_exe():
    """Devuelve la ruta del ArgusScanner.exe compilado, o None."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for p in (
        os.path.join(project_root, 'dist', 'ArgusScanner.exe'),
        os.path.join(project_root, 'downloads', 'ArgusScanner.exe'),
        os.path.join(project_root, 'source', 'dist', 'ArgusScanner.exe'),
        os.path.join(project_root, 'ArgusScanner.exe'),
    ):
        if os.path.exists(p):
            return p
    return None


_SCANNER_README = (
    "ARGUS SCANNER — Paquete autorizado para Screen Share\n"
    "====================================================\n\n"
    "1. Extraé TODO este ZIP en una carpeta (no ejecutes desde dentro del .zip).\n"
    "2. Dejá ArgusScanner.exe junto a config.json en la misma carpeta.\n"
    "3. Ejecutá ArgusScanner.exe como administrador.\n"
    "4. Se autentica solo con la licencia firmada — NO hay que tipear ningún código.\n"
    "5. Dejá la ventana abierta hasta que el staff te lo indique.\n\n"
    "La licencia caduca sola. Si ves 'Licencia expirada', pedile al staff un link nuevo.\n"
)


def _no_store(resp):
    """Evita que proxies/navegadores cacheen una descarga con licencia."""
    try:
        resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, private'
        resp.headers['Pragma'] = 'no-cache'
        resp.headers['X-Content-Type-Options'] = 'nosniff'
    except Exception:
        pass
    return resp


def _send_scanner_zip_with_license(license_str):
    """Arma y envia un ZIP con ArgusScanner.exe + config.json (con la licencia
    firmada embebida) + README.txt. Devuelve (response, None) o (None, error_msg)."""
    import zipfile
    import tempfile
    import threading as _threading
    import json as json_lib

    exe_path = _locate_scanner_exe()
    if not exe_path:
        return None, 'El ejecutable no está disponible todavía. Contactá a un administrador.'

    api_url = (get_api_url('').rstrip('/api')) or 'https://asperss.onrender.com'
    web_url = request.host_url.rstrip('/') if not IS_RENDER else os.environ.get('RENDER_EXTERNAL_URL', request.host_url).rstrip('/')
    config_data = {
        "discord_webhook": "",
        "auth_token": "",
        "scan_timeout": 300,
        "scan_token": license_str,   # los .exe actuales leen scan_token y auto-validan
        "license": license_str,      # alias semantico para builds nuevos
        "api_url": api_url,
        "web_url": web_url,
        "enable_db_integration": True,
        "enable_ai_analysis": True,
        "enable_discord_report": False,
        "enable_web_report": True,
    }

    temp_dir = tempfile.gettempdir()
    zip_path = os.path.join(temp_dir, f'ArgusScanner_lic_{secrets.token_hex(8)}.zip')
    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(exe_path, 'ArgusScanner.exe')
            zipf.writestr('config.json', json_lib.dumps(config_data, indent=2))
            zipf.writestr('LEEME.txt', _SCANNER_README)
    except Exception as e:
        print(f"[scanner-firmado] error creando ZIP: {e}")
        return None, 'Error generando el paquete de descarga.'

    resp = send_file(zip_path, as_attachment=True, download_name='ArgusScanner.zip', mimetype='application/zip')
    _no_store(resp)

    def _cleanup():
        import time as _t
        _t.sleep(5)
        try:
            if os.path.exists(zip_path):
                os.remove(zip_path)
        except Exception:
            pass
    _threading.Thread(target=_cleanup, daemon=True).start()
    return resp, None


def _scanner_firmado_html_error(msg, code=403):
    if request.headers.get('X-Requested-With') == 'fetch' or 'application/json' in (request.headers.get('Accept') or ''):
        return jsonify({'error': msg}), code
    return Response(
        '<!doctype html><meta charset="utf-8">'
        '<body style="background:#0d1117;color:#e6edf3;font-family:Segoe UI,system-ui,sans-serif;'
        'display:flex;align-items:center;justify-content:center;height:100vh;margin:0;text-align:center">'
        f'<div style="max-width:480px;padding:24px"><h2 style="color:#f87171">No se pudo generar la descarga</h2>'
        f'<p style="color:#a1a1aa">{msg}</p>'
        '<a href="/panel" style="color:#E8A86F">Volver al panel</a></div></body>',
        status=code, mimetype='text/html'
    )


@app.route('/descargar/scanner-firmado')
@login_required
@_limit("40 per hour")
@audit_action('scanner.license.download', 'company')
def descargar_scanner_firmado():
    """Descarga ArgusScanner con una LICENCIA firmada embebida en config.json.

    Reemplaza el token manual de 6 chars: solo un staff logueado cuya empresa
    tenga suscripcion activa puede generar la licencia, que prueba "soy staff
    que paga" sin que nadie tenga que tipear un codigo. El staff abre este link
    (p. ej. via AnyDesk en el PC del jugador), descarga el ZIP y corre el .exe:
    se autentica solo."""
    user = get_user_by_id(session.get('user_id'))
    if not user:
        return _scanner_firmado_html_error('Sesión inválida. Iniciá sesión de nuevo.', 401)

    company_id = user.get('company_id')
    if not company_id:
        return _scanner_firmado_html_error('Tu cuenta no está asociada a una empresa. Usá una cuenta de empresa para generar la licencia del scanner.')
    if not _company_subscription_active(company_id):
        return _scanner_firmado_html_error('La suscripción de tu empresa está inactiva o vencida. Renová para usar el scanner.')

    license_str = _mint_scan_license(company_id, user.get('username'))
    resp, err = _send_scanner_zip_with_license(license_str)
    if err:
        return _scanner_firmado_html_error(err, 404 if 'no está disponible' in err else 500)
    return resp


def _ss_base_url():
    return os.environ.get('RENDER_EXTERNAL_URL', request.host_url).rstrip('/') if IS_RENDER else request.host_url.rstrip('/')


@app.route('/api/ss-license', methods=['POST'])
@login_required
@_limit("60 per hour")
@audit_action('scanner.license.mint', 'company')
def api_ss_license():
    """Mina una licencia firmada y devuelve un LINK publico de descarga listo
    para pegar (p. ej. en el navegador del PC del jugador via AnyDesk).

    El link NO requiere login: la licencia firmada que lleva en la URL es la
    prueba de que un staff que paga la genero. Caduca con la licencia."""
    user = get_user_by_id(session.get('user_id'))
    if not user:
        return jsonify({'success': False, 'error': 'Sesión inválida'}), 401
    company_id = user.get('company_id')
    if not company_id:
        return jsonify({'success': False, 'error': 'Tu cuenta no está asociada a una empresa.'}), 403
    if not _company_subscription_active(company_id):
        return jsonify({'success': False, 'error': 'Suscripción inactiva o vencida. Renová para usar el scanner.'}), 403

    license_str = _mint_scan_license(company_id, user.get('username'))
    download_url = f"{_ss_base_url()}/dl/ss/{license_str}"
    expires_at = (datetime.datetime.utcnow() + datetime.timedelta(seconds=_LICENSE_MAX_AGE)).isoformat() + 'Z'
    # Snippet PowerShell "SS instantaneo": descarga, extrae y ejecuta en un comando
    ps_oneliner = (
        "$d=\"$env:TEMP\\ArgusSS\";"
        f"iwr '{download_url}' -OutFile \"$d.zip\";"
        "Expand-Archive \"$d.zip\" $d -Force;"
        "Start-Process \"$d\\ArgusScanner.exe\" -Verb RunAs"
    )
    return jsonify({
        'success': True,
        'download_url': download_url,
        'license': license_str,
        'expires_in_hours': round(_LICENSE_MAX_AGE / 3600, 1),
        'expires_at': expires_at,
        'ps_oneliner': ps_oneliner,
        'company_id': company_id,
    })


@app.route('/api/ss-license/info', methods=['POST'])
@login_required
def api_ss_license_info():
    """Decodifica/valida una licencia (para el boton 'Probar mi licencia').
    No descarga nada: solo dice si esta verde y cuanto le queda."""
    data = request.json or {}
    blob = (data.get('license') or '').strip()
    if not blob:
        return jsonify({'success': False, 'error': 'Licencia no proporcionada'}), 400
    if not blob.startswith(_LICENSE_PREFIX):
        return jsonify({'success': False, 'valid': False, 'error': 'No parece una licencia Argus.'}), 200
    lic = _verify_scan_license(blob)
    if lic is None:
        return jsonify({'success': False, 'valid': False, 'error': 'Formato inválido.'}), 200
    if lic.get('error'):
        return jsonify({'success': True, 'valid': False, 'error': lic['error']}), 200
    # Tiempo restante: re-firmar para leer el timestamp es caro; estimamos por el max_age
    return jsonify({
        'success': True,
        'valid': True,
        'company_id': lic.get('company_id'),
        'created_by': lic.get('created_by'),
        'message': 'Licencia válida y suscripción activa.',
    })


@app.route('/dl/ss/<path:blob>')
@_limit("120 per hour")
def dl_ss_public(blob):
    """Descarga publica del scanner usando una licencia firmada en la URL.
    Pensado para pegar el link en el PC del jugador (AnyDesk): descarga el ZIP
    con la licencia ya embebida y el .exe se autentica solo."""
    lic = _verify_scan_license(blob)
    if lic is None:
        return _scanner_firmado_html_error('Link inválido.', 400)
    if lic.get('error'):
        # Mensaje fino segun expiracion vs suscripcion
        code = 410 if 'expirad' in lic['error'].lower() else 403
        return _scanner_firmado_html_error(lic['error'], code)
    resp, err = _send_scanner_zip_with_license(blob)
    if err:
        return _scanner_firmado_html_error(err, 404 if 'no está disponible' in err else 500)
    return resp


@app.route('/descargar/exe-lite')
def descargar_exe_lite():
    """Endpoint publico para descargar ArgusScannerLite.exe."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    possible_paths = [
        os.path.join(project_root, 'dist', 'ArgusScannerLite.exe'),
        os.path.join(project_root, 'downloads', 'ArgusScannerLite.exe'),
        os.path.join(project_root, 'source', 'dist', 'ArgusScannerLite.exe'),
        os.path.join(project_root, 'ArgusScannerLite.exe'),
    ]
    for path in possible_paths:
        if os.path.exists(path):
            return send_file(path, as_attachment=True, download_name='ArgusScannerLite.exe')
    return jsonify({'error': 'ArgusScannerLite.exe no disponible aún. Contacta a un administrador.'}), 404


@app.route('/descargar/linux')
def descargar_linux():
    """Plataforma Linux #13 â€” sirve el paquete `argus_linux/` como tar.gz.

    Empaqueta on-the-fly el directorio source/argus_linux/ con scanner.py,
    run-argus.sh, README, etc. El tester solo tiene que extraer y correr:
        tar -xzf argus-linux.tar.gz
        chmod +x argus_linux/run-argus.sh
        ./argus_linux/run-argus.sh TOKEN
    """
    import io
    import tarfile

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src_dir = os.path.join(project_root, 'source', 'argus_linux')
    if not os.path.isdir(src_dir):
        return jsonify({'error': 'Paquete Linux no disponible aÃºn en el servidor.'}), 404

    # Construir tar.gz en memoria â€” el directorio es pequeÃ±o (<50KB), no
    # vale la pena cachear en disco. Si crece a >1MB conviene refactor.
    buf = io.BytesIO()
    excluded_names = {'__pycache__', '.pytest_cache', '.mypy_cache'}
    excluded_suffixes = ('.pyc', '.pyo')
    try:
        with tarfile.open(fileobj=buf, mode='w:gz', compresslevel=6) as tar:
            for dirpath, dirnames, filenames in os.walk(src_dir):
                dirnames[:] = [d for d in dirnames if d not in excluded_names]
                for fn in filenames:
                    if fn.endswith(excluded_suffixes):
                        continue
                    full = os.path.join(dirpath, fn)
                    arc = os.path.join('argus_linux',
                                        os.path.relpath(full, src_dir)).replace(os.sep, '/')
                    # Marcar el .sh como ejecutable dentro del tar
                    info = tar.gettarinfo(full, arcname=arc)
                    if fn.endswith('.sh') or fn == 'scanner.py':
                        info.mode = 0o755
                    with open(full, 'rb') as f:
                        tar.addfile(info, f)
    except Exception as e:
        return jsonify({'error': f'Error empaquetando: {e}'}), 500

    buf.seek(0)
    return send_file(
        buf,
        mimetype='application/gzip',
        as_attachment=True,
        download_name='argus-linux.tar.gz',
    )


# â”€â”€ Plataforma Android #13 â€” endpoint de descarga â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Tag rolling del release de GitHub que el workflow .github/workflows/
# android-build.yml mantiene actualizado en cada push a main. La URL del
# asset es estable y pÃºblica (no requiere token), por lo que podemos
# redirigir aquÃ­ sin gastar bandwidth de Render.
ANDROID_RELEASE_TAG = 'android-latest'
ANDROID_RELEASE_ASSET = 'argus-android.apk'
ANDROID_RELEASE_URL = (
    f'https://github.com/SkzfXrolo/AsperSS/releases/download/'
    f'{ANDROID_RELEASE_TAG}/{ANDROID_RELEASE_ASSET}'
)
ANDROID_RELEASE_API = (
    'https://api.github.com/repos/SkzfXrolo/AsperSS/releases/tags/'
    f'{ANDROID_RELEASE_TAG}'
)

# Cache simple en proceso para no martillar la API de GitHub (60 req/h
# sin auth). TTL 5min â€” coincide con el ritmo realista de re-deploys.
_android_version_cache: dict = {'data': None, 'fetched_at': 0.0}
_ANDROID_VERSION_TTL_S = 300


def _android_version_payload() -> dict:
    """Item Android #15 â€” meta del Ãºltimo APK publicado.

    Devuelve {latest_commit, short_commit, apk_url, published_at,
    release_name, size_bytes, release_notes}. Si la API de GitHub falla,
    cae a un payload mÃ­nimo con apk_url estable.
    """
    now = _time_mod.time()
    cached = _android_version_cache.get('data')
    if cached and now - _android_version_cache['fetched_at'] < _ANDROID_VERSION_TTL_S:
        return cached

    fallback = {
        'latest_commit': None,
        'short_commit': None,
        'apk_url': ANDROID_RELEASE_URL,
        'published_at': None,
        'release_name': None,
        'size_bytes': None,
        'release_notes': None,
        'tag': ANDROID_RELEASE_TAG,
        'source': 'fallback',
    }
    try:
        resp = requests.get(ANDROID_RELEASE_API, timeout=4)
        if resp.status_code != 200:
            _android_version_cache['data'] = fallback
            _android_version_cache['fetched_at'] = now
            return fallback
        data = resp.json() or {}
        commit = (data.get('target_commitish') or '').strip() or None
        apk_asset = None
        for asset in data.get('assets') or []:
            if (asset.get('name') or '').lower() == ANDROID_RELEASE_ASSET:
                apk_asset = asset
                break
        payload = {
            'latest_commit': commit,
            'short_commit': commit[:7] if commit else None,
            'apk_url': (apk_asset or {}).get('browser_download_url') or ANDROID_RELEASE_URL,
            'published_at': data.get('published_at'),
            'release_name': data.get('name'),
            'size_bytes': (apk_asset or {}).get('size'),
            'release_notes': (data.get('body') or '').strip()[:1500] or None,
            'tag': ANDROID_RELEASE_TAG,
            'source': 'github',
        }
        _android_version_cache['data'] = payload
        _android_version_cache['fetched_at'] = now
        return payload
    except Exception:
        _android_version_cache['data'] = fallback
        _android_version_cache['fetched_at'] = now
        return fallback


@app.route('/api/android-version')
def api_android_version():
    """Item Android #15 â€” endpoint que la app Argus consulta al iniciar
    para detectar versiÃ³n nueva.

    Cliente tÃ­pico: la app envÃ­a su BuildConfig.ARGUS_BUILD_COMMIT como
    ?current=abc1234. Si no coincide con `short_commit` y la release
    es mÃ¡s reciente, la app muestra "Hay versiÃ³n nueva" + botÃ³n
    Actualizar (que abre apk_url en el navegador para que el usuario
    descargue e instale el APK firmado).

    Sin parÃ¡metro `current`, devuelve solo la meta del Ãºltimo build.
    """
    payload = _android_version_payload()
    current = (request.args.get('current') or '').strip().lower()
    update_available = False
    if current and payload.get('short_commit'):
        update_available = (current != payload['short_commit'].lower())
    out = dict(payload)
    out['update_available'] = update_available
    out['current'] = current or None
    return jsonify(out)


@app.route('/descargar/android')
def descargar_android():
    """Plataforma Android #13 â€” sirve el APK Argus Android.

    Estrategia de servidos en cascada:
      1) Si el operador del servidor copiÃ³ manualmente un APK firmado a
         `web_app/static/dist/argus-android.apk`, lo servimos directo
         (use case: dev local, on-prem, o release firmado con keystore).
      2) Si no, redirigimos 302 al asset estable de GitHub Releases
         (rolling tag `android-latest`) que el workflow CI mantiene al
         dÃ­a con cada push a `main`. Esto cubre el caso por defecto de
         Render: GH Actions buildea â†’ publica release â†’ este endpoint
         redirige sin necesidad de redeploy.

    El parÃ¡metro `?direct=1` permite forzar la URL absoluta del release
    (Ãºtil para QR / chat apps que no toleran redirects).
    """
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    apk_path = os.path.join(project_root, 'web_app', 'static', 'dist',
                            'argus-android.apk')

    if os.path.isfile(apk_path):
        return send_file(
            apk_path,
            mimetype='application/vnd.android.package-archive',
            as_attachment=True,
            download_name='argus-android.apk',
        )

    # Fallback: redirect al release pÃºblico de GitHub. 302 (Found) con
    # ?direct=1 da la URL "as-is" para clientes que no siguen redirects.
    if request.args.get('direct') == '1':
        return jsonify({'url': ANDROID_RELEASE_URL}), 200
    return redirect(ANDROID_RELEASE_URL, code=302)


# â”€â”€ Plugin Minecraft (/ss) â€” endpoint de descarga â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Mismo patrÃ³n que Android: el workflow .github/workflows/build-plugin.yml
# compila el .jar en cada push y lo publica como release "plugin-latest".
# Esta URL es estable y pÃºblica (no requiere token), redirigimos sin
# gastar bandwidth de Render.
PLUGIN_RELEASE_TAG = 'plugin-latest'
PLUGIN_RELEASE_ASSET = 'argus-mc-1.0.0.jar'
PLUGIN_RELEASE_URL = (
    f'https://github.com/SkzfXrolo/AsperSS/releases/download/'
    f'{PLUGIN_RELEASE_TAG}/{PLUGIN_RELEASE_ASSET}'
)
PLUGIN_RELEASE_API = (
    'https://api.github.com/repos/SkzfXrolo/AsperSS/releases/tags/'
    f'{PLUGIN_RELEASE_TAG}'
)

_plugin_version_cache: dict = {'data': None, 'fetched_at': 0.0}
_PLUGIN_VERSION_TTL_S = 300


def _plugin_version_payload() -> dict:
    """Meta del Ãºltimo .jar publicado en el release plugin-latest."""
    now = _time_mod.time()
    cached = _plugin_version_cache.get('data')
    if cached and now - _plugin_version_cache['fetched_at'] < _PLUGIN_VERSION_TTL_S:
        return cached

    fallback = {
        'latest_commit': None,
        'short_commit':  None,
        'jar_url':       PLUGIN_RELEASE_URL,
        'published_at':  None,
        'release_name':  None,
        'size_bytes':    None,
        'release_notes': None,
        'tag':           PLUGIN_RELEASE_TAG,
        'source':        'fallback',
    }
    try:
        resp = requests.get(PLUGIN_RELEASE_API, timeout=4)
        if resp.status_code != 200:
            _plugin_version_cache['data'] = fallback
            _plugin_version_cache['fetched_at'] = now
            return fallback
        data = resp.json() or {}
        commit = (data.get('target_commitish') or '').strip() or None
        jar_asset = None
        for asset in data.get('assets') or []:
            name = (asset.get('name') or '').lower()
            if name.endswith('.jar') and 'argus' in name:
                jar_asset = asset
                break
        payload = {
            'latest_commit': commit,
            'short_commit':  commit[:7] if commit else None,
            'jar_url':       (jar_asset or {}).get('browser_download_url') or PLUGIN_RELEASE_URL,
            'published_at':  data.get('published_at'),
            'release_name':  data.get('name'),
            'size_bytes':    (jar_asset or {}).get('size'),
            'release_notes': (data.get('body') or '').strip()[:1500] or None,
            'tag':           PLUGIN_RELEASE_TAG,
            'source':        'github',
        }
        _plugin_version_cache['data'] = payload
        _plugin_version_cache['fetched_at'] = now
        return payload
    except Exception:
        _plugin_version_cache['data'] = fallback
        _plugin_version_cache['fetched_at'] = now
        return fallback


@app.route('/api/plugin-version')
def api_plugin_version():
    """Endpoint pÃºblico con la meta del Ãºltimo .jar (commit, tamaÃ±o, URL).
    Ãštil para mostrar 'Ãšltima versiÃ³n: 1.0.0 (#abc1234, 12 KB)' en la UI.
    """
    return jsonify(_plugin_version_payload())


@app.route('/descargar/plugin')
def descargar_plugin():
    """Sirve el plugin Bukkit/Paper Argus MC.

    Estrategia en cascada:
      1) Si hay un .jar buildado a mano en `web_app/static/dist/argus-mc.jar`,
         lo servimos directo (Ãºtil para dev local / on-prem).
      2) Si no, redirigimos al asset estable del release de GitHub que el
         workflow CI mantiene al dÃ­a con cada push a `main` que toque
         `minecraft_plugin/`.

    `?direct=1` devuelve la URL absoluta como JSON (Ãºtil para clientes que
    no toleran redirects, p. ej. paneles de Aternos via webhook).
    """
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    jar_path = os.path.join(project_root, 'web_app', 'static', 'dist',
                            'argus-mc.jar')

    if os.path.isfile(jar_path):
        return send_file(
            jar_path,
            mimetype='application/java-archive',
            as_attachment=True,
            download_name=PLUGIN_RELEASE_ASSET,
        )

    if request.args.get('direct') == '1':
        return jsonify({'url': PLUGIN_RELEASE_URL}), 200
    return redirect(PLUGIN_RELEASE_URL, code=302)


@app.route('/descargar/android-source')
def descargar_android_source():
    """Plataforma Android #13 â€” empaqueta el proyecto Android como tar.gz.

    Ãštil para que devs / CI / contributors lo compilen localmente. Excluye
    build/, .gradle/, *.iml, .DS_Store.
    """
    import io
    import tarfile

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src_dir = os.path.join(project_root, 'mobile', 'argus_android')
    if not os.path.isdir(src_dir):
        return jsonify({'error': 'Proyecto Android no disponible.'}), 404

    buf = io.BytesIO()
    excluded_dirs = {'.gradle', 'build', '.idea', '__pycache__', 'captures'}
    excluded_suffixes = ('.iml', '.apk', '.aab', '.jks', '.keystore', '.pyc')
    try:
        with tarfile.open(fileobj=buf, mode='w:gz', compresslevel=6) as tar:
            for dirpath, dirnames, filenames in os.walk(src_dir):
                dirnames[:] = [d for d in dirnames if d not in excluded_dirs]
                for fn in filenames:
                    if fn.endswith(excluded_suffixes):
                        continue
                    full = os.path.join(dirpath, fn)
                    arc = os.path.join('argus_android',
                                        os.path.relpath(full, src_dir)).replace(os.sep, '/')
                    info = tar.gettarinfo(full, arcname=arc)
                    if fn.endswith('.sh') or fn == 'gradlew':
                        info.mode = 0o755
                    with open(full, 'rb') as f:
                        tar.addfile(info, f)
    except Exception as e:
        return jsonify({'error': f'Error empaquetando: {e}'}), 500

    buf.seek(0)
    return send_file(
        buf,
        mimetype='application/gzip',
        as_attachment=True,
        download_name='argus-android-source.tar.gz',
    )


@app.route('/api/scans/<int:scan_id>/report-html', methods=['GET'])
@login_required
def get_scan_report_html(scan_id):
    """Genera un reporte HTML descargable para un escaneo especÃ­fico - OPTIMIZADO: Acceso directo a BD"""
    from datetime import datetime
    
    try:
        # Acceso directo a BD (SIN HTTP - MUCHO MÃS RÃPIDO)
        with get_api_db_cursor() as cursor:
            # Obtener informaciÃ³n del escaneo
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
            <h1>ðŸ” ASPERS Projects - Reporte de Escaneo</h1>
            <p>Generado el {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</p>
        </div>
        
        <div class="summary">
            <div class="summary-card">
                <h3>Escaneo ID</h3>
                <div class="value">#{scan['id']}</div>
            </div>
            <div class="summary-card">
                <h3>MÃ¡quina</h3>
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
                <h3>DuraciÃ³n</h3>
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
                    {f'<span class="badge badge-success">âœ“ Verificado: {result["feedback"]}</span>' if result.get('feedback') else ''}
                </div>
            </div>
            <div class="issue-details">
                {f'<div><strong>Tipo:</strong> {result["issue_type"]}</div>' if result.get('issue_type') else ''}
                {f'<div><strong>CategorÃ­a:</strong> {result["issue_category"]}</div>' if result.get('issue_category') else ''}
                {f'<div><strong>AnÃ¡lisis IA:</strong> {result["ai_analysis"]}</div>' if result.get('ai_analysis') else ''}
                {f'<div><strong>Confianza IA:</strong> {result["ai_confidence"]}%</div>' if result.get('ai_confidence') else ''}
                {f'<div><strong>Patrones detectados:</strong> {", ".join(result["detected_patterns"])}</div>' if result.get('detected_patterns') and len(result['detected_patterns']) > 0 else ''}
                {f'<div><strong>Hash:</strong> <code>{result["file_hash"]}</code></div>' if result.get('file_hash') else ''}
                {f'<div><strong>OfuscaciÃ³n detectada:</strong> {"SÃ­" if result["obfuscation_detected"] else "No"}</div>'}
            </div>
'''
            
            if result.get('feedback'):
                html += f'''
            <div class="feedback-section">
                <h4>Feedback del Staff</h4>
                <div><strong>VerificaciÃ³n:</strong> {result['feedback']}</div>
                {f'<div><strong>Notas:</strong> {result["feedback_notes"]}</div>' if result.get('feedback_notes') else ''}
                {f'<div><strong>Fecha:</strong> {result["feedback_date"]}</div>' if result.get('feedback_date') else ''}
            </div>
'''
            
            html += '</div>'
        
        html += f'''
        <div class="footer">
            <p>Reporte generado por ASPERS Projects - Sistema de DetecciÃ³n Avanzada</p>
            <p>Este reporte puede ser compartido con el staff superior para revisiÃ³n de archivos sospechosos.</p>
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
    """Obtiene el ejecutable mÃ¡s reciente disponible (ya compilado)"""
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

    # TambiÃ©n buscar en la raÃ­z del proyecto
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
        error_msg = 'No se encontrÃ³ ejecutable compilado.'
        if IS_RENDER:
            error_msg += '\n\nEl archivo .exe debe estar en GitHub en una de estas ubicaciones:\n'
            error_msg += 'â€¢ source/dist/MinecraftSSTool.exe\n'
            error_msg += 'â€¢ downloads/MinecraftSSTool.exe\n\n'
            error_msg += 'Pasos para solucionarlo:\n'
            error_msg += '1. Compila el .exe localmente\n'
            error_msg += '2. Ejecuta SUBIR_EXE_A_GITHUB.bat\n'
            error_msg += '3. Sube los cambios a GitHub\n'
            error_msg += '4. Render se actualizarÃ¡ automÃ¡ticamente'
        else:
            error_msg += ' AsegÃºrate de que el archivo .exe estÃ© en la carpeta downloads/, source/dist/, o en la raÃ­z del proyecto.'
        
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

    print(f"ðŸ”— Solicitud de creaciÃ³n de enlace de descarga recibida")
    print(f"ðŸ“‹ Datos recibidos: {request.json}")

    # Verificar permisos (solo admin)
    user_id = session.get('user_id')
    current_user = get_user_by_id(user_id)
    if not is_admin(current_user):
        print(f"âŒ Usuario {user_id} no tiene permisos de admin")
        return jsonify({'error': 'No tienes permisos para crear enlaces de descarga'}), 403

    data = request.json or {}
    filename      = data.get('filename', 'MinecraftSSTool.exe')
    expires_hours = data.get('expires_hours', 24)
    max_downloads = data.get('max_downloads', 1)
    description   = data.get('description', '')

    print(f"ðŸ“ Archivo: {filename}, â° {expires_hours}h, ðŸ“Š max={max_downloads}")

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

        print(f"âœ… Enlace guardado en BD con ID: {link_id}")
        
        # Generar URL completa
        base_url = request.host_url.rstrip('/')
        if IS_RENDER:
            render_url = os.environ.get('RENDER_EXTERNAL_URL', '')
            if render_url:
                base_url = render_url.rstrip('/')
        download_url = f"{base_url}/d/{token}"
        
        print(f"ðŸŒ URL generada: {download_url}")
        
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
        print(f"âŒ Error creando enlace de descarga: {e}")
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
        print(f"âŒ Error listando enlaces: {e}")
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
    """Importa resultados histÃ³ricos de Echo Scanner"""
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
        w.writerow(['# MÃ¡quina', g(1,'machine_name')])
        w.writerow(['# Minecraft Username', g(2,'minecraft_username') or 'No detectado'])
        w.writerow(['# Fecha inicio', g(3,'started_at')])
        w.writerow(['# Fecha fin', g(4,'completed_at')])
        w.writerow(['# Archivos escaneados', g(6,'total_files_scanned')])
        w.writerow(['# Issues totales', g(7,'issues_found')])
        w.writerow(['# Veredicto', g(11,'verdict') or 'pendiente'])
        w.writerow(['# RazÃ³n veredicto', g(12,'verdict_reason') or ''])
        w.writerow([])

        # Column headers
        w.writerow(['Tipo', 'Nombre', 'Ruta', 'CategorÃ­a', 'Nivel de alerta',
                    'Confianza %', 'OfuscaciÃ³n detectada', 'Hash SHA256',
                    'AnÃ¡lisis IA', 'Confianza IA %'])

        for r in results:
            w.writerow([
                _row_get(r, 0, 'issue_type'),
                _row_get(r, 1, 'issue_name'),
                _row_get(r, 2, 'issue_path'),
                _row_get(r, 3, 'issue_category'),
                _row_get(r, 4, 'alert_level'),
                _row_get(r, 5, 'confidence'),
                'SÃ­' if _row_get(r, 6, 'obfuscation_detected') else 'No',
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

        # â”€â”€ Build PDF â”€â”€
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
        pdf.cell(0, 8, f'Reporte de Escaneo â€” {machine}', ln=True)
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
    if _sa_imperial_flags().get('panel_readonly') and not session.get('impersonated_by_sa'):
        return jsonify({'error': 'Panel en modo solo lectura (God Mode activo).'}), 503
    current_user = get_user_by_id(session.get('user_id'))
    if not can_change_verdict(current_user):
        return jsonify({'error': 'No tienes permisos para cambiar veredictos (se requiere Moderador o superior)'}), 403
    data   = request.json or {}
    verdict = (data.get('verdict') or '').strip().lower()
    reason  = (data.get('reason') or '').strip()
    if verdict not in ('clean', 'hack', 'pending'):
        return jsonify({'error': 'Veredicto invÃ¡lido. Usar: clean, hack, pending'}), 400
    if not reason:
        return jsonify({'error': 'La razÃ³n del veredicto es obligatoria'}), 400
    user = session.get('username', 'staff')
    user_id = session.get('user_id')
    try:
        with get_api_db_cursor() as cursor:
            # Pack 32 â€” Capturar ensemble verdict, prior verdict y company
            # ANTES de overwriteear, para alimentar staff_trust + cooldown.
            prior_verdict = None
            ensemble_verdict_str = None
            scan_company_id = None
            try:
                cursor.execute(
                    f'SELECT verdict, ensemble_data, company_id '
                    f'FROM scans WHERE id={_PH}',
                    (scan_id,)
                )
                _vrow = cursor.fetchone()
                if _vrow:
                    prior_verdict = _row_get(_vrow, 0, 'verdict')
                    _ed = _row_get(_vrow, 1, 'ensemble_data')
                    if _ed:
                        try:
                            _edd = json.loads(_ed) if isinstance(_ed, str) else _ed
                            ensemble_verdict_str = (_edd or {}).get('verdict')
                        except Exception:
                            pass
                    scan_company_id = _row_get(_vrow, 2, 'company_id')
            except Exception:
                pass

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

            # Pack 32 F#54 â€” Actualizar staff_trust comparando humano vs
            # ensemble. Idempotente, dentro de SAVEPOINT por si la tabla
            # estÃ¡ corrupta no rompe el verdict.
            if _AI_TRUST_AVAILABLE and user_id and ensemble_verdict_str:
                try:
                    cursor.execute('SAVEPOINT staff_trust_save')
                    _ai_trust.update_staff_trust_on_verdict(
                        cursor,
                        user_id=user_id,
                        human_verdict=verdict,
                        ensemble_verdict=ensemble_verdict_str,
                        prior_human_verdict=(prior_verdict or None),
                    )
                    cursor.execute('RELEASE SAVEPOINT staff_trust_save')
                except Exception:
                    try:
                        cursor.execute('ROLLBACK TO SAVEPOINT staff_trust_save')
                    except Exception:
                        pass

            # Pack 36 â€” Auto-learn de patterns desde verdict='hack' por
            # staff con alto trust. Solo si tenemos ai_autolearn + el
            # staff llegÃ³ a >=65 trust en F#54.
            if (_AI_AUTOLEARN_AVAILABLE and verdict == 'hack' and
                user_id and _AI_TRUST_AVAILABLE):
                try:
                    cursor.execute('SAVEPOINT autolearn_save')
                    trust_data = _ai_trust.get_staff_trust(cursor, user_id)
                    trust_score = float(trust_data.get('trust_score') or 50.0)
                    learn_stats = _ai_autolearn.auto_learn_from_hack_verdict(
                        cursor,
                        scan_id=scan_id,
                        staff_user_id=user_id,
                        staff_trust_score=trust_score,
                        results=None,  # autolearn los lee del scan
                    )
                    if learn_stats.get('learned', 0) > 0:
                        try:
                            _log_staff_action(
                                'ai_autolearn',
                                detail=f'scan_id={scan_id} learned={learn_stats["learned"]}/{learn_stats["scanned"]}'
                            )
                        except Exception:
                            pass
                    cursor.execute('RELEASE SAVEPOINT autolearn_save')
                except Exception as _e_al:
                    try:
                        cursor.execute('ROLLBACK TO SAVEPOINT autolearn_save')
                    except Exception:
                        pass
                    print(f'[set_verdict.autolearn] {_e_al}')

            # Pack 32 F#60 â€” Si el verdict actual es 'clean' y el prior
            # era 'hack' (o el ensemble decÃ­a hack), incrementar
            # overturn cooldown de la empresa.
            if _AI_TRUST_AVAILABLE and scan_company_id:
                is_overturn_to_clean = (
                    verdict == 'clean' and (
                        (prior_verdict and prior_verdict.lower() == 'hack') or
                        (ensemble_verdict_str and ensemble_verdict_str.upper() in
                         ('HACK_CONFIRMADO', 'MUY_SOSPECHOSO'))
                    )
                )
                if is_overturn_to_clean:
                    try:
                        cursor.execute('SAVEPOINT cooldown_save')
                        _ai_trust.increment_cooldown(
                            cursor, scan_company_id, kind='overturn'
                        )
                        cursor.execute('RELEASE SAVEPOINT cooldown_save')
                    except Exception:
                        try:
                            cursor.execute('ROLLBACK TO SAVEPOINT cooldown_save')
                        except Exception:
                            pass

            cursor.execute(
                f'SELECT machine_name, minecraft_username FROM scans WHERE id={_PH}',
                (scan_id,)
            )
            srow = cursor.fetchone()
        machine  = (_row_get(srow, 0, 'machine_name')       or 'N/A') if srow else 'N/A'
        username = (_row_get(srow, 1, 'minecraft_username')  or 'N/A') if srow else 'N/A'
        # Invalidar cachÃ© de estadÃ­sticas
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
        return jsonify({'error': 'El cuerpo de la nota no puede estar vacÃ­o'}), 400
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
    """Returns all known hack hashes â€” used by the scanner at startup."""
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
        return jsonify({'error': 'SHA256 invÃ¡lido (debe ser 64 hex chars)'}), 400
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


# â”€â”€ P3 #4 â€” Clustering de perfiles de scan â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@app.route('/api/ml/cluster', methods=['POST'])
@login_required
def ml_cluster():
    """K-Means clustering sobre los Ãºltimos N scans completados.
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
            return jsonify({'error': f'Insuficientes scans: {len(rows)} (mÃ­n {n_clusters*2})'}), 200

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
            'alert_message': (f'âš  {len(high_risk_clusters)} cluster(s) de alto riesgo detectados con risk_score promedio â‰¥ 60'
                             if high_risk_clusters else None),
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# â”€â”€ P3 #1 â€” Clasificador Random Forest â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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
    """Estado del clasificador ML: si estÃ¡ disponible y con cuÃ¡ntas muestras."""
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


@app.route('/api/ml/drift', methods=['GET'])
@login_required
def ml_drift_check():
    """P3 #9 â€” DetecciÃ³n de concept drift: compara concordancia del modelo con veredictos recientes.
    Si concordancia <70% en los Ãºltimos 30 scans con veredicto â†’ alerta de reentrenamiento.
    """
    try:
        from ml_classifier import get_classifier
        clf = get_classifier()
        if not clf.is_available:
            return jsonify({'drift': False, 'reason': 'Modelo no disponible', 'concordance': None}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    try:
        with get_api_db_cursor() as cur:
            cur.execute(f"""
                SELECT sr.alert_level, sr.issue_category, sr.confidence,
                       sr.obfuscation_detected, s.verdict
                FROM scan_results sr
                JOIN scans s ON sr.scan_id = s.id
                WHERE s.verdict IN ('hack','clean')
                ORDER BY s.id DESC LIMIT 500
            """)
            rows = cur.fetchall() or []
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    if len(rows) < 30:
        return jsonify({'drift': False, 'reason': 'Insuficientes datos recientes (<30)', 'concordance': None}), 200

    correct = 0
    total   = 0
    for r in rows[:300]:
        verdict  = str(r[4] if not hasattr(r, 'keys') else r.get('verdict', ''))
        features = {'alert_level': r[0] if not hasattr(r,'keys') else r.get('alert_level'),
                    'issue_category': r[1] if not hasattr(r,'keys') else r.get('issue_category'),
                    'confidence': r[2] if not hasattr(r,'keys') else r.get('confidence'),
                    'obfuscation_detected': r[3] if not hasattr(r,'keys') else r.get('obfuscation_detected')}
        pred = clf.predict(features)
        if pred.get('label') == verdict:
            correct += 1
        total += 1

    concordance = round(correct / total, 4) if total else 0
    drift = concordance < 0.70

    return jsonify({
        'drift':         drift,
        'concordance':   concordance,
        'samples_used':  total,
        'reason': ('Concordancia del modelo con veredictos recientes por debajo del 70% â€” reentrenamiento recomendado'
                   if drift else 'Concordancia aceptable'),
        'retrain_recommended': drift,
    }), 200


@app.route('/api/ml/anomaly/<int:scan_id>', methods=['GET'])
@login_required
def ml_anomaly_detect(scan_id):
    """P3 #3 â€” Isolation Forest para detectar si un scan es anÃ³malo respecto al baseline.
    Compara los hallazgos del scan actual contra el perfil histÃ³rico de scans limpios.
    Devuelve: {anomaly_score: float, is_anomaly: bool, reason: str}
    """
    try:
        from sklearn.ensemble import IsolationForest
        from sklearn.preprocessing import StandardScaler
        import numpy as np
    except ImportError:
        return jsonify({'error': 'scikit-learn no instalado'}), 500

    try:
        with get_api_db_cursor() as cur:
            # Perfil del scan actual
            cur.execute(
                f'SELECT issues_found, risk_score, scan_duration, total_files_scanned '
                f'FROM scans WHERE id={_PH}', (scan_id,)
            )
            row = cur.fetchone()
            if not row:
                return jsonify({'error': 'Scan no encontrado'}), 404
            current = [
                int(_row_get(row, 0, 'issues_found') or 0),
                int(_row_get(row, 1, 'risk_score') or 0),
                float(_row_get(row, 2, 'scan_duration') or 0),
                int(_row_get(row, 3, 'total_files_scanned') or 0),
            ]
            # Baseline: Ãºltimos 200 scans con veredicto limpio
            cur.execute(
                f"SELECT issues_found, risk_score, scan_duration, total_files_scanned "
                f"FROM scans WHERE verdict='clean' ORDER BY id DESC LIMIT 200"
            )
            baseline_rows = cur.fetchall() or []
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    if len(baseline_rows) < 20:
        return jsonify({'anomaly_score': 0.0, 'is_anomaly': False,
                        'reason': 'Insuficientes scans limpios para baseline (mÃ­n 20)'}), 200

    baseline = [
        [int(_row_get(r, 0, 'issues_found') or 0),
         int(_row_get(r, 1, 'risk_score') or 0),
         float(_row_get(r, 2, 'scan_duration') or 0),
         int(_row_get(r, 3, 'total_files_scanned') or 0)]
        for r in baseline_rows
    ]
    X_base = np.array(baseline, dtype=float)
    X_curr = np.array([current], dtype=float)

    scaler = StandardScaler().fit(X_base)
    X_base_s = scaler.transform(X_base)
    X_curr_s = scaler.transform(X_curr)

    iso = IsolationForest(contamination=0.1, random_state=42)
    iso.fit(X_base_s)
    score     = float(iso.decision_function(X_curr_s)[0])  # negative = more anomalous
    is_anomaly = bool(iso.predict(X_curr_s)[0] == -1)

    reason = ''
    if is_anomaly:
        if current[0] > float(np.percentile(X_base[:, 0], 90)):
            reason += f'Hallazgos ({current[0]}) por encima del percentil 90 del baseline. '
        if current[1] > float(np.percentile(X_base[:, 1], 90)):
            reason += f'Risk score ({current[1]}) anormalmente alto. '
        if current[3] < float(np.percentile(X_base[:, 3], 10)) and current[3] > 0:
            reason += f'Muy pocos archivos escaneados ({current[3]}), posible evasiÃ³n. '
        if not reason:
            reason = 'Perfil del scan estadÃ­sticamente inusual.'

    return jsonify({
        'anomaly_score': round(-score, 4),  # positive = more anomalous
        'is_anomaly':    is_anomaly,
        'reason':        reason.strip(),
        'baseline_size': len(baseline_rows),
    }), 200


@app.route('/api/predict', methods=['POST'])
def api_predict():
    """P3 #35 â€” PredicciÃ³n de riesgo pre-scan.
    El scanner envÃ­a features bÃ¡sicas del sistema antes de escanear.
    Devuelve risk_level y si el staff quiere scan completo o rÃ¡pido.
    Body: { token, machine_id, prev_verdicts (list), mc_versions (int),
            suspicious_dirs (list of found dirs), os_version }
    """
    data       = request.json or {}
    token      = (data.get('token') or '').strip()
    machine_id = (data.get('machine_id') or '').strip()
    if not token:
        return jsonify({'error': 'token requerido'}), 400

    try:
        with get_api_db_cursor() as cur:
            cur.execute(f'SELECT id FROM scan_tokens WHERE token={_PH} AND (expires_at IS NULL OR expires_at > NOW())', (token,))
            if not cur.fetchone():
                return jsonify({'error': 'token invÃ¡lido o expirado'}), 403

            # Historial de veredictos previos del mismo machine_id
            prev_hack  = 0
            prev_total = 0
            if machine_id:
                cur.execute(
                    f"SELECT COUNT(*) FROM scans WHERE machine_id={_PH} AND verdict='hack'",
                    (machine_id,)
                )
                row = cur.fetchone()
                prev_hack = int((row[0] if isinstance(row, (list, tuple)) else row.get('count', 0)) or 0)
                cur.execute(f"SELECT COUNT(*) FROM scans WHERE machine_id={_PH}", (machine_id,))
                row = cur.fetchone()
                prev_total = int((row[0] if isinstance(row, (list, tuple)) else row.get('count', 0)) or 0)

        # Calcular risk_level pre-scan basado en seÃ±ales simples
        risk = 0
        reasons = []

        if prev_hack > 0:
            risk += min(60, prev_hack * 20)
            reasons.append(f'{prev_hack} veredicto(s) previo(s) como hack')

        mc_versions = int(data.get('mc_versions') or 0)
        if mc_versions >= 7:
            risk += 25; reasons.append(f'{mc_versions} versiones MC instaladas')
        elif mc_versions >= 4:
            risk += 10; reasons.append(f'{mc_versions} versiones MC instaladas')

        suspicious_dirs = data.get('suspicious_dirs') or []
        if isinstance(suspicious_dirs, list) and suspicious_dirs:
            risk += min(40, len(suspicious_dirs) * 15)
            reasons.append(f'Directorios sospechosos: {", ".join(str(d) for d in suspicious_dirs[:3])}')

        risk = min(100, risk)
        risk_level = 'ALTO' if risk >= 70 else 'MEDIO' if risk >= 30 else 'BAJO'

        return jsonify({
            'risk_level':  risk_level,
            'risk_score':  risk,
            'reasons':     reasons,
            'recommend_full_scan': risk >= 30,
            'prev_hacks':  prev_hack,
            'prev_scans':  prev_total,
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# â”€â”€ P2 #1 â€” Whitelist dinÃ¡mica de mods legÃ­timos â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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
        return jsonify({'error': 'SHA256 invÃ¡lido'}), 400
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


# â”€â”€ P3 #17 â€” Dynamic hash blacklist (auto-propagated from verdict history) â”€â”€â”€â”€

@app.route('/api/hack_blacklist', methods=['GET'])
def get_hack_blacklist():
    """Returns SHA256 hashes confirmed as hacks across all servers.
    Auto-populated by /api/hack_blacklist/sync â€” scanner fetches on startup.
    """
    try:
        with get_api_db_cursor() as cursor:
            cursor.execute('SELECT sha256, hack_name, first_seen, times_confirmed FROM hack_blacklist ORDER BY times_confirmed DESC LIMIT 5000')
            rows = cursor.fetchall() or []
        return jsonify({
            'hashes': [
                {
                    'sha256':           _row_get(r, 0, 'sha256'),
                    'hack_name':        _row_get(r, 1, 'hack_name'),
                    'first_seen':       str(_row_get(r, 2, 'first_seen') or ''),
                    'times_confirmed':  int(_row_get(r, 3, 'times_confirmed') or 1),
                }
                for r in rows
            ]
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/hack_blacklist/sync', methods=['POST'])
@login_required
def sync_hack_blacklist():
    """Scans scan_results for file_hash values in scans with verdict='hack',
    and adds them to hack_blacklist if seen in 3+ hack scans.
    Run after bulk verdict processing or on a schedule.
    """
    try:
        with get_api_db_cursor() as cursor:
            if _USE_PG:
                cursor.execute('''
                    SELECT sr.file_hash, sr.issue_name,
                           COUNT(DISTINCT s.id) AS times_confirmed
                    FROM scan_results sr
                    JOIN scans s ON sr.scan_id = s.id
                    WHERE s.verdict = 'hack'
                      AND sr.file_hash IS NOT NULL AND sr.file_hash != ''
                      AND LENGTH(sr.file_hash) IN (64, 40)
                    GROUP BY sr.file_hash, sr.issue_name
                    HAVING COUNT(DISTINCT s.id) >= 3
                ''')
            else:
                cursor.execute('''
                    SELECT sr.file_hash, sr.issue_name,
                           COUNT(DISTINCT s.id) AS times_confirmed
                    FROM scan_results sr JOIN scans s ON sr.scan_id = s.id
                    WHERE s.verdict = 'hack'
                      AND sr.file_hash IS NOT NULL AND sr.file_hash != ''
                      AND (LENGTH(sr.file_hash) = 64 OR LENGTH(sr.file_hash) = 40)
                    GROUP BY sr.file_hash, sr.issue_name
                    HAVING COUNT(DISTINCT s.id) >= 3
                ''')
            rows = cursor.fetchall() or []
            inserted = 0
            for r in rows:
                sha256 = _row_get(r, 0, 'file_hash') or ''
                hack_name = (_row_get(r, 1, 'issue_name') or 'unknown')[:120]
                times = int(_row_get(r, 2, 'times_confirmed') or 3)
                try:
                    if _USE_PG:
                        cursor.execute('''
                            INSERT INTO hack_blacklist (sha256, hack_name, times_confirmed)
                            VALUES (%s, %s, %s)
                            ON CONFLICT (sha256) DO UPDATE SET
                              times_confirmed = EXCLUDED.times_confirmed,
                              hack_name = EXCLUDED.hack_name
                        ''', (sha256, hack_name, times))
                    else:
                        cursor.execute(
                            'INSERT OR REPLACE INTO hack_blacklist (sha256, hack_name, times_confirmed) VALUES (?,?,?)',
                            (sha256, hack_name, times)
                        )
                    inserted += 1
                except Exception:
                    pass
        return jsonify({'synced': inserted}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# â”€â”€ P3 #18 â€” Score breakdown (SHAP-style explanation) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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

        # P3 #12 â€” Intervalo de confianza basado en varianza de confidence de los hallazgos
        confidences = [r['confidence'] for r in results if r.get('confidence', 0) > 0]
        if len(confidences) >= 2:
            avg_conf = sum(confidences) / len(confidences)
            variance = sum((c - avg_conf)**2 for c in confidences) / len(confidences)
            std_dev  = variance ** 0.5
            # Margen Â±15 puntos de risk_score cuando std_dev es alto
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


# â”€â”€ P2 #30 â€” Umbrales de confianza por tipo (feedback loop) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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


# â”€â”€ P3 #5 â€” Perfil de jugador / baseline â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@app.route('/api/player_baseline/<string:machine_id>', methods=['GET'])
def get_player_baseline(machine_id):
    """Returns historical baseline for a machine (avg issues_found, risk_score, known issue types).
    Used by the scanner to compare current scan vs historical behaviour.
    Only returns data for the last 10 scans of this machine.
    """
    machine_id = machine_id.strip()
    if not machine_id or len(machine_id) > 200:
        return jsonify({'error': 'machine_id invÃ¡lido'}), 400
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
    Ãštil para detectar quÃ© apareciÃ³ o desapareciÃ³ entre sesiones."""
    _ensure_dual_scanner_schema()
    try:
        with get_api_db_cursor() as cursor:
            diff = _build_scan_diff(cursor, int(scan_a), int(scan_b))
        return jsonify(diff), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/scans/compare', methods=['GET'])
@login_required
def compare_scans_query():
    """Dual-scanner compare endpoint: /api/scans/compare?scan1=..&scan2=.."""
    _ensure_dual_scanner_schema()
    try:
        scan1 = int(request.args.get('scan1') or 0)
        scan2 = int(request.args.get('scan2') or 0)
    except Exception:
        scan1 = 0
        scan2 = 0
    if scan1 <= 0 or scan2 <= 0:
        return jsonify({'error': 'scan1 y scan2 requeridos'}), 400
    try:
        with get_api_db_cursor() as cursor:
            diff = _build_scan_diff(cursor, scan1, scan2)
        return jsonify(diff), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/scans/<int:scan_id>/set-baseline', methods=['POST'])
@login_required
@audit_action('scan.set_baseline', 'scan')
def set_scan_baseline(scan_id: int):
    _ensure_dual_scanner_schema()
    try:
        with get_api_db_cursor() as cursor:
            cursor.execute(
                f"SELECT id, company_id, machine_name, minecraft_username FROM scans WHERE id = {_PH}",
                (scan_id,)
            )
            row = cursor.fetchone()
            if not row:
                return jsonify({'success': False, 'error': 'Scan no encontrado'}), 404
            d = dict(row) if not isinstance(row, dict) else row
            company_id = int(d.get('company_id') or 0)
            host = str(d.get('machine_name') or '').strip()
            usern = str(d.get('minecraft_username') or '').strip()
            cursor.execute(
                f"UPDATE scans SET is_baseline = FALSE "
                f"WHERE company_id = {_PH} AND machine_name = {_PH} AND minecraft_username = {_PH}",
                (company_id, host, usern)
            )
            cursor.execute(
                f"UPDATE scans SET is_baseline = TRUE WHERE id = {_PH}",
                (scan_id,)
            )
        return jsonify({'success': True, 'scan_id': scan_id, 'is_baseline': True}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/scans/timeline', methods=['GET'])
@login_required
def scans_timeline():
    _ensure_dual_scanner_schema()
    user_q = str(request.args.get('user') or '').strip()
    host_q = str(request.args.get('host') or '').strip()
    limit = max(1, min(120, int(request.args.get('limit', 30) or 30)))
    if not user_q and not host_q:
        return jsonify({'success': False, 'error': 'user o host requerido'}), 400
    try:
        with get_api_db_cursor() as cursor:
            where = []
            params = []
            if user_q:
                where.append(f"(CAST(created_by AS TEXT) = {_PH} OR LOWER(minecraft_username) = LOWER({_PH}))")
                params.extend([user_q, user_q])
            if host_q:
                where.append(f"LOWER(machine_name) = LOWER({_PH})")
                params.append(host_q)
            where_sql = " AND ".join(where) if where else "1=1"
            cursor.execute(
                f"SELECT id, started_at, issues_found, risk_score, verdict, machine_name, minecraft_username, "
                f"COALESCE(is_baseline,FALSE) AS is_baseline "
                f"FROM scans WHERE {where_sql} ORDER BY started_at DESC LIMIT {_PH}",
                tuple(params + [limit])
            )
            rows = cursor.fetchall() or []
        timeline = []
        for r in rows:
            d = dict(r) if not isinstance(r, dict) else r
            timeline.append({
                'scan_id': d.get('id'),
                'timestamp': str(d.get('started_at') or ''),
                'issues_found': int(d.get('issues_found') or 0),
                'risk_score': float(d.get('risk_score') or 0.0),
                'verdict': d.get('verdict') or 'pending',
                'host': d.get('machine_name') or '',
                'user': d.get('minecraft_username') or '',
                'is_baseline': bool(d.get('is_baseline') or False),
            })
        timeline.reverse()
        return jsonify({'success': True, 'timeline': timeline}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/schedules', methods=['GET', 'POST', 'PUT', 'DELETE'])
@login_required
@audit_action('schedules.mutate', 'scan_schedule')
def api_schedules():
    _ensure_dual_scanner_schema()
    uid = int(session.get('user_id') or 0)
    if uid <= 0:
        return jsonify({'success': False, 'error': 'No autenticado'}), 401
    if request.method == 'GET':
        try:
            with get_api_db_cursor() as cursor:
                cursor.execute(
                    f"SELECT id, user_id, host, frequency_hours, last_run, next_run, enabled "
                    f"FROM scan_schedules WHERE user_id = {_PH} ORDER BY next_run ASC",
                    (uid,)
                )
                rows = cursor.fetchall() or []
            return jsonify({'success': True, 'items': [dict(r) if not isinstance(r, dict) else r for r in rows]}), 200
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    data = request.json or {}
    try:
        with get_api_db_cursor() as cursor:
            if request.method == 'POST':
                host = str(data.get('host') or '').strip()[:255]
                freq = max(1, min(168, int(data.get('frequency_hours') or 24)))
                if not host:
                    return jsonify({'success': False, 'error': 'host requerido'}), 400
                sid = _insert_id(
                    cursor,
                    f"INSERT INTO scan_schedules (user_id, host, frequency_hours, next_run, enabled) "
                    f"VALUES ({_PH},{_PH},{_PH},CURRENT_TIMESTAMP,{_PH})",
                    (uid, host, freq, bool(data.get('enabled', True)))
                )
                return jsonify({'success': True, 'id': sid}), 200
            if request.method == 'PUT':
                sid = int(data.get('id') or 0)
                if sid <= 0:
                    return jsonify({'success': False, 'error': 'id requerido'}), 400
                host = str(data.get('host') or '').strip()[:255]
                freq = max(1, min(168, int(data.get('frequency_hours') or 24)))
                enabled = bool(data.get('enabled', True))
                cursor.execute(
                    f"UPDATE scan_schedules SET host = {_PH}, frequency_hours = {_PH}, enabled = {_PH}, "
                    f"updated_at = CURRENT_TIMESTAMP WHERE id = {_PH} AND user_id = {_PH}",
                    (host, freq, enabled, sid, uid)
                )
                return jsonify({'success': True}), 200
            # DELETE
            sid = int(data.get('id') or request.args.get('id') or 0)
            if sid <= 0:
                return jsonify({'success': False, 'error': 'id requerido'}), 400
            cursor.execute(f"DELETE FROM scan_schedules WHERE id = {_PH} AND user_id = {_PH}", (sid, uid))
            return jsonify({'success': True}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


def scan_scheduler_tick():
    """Tick cada 5m: avanza next_run para schedules vencidos (placeholder trigger)."""
    _ensure_dual_scanner_schema()
    try:
        now = datetime.datetime.utcnow()
        with get_api_db_cursor() as cursor:
            cursor.execute(
                f"SELECT id, user_id, host, frequency_hours FROM scan_schedules "
                f"WHERE enabled = TRUE AND next_run IS NOT NULL AND next_run <= {_PH} "
                f"ORDER BY next_run ASC LIMIT 100",
                (now,)
            )
            due = cursor.fetchall() or []
            for r in due:
                d = dict(r) if not isinstance(r, dict) else r
                sid = int(d.get('id') or 0)
                freq = max(1, int(d.get('frequency_hours') or 24))
                # Placeholder de trigger real: por ahora solo actualiza ventanas de ejecución
                cursor.execute(
                    f"UPDATE scan_schedules SET last_run = {_PH}, next_run = {_PH}, updated_at = CURRENT_TIMESTAMP "
                    f"WHERE id = {_PH}",
                    (now, now + datetime.timedelta(hours=freq), sid)
                )
        if due:
            print(f"[scan_scheduler] tick ejecutado: {len(due)} schedules")
    except Exception as e:
        print(f"[scan_scheduler] error: {e}")


# â”€â”€ P3 #2 â€” Scoring por rareza â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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


# â”€â”€ P3 #16 â€” Patrones de bans (cruce con historial) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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


# â”€â”€ Items 37/38/39 â€” Auto-whitelist / auto-blacklist from verdict history â”€â”€â”€â”€â”€

@app.route('/api/learning/auto_weights', methods=['GET'])
def get_auto_weights():
    """#38/#39 â€” Returns dynamically computed confidence weights per issue_type
    based on historical verdict ratios (no manual input needed).
    hack_rate = count_in_hack_scans / total_scans_with_this_type
    Response: {weights: [{issue_type, hack_rate, weight_multiplier}]}
    """
    try:
        with get_api_db_cursor() as cursor:
            if _USE_PG:
                cursor.execute('''
                    SELECT
                        sr.issue_type,
                        COUNT(*) FILTER (WHERE s.verdict = 'hack')   AS hack_n,
                        COUNT(*) FILTER (WHERE s.verdict = 'clean')  AS clean_n,
                        COUNT(*) AS total
                    FROM scan_results sr
                    JOIN scans s ON sr.scan_id = s.id
                    WHERE s.verdict IN ('hack', 'clean')
                      AND sr.issue_type IS NOT NULL AND sr.issue_type != ''
                    GROUP BY sr.issue_type
                    HAVING COUNT(*) >= 10
                    ORDER BY total DESC
                    LIMIT 200
                ''')
            else:
                cursor.execute('''
                    SELECT sr.issue_type,
                        SUM(CASE WHEN s.verdict='hack'  THEN 1 ELSE 0 END) AS hack_n,
                        SUM(CASE WHEN s.verdict='clean' THEN 1 ELSE 0 END) AS clean_n,
                        COUNT(*) AS total
                    FROM scan_results sr JOIN scans s ON sr.scan_id = s.id
                    WHERE s.verdict IN ('hack','clean')
                      AND sr.issue_type IS NOT NULL AND sr.issue_type != ''
                    GROUP BY sr.issue_type HAVING COUNT(*) >= 10
                    ORDER BY total DESC LIMIT 200
                ''')
            rows = cursor.fetchall() or []
        result = []
        for r in rows:
            issue_type  = _row_get(r, 0, 'issue_type') or ''
            hack_n      = int(_row_get(r, 1, 'hack_n') or 0)
            clean_n     = int(_row_get(r, 2, 'clean_n') or 0)
            total       = int(_row_get(r, 3, 'total') or 1)
            hack_rate   = round(hack_n / total, 4) if total > 0 else 0.5
            # weight_multiplier: 0.3 for near-0 hack_rate, 1.5 for near-1.0
            multiplier  = round(0.3 + 1.2 * hack_rate, 3)
            result.append({
                'issue_type':         issue_type,
                'hack_rate':          hack_rate,
                'weight_multiplier':  multiplier,
                'hack_count':         hack_n,
                'clean_count':        clean_n,
                'total':              total,
            })
        return jsonify({'weights': result, 'count': len(result)}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/learning/auto_whitelist', methods=['GET'])
def get_auto_whitelist():
    """#37 â€” Returns issue_type + path patterns that appear in >=30 clean scans
    and never (or rarely, <5%) in hack scans â€” these are systematic FPs.
    The scanner can fetch this on startup to extend its whitelist dynamically.
    """
    try:
        min_clean = int(request.args.get('min_clean', 30))
        max_hack_rate = float(request.args.get('max_hack_rate', 0.05))
        with get_api_db_cursor() as cursor:
            if _USE_PG:
                cursor.execute('''
                    SELECT
                        sr.issue_type,
                        sr.nombre,
                        COUNT(*) FILTER (WHERE s.verdict = 'clean') AS clean_n,
                        COUNT(*) FILTER (WHERE s.verdict = 'hack')  AS hack_n,
                        COUNT(*) AS total
                    FROM scan_results sr
                    JOIN scans s ON sr.scan_id = s.id
                    WHERE s.verdict IN ('hack', 'clean')
                      AND sr.issue_type IS NOT NULL AND sr.issue_type != ''
                    GROUP BY sr.issue_type, sr.nombre
                    HAVING COUNT(*) FILTER (WHERE s.verdict = 'clean') >= %s
                       AND (COUNT(*) FILTER (WHERE s.verdict = 'hack')::float / NULLIF(COUNT(*), 0)) <= %s
                    ORDER BY clean_n DESC
                    LIMIT 500
                ''', (min_clean, max_hack_rate))
            else:
                cursor.execute('''
                    SELECT sr.issue_type, sr.nombre,
                        SUM(CASE WHEN s.verdict='clean' THEN 1 ELSE 0 END) AS clean_n,
                        SUM(CASE WHEN s.verdict='hack'  THEN 1 ELSE 0 END) AS hack_n,
                        COUNT(*) AS total
                    FROM scan_results sr JOIN scans s ON sr.scan_id = s.id
                    WHERE s.verdict IN ('hack','clean')
                      AND sr.issue_type IS NOT NULL AND sr.issue_type != ''
                    GROUP BY sr.issue_type, sr.nombre
                    HAVING SUM(CASE WHEN s.verdict='clean' THEN 1 ELSE 0 END) >= ?
                       AND CAST(SUM(CASE WHEN s.verdict='hack' THEN 1 ELSE 0 END) AS FLOAT)
                           / MAX(1, COUNT(*)) <= ?
                    ORDER BY clean_n DESC LIMIT 500
                ''', (min_clean, max_hack_rate))
            rows = cursor.fetchall() or []
        result = [
            {
                'issue_type':  _row_get(r, 0, 'issue_type') or '',
                'nombre':      _row_get(r, 1, 'nombre') or '',
                'clean_count': int(_row_get(r, 2, 'clean_n') or 0),
                'hack_count':  int(_row_get(r, 3, 'hack_n') or 0),
            }
            for r in rows
        ]
        return jsonify({'whitelist': result, 'count': len(result)}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================
# GESTIÃ“N DE STAFF / ROLES
# ============================================================

@app.route('/api/staff/users', methods=['GET'])
@login_required
def list_staff_users():
    """Lista usuarios con su rol de staff. Solo Admin o superior.

    AISLAMIENTO ESTRICTO ENTRE EMPRESAS (P42):
    - Super-admin global ('admin'): ve todos los usuarios.
    - Admin/Owner de empresa (company_id != NULL): SOLO ve los usuarios con
      su mismo company_id. NUNCA ve staff de otras empresas ni huÃ©rfanos
      cross-empresa.
    - Staff individual (company_id NULL): SOLO ve a otros usuarios sin
      empresa (otros individuales). Nunca ve staff de empresas.
    La adopciÃ³n de staff huÃ©rfanos legacy ahora es responsabilidad exclusiva
    del SuperAdmin (panel /aspers-sa).
    """
    current_user = get_user_by_id(session.get('user_id'))
    if not can_manage_staff(current_user):
        return jsonify({'error': 'Se requiere rol Admin o superior'}), 403

    all_users = list_users() or []
    own_company_id = current_user.get('company_id') if current_user else None
    is_super = is_super_admin(current_user)

    if is_super:
        users = all_users
    elif own_company_id is not None:
        users = [u for u in all_users if u.get('company_id') == own_company_id]
    else:
        users = [u for u in all_users if u.get('company_id') is None]

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
            'company_id': u.get('company_id'),
            'in_my_company': bool(own_company_id) and u.get('company_id') == own_company_id,
        })
    return jsonify({
        'users': result,
        'my_company_id': own_company_id,
        'is_super_admin': is_super,
    }), 200


@app.route('/api/staff/users/<int:user_id>/role', methods=['PUT'])
@login_required
def update_staff_role(user_id):
    """Asigna un rol de staff a un usuario. Solo Admin o superior.

    AISLAMIENTO ENTRE EMPRESAS (P42):
    - Super-admin global ('admin'): puede modificar a cualquier usuario.
    - Admin/Owner de empresa: SOLO puede modificar a usuarios de su empresa.
      No puede tocar huÃ©rfanos (company_id NULL) ni usuarios de otras empresas.
    - Staff individual (sin company_id): SOLO puede modificar a otros sin
      company_id.

    Si el target no tiene company_id y el caller sÃ­, se le asigna company_id
    automÃ¡ticamente, manteniÃ©ndose el aislamiento.
    """
    current_user = get_user_by_id(session.get('user_id'))
    if not can_manage_staff(current_user):
        return jsonify({'error': 'Se requiere rol Admin o superior'}), 403
    data = request.json or {}
    new_role = (data.get('role') or '').strip().lower()
    if new_role not in STAFF_ROLE_HIERARCHY:
        return jsonify({'error': f'Rol invÃ¡lido. Opciones: {", ".join(STAFF_ROLE_HIERARCHY)}'}), 400
    if new_role == 'owner' and get_staff_role(current_user) != 'owner':
        return jsonify({'error': 'Solo un Owner puede asignar el rol de Owner'}), 403
    target = get_user_by_id(user_id)
    if not target:
        return jsonify({'error': 'Usuario no encontrado'}), 404

    own_company_id = current_user.get('company_id') if current_user else None
    target_company_id = target.get('company_id')
    is_super = is_super_admin(current_user)

    if not is_super:
        if own_company_id is not None:
            if target_company_id != own_company_id:
                return jsonify({'error': 'No puedes modificar usuarios fuera de tu empresa'}), 403
        else:
            if target_company_id is not None:
                return jsonify({'error': 'No puedes modificar usuarios de empresas'}), 403

    existing = target.get('roles', []) if isinstance(target.get('roles'), list) else []
    non_staff = [r for r in existing if r not in STAFF_ROLE_HIERARCHY]
    updated = non_staff + [new_role]

    set_company = (
        own_company_id is not None
        and target_company_id is None
    )

    import json as _json
    try:
        from auth import _auth_cursor, _ph
        ph = _ph()
        with _auth_cursor() as cursor:
            if set_company:
                cursor.execute(
                    f'UPDATE users SET roles = {ph}, company_id = {ph} WHERE id = {ph}',
                    (_json.dumps(updated), own_company_id, user_id)
                )
            else:
                cursor.execute(
                    f'UPDATE users SET roles = {ph} WHERE id = {ph}',
                    (_json.dumps(updated), user_id)
                )
        return jsonify({
            'success': True,
            'role': new_role,
            'company_attached': set_company,
            'company_id': own_company_id if set_company else target_company_id,
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# NOTA (P42): los endpoints /api/staff/users/.../attach* fueron retirados.
# La asignaciÃ³n de staff huÃ©rfanos (legacy con company_id NULL) ahora es
# responsabilidad EXCLUSIVA del SuperAdmin desde /aspers-sa, para evitar que
# admins de una empresa puedan "adoptar" usuarios de otra empresa o staff
# individual. Ver: /aspers-sa/api/orphan-staff y .../assign mÃ¡s abajo.


@app.route('/api/staff/users/<int:user_id>/avatar', methods=['PUT'])
@login_required
def update_user_avatar(user_id):
    """Actualiza el avatar de un usuario. Acepta URL externa o data URL base64. Admin o superior."""
    current_user = get_user_by_id(session.get('user_id'))
    if not can_manage_staff(current_user):
        return jsonify({'error': 'Se requiere rol Admin o superior'}), 403
    data = request.json or {}
    avatar_url = (data.get('avatar_url') or '').strip()
    # Validar tamaÃ±o: mÃ¡x 600 KB de texto (cubre imÃ¡genes base64 de ~430 KB originales)
    if len(avatar_url) > 614_400:
        return jsonify({'error': 'Imagen demasiado grande (mÃ¡x 450 KB)'}), 413
    # Validar que sea URL o data URL de imagen
    if avatar_url and not (
        avatar_url.startswith('http://') or
        avatar_url.startswith('https://') or
        avatar_url.startswith('data:image/')
    ):
        return jsonify({'error': 'Formato no vÃ¡lido: se esperaba URL o data URL de imagen'}), 400
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


# â”€â”€ Staff AI Chat â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

# â”€â”€ Staff AI Chat â€” ensemble: Claude + Groq + Gemini + DuckDuckGo â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

try:
    from argus_core_prompt import ARGUS_CORE_SYSTEM as _CHAT_SYSTEM
except ImportError:
    _CHAT_SYSTEM = (
        'Eres Argus Core, copiloto forense de ASPERS Projects. '
        'Respondes en español, directo y técnico.'
    )


def _ai_web_search(query, n=4):
    """Busca con DuckDuckGo y devuelve string con resultados formateados."""
    try:
        from duckduckgo_search import DDGS
        hits = DDGS().text(query, max_results=n)
        if not hits:
            return ''
        return '\n\n'.join(
            f"[{h.get('title','')}] {h.get('body','')[:300]} â€” {h.get('href','')}"
            for h in hits
        )
    except Exception as e:
        print(f'[ai_search] {e}')
        return ''


def _ai_call_claude(key, system, messages):
    try:
        import anthropic as _ant
        resp = _ant.Anthropic(api_key=key).messages.create(
            model='claude-sonnet-4-6',
            max_tokens=700,
            system=system,
            messages=messages,
        )
        return ''.join(b.text for b in resp.content if hasattr(b, 'text')).strip()
    except Exception as e:
        print(f'[claude] {e}')
        return None


def _ai_call_groq(key, system, messages):
    try:
        payload = {
            'model': 'llama-3.3-70b-versatile',
            'messages': [{'role': 'system', 'content': system}] + messages,
            'max_tokens': 700,
            'temperature': 0.6,
        }
        r = requests.post(
            'https://api.groq.com/openai/v1/chat/completions',
            headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
            json=payload, timeout=25,
        )
        r.raise_for_status()
        return r.json()['choices'][0]['message']['content'].strip()
    except Exception as e:
        print(f'[groq] {e}')
        return None


_GEMINI_MODEL = os.environ.get('ARGUS_GEMINI_MODEL', 'gemini-2.0-flash')
_GEMINI_MODEL_ACTIVE = _GEMINI_MODEL


def _gemini_models_to_try():
    primary = (_GEMINI_MODEL or 'gemini-2.0-flash').strip()
    fallbacks = ('gemini-2.0-flash-lite', 'gemini-1.5-flash', 'gemini-1.5-flash-8b')
    out = [primary]
    for m in fallbacks:
        if m and m not in out:
            out.append(m)
    return out


def _argus_core_provider():
    """gemini = solo Gemini (Argus Core). ensemble = Claude+Groq+Gemini."""
    p = (os.environ.get('ARGUS_CORE_PROVIDER') or 'gemini').strip().lower()
    return p if p in ('gemini', 'ensemble') else 'gemini'


def _chat_history_session_key(scan_id):
    return f'chat_history_scan_{int(scan_id)}' if scan_id else 'chat_history'


def _build_argus_core_scan_context(scan_id):
    """Contexto forense completo para conversar scan a scan con Gemini."""
    if not scan_id:
        return ''
    try:
        sid = int(scan_id)
    except (TypeError, ValueError):
        return ''
    try:
        with get_api_db_cursor() as cur:
            cur.execute(
                f'SELECT machine_name, minecraft_username, verdict, issues_found, risk_score, '
                f'started_at, scanner_version FROM scans WHERE id = {_PH}',
                (sid,),
            )
            row = cur.fetchone()
            if not row:
                return ''
            machine = _row_get(row, 0, 'machine_name') or '?'
            mc_user = _row_get(row, 1, 'minecraft_username') or '?'
            verdict = _row_get(row, 2, 'verdict') or 'pendiente'
            n_issues = int(_row_get(row, 3, 'issues_found') or 0)
            risk = int(_row_get(row, 4, 'risk_score') or 0)
            started = str(_row_get(row, 5, 'started_at') or '')[:19]
            scanner_ver = _row_get(row, 6, 'scanner_version') or ''

            lines = [
                f'\n\n[CASO ACTIVO — SCAN #{sid}]',
                f'Jugador: {mc_user} | Máquina: {machine}',
                f'Risk: {risk}/100 | Veredicto: {verdict} | Hallazgos: {n_issues}',
                f'Fecha: {started}' + (f' | Scanner: {scanner_ver}' if scanner_ver else ''),
                'Listado de hallazgos (ordenados por confianza):',
            ]
            cur.execute(
                f'SELECT issue_name, issue_category, alert_level, confidence, issue_type '
                f'FROM scan_results WHERE scan_id = {_PH} '
                f'ORDER BY CASE alert_level WHEN \'CRITICAL\' THEN 0 WHEN \'SEVERE\' THEN 1 '
                f'WHEN \'ALERT\' THEN 2 ELSE 3 END, confidence DESC LIMIT 45',
                (sid,),
            )
            for r in (cur.fetchall() or []):
                name = _row_get(r, 0, 'issue_name') or ''
                cat = _row_get(r, 1, 'issue_category') or ''
                lvl = _row_get(r, 2, 'alert_level') or ''
                tipo = _row_get(r, 4, 'issue_type') or ''
                try:
                    conf_s = f'{float(_row_get(r, 3, "confidence") or 0):.0%}'
                except Exception:
                    conf_s = ''
                lines.append(f'  [{lvl}] {name} ({cat}/{tipo}) conf={conf_s}')
            lines.append(
                'Instrucción: analizá SOLO este scan. Si el staff pregunta por otro, pedí que abra ese scan en el panel.'
            )
            return '\n'.join(lines) + '\n'
    except Exception as e:
        print(f'[argus_core] scan ctx error: {e}')
        return ''


def _ai_call_gemini(key, system, history, user_msg=None):
    """Gemini multi-turn con systemInstruction (Argus Core). Prueba modelos alternativos si hay 429."""
    global _GEMINI_MODEL_ACTIVE
    contents = []
    for m in history:
        role = m.get('role')
        text = (m.get('content') or '').strip()
        if not text:
            continue
        if role == 'user':
            contents.append({'role': 'user', 'parts': [{'text': text}]})
        elif role in ('assistant', 'model'):
            contents.append({'role': 'model', 'parts': [{'text': text}]})
    if not contents:
        contents.append({'role': 'user', 'parts': [{'text': user_msg or 'Hola'}]})
    payload = {
        'systemInstruction': {'parts': [{'text': system}]},
        'contents': contents,
        'generationConfig': {'maxOutputTokens': 1024, 'temperature': 0.45},
    }
    last_err = None
    for model in _gemini_models_to_try():
        try:
            url = (
                f'https://generativelanguage.googleapis.com/v1beta/models/'
                f'{model}:generateContent?key={key}'
            )
            r = requests.post(url, json=payload, timeout=45)
            if r.status_code in (429, 503, 404):
                print(f'[gemini] {model} HTTP {r.status_code}')
                last_err = r.text[:200]
                continue
            r.raise_for_status()
            data = r.json()
            cands = data.get('candidates') or []
            if not cands:
                continue
            parts = (cands[0].get('content') or {}).get('parts') or []
            if not parts:
                continue
            text = (parts[0].get('text') or '').strip()
            if text:
                _GEMINI_MODEL_ACTIVE = model
                return text
        except Exception as e:
            print(f'[gemini] {model} {e}')
            last_err = str(e)
    if last_err:
        print(f'[gemini] todos los modelos fallaron: {last_err}')
    return None


def _ai_synthesize(responses, question, synth_fn):
    """Llama a synth_fn para fusionar las respuestas de los modelos en una sola."""
    joined = '\n\n---\n\n'.join(
        f'[IA {i+1}]: {r}' for i, r in enumerate(responses)
    )
    prompt = (
        f'El staff preguntÃ³: "{question}"\n\n'
        f'Estas son las respuestas de {len(responses)} modelos de IA:\n\n{joined}\n\n'
        'Sintetiza la respuesta mÃ¡s certera y completa combinando los puntos mÃ¡s '
        'precisos de cada una. Elimina redundancias. Responde en espaÃ±ol, mÃ¡x 250 palabras.'
    )
    return synth_fn([{'role': 'user', 'content': prompt}])


def _ensure_oracle_conversations_schema():
    """Crea la tabla de memoria conversacional del assistant (si no existe)."""
    try:
        with get_api_db_cursor() as cur:
            try:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS oracle_conversations (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        company_id INTEGER,
                        scan_id INTEGER,
                        message TEXT NOT NULL,
                        response TEXT,
                        feedback SMALLINT,
                        feedback_note TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                cur.execute("CREATE INDEX IF NOT EXISTS idx_oracle_conv_user ON oracle_conversations(user_id, created_at DESC)")
                # Migración no destructiva: agregar columnas si tabla ya existe sin ellas
                for _col, _def in [('feedback', 'SMALLINT'), ('feedback_note', 'TEXT'), ('company_id', 'INTEGER'), ('scan_id', 'INTEGER')]:
                    try:
                        cur.execute(f"ALTER TABLE oracle_conversations ADD COLUMN IF NOT EXISTS {_col} {_def}")
                    except Exception:
                        pass
            except Exception:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS oracle_conversations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        company_id INTEGER,
                        scan_id INTEGER,
                        message TEXT NOT NULL,
                        response TEXT,
                        feedback INTEGER,
                        feedback_note TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                cur.execute("CREATE INDEX IF NOT EXISTS idx_oracle_conv_user ON oracle_conversations(user_id, created_at DESC)")
    except Exception as e:
        print(f"[oracle_conversations] schema error: {e}")


def _load_oracle_history(user_id: int, limit: int = 10, scan_id=None) -> list[dict]:
    out: list[dict] = []
    try:
        with get_api_db_cursor() as cur:
            if scan_id is not None:
                cur.execute(
                    f"SELECT id, message, response, created_at, scan_id, feedback, feedback_note "
                    f"FROM oracle_conversations WHERE user_id = {_PH} AND scan_id = {_PH} "
                    f"ORDER BY created_at DESC LIMIT {_PH}",
                    (int(user_id), int(scan_id), int(limit)),
                )
            else:
                cur.execute(
                    f"SELECT id, message, response, created_at, scan_id, feedback, feedback_note "
                    f"FROM oracle_conversations WHERE user_id = {_PH} AND scan_id IS NULL "
                    f"ORDER BY created_at DESC LIMIT {_PH}",
                    (int(user_id), int(limit)),
                )
            for r in (cur.fetchall() or []):
                d = dict(r) if not isinstance(r, dict) else r
                out.append({
                    'id': d.get('id'),
                    'message': d.get('message') or '',
                    'response': d.get('response') or '',
                    'created_at': str(d.get('created_at')) if d.get('created_at') else None,
                    'scan_id': d.get('scan_id'),
                    'feedback': d.get('feedback'),
                    'feedback_note': d.get('feedback_note'),
                })
    except Exception as e:
        print(f"[oracle_conversations] load history error: {e}")
    return out


@app.route('/api/argus-core/brief', methods=['GET'])
@login_required
def argus_core_brief():
    """Saludo proactivo + estado del panel para Argus Core (copiloto)."""
    import datetime as _dt
    try:
        from argus_core_prompt import ARGUS_CORE_GREETINGS
    except ImportError:
        ARGUS_CORE_GREETINGS = {'morning': 'Argus Core en línea.'}

    try:
        user = get_user_by_id(session.get('user_id'))
        uname = (user.get('username') if user else session.get('username')) or 'Staff'
        hour = _dt.datetime.now().hour
        if hour < 12:
            slot = 'morning'
        elif hour < 18:
            slot = 'afternoon'
        elif hour < 22:
            slot = 'evening'
        else:
            slot = 'night'
        base = ARGUS_CORE_GREETINGS.get(slot, 'Argus Core en línea.')

        pending = today_total = high_risk = 0
        try:
            with get_api_db_cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM scans WHERE verdict IS NULL OR verdict = 'pending'"
                )
                row = cur.fetchone()
                pending = int(_row_get(row, 0, list(row.keys())[0] if row else 0) or 0)

                today = _dt.datetime.utcnow().strftime('%Y-%m-%d')
                if _USE_PG:
                    cur.execute(
                        f"SELECT COUNT(*) FROM scans WHERE DATE(started_at) = {_PH}",
                        (today,),
                    )
                else:
                    cur.execute(
                        "SELECT COUNT(*) FROM scans WHERE DATE(started_at) = ?",
                        (today,),
                    )
                row2 = cur.fetchone()
                today_total = int(_row_get(row2, 0, list(row2.keys())[0] if row2 else 0) or 0)

                cur.execute(
                    "SELECT COUNT(*) FROM scans WHERE risk_score >= 70 "
                    "AND (verdict IS NULL OR verdict = 'pending')"
                )
                row3 = cur.fetchone()
                high_risk = int(_row_get(row3, 0, list(row3.keys())[0] if row3 else 0) or 0)
        except Exception as e:
            print(f'[argus-core/brief] {e}')

        hints = []
        if pending:
            hints.append(f'{pending} escaneo(s) sin veredicto')
        if high_risk:
            hints.append(f'{high_risk} con risk alto (70+)')
        if today_total:
            hints.append(f'{today_total} hoy')

        greeting = f'{base} Hola, {uname}.'
        greeting += (' ' + ' · '.join(hints) + '.') if hints else ' Panel al día.'

        return jsonify({
            'greeting': greeting,
            'status': 'online',
            'pending_scans': pending,
            'high_risk_pending': high_risk,
            'scans_today': today_total,
            'staff': uname,
        }), 200
    except Exception as e:
        return jsonify({'greeting': 'Argus Core en línea.', 'status': 'degraded', 'error': str(e)}), 200


@app.route('/api/argus-core/status', methods=['GET'])
@login_required
def argus_core_status():
    """Estado del motor IA (Gemini) para Argus Core."""
    k_gemini = os.environ.get('GEMINI_API_KEY')
    provider = _argus_core_provider()
    ready = bool(k_gemini) if provider == 'gemini' else bool(
        k_gemini or os.environ.get('GROQ_API_KEY') or os.environ.get('ANTHROPIC_API_KEY')
    )
    return jsonify({
        'provider': provider,
        'model': _GEMINI_MODEL_ACTIVE if provider == 'gemini' else 'ensemble',
        'gemini_configured': bool(k_gemini),
        'ready': ready,
        'hint': None if ready else 'Configurá GEMINI_API_KEY en .env.local (ver .env.local.example).',
    })


@app.route('/api/argus-core/history', methods=['GET'])
@login_required
def argus_core_history():
    """Historial de chat Argus Core para un scan (o global sin scan_id)."""
    user_id = int(session.get('user_id') or 0)
    scan_raw = request.args.get('scan_id')
    scan_id = int(scan_raw) if scan_raw and str(scan_raw).isdigit() else None
    turns = []
    for h in reversed(_load_oracle_history(user_id, limit=12, scan_id=scan_id)):
        if h.get('message'):
            turns.append({'role': 'user', 'text': h['message']})
        if h.get('response'):
            turns.append({'role': 'bot', 'text': h['response']})
    return jsonify({'scan_id': scan_id, 'turns': turns})


@app.route('/api/staff/chat', methods=['POST'])
@login_required
@_limit("30 per minute")
@audit_action('oracle.chat', 'oracle')
def staff_chat():
    """Chat de IA para staff â€” ensemble Claude + Groq + Gemini con bÃºsqueda web."""
    import concurrent.futures as _cf

    # Rate limit: 20 mensajes/hora por sesiÃ³n
    now_ts = datetime.datetime.utcnow().timestamp()
    rate_log = session.get('chat_rate_log', [])
    rate_log = [ts for ts in rate_log if now_ts - ts < 3600]
    if len(rate_log) >= 20:
        return jsonify({'error': 'LÃ­mite de 20 mensajes/hora alcanzado.'}), 429
    rate_log.append(now_ts)
    session['chat_rate_log'] = rate_log

    data    = request.json or {}
    user_msg = (data.get('message') or '').strip()
    scan_id  = data.get('scan_id')
    if not user_msg:
        return jsonify({'error': 'Mensaje vacÃ­o'}), 400
    user_id = int(session.get('user_id') or 0)
    _ensure_oracle_conversations_schema()

    # Slash commands básicos (#415)
    if user_msg.startswith('/'):
        parts = user_msg.split()
        cmd = parts[0].lower()
        arg = ' '.join(parts[1:]).strip() if len(parts) > 1 else ''
        if cmd == '/help':
            reply = (
                "Comandos disponibles:\n"
                "/status <player>\n"
                "/explain <decision_id>\n"
                "/ban <player>\n"
                "/help"
            )
            return jsonify({'reply': reply, 'providers_used': [], 'search_done': False, 'scan_id': scan_id}), 200
        if cmd == '/status' and arg:
            try:
                import argus_ai_assistant as A
                with get_api_db_cursor() as cur:
                    user = get_user_by_id(user_id)
                    company_id = int((user or {}).get('company_id') or 0)
                    ctx = _build_assistant_player_ctx(cur, company_id, arg)
                if not ctx:
                    return jsonify({'reply': f'No encontré datos para {arg}.', 'providers_used': [], 'search_done': False, 'scan_id': scan_id}), 200
                out = A.generate_response(f"status {arg}", lambda name: ctx if name.lower() == arg.lower() else None)
                return jsonify({'reply': out.get('answer') or 'Sin respuesta.', 'providers_used': [], 'search_done': False, 'scan_id': scan_id}), 200
            except Exception as e:
                return jsonify({'error': f'Error en /status: {e}'}), 500
        if cmd == '/explain' and arg.isdigit():
            try:
                decision_id = int(arg)
                with get_api_db_cursor() as cur:
                    cur.execute(
                        f"SELECT action, score, confidence, reasoning FROM ai_decisions_log WHERE id = {_PH}",
                        (decision_id,)
                    )
                    row = cur.fetchone()
                if not row:
                    return jsonify({'reply': f'No existe decisión #{decision_id}.', 'providers_used': [], 'search_done': False, 'scan_id': scan_id}), 200
                row = dict(row) if not isinstance(row, dict) else row
                reply = (
                    f"Decisión #{decision_id}: acción={row.get('action')} | "
                    f"score={row.get('score')} | confianza={row.get('confidence')}.\n"
                    f"Razón: {row.get('reasoning') or 'sin detalle'}"
                )
                return jsonify({'reply': reply, 'providers_used': [], 'search_done': False, 'scan_id': scan_id}), 200
            except Exception as e:
                return jsonify({'error': f'Error en /explain: {e}'}), 500
        if cmd == '/ban' and arg:
            return jsonify({
                'reply': f'Sugerencia: revisá {arg} con /status y /explain antes de aplicar ban manual.',
                'providers_used': [],
                'search_done': False,
                'scan_id': scan_id
            }), 200

    k_claude = os.environ.get('ANTHROPIC_API_KEY')
    k_groq   = os.environ.get('GROQ_API_KEY')
    k_gemini = os.environ.get('GEMINI_API_KEY')
    provider_mode = _argus_core_provider()

    if provider_mode == 'gemini':
        if not k_gemini:
            return jsonify({
                'error': 'Argus Core usa Gemini. Configurá GEMINI_API_KEY en web_app/.env.local y reiniciá el panel.',
            }), 503
    elif not any([k_claude, k_groq, k_gemini]):
        return jsonify({'error': 'No hay API keys de IA (GEMINI_API_KEY / GROQ_API_KEY / ANTHROPIC_API_KEY).'}), 503

    scan_context = _build_argus_core_scan_context(scan_id)
    hist_key = _chat_history_session_key(scan_id)

    history = []
    for h in reversed(_load_oracle_history(user_id, limit=12, scan_id=int(scan_id) if scan_id else None)):
        if h.get('message'):
            history.append({'role': 'user', 'content': h['message']})
        if h.get('response'):
            history.append({'role': 'assistant', 'content': h['response']})
    history.extend(list(session.get(hist_key, [])))
    history.append({'role': 'user', 'content': user_msg})

    search_text = ''
    search_query = user_msg[:120]
    system_full = _CHAT_SYSTEM + scan_context

    providers_used = []
    final_reply = ''

    if provider_mode == 'gemini':
        want_search = any(w in user_msg.lower() for w in ('busca', 'buscar', 'web', 'internet', 'google'))
        if want_search:
            search_text = _ai_web_search(search_query) or ''
            if search_text:
                system_full += f'\n\n[BÚSQUEDA WEB]\n{search_text[:1200]}'
        final_reply = _ai_call_gemini(k_gemini, system_full, list(history))
        if final_reply:
            providers_used = ['gemini']
        else:
            return jsonify({
                'error': f'Gemini no respondió ({_GEMINI_MODEL}). Revisá GEMINI_API_KEY o probá ARGUS_GEMINI_MODEL=gemini-1.5-flash.',
            }), 503
    else:
        futures = {}
        with _cf.ThreadPoolExecutor(max_workers=4) as pool:
            futures['search'] = pool.submit(_ai_web_search, search_query)
            if k_claude:
                futures['claude'] = pool.submit(_ai_call_claude, k_claude, system_full, list(history))
            if k_groq:
                futures['groq'] = pool.submit(_ai_call_groq, k_groq, system_full, list(history))
            if k_gemini:
                futures['gemini'] = pool.submit(_ai_call_gemini, k_gemini, system_full, list(history))

            results = {name: f.result() for name, f in futures.items()}

        search_text = results.pop('search', '') or ''
        ai_responses = []
        for name in ('claude', 'groq', 'gemini'):
            if name in results and results[name]:
                providers_used.append(name)
                ai_responses.append(results[name])

        if not ai_responses:
            return jsonify({'error': 'Todos los modelos fallaron. Verifica las API keys.'}), 503

        if search_text:
            system_full += f'\n\n[BÚSQUEDA WEB]\n{search_text[:1200]}'

        if len(ai_responses) == 1:
            final_reply = ai_responses[0]
        else:
            if k_groq:
                synth_fn = lambda msgs: _ai_call_groq(k_groq, system_full, msgs)
            elif k_gemini:
                synth_fn = lambda msgs: _ai_call_gemini(k_gemini, system_full, msgs)
            else:
                synth_fn = lambda msgs: _ai_call_claude(k_claude, system_full, msgs)
            final_reply = _ai_synthesize(ai_responses, user_msg, synth_fn) or ai_responses[0]

    history.append({'role': 'assistant', 'content': final_reply})
    session[hist_key] = history[-20:]
    conv_id = None
    try:
        user = get_user_by_id(user_id)
        company_id = int((user or {}).get('company_id') or 0)
        with get_api_db_cursor() as cur:
            conv_id = _insert_id(
                cur,
                f"INSERT INTO oracle_conversations (user_id, company_id, scan_id, message, response) "
                f"VALUES ({_PH},{_PH},{_PH},{_PH},{_PH})",
                (user_id, company_id, scan_id if scan_id else None, user_msg, final_reply)
            )
    except Exception as e:
        print(f"[oracle_conversations] persist error: {e}")

    return jsonify({
        'reply':          final_reply,
        'providers_used': providers_used,
        'provider_mode':  provider_mode,
        'model':          _GEMINI_MODEL if provider_mode == 'gemini' else 'ensemble',
        'search_done':    bool(search_text),
        'scan_id':        scan_id,
        'conversation_id': conv_id,
    })


@app.route('/api/staff/chat/clear', methods=['POST'])
@login_required
def staff_chat_clear():
    """Borra historial de sesión (por scan si se envía scan_id)."""
    data = request.json or {}
    scan_id = data.get('scan_id')
    if scan_id:
        session.pop(_chat_history_session_key(scan_id), None)
    else:
        session.pop('chat_history', None)
        for key in list(session.keys()):
            if isinstance(key, str) and key.startswith('chat_history_scan_'):
                session.pop(key, None)
    return jsonify({'success': True, 'scan_id': scan_id})


@app.route('/api/oracle/history', methods=['GET'])
@login_required
def api_oracle_history():
    """Devuelve las últimas conversaciones Oracle del usuario actual."""
    _ensure_oracle_conversations_schema()
    uid = int(session.get('user_id') or 0)
    if not uid:
        return jsonify({'success': False, 'error': 'No autenticado'}), 401
    rows = _load_oracle_history(uid, limit=10)
    return jsonify({'success': True, 'history': rows}), 200


@app.route('/api/oracle/feedback', methods=['POST'])
@login_required
def api_oracle_feedback():
    """Feedback de conversación Oracle (thumb up/down)."""
    _ensure_oracle_conversations_schema()
    uid = int(session.get('user_id') or 0)
    data = request.json or {}
    conv_id = int(data.get('conversation_id') or 0)
    thumb = str(data.get('thumb') or '').strip().lower()
    note = str(data.get('note') or '').strip()[:500]
    if not conv_id or thumb not in ('up', 'down'):
        return jsonify({'success': False, 'error': 'Parámetros inválidos'}), 400
    fb = 1 if thumb == 'up' else -1
    try:
        with get_api_db_cursor() as cur:
            cur.execute(
                f"UPDATE oracle_conversations SET feedback = {_PH}, feedback_note = {_PH} "
                f"WHERE id = {_PH} AND user_id = {_PH}",
                (fb, note or None, conv_id, uid)
            )
        return jsonify({'success': True}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/oracle/conversations/<int:conversation_id>/export', methods=['GET'])
@login_required
def api_oracle_conversation_export(conversation_id: int):
    """Exporta una conversación en markdown o texto plano para PDF."""
    _ensure_oracle_conversations_schema()
    uid = int(session.get('user_id') or 0)
    fmt = (request.args.get('format') or 'md').strip().lower()
    if fmt not in ('md', 'pdf'):
        return jsonify({'success': False, 'error': 'Formato no soportado (md|pdf)'}), 400
    try:
        with get_api_db_cursor() as cur:
            cur.execute(
                f"SELECT id, message, response, created_at, scan_id "
                f"FROM oracle_conversations WHERE id = {_PH} AND user_id = {_PH} LIMIT 1",
                (conversation_id, uid)
            )
            row = cur.fetchone()
        if not row:
            return jsonify({'success': False, 'error': 'Conversación no encontrada'}), 404
        row = dict(row) if not isinstance(row, dict) else row
        md = (
            f"# Oracle Conversation #{row.get('id')}\n\n"
            f"- Fecha: {row.get('created_at')}\n"
            f"- Scan ID: {row.get('scan_id')}\n\n"
            f"## Staff\n\n{row.get('message') or ''}\n\n"
            f"## Oracle\n\n{row.get('response') or ''}\n"
        )
        if fmt == 'md':
            return Response(
                md,
                mimetype='text/markdown; charset=utf-8',
                headers={'Content-Disposition': f'attachment; filename=oracle-conversation-{conversation_id}.md'}
            )
        # Fallback ligero: export "pdf" como texto si no hay librería PDF instalada.
        return Response(
            md,
            mimetype='text/plain; charset=utf-8',
            headers={'Content-Disposition': f'attachment; filename=oracle-conversation-{conversation_id}.pdf.txt'}
        )
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/staff/ai/suggest-verdict/<int:scan_id>', methods=['GET'])
@login_required
def ai_suggest_verdict(scan_id):
    """Analiza los hallazgos de un scan y sugiere veredicto con justificaciÃ³n."""
    k_groq   = os.environ.get('GROQ_API_KEY')
    k_gemini = os.environ.get('GEMINI_API_KEY')
    k_claude = os.environ.get('ANTHROPIC_API_KEY')
    if not any([k_groq, k_gemini, k_claude]):
        return jsonify({'error': 'Sin API keys configuradas'}), 503

    try:
        with get_api_db_cursor() as cur:
            cur.execute(
                f'SELECT machine_name, minecraft_username, issues_found, risk_score '
                f'FROM scans WHERE id = {_PH}', (scan_id,)
            )
            row = cur.fetchone()
            if not row:
                return jsonify({'error': 'Scan no encontrado'}), 404
            mc_user  = _row_get(row, 1, 'minecraft_username') or '?'
            n_issues = _row_get(row, 2, 'issues_found') or 0
            risk     = _row_get(row, 3, 'risk_score') or 0

            cur.execute(
                f'SELECT issue_name, issue_category, alert_level, confidence '
                f'FROM scan_results WHERE scan_id = {_PH} ORDER BY confidence DESC LIMIT 25',
                (scan_id,)
            )
            findings_rows = cur.fetchall() or []
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    if not findings_rows:
        return jsonify({'verdict': 'LIMPIO', 'confidence': 90,
                        'reasons': ['No se encontraron hallazgos en el scan.',
                                    'Sin evidencia de hacks instalados o ejecutados.',
                                    'Risk score bajo â€” comportamiento esperado de un usuario limpio.']})

    findings_text = '\n'.join(
        f"  [{_row_get(r, 2, 'alert_level')}] {_row_get(r, 0, 'issue_name')} "
        f"({_row_get(r, 1, 'issue_category')}) "
        f"conf:{float(_row_get(r, 3, 'confidence') or 0):.0%}"
        for r in findings_rows
    )

    prompt = (
        f'Analiza los siguientes hallazgos del scanner Argus para el jugador "{mc_user}" '
        f'(scan #{scan_id}, risk score: {risk}/100, total hallazgos: {n_issues}):\n\n'
        f'{findings_text}\n\n'
        'Determina si el jugador tiene hacks o estÃ¡ limpio. '
        'Responde ÃšNICAMENTE con este JSON vÃ¡lido (sin texto extra):\n'
        '{"verdict":"HACK","confidence":85,"reasons":["razÃ³n 1","razÃ³n 2","razÃ³n 3"]}\n'
        'verdict = "HACK" o "LIMPIO", confidence = 0-100, reasons = 3 strings cortos en espaÃ±ol.'
    )

    system = 'Eres un experto en detecciÃ³n de hacks de Minecraft. Responde solo con JSON vÃ¡lido.'
    messages = [{'role': 'user', 'content': prompt}]

    raw = None
    if k_groq:
        raw = _ai_call_groq(k_groq, system, messages)
    if not raw and k_gemini:
        raw = _ai_call_gemini(k_gemini, system, [], prompt)
    if not raw and k_claude:
        raw = _ai_call_claude(k_claude, system, messages)

    if not raw:
        return jsonify({'error': 'Todos los modelos fallaron'}), 503

    try:
        import re as _re
        match = _re.search(r'\{[^{}]+\}', raw, _re.DOTALL)
        parsed = json.loads(match.group(0) if match else raw)
        return jsonify({
            'verdict':    str(parsed.get('verdict', 'LIMPIO')).upper(),
            'confidence': int(parsed.get('confidence', 50)),
            'reasons':    list(parsed.get('reasons', []))[:3],
        })
    except Exception:
        return jsonify({'raw': raw, 'verdict': 'LIMPIO', 'confidence': 50,
                        'reasons': ['No se pudo parsear la respuesta de la IA.']})


@app.route('/api/staff/ai/explain', methods=['GET'])
@login_required
def ai_explain_finding():
    """Devuelve una explicaciÃ³n de 1-2 lÃ­neas de un hallazgo especÃ­fico."""
    name  = (request.args.get('name')  or '').strip()[:120]
    level = (request.args.get('level') or 'SOSPECHOSO').strip()
    if not name:
        return jsonify({'error': 'ParÃ¡metro name requerido'}), 400

    k_groq   = os.environ.get('GROQ_API_KEY')
    k_gemini = os.environ.get('GEMINI_API_KEY')
    k_claude = os.environ.get('ANTHROPIC_API_KEY')
    if not any([k_groq, k_gemini, k_claude]):
        return jsonify({'explanation': 'Sin API keys configuradas.'}), 200

    prompt = (
        f'En mÃ¡ximo 2 oraciones cortas, explica quÃ© es "{name}" '
        f'(nivel de alerta: {level}) en el contexto de trampas en Minecraft '
        f'y por quÃ© es sospechoso. SÃ© tÃ©cnico y directo. Solo el texto, sin bullet points.'
    )
    system   = 'Eres un experto en seguridad de Minecraft. Responde en espaÃ±ol, mÃ¡x 2 oraciones.'
    messages = [{'role': 'user', 'content': prompt}]

    expl = None
    if k_groq:
        expl = _ai_call_groq(k_groq, system, messages)
    if not expl and k_gemini:
        expl = _ai_call_gemini(k_gemini, system, [], prompt)
    if not expl and k_claude:
        expl = _ai_call_claude(k_claude, system, messages)

    return jsonify({'explanation': expl or 'No se pudo generar explicaciÃ³n.'})


@app.route('/api/staff/ai/scan-summary/<int:scan_id>', methods=['GET'])
@login_required
def ai_scan_summary(scan_id):
    """P3 #12 â€” Genera un resumen en lenguaje natural del scan para el staff.
    Returns: {summary: str}  â€” pÃ¡rrafo de 3-5 oraciones en espaÃ±ol.
    """
    k_groq   = os.environ.get('GROQ_API_KEY')
    k_gemini = os.environ.get('GEMINI_API_KEY')
    k_claude = os.environ.get('ANTHROPIC_API_KEY')
    if not any([k_groq, k_gemini, k_claude]):
        return jsonify({'summary': 'Sin API keys configuradas para IA.'}), 200

    try:
        with get_api_db_cursor() as cursor:
            cursor.execute(
                f'SELECT minecraft_username, risk_score, verdict, started_at FROM scans WHERE id={_PH}',
                (scan_id,)
            )
            scan_row = cursor.fetchone()
            if not scan_row:
                return jsonify({'error': 'Scan no encontrado'}), 404
            mc_user   = _row_get(scan_row, 0, 'minecraft_username') or 'unknown'
            risk      = int(_row_get(scan_row, 1, 'risk_score') or 0)
            verdict   = _row_get(scan_row, 2, 'verdict') or 'pending'

            cursor.execute(
                f'''SELECT issue_name, issue_category, alert_level, confidence, issue_type
                    FROM scan_results WHERE scan_id={_PH}
                    ORDER BY (CASE alert_level WHEN 'CRITICAL' THEN 0 WHEN 'SOSPECHOSO' THEN 1
                              WHEN 'POCO_SOSPECHOSO' THEN 2 ELSE 3 END), confidence DESC
                    LIMIT 20''',
                (scan_id,)
            )
            findings_rows = cursor.fetchall() or []
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    if not findings_rows:
        return jsonify({'summary': f'El scan del jugador {mc_user} no arrojÃ³ hallazgos relevantes.'}), 200

    findings_lines = '\n'.join(
        f'  [{_row_get(r, 2, "alert_level")}] {_row_get(r, 0, "issue_name")} '
        f'({_row_get(r, 1, "issue_category")}, {_row_get(r, 4, "issue_type")}) '
        f'conf:{float(_row_get(r, 3, "confidence") or 0):.0%}'
        for r in findings_rows
    )

    prompt = (
        f'Soy staff de un servidor de Minecraft revisando el scan del jugador "{mc_user}". '
        f'Risk score: {risk}/100. Veredicto actual: {verdict}.\n\n'
        f'Hallazgos principales:\n{findings_lines}\n\n'
        'Escribe un resumen ejecutivo de 3-5 oraciones en espaÃ±ol que explique claramente:\n'
        '1. QuÃ© evidencia concreta existe de hacks\n'
        '2. CuÃ¡les son los hallazgos mÃ¡s importantes\n'
        '3. Tu conclusiÃ³n sobre si el jugador es sospechoso o no\n'
        'SÃ© directo y tÃ©cnico. No uses bullet points.'
    )
    system   = 'Eres un experto en anÃ¡lisis forense de hacks en Minecraft. Responde en espaÃ±ol.'
    messages = [{'role': 'user', 'content': prompt}]

    summary = None
    if k_groq:
        summary = _ai_call_groq(k_groq, system, messages)
    if not summary and k_gemini:
        summary = _ai_call_gemini(k_gemini, system, [], prompt)
    if not summary and k_claude:
        summary = _ai_call_claude(k_claude, system, messages)

    return jsonify({'summary': summary or 'No se pudo generar el resumen.'})


@app.route('/api/staff/ai/inconsistencies/<int:scan_id>', methods=['GET'])
@login_required
def ai_detect_inconsistencies(scan_id):
    """P3 #23 â€” IA detecta inconsistencias en el conjunto de hallazgos de un scan."""
    k_groq   = os.environ.get('GROQ_API_KEY')
    k_gemini = os.environ.get('GEMINI_API_KEY')
    k_claude = os.environ.get('ANTHROPIC_API_KEY')
    if not any([k_groq, k_gemini, k_claude]):
        return jsonify({'inconsistencies': []}), 200
    try:
        with get_api_db_cursor() as cur:
            cur.execute(
                f'SELECT issue_name, issue_category, alert_level, confidence, issue_type '
                f'FROM scan_results WHERE scan_id={_PH} ORDER BY confidence DESC LIMIT 30',
                (scan_id,)
            )
            rows = cur.fetchall() or []
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    if len(rows) < 3:
        return jsonify({'inconsistencies': []}), 200

    findings_text = '\n'.join(
        f'  [{_row_get(r, 2, "alert_level")}] {_row_get(r, 0, "issue_name")} ({_row_get(r, 1, "issue_category")})'
        for r in rows
    )
    prompt = (
        f'Analiza estos hallazgos del scanner Argus (scan #{scan_id}):\n{findings_text}\n\n'
        'Identifica SOLO inconsistencias reales, contradicciones o patrones inusuales entre los hallazgos. '
        'Ejemplos: "Tiene Forge instalado pero tambiÃ©n agentlib (inusual)", '
        '"Detectado Vape pero no hay historial de visitas a vape.gg", '
        '"MÃºltiples ghost clients instalados simultÃ¡neamente". '
        'Responde SOLO con JSON: {"inconsistencies": ["descripciÃ³n 1", "descripciÃ³n 2"]} '
        'Si no hay inconsistencias, devuelve {"inconsistencies": []}. '
        'MÃ¡ximo 3 inconsistencias. Sin texto extra fuera del JSON.'
    )
    system   = 'Eres un experto en anÃ¡lisis forense de hacks de Minecraft. Responde solo con JSON.'
    messages = [{'role': 'user', 'content': prompt}]
    raw = None
    if k_groq:
        raw = _ai_call_groq(k_groq, system, messages)
    if not raw and k_gemini:
        raw = _ai_call_gemini(k_gemini, system, [], prompt)
    if not raw and k_claude:
        raw = _ai_call_claude(k_claude, system, messages)
    if not raw:
        return jsonify({'inconsistencies': []}), 200
    try:
        import re as _re
        m = _re.search(r'\{[^{}]+\}', raw, _re.DOTALL)
        parsed = json.loads(m.group(0) if m else raw)
        return jsonify({'inconsistencies': list(parsed.get('inconsistencies', []))[:3]}), 200
    except Exception:
        return jsonify({'inconsistencies': []}), 200


_REVIEW_SECRET = os.environ.get('ARGUS_INTERNAL_REVIEW_SECRET', '').strip()
if not _REVIEW_SECRET:
    _REVIEW_SECRET = secrets.token_urlsafe(32)
    app.logger.warning('[security] ARGUS_INTERNAL_REVIEW_SECRET no configurado; generado secreto efímero de proceso')

@app.route('/internal/scan-review/<int:scan_id>')
def internal_scan_review(scan_id):
    token = request.args.get('token') or request.headers.get('X-Argus-Internal-Review-Secret') or ''
    if not secrets.compare_digest(str(token), _REVIEW_SECRET):
        return 'Acceso denegado', 403
    import traceback as _tb
    try:
        scan_data = {}
        results_rows = []
        with get_api_db_cursor() as cur:
            cur.execute(
                f'SELECT id, machine_name, minecraft_username, country, started_at, '
                f'total_files_scanned, issues_found, scan_duration, status, verdict '
                f'FROM scans WHERE id = {_PH}', (scan_id,)
            )
            scan = cur.fetchone()
            if not scan:
                return jsonify({'error': 'Scan no encontrado'}), 404
            scan_data = {
                'id':                  _row_get(scan, 0, 'id'),
                'machine':             _row_get(scan, 1, 'machine_name'),
                'minecraft_username':  _row_get(scan, 2, 'minecraft_username'),
                'country':             _row_get(scan, 3, 'country'),
                'started_at':          str(_row_get(scan, 4, 'started_at') or ''),
                'total_files_scanned': _row_get(scan, 5, 'total_files_scanned') or 0,
                'issues_found':        _row_get(scan, 6, 'issues_found') or 0,
                'scan_duration':       _row_get(scan, 7, 'scan_duration') or 0,
                'status':              _row_get(scan, 8, 'status'),
                'verdict':             _row_get(scan, 9, 'verdict'),
            }
            cur.execute(
                f'SELECT issue_name, issue_path, issue_category, alert_level, confidence '
                f'FROM scan_results WHERE scan_id = {_PH} ORDER BY confidence DESC',
                (scan_id,)
            )
            results_rows = cur.fetchall()

        scan_data['results_count'] = len(results_rows)
        scan_data['results'] = [
            {
                'name':       _row_get(r, 0, 'issue_name'),
                'path':       _row_get(r, 1, 'issue_path'),
                'category':   _row_get(r, 2, 'issue_category'),
                'level':      _row_get(r, 3, 'alert_level'),
                'confidence': _row_get(r, 4, 'confidence'),
            }
            for r in results_rows
        ]
        return jsonify(scan_data), 200
    except Exception as exc:
        return jsonify({'error': str(exc), 'trace': _tb.format_exc()}), 500


# â”€â”€ P3 #19 â€” ReputaciÃ³n cross-server por machine_id â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@app.route('/api/player_reputation/<string:machine_id>', methods=['GET'])
@login_required
def player_reputation(machine_id):
    """P3 #19 â€” ReputaciÃ³n histÃ³rica agregada de un jugador por machine_id.
    Devuelve veredictos, risk_score promedio y tipos de hallazgos mÃ¡s frecuentes.
    """
    if not machine_id or len(machine_id) > 128:
        return jsonify({'error': 'machine_id invÃ¡lido'}), 400
    try:
        with get_api_db_cursor() as cur:
            cur.execute(
                f'SELECT id, verdict, risk_score, issues_found, started_at'
                f' FROM scans WHERE machine_id={_PH} AND status={_PH} ORDER BY id DESC LIMIT 50',
                (machine_id, 'completed')
            )
            scans = cur.fetchall() or []
            if not scans:
                return jsonify({'machine_id': machine_id, 'scan_count': 0, 'reputation': None}), 200

            scan_ids = [_row_get(r, 0, 'id') for r in scans]
            verdicts  = [(_row_get(r, 1, 'verdict') or '').lower() for r in scans]
            risks     = [int(_row_get(r, 2, 'risk_score') or 0) for r in scans]

            hack_count  = verdicts.count('hack')
            clean_count = verdicts.count('clean')
            total       = len(scans)

            # Top issue types across all scans
            placeholders = ','.join([_PH] * len(scan_ids))
            cur.execute(
                f'SELECT issue_type, COUNT(*) as cnt FROM scan_results'
                f' WHERE scan_id IN ({placeholders})'
                f' GROUP BY issue_type ORDER BY cnt DESC LIMIT 10',
                scan_ids
            )
            top_types = [
                {'type': _row_get(r, 0, 'issue_type'), 'count': int(_row_get(r, 1, 'cnt') or 0)}
                for r in (cur.fetchall() or [])
            ]

        hack_rate   = round(hack_count / total, 3) if total else 0
        avg_risk    = round(sum(risks) / total, 1) if total else 0
        rep_label   = 'ALTO_RIESGO' if hack_rate >= 0.5 else 'SOSPECHOSO' if hack_rate >= 0.2 else 'LIMPIO'

        return jsonify({
            'machine_id':  machine_id,
            'scan_count':  total,
            'hack_count':  hack_count,
            'clean_count': clean_count,
            'hack_rate':   hack_rate,
            'avg_risk':    avg_risk,
            'reputation':  rep_label,
            'top_types':   top_types,
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# â”€â”€ P2 #31 â€” TF-IDF sobre nombres de archivos en scans histÃ³ricos â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@app.route('/api/ml/tfidf-names', methods=['GET'])
@login_required
def ml_tfidf_names():
    """P2 #31 â€” TF-IDF sobre issue_name de scans con veredicto hack.
    Retorna los tÃ©rminos mÃ¡s discriminantes entre scans hack vs clean.
    """
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        import numpy as np

        with get_api_db_cursor() as cur:
            cur.execute(
                f'SELECT sr.issue_name, s.verdict FROM scan_results sr'
                f' JOIN scans s ON sr.scan_id=s.id'
                f' WHERE s.verdict IN ({_PH},{_PH}) AND sr.issue_name IS NOT NULL'
                f' ORDER BY sr.id DESC LIMIT 5000',
                ('hack', 'clean')
            )
            rows = cur.fetchall() or []

        if len(rows) < 20:
            return jsonify({'error': 'Insuficientes datos para TF-IDF'}), 400

        docs    = [str(_row_get(r, 0, 'issue_name') or '') for r in rows]
        labels  = [str(_row_get(r, 1, 'verdict') or '') for r in rows]

        vect = TfidfVectorizer(max_features=200, ngram_range=(1, 2), min_df=2)
        X    = vect.fit_transform(docs)

        feature_names = vect.get_feature_names_out()
        hack_mask  = np.array([l == 'hack'  for l in labels])
        clean_mask = np.array([l == 'clean' for l in labels])

        hack_mean  = X[hack_mask].mean(axis=0).A1  if hack_mask.any()  else np.zeros(len(feature_names))
        clean_mean = X[clean_mask].mean(axis=0).A1 if clean_mask.any() else np.zeros(len(feature_names))
        diff       = hack_mean - clean_mean

        top_idx    = diff.argsort()[::-1][:30]
        top_terms  = [{'term': feature_names[i], 'hack_bias': round(float(diff[i]), 4)} for i in top_idx]

        return jsonify({'top_hack_terms': top_terms, 'samples': len(rows)}), 200
    except ImportError:
        return jsonify({'error': 'sklearn no disponible'}), 503
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# â”€â”€ P3 #32 â€” Feature store: precomputar features por machine_id â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@app.route('/api/ml/feature-store/<string:machine_id>', methods=['GET'])
@login_required
def feature_store_get(machine_id):
    """P3 #32 â€” Devuelve features precalculadas para un machine_id.
    Si no estÃ¡n en cachÃ©, las calcula y las guarda para futuras consultas.
    """
    if not machine_id or len(machine_id) > 128:
        return jsonify({'error': 'machine_id invÃ¡lido'}), 400
    try:
        with get_api_db_cursor() as cur:
            # Intentar leer de cachÃ© (tabla feature_cache si existe)
            try:
                cur.execute(
                    f'SELECT features, updated_at FROM feature_cache WHERE machine_id={_PH}',
                    (machine_id,)
                )
                cached = cur.fetchone()
                if cached:
                    import json as _j
                    feat_raw = _row_get(cached, 0, 'features') or '{}'
                    updated  = str(_row_get(cached, 1, 'updated_at') or '')
                    features = _j.loads(feat_raw) if isinstance(feat_raw, str) else feat_raw
                    return jsonify({'machine_id': machine_id, 'features': features,
                                    'cached': True, 'updated_at': updated}), 200
            except Exception:
                pass  # tabla no existe aÃºn â†’ calcular igualmente

            # Calcular features desde cero
            cur.execute(
                f'SELECT verdict, risk_score, issues_found, scan_duration'
                f' FROM scans WHERE machine_id={_PH} AND status={_PH} ORDER BY id DESC LIMIT 20',
                (machine_id, 'completed')
            )
            rows = cur.fetchall() or []
            if not rows:
                return jsonify({'machine_id': machine_id, 'features': None, 'cached': False}), 200

            verdicts = [(_row_get(r, 0, 'verdict') or '').lower() for r in rows]
            risks    = [float(_row_get(r, 1, 'risk_score') or 0) for r in rows]
            issues   = [int(_row_get(r, 2, 'issues_found') or 0) for r in rows]
            durs     = [float(_row_get(r, 3, 'scan_duration') or 0) for r in rows]

            features = {
                'scan_count':       len(rows),
                'hack_rate':        round(verdicts.count('hack') / len(rows), 3),
                'avg_risk':         round(sum(risks) / len(risks), 1),
                'max_risk':         max(risks),
                'avg_issues':       round(sum(issues) / len(issues), 1),
                'avg_duration':     round(sum(durs) / len(durs), 1),
                'recent_hack':      int(verdicts[0] == 'hack') if verdicts else 0,
            }

            # Guardar en cachÃ© si la tabla existe
            try:
                import json as _j
                cur.execute(
                    f'INSERT INTO feature_cache (machine_id, features, updated_at)'
                    f' VALUES ({_PH},{_PH},NOW())'
                    f' ON CONFLICT (machine_id) DO UPDATE SET features={_PH}, updated_at=NOW()',
                    (machine_id, _j.dumps(features), _j.dumps(features))
                )
            except Exception:
                pass

        return jsonify({'machine_id': machine_id, 'features': features, 'cached': False}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# â”€â”€ P3 #24 â€” Preguntas de seguimiento para el staff â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@app.route('/api/staff/ai/followup-questions/<int:scan_id>', methods=['GET'])
@login_required
def ai_followup_questions(scan_id):
    """P3 #24 â€” Genera preguntas de seguimiento que el staff deberÃ­a hacerle al jugador."""
    try:
        with get_api_db_cursor() as cur:
            cur.execute(
                f'SELECT machine_name, minecraft_username, risk_score, issues_found, verdict'
                f' FROM scans WHERE id={_PH}', (scan_id,)
            )
            row = cur.fetchone()
            if not row:
                return jsonify({'error': 'Scan no encontrado'}), 404
            machine   = _row_get(row, 0, 'machine_name') or 'N/A'
            username  = _row_get(row, 1, 'minecraft_username') or 'N/A'
            risk      = int(_row_get(row, 2, 'risk_score') or 0)
            n_issues  = int(_row_get(row, 3, 'issues_found') or 0)
            verdict   = _row_get(row, 4, 'verdict') or 'pending'

            cur.execute(
                f'SELECT issue_name, issue_category, alert_level, confidence'
                f' FROM scan_results WHERE scan_id={_PH} ORDER BY confidence DESC LIMIT 15',
                (scan_id,)
            )
            results = cur.fetchall() or []

        findings_summary = '\n'.join(
            f"- [{_row_get(r,2,'alert_level')}] {_row_get(r,0,'issue_name')} ({_row_get(r,1,'issue_category')})"
            for r in results
        )

        prompt = (
            f"Eres un moderador senior de Minecraft analizando un reporte de anti-cheat.\n\n"
            f"Jugador: {username} | MÃ¡quina: {machine}\n"
            f"Risk Score: {risk}/100 | Hallazgos: {n_issues} | Veredicto actual: {verdict}\n\n"
            f"Hallazgos principales:\n{findings_summary}\n\n"
            f"Genera 5 preguntas especÃ­ficas y directas que el staff deberÃ­a hacerle al jugador "
            f"para clarificar los hallazgos. Las preguntas deben ser concretas, basadas en los "
            f"hallazgos encontrados, y ayudar a distinguir entre falsos positivos y hacks reales. "
            f"Formato: lista numerada, sin explicaciones adicionales."
        )

        ai_key = os.environ.get('ANTHROPIC_API_KEY', '')
        questions_text = None

        if ai_key:
            resp = _ai_call_claude(
                ai_key,
                "Eres un moderador experto de servidores Minecraft.",
                [{"role": "user", "content": prompt}]
            )
            questions_text = resp

        if not questions_text:
            groq_key = os.environ.get('GROQ_API_KEY', '')
            if groq_key:
                resp = _ai_call_groq(
                    groq_key,
                    "Eres un moderador experto de servidores Minecraft.",
                    [{"role": "user", "content": prompt}]
                )
                questions_text = resp

        if not questions_text:
            return jsonify({'error': 'No hay API de IA configurada'}), 503

        questions = [q.strip() for q in questions_text.strip().split('\n') if q.strip() and q.strip()[0].isdigit()]
        return jsonify({'scan_id': scan_id, 'questions': questions, 'raw': questions_text}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# â”€â”€ P2 #33 â€” DistribuciÃ³n de tamaÃ±os de archivos sospechosos â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@app.route('/api/ml/size-distribution', methods=['GET'])
@login_required
def ml_size_distribution():
    """P2 #33 â€” Analiza distribuciÃ³n de tamaÃ±os (confidence proxy) de hallazgos hack vs clean.
    Detecta si hay un rango de tamaÃ±o/confidence que discrimina bien entre categorÃ­as.
    """
    try:
        with get_api_db_cursor() as cur:
            cur.execute(
                f'SELECT sr.confidence, sr.alert_level, s.verdict'
                f' FROM scan_results sr JOIN scans s ON sr.scan_id=s.id'
                f' WHERE s.verdict IN ({_PH},{_PH}) AND sr.confidence IS NOT NULL'
                f' ORDER BY sr.id DESC LIMIT 10000',
                ('hack', 'clean')
            )
            rows = cur.fetchall() or []

        if len(rows) < 20:
            return jsonify({'error': 'Insuficientes datos'}), 400

        buckets = {}
        for r in rows:
            conf    = float(_row_get(r, 0, 'confidence') or 0)
            verdict = str(_row_get(r, 2, 'verdict') or '')
            bucket  = f'{int(conf * 10) * 10}-{int(conf * 10) * 10 + 10}%'
            if bucket not in buckets:
                buckets[bucket] = {'hack': 0, 'clean': 0, 'total': 0}
            buckets[bucket][verdict] = buckets[bucket].get(verdict, 0) + 1
            buckets[bucket]['total'] += 1

        for b in buckets.values():
            t = b['total']
            b['hack_rate'] = round(b.get('hack', 0) / t, 3) if t else 0

        sorted_buckets = sorted(buckets.items())
        return jsonify({'buckets': [{'range': k, **v} for k, v in sorted_buckets],
                        'total_samples': len(rows)}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# â”€â”€ P2 #40 â€” A/B testing de filtros con veredictos histÃ³ricos â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@app.route('/api/ml/ab-test', methods=['GET'])
@login_required
def ml_ab_test():
    """P2 #40 â€” Compara dos conjuntos de alert_level thresholds usando veredictos histÃ³ricos.
    threshold_a y threshold_b son valores 0â€“100. Calcula precision/recall para cada uno.
    """
    try:
        threshold_a = int(request.args.get('threshold_a', 50))
        threshold_b = int(request.args.get('threshold_b', 70))

        with get_api_db_cursor() as cur:
            cur.execute(
                f'SELECT risk_score, verdict FROM scans'
                f' WHERE verdict IN ({_PH},{_PH}) AND risk_score IS NOT NULL'
                f' ORDER BY id DESC LIMIT 2000',
                ('hack', 'clean')
            )
            rows = cur.fetchall() or []

        if len(rows) < 20:
            return jsonify({'error': 'Insuficientes datos para A/B test'}), 400

        def _metrics(threshold):
            tp = fp = tn = fn = 0
            for r in rows:
                score   = int(_row_get(r, 0, 'risk_score') or 0)
                verdict = str(_row_get(r, 1, 'verdict') or '')
                pred_hack = score >= threshold
                real_hack = verdict == 'hack'
                if pred_hack and real_hack:  tp += 1
                elif pred_hack:              fp += 1
                elif real_hack:              fn += 1
                else:                        tn += 1
            precision = round(tp / (tp + fp), 3) if (tp + fp) > 0 else 0
            recall    = round(tp / (tp + fn), 3) if (tp + fn) > 0 else 0
            f1        = round(2 * precision * recall / (precision + recall), 3) if (precision + recall) > 0 else 0
            accuracy  = round((tp + tn) / len(rows), 3) if rows else 0
            return {'threshold': threshold, 'tp': tp, 'fp': fp, 'tn': tn, 'fn': fn,
                    'precision': precision, 'recall': recall, 'f1': f1, 'accuracy': accuracy}

        return jsonify({
            'a': _metrics(threshold_a),
            'b': _metrics(threshold_b),
            'samples': len(rows),
            'winner': 'a' if _metrics(threshold_a)['f1'] >= _metrics(threshold_b)['f1'] else 'b',
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# â”€â”€ P3 #2 â€” Embeddings semÃ¡nticos ligeros (TF-IDF cosine, sin sentence-transformers) â”€â”€

@app.route('/api/ml/semantic-similarity', methods=['POST'])
@login_required
def ml_semantic_similarity():
    """P3 #2 â€” Calcula similitud semÃ¡ntica entre un nombre de archivo y corpus de hacks conocidos.
    Usa TF-IDF + cosine similarity como aproximaciÃ³n ligera a embeddings.
    Body: { name: str, top_n: int }
    """
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        import numpy as np

        data  = request.json or {}
        name  = str(data.get('name') or '').strip()
        top_n = min(int(data.get('top_n') or 5), 20)
        if not name:
            return jsonify({'error': 'name requerido'}), 400

        HACK_CORPUS = [
            'liquidbounce ghost client', 'wurst hacked client', 'meteor client',
            'sigma client cheat', 'aristois hack', 'weave loader injection',
            'jigsaw client', 'novoline hacked', 'inertia client',
            'entropy hack', 'drip client', 'bleach hack', 'rusherhack',
            'rise client hack', 'kilo client cheat', 'aimbot killaura',
            'autoclick macro mouse', 'esp wallhack xray', 'scaffold fly speed',
            'java agent injection', 'bytecode injection mixin',
            'nodus client hack', 'vape client hacked', 'impact client',
            'gorilla tag mod hack', 'triggerbot aimassist',
        ]

        docs = HACK_CORPUS + [name]
        vect = TfidfVectorizer(analyzer='char_wb', ngram_range=(2, 4))
        X    = vect.fit_transform(docs)

        query_vec = X[-1]
        corpus_X  = X[:-1]
        sims      = cosine_similarity(query_vec, corpus_X)[0]
        top_idx   = sims.argsort()[::-1][:top_n]

        results = [
            {'corpus_entry': HACK_CORPUS[i], 'similarity': round(float(sims[i]), 4)}
            for i in top_idx if sims[i] > 0
        ]
        max_sim = float(sims.max()) if len(sims) else 0
        is_suspicious = max_sim >= 0.35

        return jsonify({
            'name': name,
            'max_similarity': round(max_sim, 4),
            'is_suspicious': is_suspicious,
            'top_matches': results,
        }), 200
    except ImportError:
        return jsonify({'error': 'sklearn no disponible'}), 503
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# â”€â”€ P3 #34 â€” Pipeline de ingesta de inteligencia de hacks (scraper) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@app.route('/api/admin/ingest-hack-intel', methods=['POST'])
@login_required
def ingest_hack_intel():
    """P3 #34 â€” Scraper pasivo de inteligencia sobre nuevos hack clients.
    Consulta fuentes pÃºblicas (GitHub releases, SpigotMC) para detectar nuevos names/hashes.
    Requiere rol admin. Resultados se guardan en hack_intel_log.
    """
    if not session.get('is_admin'):
        return jsonify({'error': 'Solo administradores'}), 403
    try:
        import threading as _thr
        results = []

        # Source 1: known GitHub repos â€” buscar release names de hack clients conocidos
        GITHUB_REPOS = [
            ('CCBlueX',   'LiquidBounce'),
            ('MeteorDevelopment', 'meteor-client'),
            ('Wurst-Imperium', 'Wurst7'),
        ]
        for owner, repo in GITHUB_REPOS:
            try:
                resp = requests.get(
                    f'https://api.github.com/repos/{owner}/{repo}/releases/latest',
                    headers={'Accept': 'application/vnd.github.v3+json'},
                    timeout=6,
                )
                if resp.status_code == 200:
                    rel = resp.json()
                    tag  = rel.get('tag_name', '')
                    name = rel.get('name', '')
                    assets = [a.get('name', '') for a in rel.get('assets', []) if a.get('name', '').endswith('.jar')]
                    results.append({
                        'source': f'github:{owner}/{repo}',
                        'version': tag,
                        'release_name': name,
                        'jar_assets': assets[:5],
                    })
            except Exception:
                pass

        # Source 2: MalwareBazaar tag search for minecraft-related malware
        try:
            mb_resp = requests.post(
                'https://mb.api.abuse.ch/api/v1/',
                data={'query': 'get_taginfo', 'tag': 'minecraft', 'limit': 10},
                timeout=6,
            )
            if mb_resp.ok:
                mb_data = mb_resp.json()
                if mb_data.get('query_status') == 'ok':
                    for entry in (mb_data.get('data') or [])[:5]:
                        results.append({
                            'source': 'malwarebazaar',
                            'sha256': entry.get('sha256_hash', ''),
                            'file_name': entry.get('file_name', ''),
                            'tags': entry.get('tags', []),
                        })
        except Exception:
            pass

        return jsonify({'ingested': len(results), 'results': results}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# â”€â”€ P3 #14 â€” ExtracciÃ³n de IOCs de texto libre â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@app.route('/api/staff/extract-iocs', methods=['POST'])
def extract_iocs():
    """Extrae IPs, hashes, dominios y rutas de un texto libre del staff."""
    import re as _re
    if not _is_staff_authenticated():
        return jsonify({'error': 'unauthorized'}), 403
    data = request.get_json(silent=True) or {}
    text = data.get('text', '')
    if not text:
        return jsonify({'error': 'text required'}), 400
    if len(text) > 100_000:
        return jsonify({'error': 'text too long (max 100000 chars)'}), 400

    # IPv4
    raw_ips = _re.findall(
        r'\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b', text)
    def _is_public(ip):
        try:
            a, b = int(ip.split('.')[0]), int(ip.split('.')[1])
            return not (a == 10 or a == 127 or
                        (a == 172 and 16 <= b <= 31) or
                        (a == 192 and b == 168))
        except Exception:
            return False
    all_ips    = list(dict.fromkeys(raw_ips))
    public_ips = [ip for ip in all_ips if _is_public(ip)]

    # Hashes (SHA-256 = 64 hex, SHA-1 = 40, MD5 = 32 â€” en orden para evitar subsets)
    sha256 = list(dict.fromkeys(_re.findall(r'\b[0-9a-fA-F]{64}\b', text)))
    # Quitar hashes SHA-256 para no incluirlos en SHA-1/MD5
    text_no256 = _re.sub(r'\b[0-9a-fA-F]{64}\b', '', text)
    sha1 = list(dict.fromkeys(_re.findall(r'\b[0-9a-fA-F]{40}\b', text_no256)))
    text_no4040 = _re.sub(r'\b[0-9a-fA-F]{40}\b', '', text_no256)
    md5  = list(dict.fromkeys(_re.findall(r'\b[0-9a-fA-F]{32}\b', text_no4040)))

    # Dominios (TLDs comunes)
    domains = list(dict.fromkeys(_re.findall(
        r'\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+(?:com|net|org|io|xyz|gg|ru|'
        r'cn|me|to|cc|tv|pro|online|dev|app|cloud|site)\b', text, _re.IGNORECASE
    )))

    # Rutas Windows
    paths = list(dict.fromkeys(_re.findall(
        r'[A-Za-z]:\\(?:[^\\\s"<>|]+\\)*[^\\\s"<>|]+', text)))[:30]

    # Archivos JAR
    jars = list(dict.fromkeys(_re.findall(r'\b[\w\-. ]+\.jar\b', text, _re.IGNORECASE)))[:20]

    total = len(all_ips) + len(sha256) + len(sha1) + len(md5) + len(domains) + len(paths) + len(jars)
    return jsonify({
        'ips':        {'public': public_ips, 'all': all_ips},
        'hashes':     {'sha256': sha256, 'sha1': sha1, 'md5': md5},
        'domains':    domains,
        'file_paths': paths,
        'jar_files':  jars,
        'total':      total,
    }), 200


# â”€â”€ P2 #10 â€” AbuseIPDB â€” reputaciÃ³n de IPs â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@app.route('/api/ml/check-ip-reputation', methods=['POST'])
def check_ip_reputation():
    """Consulta AbuseIPDB para obtener el historial de abuso de una IP.
    Requiere la variable de entorno ABUSEIPDB_API_KEY (tier gratuito: 1000 req/dÃ­a).
    """
    if not _is_staff_authenticated():
        return jsonify({'error': 'unauthorized'}), 403
    api_key = os.environ.get('ABUSEIPDB_API_KEY', '').strip()
    if not api_key:
        return jsonify({'error': 'ABUSEIPDB_API_KEY not configured on server'}), 503
    data = request.get_json(silent=True) or {}
    ip = data.get('ip', '').strip()
    if not ip:
        return jsonify({'error': 'ip required'}), 400
    try:
        resp = requests.get(
            'https://api.abuseipdb.com/api/v2/check',
            headers={'Key': api_key, 'Accept': 'application/json'},
            params={'ipAddress': ip, 'maxAgeInDays': 90},
            timeout=8,
        )
        if not resp.ok:
            return jsonify({'error': f'AbuseIPDB returned HTTP {resp.status_code}'}), 502
        d = resp.json().get('data', {})
        score = d.get('abuseConfidenceScore', 0)
        label = 'LIMPIO' if score < 25 else ('SOSPECHOSO' if score < 75 else 'MALICIOSO')
        return jsonify({
            'ip':            ip,
            'abuse_score':   score,
            'label':         label,
            'country':       d.get('countryCode', ''),
            'isp':           d.get('isp', ''),
            'domain':        d.get('domain', ''),
            'usage_type':    d.get('usageType', ''),
            'total_reports': d.get('totalReports', 0),
            'last_reported': d.get('lastReportedAt', ''),
            'is_tor':        d.get('isTor', False),
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# â”€â”€ P2 #9 â€” IP ASN / hosting check vÃ­a ip-api.com (gratis, sin API key) â”€â”€â”€â”€â”€â”€

@app.route('/api/ml/check-ip-asn', methods=['POST'])
def check_ip_asn():
    """Consulta ip-api.com para obtener ASN, ISP y si la IP es hosting/proxy.
    AproximaciÃ³n gratuita de Shodan: detecta IPs de proveedores tÃ­picos de C2.
    LÃ­mite: 45 req/min sin API key.
    """
    if not _is_staff_authenticated():
        return jsonify({'error': 'unauthorized'}), 403
    data = request.get_json(silent=True) or {}
    ip = data.get('ip', '').strip()
    if not ip:
        return jsonify({'error': 'ip required'}), 400

    # ASNs/orgs frecuentemente asociadas a hosting de C2 / servidores privados de hacks
    SUSPICIOUS_ORGS = {
        'digitalocean', 'vultr', 'ovh', 'hetzner', 'linode', 'leaseweb',
        'm247', 'frantech', 'ponynet', 'buyvm', 'privatelayer', 'psychz',
        'serverius', 'hostinger', 'contabo', 'serverspace', 'greencloud',
        'datacamp', 'alexhost', 'combahton',
    }
    try:
        resp = requests.get(
            f'http://ip-api.com/json/{ip}',
            params={'fields': 'status,message,country,regionName,city,isp,org,as,proxy,hosting,query'},
            timeout=6,
        )
        if not resp.ok:
            return jsonify({'error': f'ip-api.com HTTP {resp.status_code}'}), 502
        d = resp.json()
        if d.get('status') != 'success':
            return jsonify({'error': d.get('message', 'lookup failed')}), 400

        org_lower = (d.get('org', '') + ' ' + d.get('isp', '') + ' ' + d.get('as', '')).lower()
        is_suspicious_org = any(s in org_lower for s in SUSPICIOUS_ORGS)
        is_hosting  = d.get('hosting', False)
        is_proxy    = d.get('proxy',   False)
        risk_flags  = []
        if is_hosting:        risk_flags.append('hosting_provider')
        if is_proxy:          risk_flags.append('proxy_vpn')
        if is_suspicious_org: risk_flags.append('c2_hosting_asn')

        label = 'LIMPIO'
        if risk_flags:
            label = 'SOSPECHOSO' if len(risk_flags) == 1 else 'ALTO_RIESGO'

        return jsonify({
            'ip':          ip,
            'label':       label,
            'risk_flags':  risk_flags,
            'country':     d.get('country', ''),
            'region':      d.get('regionName', ''),
            'city':        d.get('city', ''),
            'isp':         d.get('isp', ''),
            'org':         d.get('org', ''),
            'asn':         d.get('as', ''),
            'is_hosting':  is_hosting,
            'is_proxy':    is_proxy,
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# â”€â”€ P3 #33 â€” SimHash: similitud de archivos por hash local â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@app.route('/api/ml/simhash', methods=['POST'])
def simhash_similarity():
    """Calcula la similitud entre el hash de un archivo y la base de datos de hacks
    usando SimHash (Hamming distance sobre SHA-256 bits). Sin modelos de ML externos.
    TambiÃ©n acepta mÃºltiples hashes para encontrar clusters de archivos similares.
    """
    if not _is_staff_authenticated():
        return jsonify({'error': 'unauthorized'}), 403
    data = request.get_json(silent=True) or {}
    hashes = data.get('hashes', [])
    if isinstance(hashes, str):
        hashes = [hashes]
    if not hashes or len(hashes) > 100:
        return jsonify({'error': 'hashes list required (max 100)'}), 400

    def _hex_to_bits(h: str) -> int:
        try:
            return int(h[:16], 16)  # primeros 64 bits del SHA-256
        except Exception:
            return 0

    def _hamming(a: int, b: int) -> int:
        return bin(a ^ b).count('1')

    try:
        with get_api_db_cursor() as cur:
            # Obtener hashes de scans con veredicto "hack" de los Ãºltimos 90 dÃ­as
            cur.execute(f'''
                SELECT DISTINCT sr.file_hash
                FROM scan_results sr
                JOIN scans s ON sr.scan_id = s.id
                WHERE s.verdict = 'hack'
                  AND sr.file_hash IS NOT NULL
                  AND LENGTH(sr.file_hash) = 64
                  AND s.created_at >= NOW() - INTERVAL '90 days'
                LIMIT 2000
            ''')
            rows = cur.fetchall()
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    known_hack_bits = [_hex_to_bits(r[0] if isinstance(r, (list, tuple)) else r.get('file_hash', ''))
                       for r in rows if r]

    results = []
    for h in hashes:
        if len(h) != 64:
            results.append({'hash': h, 'error': 'not SHA-256'})
            continue
        qbits = _hex_to_bits(h)
        if not known_hack_bits:
            results.append({'hash': h, 'min_hamming': None, 'similar_hacks': 0, 'is_suspicious': False})
            continue
        distances = [_hamming(qbits, kb) for kb in known_hack_bits]
        min_dist  = min(distances)
        near_count = sum(1 for d in distances if d <= 8)  # â‰¤8 bits diferentes de 64 = muy similar
        is_suspicious = min_dist <= 12 or near_count >= 3
        results.append({
            'hash':          h,
            'min_hamming':   min_dist,
            'similar_hacks': near_count,
            'is_suspicious': is_suspicious,
            'similarity_pct': round((64 - min_dist) / 64 * 100, 1),
        })

    return jsonify({'results': results, 'known_hack_hashes': len(known_hack_bits)}), 200


# â”€â”€ P5 #30 â€” System health dashboard â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@app.route('/api/admin/health', methods=['GET'])
@login_required
def system_health():
    """Dashboard de salud del sistema: BD, cola de scans, uptime, errores recientes."""
    import time as _t
    health = {}
    # BD latency
    t0 = _t.time()
    try:
        with get_api_db_cursor() as cur:
            cur.execute('SELECT 1')
        health['db_latency_ms'] = round((_t.time() - t0) * 1000, 1)
        health['db_ok'] = True
    except Exception as e:
        health['db_ok'] = False
        health['db_error'] = str(e)
        health['db_latency_ms'] = None
    # Scans en cola/recientes
    try:
        with get_api_db_cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM scans WHERE started_at > NOW() - INTERVAL '1 hour'")
            health['scans_last_hour'] = (cur.fetchone() or [0])[0]
            cur.execute("SELECT COUNT(*) FROM scans WHERE started_at > NOW() - INTERVAL '24 hours'")
            health['scans_last_24h'] = (cur.fetchone() or [0])[0]
            cur.execute('SELECT COUNT(*) FROM scans')
            health['scans_total'] = (cur.fetchone() or [0])[0]
    except Exception:
        health['scans_last_hour'] = None
    # Errores recientes (tabla app_meta si la tenemos)
    try:
        with get_api_db_cursor() as cur:
            cur.execute("SELECT value FROM app_meta WHERE key = 'last_error' LIMIT 1")
            row = cur.fetchone()
            health['last_error'] = (row[0] if isinstance(row, (list,tuple)) else row.get('value')) if row else None
    except Exception:
        health['last_error'] = None
    # VersiÃ³n
    health['argus_version'] = _ARGUS_VERSION
    health['timestamp'] = datetime.datetime.utcnow().isoformat() + 'Z'
    return jsonify(health), 200


# â”€â”€ P5 #17 â€” Staff Audit Log â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _log_staff_action(action: str, target_scan_id=None, detail: str = '', user_id=None):
    """Registra una acciÃ³n del staff en la tabla staff_audit_log."""
    uid = user_id or session.get('user_id')
    if not uid:
        return
    try:
        with get_api_db_cursor() as cur:
            cur.execute('''
                CREATE TABLE IF NOT EXISTS staff_audit_log (
                    id          SERIAL PRIMARY KEY,
                    user_id     INTEGER NOT NULL,
                    action      VARCHAR(100) NOT NULL,
                    scan_id     INTEGER,
                    detail      TEXT,
                    ip_address  VARCHAR(45),
                    created_at  TIMESTAMP DEFAULT NOW()
                )
            ''')
            cur.execute(
                'INSERT INTO staff_audit_log (user_id, action, scan_id, detail, ip_address) '
                'VALUES (%s, %s, %s, %s, %s)',
                (uid, action[:100], target_scan_id, detail[:500] if detail else None,
                 request.remote_addr if request else None)
            )
    except Exception as e:
        print(f'[AuditLog] Error: {e}')


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Pack 32 â€” F#54/F#55/F#60 endpoints
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

@app.route('/api/staff/my-trust', methods=['GET'])
@login_required
def get_my_trust():
    """Trust score del staff logueado (F#54).
    Cualquier staff lo ve para sÃ­ mismo; admin ve cualquiera.
    """
    if not _AI_TRUST_AVAILABLE:
        return jsonify({'available': False, 'reason': 'ai_trust no cargado'}), 200
    user_id = session.get('user_id')
    qs_uid  = request.args.get('user_id', type=int)
    if qs_uid and qs_uid != user_id and not is_admin(user_id):
        return jsonify({'error': 'Solo admin puede ver trust de otros'}), 403
    target = qs_uid or user_id
    try:
        with get_api_db_cursor() as cur:
            data = _ai_trust.get_staff_trust(cur, target)
        # Bayesian alpha/beta para info
        a = data.get('agreements', 0) + 2 * data.get('confirmed_correct', 0)
        b = data.get('disagreements', 0) + 2 * data.get('confirmed_wrong', 0)
        return jsonify({
            'available':         True,
            'user_id':           target,
            'trust_score':       data.get('trust_score', 50.0),
            'verdicts_total':    data.get('verdicts_total', 0),
            'agreements':        data.get('agreements', 0),
            'disagreements':     data.get('disagreements', 0),
            'overturns_to_clean': data.get('overturns_to_clean', 0),
            'overturns_to_hack':  data.get('overturns_to_hack', 0),
            'confirmed_correct': data.get('confirmed_correct', 0),
            'confirmed_wrong':   data.get('confirmed_wrong', 0),
            'last_verdict_at':   data.get('updated_at', ''),
            'bayesian':          {'alpha': a + 1, 'beta': b + 1},
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/staff-trust', methods=['GET'])
@login_required
def get_admin_staff_trust():
    """Ranking global de staff_trust (admin only)."""
    if not is_admin(session.get('user_id')):
        return jsonify({'error': 'Acceso denegado'}), 403
    if not _AI_TRUST_AVAILABLE:
        return jsonify({'available': False, 'rows': []}), 200
    try:
        with get_api_db_cursor() as cur:
            _ai_trust.ensure_trust_tables(cur)
            cur.execute(
                'SELECT user_id, verdicts_total, agreements, disagreements, '
                'overturns_to_clean, overturns_to_hack, confirmed_correct, '
                'confirmed_wrong, trust_score, updated_at '
                'FROM staff_trust ORDER BY verdicts_total DESC, trust_score DESC '
                'LIMIT 200'
            )
            rows = cur.fetchall() or []
            out = []
            for r in rows:
                uid = _row_get(r, 0, 'user_id')
                out.append({
                    'user_id':           uid,
                    'verdicts_total':    int(_row_get(r, 1, 'verdicts_total')     or 0),
                    'agreements':        int(_row_get(r, 2, 'agreements')         or 0),
                    'disagreements':     int(_row_get(r, 3, 'disagreements')      or 0),
                    'overturns_to_clean': int(_row_get(r, 4, 'overturns_to_clean') or 0),
                    'overturns_to_hack':  int(_row_get(r, 5, 'overturns_to_hack')  or 0),
                    'confirmed_correct':  int(_row_get(r, 6, 'confirmed_correct')  or 0),
                    'confirmed_wrong':    int(_row_get(r, 7, 'confirmed_wrong')    or 0),
                    'trust_score':        float(_row_get(r, 8, 'trust_score')      or 50.0),
                    'updated_at':         str(_row_get(r, 9, 'updated_at')         or ''),
                })
            # Enriquecer con username si tenemos auth.list_users
            try:
                user_map = {u.get('id'): u.get('username') for u in (list_users() or [])}
                for o in out:
                    o['username'] = user_map.get(o['user_id'], f'user_{o["user_id"]}')
            except Exception:
                for o in out:
                    o['username'] = f'user_{o["user_id"]}'
        return jsonify({'available': True, 'rows': out, 'count': len(out)}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/company-cooldowns', methods=['GET'])
@login_required
def get_admin_company_cooldowns():
    """Lista de empresas con cooldown activo o reciente (admin only)."""
    if not is_admin(session.get('user_id')):
        return jsonify({'error': 'Acceso denegado'}), 403
    if not _AI_TRUST_AVAILABLE:
        return jsonify({'available': False, 'rows': []}), 200
    try:
        with get_api_db_cursor() as cur:
            _ai_trust.ensure_trust_tables(cur)
            cur.execute(
                'SELECT company_id, fp_count_24h, overturn_count_24h, '
                'threshold_bump, cooldown_until, last_event_at, updated_at '
                'FROM company_fp_cooldown '
                'ORDER BY threshold_bump DESC, last_event_at DESC '
                'LIMIT 200'
            )
            rows = cur.fetchall() or []
            out = []
            for r in rows:
                cid = _row_get(r, 0, 'company_id')
                out.append({
                    'company_id':         cid,
                    'fp_count_24h':       int(_row_get(r, 1, 'fp_count_24h')       or 0),
                    'overturn_count_24h': int(_row_get(r, 2, 'overturn_count_24h') or 0),
                    'threshold_bump':     int(_row_get(r, 3, 'threshold_bump')     or 0),
                    'cooldown_until':     str(_row_get(r, 4, 'cooldown_until')     or ''),
                    'last_event_at':      str(_row_get(r, 5, 'last_event_at')      or ''),
                    'updated_at':         str(_row_get(r, 6, 'updated_at')         or ''),
                })
            try:
                companies = list_companies() or []
                cmap = {c.get('id'): c.get('name') for c in companies}
                for o in out:
                    o['company_name'] = cmap.get(o['company_id'], f'company_{o["company_id"]}')
            except Exception:
                for o in out:
                    o['company_name'] = f'company_{o["company_id"]}'
        return jsonify({'available': True, 'rows': out, 'count': len(out)}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/staff-trust/confirm', methods=['POST'])
@login_required
def confirm_staff_trust():
    """Admin confirma o desmiente una decisiÃ³n post-facto del staff
    (F#54 â€” confirmed_correct / confirmed_wrong pesan doble en el score).

    body: {user_id: int, was_correct: bool}
    """
    if not is_admin(session.get('user_id')):
        return jsonify({'error': 'Acceso denegado'}), 403
    if not _AI_TRUST_AVAILABLE:
        return jsonify({'error': 'ai_trust no cargado'}), 503
    data = request.get_json(silent=True) or {}
    target = data.get('user_id')
    was_correct = bool(data.get('was_correct', False))
    if not target:
        return jsonify({'error': 'user_id requerido'}), 400
    try:
        with get_api_db_cursor() as cur:
            _ai_trust.confirm_staff_decision(cur, int(target), was_correct)
        try:
            _log_staff_action('staff_trust_confirm',
                              detail=f'target={target} was_correct={was_correct}')
        except Exception:
            pass
        return jsonify({'ok': True}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Pack 35 â€” AI Quality Dashboard + Adaptive Thresholds + RF retrain
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

@app.route('/api/ai-quality/metrics', methods=['GET'])
@login_required
def ai_quality_metrics():
    """MÃ©tricas de calidad del ensemble: precision/recall/f1/drift.
    Scope: si el usuario es admin, se puede pasar ?company_id=N para
    mÃ©tricas globales o de una empresa puntual; non-admin siempre ve
    solo su propia empresa.
    """
    if not _AI_QUALITY_AVAILABLE:
        return jsonify({'available': False}), 200
    user_id    = session.get('user_id')
    company_id = session.get('company_id')
    qs_company = request.args.get('company_id', type=int)
    is_glob    = is_admin(user_id)
    if qs_company and not is_glob and qs_company != company_id:
        return jsonify({'error': 'Solo admin puede ver otras empresas'}), 403
    target_company = qs_company if is_glob else company_id
    try:
        since_days = max(7, min(365, int(request.args.get('since_days', 90))))
    except Exception:
        since_days = 90
    try:
        with get_api_db_cursor() as cur:
            metrics = _ai_quality.get_quality_metrics(
                cur, company_id=target_company, since_days=since_days
            )
            suggestion = _ai_quality.suggest_threshold_adjustment(metrics)

            # Last train at: si app_versions tiene model_trained_at o algo
            # similar lo leemos. Si no, dejamos None.
            last_train_at = None
            verdicts_since = 0
            try:
                cur.execute(
                    'SELECT COUNT(*) FROM scans '
                    "WHERE verdict IN ('clean','hack') AND ensemble_data IS NOT NULL"
                )
                row = cur.fetchone()
                verdicts_since = int(_row_get(row, 0, 'count') or 0)
            except Exception:
                pass
            retrain = _ai_quality.should_retrain_rf(
                metrics, last_train_at=last_train_at,
                verdicts_since_train=verdicts_since
            )
        return jsonify({
            'available':    True,
            'metrics':      metrics,
            'suggestion':   suggestion,
            'retrain':      retrain,
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/ai-quality/learn-fp-suggestions', methods=['GET'])
@login_required
def ai_quality_learn_fp_suggestions():
    """Top 20 paths que la IA flagea pero el staff descarta.
    Candidatos para automatizar como learn-fp.
    Scope: admin ve global, non-admin solo su company.
    """
    if not _AI_QUALITY_AVAILABLE:
        return jsonify({'available': False, 'rows': []}), 200
    user_id    = session.get('user_id')
    company_id = session.get('company_id')
    qs_company = request.args.get('company_id', type=int)
    is_glob    = is_admin(user_id)
    if qs_company and not is_glob and qs_company != company_id:
        return jsonify({'error': 'Solo admin puede ver otras empresas'}), 403
    target_company = qs_company if is_glob else company_id
    try:
        limit = max(5, min(50, int(request.args.get('limit', 20))))
    except Exception:
        limit = 20
    try:
        with get_api_db_cursor() as cur:
            rows = _ai_quality.suggest_learn_fp_candidates(
                cur, company_id=target_company, limit=limit
            )
        return jsonify({'available': True, 'rows': rows, 'count': len(rows)}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Pack 36 â€” Player Risk Profile (histÃ³rico)
@app.route('/api/players/<path:username>/risk-profile', methods=['GET'])
@login_required
def get_player_risk_profile(username):
    """Perfil histÃ³rico de risk del jugador: avg, min, max, recent,
    trend (rising/stable/falling), regression alert si era clean
    histÃ³rico y ahora hack reciente.
    Pack 36."""
    if not _AI_AUTOLEARN_AVAILABLE:
        return jsonify({'available': False}), 200
    if not username:
        return jsonify({'error': 'username requerido'}), 400
    username = username.strip()[:64]
    try:
        since_days = max(7, min(730, int(request.args.get('since_days', 365))))
    except Exception:
        since_days = 365
    try:
        with get_api_db_cursor() as cur:
            profile = _ai_autolearn.get_player_risk_profile(
                cur, username, since_days=since_days
            )
        return jsonify({'available': True, **profile}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/learned-hack-patterns', methods=['GET'])
@login_required
def get_learned_hack_patterns():
    """Lista de patterns de hack auto-aprendidos. Admin / company-admin."""
    if not _AI_AUTOLEARN_AVAILABLE:
        return jsonify({'available': False, 'rows': []}), 200
    user_id    = session.get('user_id')
    company_id = session.get('company_id')
    if not (is_admin(user_id) or is_company_admin(user_id, company_id)):
        return jsonify({'error': 'Acceso denegado'}), 403
    try:
        with get_api_db_cursor() as cur:
            _ai_autolearn.ensure_autolearn_table(cur)
            cur.execute(
                'SELECT id, pattern_kind, pattern_value, confidence, '
                'hit_count, confirmed_count, learned_from_scan_id, '
                'learned_by, learned_at, last_hit_at, decay_score '
                'FROM learned_hack_patterns '
                'ORDER BY confidence DESC, confirmed_count DESC LIMIT 200'
            )
            rows = cur.fetchall() or []
            out = []
            for r in rows:
                out.append({
                    'id':                   _row_get(r, 0, 'id'),
                    'pattern_kind':         _row_get(r, 1, 'pattern_kind'),
                    'pattern_value':        _row_get(r, 2, 'pattern_value'),
                    'confidence':           float(_row_get(r, 3, 'confidence') or 0.0),
                    'hit_count':            int(_row_get(r, 4, 'hit_count') or 0),
                    'confirmed_count':      int(_row_get(r, 5, 'confirmed_count') or 0),
                    'learned_from_scan_id': _row_get(r, 6, 'learned_from_scan_id'),
                    'learned_by':           _row_get(r, 7, 'learned_by'),
                    'learned_at':           str(_row_get(r, 8, 'learned_at') or ''),
                    'last_hit_at':          str(_row_get(r, 9, 'last_hit_at') or ''),
                    'decay_score':          float(_row_get(r, 10, 'decay_score') or 1.0),
                })
        return jsonify({'available': True, 'rows': out, 'count': len(out)}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Pack 37 â€” Mantenimiento IA + ranking sancionables + index suggestions
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

@app.route('/api/admin/ai-maintenance', methods=['GET'])
@login_required
def get_ai_maintenance_dryrun():
    """DRY RUN: muestra quÃ© se harÃ­a sin tocar nada (admin only)."""
    if not is_admin(session.get('user_id')):
        return jsonify({'error': 'Acceso denegado'}), 403
    if not _AI_MAINT_AVAILABLE:
        return jsonify({'available': False}), 200
    try:
        with get_api_db_cursor() as cur:
            report = _ai_maint.run_maintenance(cur, dry_run=True)
        return jsonify({'available': True, 'report': report}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/ai-maintenance/run', methods=['POST'])
@login_required
def run_ai_maintenance():
    """EJECUTA mantenimiento (decay + cleanup + recompute) â€” admin only.
    body opcional: {notify_discord: true, include_metrics: true}
    """
    if not is_admin(session.get('user_id')):
        return jsonify({'error': 'Acceso denegado'}), 403
    if not _AI_MAINT_AVAILABLE:
        return jsonify({'error': 'ai_maintenance no cargado'}), 503
    body = request.get_json(silent=True) or {}
    notify_discord  = bool(body.get('notify_discord', False))
    include_metrics = bool(body.get('include_metrics', True))
    try:
        with get_api_db_cursor() as cur:
            report = _ai_maint.run_maintenance(cur, dry_run=False)
            metrics_block = None
            if include_metrics and _AI_QUALITY_AVAILABLE:
                try:
                    metrics_block = {
                        'metrics':    _ai_quality.get_quality_metrics(cur, since_days=90),
                        'suggestion': None,
                        'retrain':    None,
                    }
                    metrics_block['suggestion'] = _ai_quality.suggest_threshold_adjustment(metrics_block['metrics'])
                    cur.execute("SELECT COUNT(*) FROM scans WHERE verdict IN ('clean','hack') AND ensemble_data IS NOT NULL")
                    vrow = cur.fetchone()
                    vsince = int(_row_get(vrow, 0, 'count') or 0)
                    metrics_block['retrain'] = _ai_quality.should_retrain_rf(
                        metrics_block['metrics'], last_train_at=None, verdicts_since_train=vsince
                    )
                except Exception:
                    metrics_block = None

        webhook_status = None
        if notify_discord:
            try:
                webhook_status = _ai_maint.send_health_webhook(report, metrics=metrics_block)
            except Exception as _e_w:
                webhook_status = {'sent': False, 'error': str(_e_w)}

        try:
            _log_staff_action(
                'ai_maintenance_run',
                detail=str(report.get('decay_hack', {})) +
                       ' / ' + str(report.get('legit_decay', {})) +
                       ' / ' + str(report.get('cooldown_cleanup', {})) +
                       (f' / discord={webhook_status.get("sent")}' if webhook_status else '')
            )
        except Exception:
            pass
        out = {'ok': True, 'report': report}
        if metrics_block:    out['metrics'] = metrics_block
        if webhook_status:   out['webhook'] = webhook_status
        return jsonify(out), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/repeat-offenders', methods=['GET'])
@login_required
def get_repeat_offenders():
    """Top jugadores con >=2 verdicts hack en Ãºltimos N dÃ­as.
    Admin: global o por company; non-admin: solo su company.
    """
    if not _AI_MAINT_AVAILABLE:
        return jsonify({'available': False, 'rows': []}), 200
    user_id    = session.get('user_id')
    company_id = session.get('company_id')
    qs_company = request.args.get('company_id', type=int)
    is_glob    = is_admin(user_id)
    if qs_company and not is_glob and qs_company != company_id:
        return jsonify({'error': 'Solo admin puede ver otras empresas'}), 403
    target = qs_company if is_glob else company_id
    try:
        since = max(7, min(730, int(request.args.get('since_days', 90))))
        limit = max(5, min(100, int(request.args.get('limit', 20))))
    except Exception:
        since = 90
        limit = 20
    try:
        with get_api_db_cursor() as cur:
            rows = _ai_maint.get_top_repeat_offenders(
                cur, company_id=target, since_days=since, limit=limit
            )
        return jsonify({
            'available':  True,
            'rows':       rows,
            'count':      len(rows),
            'since_days': since,
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/learned-hack-patterns/<int:pid>', methods=['DELETE'])
@login_required
def delete_learned_hack_pattern(pid):
    """Borrar un pattern aprendido (si fue mal aprendido). Admin only."""
    if not is_admin(session.get('user_id')):
        return jsonify({'error': 'Acceso denegado'}), 403
    if not _AI_AUTOLEARN_AVAILABLE:
        return jsonify({'error': 'ai_autolearn no cargado'}), 503
    try:
        with get_api_db_cursor() as cur:
            cur.execute(f'DELETE FROM learned_hack_patterns WHERE id = {_PH}', (pid,))
        try:
            _log_staff_action('autolearn_delete', detail=f'pattern_id={pid}')
        except Exception:
            pass
        return jsonify({'ok': True}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/ai-quality/apply-threshold', methods=['POST'])
@login_required
def ai_quality_apply_threshold():
    """Admin de empresa aplica la sugerencia de threshold adjustment.
    body: {delta: int}  (positive = subir, negative = bajar)
    """
    if not _AI_QUALITY_AVAILABLE:
        return jsonify({'error': 'ai_quality no cargado'}), 503
    user_id    = session.get('user_id')
    company_id = session.get('company_id')
    if not company_id:
        return jsonify({'error': 'Sin empresa asignada'}), 400
    if not (is_admin(user_id) or is_company_admin(user_id, company_id)):
        return jsonify({'error': 'Solo admin/company-admin'}), 403
    data = request.get_json(silent=True) or {}
    try:
        delta = int(data.get('delta', 0))
    except Exception:
        delta = 0
    if not (-20 <= delta <= 20) or delta == 0:
        return jsonify({'error': 'delta invÃ¡lido (-20..20, no cero)'}), 400

    # Lee settings actuales y aplica delta clampeado.
    try:
        cur_settings = _get_company_settings(company_id)
        new_crit = max(20, min(99, int(cur_settings['threshold_critical']) + delta))
        new_susp = max(10, min(new_crit - 1, int(cur_settings['threshold_suspicious']) + delta))
        with get_api_db_cursor() as cur:
            cur.execute('''
                CREATE TABLE IF NOT EXISTS company_settings (
                    company_id          INTEGER PRIMARY KEY,
                    mode                VARCHAR(20)  DEFAULT 'normal',
                    threshold_critical  INTEGER      DEFAULT 70,
                    threshold_suspicious INTEGER     DEFAULT 30,
                    updated_at          TIMESTAMP DEFAULT NOW(),
                    updated_by          INTEGER
                )
            ''')
            try:
                cur.execute(
                    f'INSERT INTO company_settings (company_id, mode, threshold_critical, threshold_suspicious, updated_at, updated_by) '
                    f'VALUES ({_PH}, {_PH}, {_PH}, {_PH}, NOW(), {_PH}) '
                    f'ON CONFLICT (company_id) DO UPDATE SET '
                    f'  threshold_critical = EXCLUDED.threshold_critical, '
                    f'  threshold_suspicious = EXCLUDED.threshold_suspicious, '
                    f'  updated_at = NOW(), updated_by = EXCLUDED.updated_by',
                    (company_id, cur_settings.get('mode', 'normal'),
                     new_crit, new_susp, user_id)
                )
            except Exception:
                cur.execute(
                    f'UPDATE company_settings SET threshold_critical={_PH}, '
                    f'threshold_suspicious={_PH}, updated_by={_PH} '
                    f'WHERE company_id={_PH}',
                    (new_crit, new_susp, user_id, company_id)
                )
        _company_settings_cache.pop(company_id, None)
        try:
            _log_staff_action(
                'ai_threshold_adjust',
                detail=f'delta={delta} new_crit={new_crit} new_susp={new_susp}'
            )
        except Exception:
            pass
        return jsonify({
            'ok': True,
            'threshold_critical':   new_crit,
            'threshold_suspicious': new_susp,
            'delta_applied':        delta,
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/staff/audit-log', methods=['GET'])
@login_required
def get_staff_audit_log():
    """Devuelve el historial de acciones del staff (paginado)."""
    if not (is_admin(session.get('user_id')) or is_company_admin(session.get('user_id'), session.get('company_id'))):
        return jsonify({'error': 'Acceso denegado'}), 403
    page     = max(1, int(request.args.get('page', 1)))
    per_page = min(100, int(request.args.get('per_page', 50)))
    offset   = (page - 1) * per_page
    scan_id  = request.args.get('scan_id')
    user_flt = request.args.get('user_id')
    try:
        with get_api_db_cursor() as cur:
            base_q = '''
                SELECT sal.id, sal.user_id, u.username, sal.action, sal.scan_id,
                       sal.detail, sal.ip_address, sal.created_at
                FROM staff_audit_log sal
                LEFT JOIN users u ON u.id = sal.user_id
            '''
            conditions, params = [], []
            if scan_id:
                conditions.append('sal.scan_id = %s'); params.append(int(scan_id))
            if user_flt:
                conditions.append('sal.user_id = %s'); params.append(int(user_flt))
            where = ('WHERE ' + ' AND '.join(conditions)) if conditions else ''
            cur.execute(f'{base_q} {where} ORDER BY sal.created_at DESC LIMIT %s OFFSET %s',
                        params + [per_page, offset])
            rows = cur.fetchall() or []
            cur.execute(f'SELECT COUNT(*) FROM staff_audit_log sal {where}', params)
            total = (cur.fetchone() or [0])[0]
        entries = []
        for r in rows:
            if isinstance(r, dict):
                entries.append(r)
            else:
                entries.append({
                    'id': r[0], 'user_id': r[1], 'username': r[2],
                    'action': r[3], 'scan_id': r[4], 'detail': r[5],
                    'ip': r[6], 'created_at': str(r[7]) if r[7] else None,
                })
        return jsonify({'entries': entries, 'total': total, 'page': page, 'per_page': per_page}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# â”€â”€ Filter #11 â€” Aprendizaje incremental: enseÃ±ar un path como FP â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# El staff abre un scan, ve un FP claro (ej: "Game.exe" en
# "C:\Apps\MiAppLegit\bin\Game.exe") y lo marca como FP. El backend guarda
# un fragmento del path (la carpeta padre normalizada) en learned_patterns
# con type='legitimate_path'. _is_server_false_positive() lo aplicarÃ¡ a
# TODOS los scans futuros y a los actuales via _scrub_results_for_display.
# Cache de _get_learned_legit_paths se invalida automÃ¡ticamente en 5 min.
@app.route('/api/staff/learn-fp', methods=['POST'])
@login_required
def learn_fp_path():
    if not is_admin(session.get('user_id')) and \
       not is_company_admin(session.get('user_id'), session.get('company_id')):
        return jsonify({'error': 'Acceso denegado'}), 403
    data = request.get_json(silent=True) or {}
    raw_path = (data.get('path') or '').strip()
    raw_name = (data.get('name') or '').strip()
    fragment = (data.get('fragment') or '').strip().lower()
    if not fragment:
        # Auto-deriva el fragmento: tomamos el Ãºltimo directorio del path
        # y el nombre del archivo, p.ej "lunarclient\\game.exe".
        src = (raw_path or raw_name).replace('/', '\\').lower()
        if not src:
            return jsonify({'error': 'Falta path/name/fragment'}), 400
        parts = src.split('\\')
        # Tomamos los Ãºltimos 2 componentes (carpeta + archivo) para tener
        # un fragmento descriptivo pero especÃ­fico.
        fragment = '\\'.join(parts[-2:]) if len(parts) >= 2 else parts[-1]
    if len(fragment) < 4:
        return jsonify({'error': 'Fragmento demasiado corto (mÃ­n 4 chars)'}), 400
    fragment = fragment[:255]
    try:
        with get_api_db_cursor() as cur:
            # Schema: learned_patterns sin company_id, asÃ­ que el patrÃ³n es
            # global. Esto es intencional para acelerar el aprendizaje
            # cross-empresa, pero lo registramos quien lo enseÃ±Ã³ vÃ­a
            # staff_audit_log para auditabilidad.
            cur.execute(
                "SELECT id FROM learned_patterns WHERE pattern_type = 'legitimate_path' "
                f"AND lower(pattern_value) = {_PH}",
                (fragment,)
            )
            existing = cur.fetchone()
            if existing:
                # Ya existe: incrementamos learned_from_count y reactivamos
                eid = existing[0] if not isinstance(existing, dict) else existing.get('id')
                cur.execute(
                    "UPDATE learned_patterns SET learned_from_count = learned_from_count + 1, "
                    f"last_updated_at = NOW(), is_active = TRUE WHERE id = {_PH}",
                    (eid,)
                )
                action = 'incremented'
            else:
                cur.execute(
                    "INSERT INTO learned_patterns "
                    "(pattern_type, pattern_value, pattern_category, confidence, is_active) "
                    f"VALUES ('legitimate_path', {_PH}, 'manual_fp', 1.0, TRUE)",
                    (fragment,)
                )
                action = 'inserted'

        # Invalidar cachÃ© in-memory para que aplique YA al prÃ³ximo scan
        try:
            _lp_cache['ts'] = 0.0
        except Exception:
            pass

        try:
            _log_staff_action('learn_fp', detail=f"path_fragment={fragment} action={action}")
        except Exception:
            pass

        # Pack 32 F#60 â€” Incrementar cooldown de la empresa.
        # Detecta volÃºmenes anÃ³malos de FP-learning como seÃ±al de
        # corrupciÃ³n o filtro mal calibrado, y sube los thresholds
        # del cliente para forzar revisiÃ³n mÃ¡s estricta.
        if _AI_TRUST_AVAILABLE and session.get('company_id'):
            try:
                with get_api_db_cursor() as _ccur:
                    _ai_trust.increment_cooldown(
                        _ccur, session.get('company_id'), kind='fp'
                    )
            except Exception as _e_cd:
                print(f'[learn-fp.cooldown] {_e_cd}')

        return jsonify({
            'ok': True,
            'fragment': fragment,
            'action': action,
            'note': 'AplicarÃ¡ a scans futuros y se filtrarÃ¡ retroactivamente al servirlos.',
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# â”€â”€ Visual #46 â€” Comparador lado-a-lado: scans del mismo jugador â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Devuelve scans anteriores al `scan_id` actual del MISMO MC username (y/o
# machine_id), ordenados desc. Pensado para el comparador lado-a-lado del
# panel: el JS pide los anteriores y arma el diff. NO trae results detallados,
# solo metadata + conteos para el comparador rÃ¡pido.
@app.route('/api/scans/<int:scan_id>/related', methods=['GET'])
@login_required
def get_related_scans(scan_id):
    try:
        limit = max(1, min(20, int(request.args.get('limit', 6))))
    except Exception:
        limit = 6
    try:
        with get_api_db_cursor() as cur:
            # 1) Resolver el scan actual: tomamos minecraft_username y machine_id
            cur.execute(
                'SELECT minecraft_username, machine_id, machine_name, started_at '
                f'FROM scans WHERE id = {_PH}',
                (scan_id,)
            )
            anchor = cur.fetchone()
            if not anchor:
                return jsonify({'error': 'Scan no encontrado'}), 404
            if isinstance(anchor, dict):
                mc_user   = anchor.get('minecraft_username')
                machine_id = anchor.get('machine_id')
            else:
                mc_user, machine_id = anchor[0], anchor[1]
            if not mc_user and not machine_id:
                return jsonify({'scans': [], 'anchor_id': scan_id}), 200

            # 2) Buscar otros scans del mismo MC user O misma mÃ¡quina
            #    excluyendo el actual. Ordenamos por created_at DESC.
            conditions, params = [], []
            if mc_user:
                conditions.append(f'minecraft_username = {_PH}'); params.append(mc_user)
            if machine_id:
                conditions.append(f'machine_id = {_PH}'); params.append(machine_id)
            where = '(' + ' OR '.join(conditions) + ')' if conditions else 'FALSE'

            # Empresa: respetar el aislamiento. Solo scans de la(s) misma(s)
            # company_id que el staff. Para staff global (admin), no filtrar.
            user_id = session.get('user_id')
            company_id = session.get('company_id')
            extra_where = ''
            extra_params = []
            try:
                if not is_admin(user_id):
                    if company_id:
                        extra_where = f' AND company_id = {_PH}'
                        extra_params.append(company_id)
            except Exception:
                pass

            q = (
                'SELECT id, minecraft_username, machine_name, started_at, '
                '       risk_score, verdict, country, issues_found, issues_critical, '
                '       total_files_scanned '
                f'FROM scans WHERE {where} AND id != {_PH}{extra_where} '
                f'ORDER BY COALESCE(started_at, created_at) DESC LIMIT {_PH}'
            )
            cur.execute(q, params + [scan_id] + extra_params + [limit])
            rows = cur.fetchall() or []
        out = []
        for r in rows:
            if isinstance(r, dict):
                out.append(r)
            else:
                out.append({
                    'id':              r[0],
                    'minecraft_user':  r[1],
                    'machine_name':    r[2],
                    'started_at':      str(r[3]) if r[3] else None,
                    'risk_score':      r[4],
                    'verdict':         r[5],
                    'country':         r[6],
                    'issues_found':    r[7],
                    'issues_critical': r[8],
                    'total_files_scanned': r[9],
                })
        return jsonify({'scans': out, 'anchor_id': scan_id, 'anchor_user': mc_user}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Pack 33 â€” V#47 Timeline visual del jugador
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Devuelve eventos cronolÃ³gicos del jugador (scans + verdict changes +
# notas + first-seen evidencia + overturns) ordenados desc. El frontend
# los pinta como timeline vertical con icono+timestamp+resumen+CTA.
#
# Endpoint: GET /api/players/<username>/timeline?limit=50&since_days=180
#
# Aislamiento: respeta company_id (no-admin solo ve eventos de su empresa).
@app.route('/api/players/<path:username>/timeline', methods=['GET'])
@login_required
def get_player_timeline(username):
    if not username or len(username) < 1:
        return jsonify({'error': 'username requerido'}), 400
    username = username.strip()[:64]
    try:
        limit = max(5, min(200, int(request.args.get('limit', 50))))
    except Exception:
        limit = 50
    try:
        since_days = max(1, min(730, int(request.args.get('since_days', 180))))
    except Exception:
        since_days = 180

    user_id    = session.get('user_id')
    company_id = session.get('company_id')
    is_global  = False
    try:
        is_global = is_admin(user_id)
    except Exception:
        is_global = False

    events = []
    try:
        with get_api_db_cursor() as cur:
            extra_where = ''
            extra_params = []
            if not is_global and company_id:
                extra_where = f' AND s.company_id = {_PH}'
                extra_params.append(company_id)

            # 1) Scans del jugador (case-insensitive match)
            try:
                q_scans = (
                    'SELECT s.id, s.started_at, s.created_at, '
                    '       s.machine_name, s.risk_score, s.verdict, '
                    '       s.country, s.issues_found, s.issues_critical, '
                    '       s.total_files_scanned, s.scan_duration_ms '
                    'FROM scans s '
                    f"WHERE LOWER(s.minecraft_username) = {_PH}"
                    f"{extra_where} "
                    f"  AND COALESCE(s.created_at, s.started_at) >= "
                    f"      CURRENT_TIMESTAMP - INTERVAL '{int(since_days)} days' "
                    f'ORDER BY COALESCE(s.started_at, s.created_at) DESC '
                    f'LIMIT {_PH}'
                )
                cur.execute(q_scans,
                            [username.lower()] + extra_params + [limit])
                rows = cur.fetchall() or []
            except Exception:
                # Fallback SQLite (no INTERVAL).
                q_scans = (
                    'SELECT s.id, s.started_at, s.created_at, '
                    '       s.machine_name, s.risk_score, s.verdict, '
                    '       s.country, s.issues_found, s.issues_critical, '
                    '       s.total_files_scanned, s.scan_duration_ms '
                    'FROM scans s '
                    f"WHERE LOWER(s.minecraft_username) = {_PH}"
                    f"{extra_where} "
                    f"  AND COALESCE(s.created_at, s.started_at) >= "
                    f"      datetime('now', '-{int(since_days)} days') "
                    f'ORDER BY COALESCE(s.started_at, s.created_at) DESC '
                    f'LIMIT {_PH}'
                )
                cur.execute(q_scans,
                            [username.lower()] + extra_params + [limit])
                rows = cur.fetchall() or []

            for r in rows:
                sid       = _row_get(r, 0, 'id')
                started   = _row_get(r, 1, 'started_at')
                created   = _row_get(r, 2, 'created_at')
                machine   = _row_get(r, 3, 'machine_name')
                rs        = _row_get(r, 4, 'risk_score')
                verdict   = _row_get(r, 5, 'verdict')
                country   = _row_get(r, 6, 'country')
                issues    = _row_get(r, 7, 'issues_found')
                criticals = _row_get(r, 8, 'issues_critical')
                files     = _row_get(r, 9, 'total_files_scanned')
                durms     = _row_get(r, 10, 'scan_duration_ms')
                ts = started or created
                events.append({
                    'kind':       'scan',
                    'ts':         str(ts) if ts else None,
                    'scan_id':    sid,
                    'verdict':    verdict,
                    'risk_score': int(rs) if rs is not None else None,
                    'machine':    machine,
                    'country':    country,
                    'issues':     int(issues) if issues is not None else None,
                    'criticals':  int(criticals) if criticals is not None else None,
                    'files':      int(files) if files is not None else None,
                    'duration_ms': int(durms) if durms is not None else None,
                })

            # 2) Verdict history changes del jugador
            try:
                q_vh = (
                    'SELECT vh.scan_id, vh.verdict, vh.reason, '
                    '       vh.changed_by, vh.changed_at '
                    'FROM verdict_history vh JOIN scans s ON vh.scan_id = s.id '
                    f"WHERE LOWER(s.minecraft_username) = {_PH}"
                    f"{extra_where} "
                    f'ORDER BY vh.changed_at DESC LIMIT {_PH}'
                )
                cur.execute(q_vh,
                            [username.lower()] + extra_params + [limit])
                vh_rows = cur.fetchall() or []
            except Exception:
                vh_rows = []
            for r in vh_rows:
                sid     = _row_get(r, 0, 'scan_id')
                verdict = _row_get(r, 1, 'verdict')
                reason  = _row_get(r, 2, 'reason')
                changed_by = _row_get(r, 3, 'changed_by')
                changed_at = _row_get(r, 4, 'changed_at')
                events.append({
                    'kind':       'verdict_change',
                    'ts':         str(changed_at) if changed_at else None,
                    'scan_id':    sid,
                    'verdict':    verdict,
                    'reason':     reason,
                    'changed_by': changed_by,
                })

            # 3) Notas de scan (si existe la tabla scan_notes)
            try:
                q_notes = (
                    'SELECT sn.scan_id, sn.author, sn.body, sn.created_at '
                    'FROM scan_notes sn JOIN scans s ON sn.scan_id = s.id '
                    f"WHERE LOWER(s.minecraft_username) = {_PH}"
                    f"{extra_where} "
                    f'ORDER BY sn.created_at DESC LIMIT {_PH}'
                )
                cur.execute(q_notes,
                            [username.lower()] + extra_params + [limit])
                note_rows = cur.fetchall() or []
            except Exception:
                note_rows = []
            for r in note_rows:
                sid     = _row_get(r, 0, 'scan_id')
                author  = _row_get(r, 1, 'author')
                body    = _row_get(r, 2, 'body')
                created = _row_get(r, 3, 'created_at')
                events.append({
                    'kind':    'note',
                    'ts':      str(created) if created else None,
                    'scan_id': sid,
                    'author':  author,
                    'body':    (body or '')[:280],  # cap para timeline
                })

        # Ordenar todo por timestamp desc, fechas invÃ¡lidas al final
        def _ts_key(ev):
            ts = ev.get('ts') or ''
            return ts
        events.sort(key=_ts_key, reverse=True)
        events = events[:limit]

        # Stats agregadas para header
        scan_evs = [e for e in events if e['kind'] == 'scan']
        verdicts = [e.get('verdict') for e in scan_evs]
        hacks    = sum(1 for v in verdicts if (v or '').lower() == 'hack')
        cleans   = sum(1 for v in verdicts if (v or '').lower() == 'clean')
        pendings = sum(1 for v in verdicts if (v or '').lower() == 'pending')
        avg_rs   = None
        rss = [e['risk_score'] for e in scan_evs if e.get('risk_score') is not None]
        if rss:
            avg_rs = round(sum(rss) / len(rss), 1)

        return jsonify({
            'username':    username,
            'events':      events,
            'count':       len(events),
            'scans_total': len(scan_evs),
            'hacks':       hacks,
            'cleans':      cleans,
            'pendings':    pendings,
            'avg_risk':    avg_rs,
            'since_days':  since_days,
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# â”€â”€ Visual #11 â€” Staff activity heatmap (GitHub-style) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Devuelve la actividad del staff loggeado durante los Ãºltimos N dÃ­as (default
# 365). Cuenta dos cosas en paralelo:
#   1) Acciones registradas en staff_audit_log (verdicts, exports, etc).
#   2) Verdicts puestos en la tabla scans donde verdict_by = staff.username.
# Las dos sumas se combinan por dÃ­a para que el heatmap refleje TODA la
# actividad del staff, no solo las acciones audit. Resultado:
#   { 'days': [{date, count}], 'total_count': N, 'days_active': M, 'streak': K }
# La generaciÃ³n de la grilla 7Ã—52 se hace client-side; aquÃ­ solo damos el
# diccionario de fechas con contadores no nulos.
@app.route('/api/staff/my-activity-heatmap', methods=['GET'])
@login_required
def get_my_activity_heatmap():
    uid = session.get('user_id')
    if not uid:
        return jsonify({'error': 'No session'}), 401
    try:
        days_back = max(1, min(730, int(request.args.get('days', 365))))
    except Exception:
        days_back = 365
    try:
        from datetime import date, timedelta
        today    = date.today()
        start_dt = today - timedelta(days=days_back - 1)
        with get_api_db_cursor() as cur:
            buckets = {}

            # Audit log buckets (CREATE IF NOT EXISTS por si la tabla aÃºn no
            # existe en este deployment â€” devolvemos vacÃ­o sin romper).
            try:
                cur.execute('''
                    SELECT DATE(created_at) AS d, COUNT(*) AS c
                      FROM staff_audit_log
                     WHERE user_id = %s AND created_at >= %s
                  GROUP BY DATE(created_at)
                ''', (uid, start_dt))
                for r in cur.fetchall() or []:
                    d = r[0] if not isinstance(r, dict) else r.get('d')
                    c = r[1] if not isinstance(r, dict) else r.get('c')
                    if d:
                        buckets[str(d)] = buckets.get(str(d), 0) + int(c or 0)
            except Exception as e:
                print(f'[ActivityHeatmap] audit_log skip: {e}')

            # Verdicts del staff sobre scans (tabla scans, columna verdict_by
            # = username). Esto cubre verdicts puestos antes de que existiera
            # el staff_audit_log y los que no se loguearon por error.
            try:
                cur.execute('SELECT username FROM users WHERE id = %s', (uid,))
                _u = cur.fetchone()
                username = (_u[0] if _u and not isinstance(_u, dict)
                            else (_u or {}).get('username') if _u else None)
                if username:
                    cur.execute('''
                        SELECT DATE(verdict_at) AS d, COUNT(*) AS c
                          FROM scans
                         WHERE verdict_by = %s AND verdict_at IS NOT NULL
                           AND verdict_at >= %s
                      GROUP BY DATE(verdict_at)
                    ''', (username, start_dt))
                    for r in cur.fetchall() or []:
                        d = r[0] if not isinstance(r, dict) else r.get('d')
                        c = r[1] if not isinstance(r, dict) else r.get('c')
                        if d:
                            buckets[str(d)] = buckets.get(str(d), 0) + int(c or 0)
            except Exception as e:
                print(f'[ActivityHeatmap] scans skip: {e}')

        days = [{'date': k, 'count': v} for k, v in buckets.items()]
        days.sort(key=lambda x: x['date'])
        total = sum(d['count'] for d in days)
        active = len(days)

        # Streak actual: dÃ­as consecutivos hasta hoy con count > 0
        streak = 0
        cur_d = today
        while True:
            if buckets.get(str(cur_d), 0) > 0:
                streak += 1
                cur_d = cur_d - timedelta(days=1)
            else:
                break
        # Mejor streak histÃ³rico
        best_streak = 0
        run = 0
        prev = None
        for d in days:
            from datetime import datetime as _dt
            cur_dd = _dt.strptime(d['date'], '%Y-%m-%d').date()
            if prev is not None and (cur_dd - prev).days == 1:
                run += 1
            else:
                run = 1
            best_streak = max(best_streak, run)
            prev = cur_dd

        return jsonify({
            'days':         days,
            'total_count':  total,
            'days_active':  active,
            'streak':       streak,
            'best_streak':  best_streak,
            'days_back':    days_back,
            'today':        str(today),
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# â”€â”€ Visual #13 â€” Stats agregados del staff (achievements + line chart) â”€â”€â”€â”€â”€â”€â”€â”€
# Devuelve mÃ©tricas que alimentan tanto el sistema de logros como el line chart
# de risk score histÃ³rico. Combina staff_audit_log + scans (verdict_by).
# Cache lite por usuario, 60s.
_staff_stats_cache = {}
_STAFF_STATS_TTL = 60.0

@app.route('/api/staff/my-stats', methods=['GET'])
@login_required
def get_my_stats():
    uid = session.get('user_id')
    if not uid:
        return jsonify({'error': 'No session'}), 401
    import time as _t
    cached = _staff_stats_cache.get(uid)
    if cached and (_t.time() - cached[1]) < _STAFF_STATS_TTL:
        return jsonify(cached[0]), 200

    stats = {
        'verdicts_total': 0,
        'clean_count':    0,
        'hack_count':     0,
        'sus_count':      0,
        'days_active':    0,
        'streak':         0,
        'best_streak':    0,
        'avg_risk_30d':   0,
        'history':        [],   # [{date, value}] â€” risk score promedio por dÃ­a
    }
    try:
        from datetime import date, timedelta, datetime as _dt
        today = date.today()
        with get_api_db_cursor() as cur:
            # Username de este staff
            cur.execute(f'SELECT username FROM users WHERE id = {_PH}', (uid,))
            _u = cur.fetchone()
            if not _u:
                return jsonify(stats), 200
            username = (_u[0] if not isinstance(_u, dict) else _u.get('username'))
            if not username:
                return jsonify(stats), 200

            # Veredictos confirmados por este staff (todos los tiempos)
            try:
                cur.execute(f'''
                    SELECT verdict, risk_score, DATE(verdict_at) AS d
                      FROM scans
                     WHERE verdict_by = {_PH} AND verdict_at IS NOT NULL
                ''', (username,))
                rows = cur.fetchall() or []
                day_buckets = {}      # {date_str: {sum_risk, count}}
                seen_days = set()
                for r in rows:
                    if isinstance(r, dict):
                        v  = (r.get('verdict') or '').lower()
                        rs = r.get('risk_score') or 0
                        d  = r.get('d')
                    else:
                        v, rs, d = (r[0] or '').lower(), (r[1] or 0), r[2]
                    stats['verdicts_total'] += 1
                    if 'clean' in v or 'limpio' in v:
                        stats['clean_count'] += 1
                    elif 'hack' in v or 'cheat' in v or 'ban' in v:
                        stats['hack_count'] += 1
                    elif 'sospech' in v or 'suspicious' in v or 'sus' in v:
                        stats['sus_count'] += 1
                    if d:
                        seen_days.add(str(d))
                        b = day_buckets.setdefault(str(d), {'sum': 0, 'n': 0})
                        try: b['sum'] += int(rs); b['n'] += 1
                        except Exception: pass
                stats['days_active'] = len(seen_days)
                # Streak actual
                streak = 0
                cur_d = today
                while str(cur_d) in seen_days:
                    streak += 1
                    cur_d = cur_d - timedelta(days=1)
                stats['streak'] = streak
                # Mejor streak histÃ³rico
                if seen_days:
                    sorted_days = sorted(_dt.strptime(s, '%Y-%m-%d').date()
                                         for s in seen_days)
                    best = run = 1
                    prev = sorted_days[0]
                    for d2 in sorted_days[1:]:
                        if (d2 - prev).days == 1:
                            run += 1
                        else:
                            run = 1
                        best = max(best, run)
                        prev = d2
                    stats['best_streak'] = best
                # HistÃ³rico Ãºltimos 30 dÃ­as â€” risk score promedio diario
                history = []
                sum30, count30 = 0, 0
                for i in range(29, -1, -1):
                    dd = today - timedelta(days=i)
                    b = day_buckets.get(str(dd))
                    if b and b['n']:
                        avg = round(b['sum'] / b['n'])
                        history.append({'date': str(dd), 'value': avg, 'label': dd.strftime('%d/%m')})
                        sum30 += avg; count30 += 1
                    # Si no hay datos ese dÃ­a, no se incluye en history pero
                    # tampoco rompe la lÃ­nea (el chart conecta los puntos
                    # disponibles).
                stats['history'] = history
                stats['avg_risk_30d'] = round(sum30 / count30) if count30 else 0
            except Exception as e:
                print(f'[my-stats] scans agg: {e}')
        _staff_stats_cache[uid] = (stats, _t.time())
        return jsonify(stats), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# â”€â”€ P5 #19 â€” Auto-generate ban message â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@app.route('/api/staff/ai/generate-ban-message', methods=['POST'])
@login_required
def generate_ban_message():
    """Genera un mensaje de ban con las evidencias mÃ¡s relevantes del scan."""
    data    = request.get_json(silent=True) or {}
    scan_id = data.get('scan_id')
    if not scan_id:
        return jsonify({'error': 'scan_id requerido'}), 400

    k_groq   = os.environ.get('GROQ_API_KEY')
    k_gemini = os.environ.get('GEMINI_API_KEY')
    k_claude = os.environ.get('ANTHROPIC_API_KEY')
    if not any([k_groq, k_gemini, k_claude]):
        return jsonify({'error': 'Sin API keys de IA configuradas'}), 503

    try:
        with get_api_db_cursor() as cur:
            cur.execute(
                'SELECT sr.issue_name, sr.issue_path, sr.alert_level, sr.confidence, sr.issue_category '
                'FROM scan_results sr '
                'JOIN scans s ON s.id = sr.scan_id '
                'WHERE sr.scan_id = %s AND sr.alert_level IN (\'CRITICAL\',\'SOSPECHOSO\') '
                'ORDER BY sr.confidence DESC LIMIT 10',
                (scan_id,)
            )
            rows = cur.fetchall() or []
            cur.execute(
                'SELECT machine_name, machine_id, started_at FROM scans WHERE id = %s',
                (scan_id,)
            )
            scan_row = cur.fetchone()
    except Exception as e:
        return jsonify({'error': f'Error de BD: {e}'}), 500

    if not rows:
        return jsonify({'error': 'Sin hallazgos crÃ­ticos en este scan'}), 404

    player = ''
    if scan_row:
        player = (scan_row[0] if isinstance(scan_row, (list, tuple)) else scan_row.get('machine_name', '')) or ''

    findings_text = '\n'.join(
        f'- [{r[2] if isinstance(r,(list,tuple)) else r.get("alert_level","")}] '
        f'{r[0] if isinstance(r,(list,tuple)) else r.get("issue_name","")} '
        f'(conf: {round(float(r[3] if isinstance(r,(list,tuple)) else r.get("confidence",0))*100)}%)'
        for r in rows
    )

    prompt = (
        f'Genera un mensaje de ban formal para un jugador de Minecraft en un servidor de Roleplay/SMP. '
        f'Jugador: {player or "desconocido"}. '
        f'Evidencias encontradas por el scanner anti-hack:\n{findings_text}\n\n'
        f'El mensaje debe:\n'
        f'1. Ser profesional y en espaÃ±ol\n'
        f'2. Mencionar las 3 evidencias mÃ¡s fuertes\n'
        f'3. Indicar que el ban es permanente si hay mÃºltiples indicadores CRITICAL\n'
        f'4. No exceder 5 lÃ­neas\n'
        f'5. Incluir el nombre del escÃ¡ner (Argus Scanner)\n'
        f'Solo el texto del mensaje, sin explicaciones adicionales.'
    )

    ai_response = ''
    try:
        if k_groq:
            import urllib.request as _ur, json as _j
            req = _ur.Request('https://api.groq.com/openai/v1/chat/completions',
                data=_j.dumps({'model': 'llama-3.3-70b-versatile',
                               'messages': [{'role': 'user', 'content': prompt}],
                               'max_tokens': 200}).encode(),
                headers={'Authorization': f'Bearer {k_groq}', 'Content-Type': 'application/json'},
                method='POST')
            with _ur.urlopen(req, timeout=15) as resp:
                rd = _j.loads(resp.read())
                ai_response = rd['choices'][0]['message']['content'].strip()
        elif k_gemini:
            import urllib.request as _ur, json as _j
            url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={k_gemini}'
            body = _j.dumps({'contents': [{'parts': [{'text': prompt}]}]}).encode()
            req = _ur.Request(url, data=body, headers={'Content-Type': 'application/json'}, method='POST')
            with _ur.urlopen(req, timeout=15) as resp:
                rd = _j.loads(resp.read())
                ai_response = rd['candidates'][0]['content']['parts'][0]['text'].strip()
    except Exception as e:
        return jsonify({'error': f'Error de IA: {e}'}), 502

    _log_staff_action('generate_ban_message', scan_id, f'player={player}')
    return jsonify({'ban_message': ai_response, 'scan_id': scan_id, 'player': player}), 200


# â”€â”€ P5 #27 â€” Player clustering with DBSCAN â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@app.route('/api/ml/player-clusters', methods=['GET'])
@login_required
def player_clusters():
    """Agrupa jugadores por similitud de hallazgos usando DBSCAN."""
    try:
        with get_api_db_cursor() as cur:
            cur.execute('''
                SELECT s.machine_id, s.machine_name,
                       array_agg(DISTINCT sr.issue_type ORDER BY sr.issue_type) AS issue_types,
                       MAX(s.risk_score) AS max_risk,
                       COUNT(sr.id) AS total_findings
                FROM scans s
                JOIN scan_results sr ON sr.scan_id = s.id
                WHERE s.started_at > NOW() - INTERVAL '30 days'
                GROUP BY s.machine_id, s.machine_name
                HAVING COUNT(sr.id) > 0
                LIMIT 500
            ''')
            rows = cur.fetchall() or []
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    if len(rows) < 3:
        return jsonify({'clusters': [], 'message': 'Insuficientes datos'}), 200

    try:
        from sklearn.preprocessing import MultiLabelBinarizer
        from sklearn.cluster import DBSCAN
        import numpy as np

        all_types = []
        for r in rows:
            types = r[2] if isinstance(r, (list,tuple)) else r.get('issue_types', [])
            all_types.append(types or [])

        mlb = MultiLabelBinarizer()
        X = mlb.fit_transform(all_types)
        db = DBSCAN(eps=0.5, min_samples=2, metric='cosine').fit(X)
        labels = db.labels_

        clusters = {}
        for idx, label in enumerate(labels):
            if label == -1:
                continue
            if label not in clusters:
                clusters[label] = []
            r = rows[idx]
            if isinstance(r, dict):
                clusters[label].append({'machine_id': r.get('machine_id'), 'player': r.get('machine_name'),
                                        'risk': r.get('max_risk'), 'findings': r.get('total_findings')})
            else:
                clusters[label].append({'machine_id': r[0], 'player': r[1],
                                        'risk': r[3], 'findings': r[4]})

        result = [{'cluster_id': k, 'size': len(v), 'players': v}
                  for k, v in sorted(clusters.items(), key=lambda x: -len(x[1]))]
        return jsonify({'clusters': result, 'total_players': len(rows),
                        'noise_players': int((labels == -1).sum())}), 200
    except ImportError:
        return jsonify({'error': 'sklearn no disponible'}), 503
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# â”€â”€ P5 #28 â€” Player timeline â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@app.route('/api/player/timeline/<machine_id>', methods=['GET'])
@login_required
def player_timeline(machine_id):
    """Devuelve la serie temporal de risk scores de un jugador con tendencia lineal."""
    if not machine_id:
        return jsonify({'error': 'machine_id requerido'}), 400
    try:
        with get_api_db_cursor() as cur:
            cur.execute('''
                SELECT started_at, risk_score, verdict, machine_name
                FROM scans
                WHERE machine_id = %s AND risk_score IS NOT NULL
                ORDER BY started_at ASC
                LIMIT 100
            ''', (machine_id,))
            rows = cur.fetchall() or []
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    if not rows:
        return jsonify({'points': [], 'trend': None, 'player': machine_id}), 200

    points = []
    for r in rows:
        if isinstance(r, dict):
            points.append({'ts': str(r.get('started_at','')), 'score': r.get('risk_score',0),
                           'verdict': r.get('verdict',''), 'player': r.get('machine_name','')})
        else:
            points.append({'ts': str(r[0]), 'score': r[1], 'verdict': r[2], 'player': r[3]})

    # Tendencia lineal simple (regresiÃ³n mÃ­nimos cuadrados)
    n = len(points)
    trend = None
    if n >= 2:
        try:
            import numpy as np
            scores = [p['score'] for p in points]
            x = np.arange(n)
            slope, _ = np.polyfit(x, scores, 1)
            trend = round(float(slope), 2)
        except Exception:
            pass

    player_name = points[-1].get('player') if points else machine_id
    return jsonify({'points': points, 'trend': trend, 'player': player_name,
                    'machine_id': machine_id, 'total_scans': n}), 200


# â”€â”€ P5 #23 â€” Scan diff endpoint â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@app.route('/api/scan/diff/<int:id_a>/<int:id_b>', methods=['GET'])
@login_required
def scan_diff(id_a, id_b):
    """Compara dos scans del mismo jugador y devuelve hallazgos nuevos vs desaparecidos."""
    try:
        with get_api_db_cursor() as cur:
            cur.execute(
                'SELECT issue_name, issue_path, alert_level, issue_type, issue_category '
                'FROM scan_results WHERE scan_id = %s',
                (id_a,)
            )
            rows_a = cur.fetchall() or []
            cur.execute(
                'SELECT issue_name, issue_path, alert_level, issue_type, issue_category '
                'FROM scan_results WHERE scan_id = %s',
                (id_b,)
            )
            rows_b = cur.fetchall() or []
            cur.execute(
                'SELECT machine_name, started_at, machine_id FROM scans WHERE id IN (%s, %s)',
                (id_a, id_b)
            )
            meta_rows = cur.fetchall() or []
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    def _row_key(r):
        if isinstance(r, dict):
            return (r.get('issue_name',''), r.get('issue_path',''), r.get('issue_type',''))
        return (r[0], r[1], r[3])

    set_a = {_row_key(r): r for r in rows_a}
    set_b = {_row_key(r): r for r in rows_b}

    def _fmt(r):
        if isinstance(r, dict):
            return {'name': r.get('issue_name',''), 'path': r.get('issue_path',''),
                    'level': r.get('alert_level',''), 'type': r.get('issue_type',''),
                    'category': r.get('issue_category','')}
        return {'name': r[0], 'path': r[1], 'level': r[2], 'type': r[3], 'category': r[4]}

    new_in_b     = [_fmt(set_b[k]) for k in set_b if k not in set_a]
    gone_from_a  = [_fmt(set_a[k]) for k in set_a if k not in set_b]
    persisted    = [_fmt(set_b[k]) for k in set_b if k in set_a]

    return jsonify({
        'scan_a': id_a, 'scan_b': id_b,
        'new': new_in_b,
        'removed': gone_from_a,
        'persisted': persisted,
        'summary': {
            'total_a': len(set_a), 'total_b': len(set_b),
            'new_count': len(new_in_b), 'removed_count': len(gone_from_a),
            'persisted_count': len(persisted),
        }
    }), 200


# â”€â”€ P5 #24 â€” Telegram webhook alternative â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _notify_telegram(message: str):
    """EnvÃ­a notificaciÃ³n al canal de Telegram si TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID
    estÃ¡n configurados. No bloquea â€” se ejecuta en background thread."""
    token   = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
    chat_id = os.environ.get('TELEGRAM_CHAT_ID', '').strip()
    if not token or not chat_id:
        return

    def _send():
        import urllib.request as _ur, json as _j, urllib.parse as _up
        url  = f'https://api.telegram.org/bot{token}/sendMessage'
        body = _j.dumps({'chat_id': chat_id, 'text': message, 'parse_mode': 'HTML'}).encode()
        req  = _ur.Request(url, data=body,
                           headers={'Content-Type': 'application/json', 'User-Agent': 'ArgusBot/1.0'},
                           method='POST')
        try:
            with _ur.urlopen(req, timeout=10) as resp:
                rd = _j.loads(resp.read())
                if rd.get('ok'):
                    print(f'[Telegram] Mensaje enviado a chat {chat_id}')
                else:
                    print(f'[Telegram] Error: {rd}')
        except Exception as e:
            print(f'[Telegram] Error de envÃ­o: {e}')

    import threading
    threading.Thread(target=_send, daemon=True).start()


# â”€â”€ P5 #26 â€” Rate limiting on public API endpoints â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

import time as _time_rl
_rate_limit_store = {}  # ip -> list of timestamps

def _check_rate_limit(ip: str, max_requests: int = 10, window_seconds: int = 60) -> bool:
    """Devuelve True si la IP estÃ¡ dentro del lÃ­mite, False si lo excediÃ³."""
    now = _time_rl.time()
    window_start = now - window_seconds
    hits = _rate_limit_store.get(ip, [])
    hits = [t for t in hits if t > window_start]  # limpiar entradas viejas
    if len(hits) >= max_requests:
        _rate_limit_store[ip] = hits
        return False
    hits.append(now)
    _rate_limit_store[ip] = hits
    return True


@app.before_request
def _apply_rate_limit():
    """Rate limit en endpoints pÃºblicos sensibles."""
    PUBLIC_LIMITED = {'/api/submit', '/api/predict', '/api/scan/submit'}
    path = request.path
    if path in PUBLIC_LIMITED:
        ip = request.headers.get('X-Forwarded-For', request.remote_addr or 'unknown').split(',')[0].strip()
        if not _check_rate_limit(ip, max_requests=20, window_seconds=60):
            return jsonify({'error': 'Rate limit excedido. MÃ¡ximo 20 requests/minuto por IP.'}), 429


@app.route('/api/admin/scan-heatmap', methods=['GET'])
@login_required
def scan_heatmap():
    """P5 #18 â€” Heatmap de actividad de scans por dÃ­a de semana y hora del dÃ­a.
    Retorna una matriz 7Ã—24 con el conteo de scans iniciados en cada celda.
    """
    days_back = int(request.args.get('days', 30))
    try:
        conn = get_db_connection()
        cur  = conn.cursor()
        cutoff = (datetime.utcnow() - timedelta(days=days_back)).isoformat()
        cur.execute("""
            SELECT started_at FROM scans
            WHERE started_at >= %s AND status = 'completed'
        """, (cutoff,))
        rows = cur.fetchall()
        cur.close()
        conn.close()

        # Build 7Ã—24 matrix (day_of_week Ã— hour)
        matrix = [[0]*24 for _ in range(7)]
        detections_matrix = [[0]*24 for _ in range(7)]

        conn2 = get_db_connection()
        cur2  = conn2.cursor()
        cur2.execute("""
            SELECT started_at, verdict FROM scans
            WHERE started_at >= %s AND status = 'completed'
        """, (cutoff,))
        scan_rows = cur2.fetchall()
        cur2.close()
        conn2.close()

        for row in scan_rows:
            try:
                dt_str = str(row[0] if isinstance(row, (list, tuple)) else row['started_at'])
                dt = datetime.fromisoformat(dt_str[:19])
                dow = dt.weekday()   # 0=Mon â€¦ 6=Sun
                hour = dt.hour
                matrix[dow][hour] += 1
                verdict = (row[1] if isinstance(row, (list, tuple)) else row.get('verdict', ''))
                if verdict == 'hack':
                    detections_matrix[dow][hour] += 1
            except Exception:
                continue

        day_names = ['Lun', 'Mar', 'MiÃ©', 'Jue', 'Vie', 'SÃ¡b', 'Dom']
        return jsonify({
            'matrix': matrix,
            'detections_matrix': detections_matrix,
            'day_names': day_names,
            'days_back': days_back,
            'total_scans': sum(sum(row) for row in matrix),
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/player/mojang-profile', methods=['GET'])
@login_required
def mojang_profile():
    """P5 #20 â€” Buscar perfil de Mojang por UUID o nickname.
    Proxy seguro para evitar CORS: el frontend llama a este endpoint.
    """
    identifier = request.args.get('q', '').strip()
    if not identifier:
        return jsonify({'error': 'ParÃ¡metro q requerido'}), 400
    import urllib.request as _ur
    import json as _json
    try:
        # Determine if it's a UUID (contains hyphens or is 32 hex chars) or a username
        is_uuid = len(identifier.replace('-', '')) == 32 and all(c in '0123456789abcdefABCDEF-' for c in identifier)
        if is_uuid:
            uuid_clean = identifier.replace('-', '')
            # UUID â†’ profile
            url = f'https://sessionserver.mojang.com/session/minecraft/profile/{uuid_clean}'
            with _ur.urlopen(url, timeout=5) as r:
                profile = _json.loads(r.read())
            return jsonify({
                'uuid': profile.get('id'),
                'username': profile.get('name'),
                'source': 'mojang_session',
            })
        else:
            # Username â†’ UUID
            url = f'https://api.mojang.com/users/profiles/minecraft/{identifier}'
            with _ur.urlopen(url, timeout=5) as r:
                data = _json.loads(r.read())
            return jsonify({
                'uuid': data.get('id'),
                'username': data.get('name'),
                'source': 'mojang_api',
            })
    except Exception as e:
        return jsonify({'error': f'No se pudo consultar Mojang: {str(e)}'}), 404


@app.route('/api/ml/coordinated-cheating', methods=['GET'])
@login_required
def coordinated_cheating():
    """P5 #25 â€” Detectar cheating coordinado: mÃºltiples jugadores del mismo equipo
    que tienen hallazgos del mismo tipo en un rango de tiempo cercano.
    Busca clusters de mÃ¡quinas con hacks similares enviados en la misma ventana de 24h.
    """
    days_back = int(request.args.get('days', 7))
    min_cluster = int(request.args.get('min_players', 2))
    try:
        conn = get_db_connection()
        cur  = conn.cursor()
        cutoff = (datetime.utcnow() - timedelta(days=days_back)).isoformat()
        cur.execute("""
            SELECT s.id, s.machine_name, s.machine_id, s.started_at, s.verdict,
                   i.issue_type
            FROM scans s
            JOIN issues i ON i.scan_id = s.id
            WHERE s.started_at >= %s
              AND s.verdict = 'hack'
              AND i.alert_level IN ('CRITICAL', 'SOSPECHOSO')
            ORDER BY s.started_at
        """, (cutoff,))
        rows = cur.fetchall()
        cur.close()
        conn.close()

        if not rows:
            return jsonify({'clusters': [], 'total_groups': 0})

        # Group by (issue_type, date bucket of 24h)
        from collections import defaultdict
        import hashlib as _hl

        buckets = defaultdict(list)
        for row in rows:
            row_d = dict(zip(['id','machine_name','machine_id','started_at','verdict','issue_type'], row)) \
                if isinstance(row, (list, tuple)) else dict(row)
            try:
                dt = datetime.fromisoformat(str(row_d['started_at'])[:19])
                day_bucket = dt.strftime('%Y-%m-%d')
                key = f"{row_d['issue_type']}|{day_bucket}"
                buckets[key].append(row_d)
            except Exception:
                continue

        clusters = []
        seen_scan_ids = set()
        for key, entries in buckets.items():
            machines = {e['machine_id'] or e['machine_name'] for e in entries}
            if len(machines) < min_cluster:
                continue
            issue_type, day = key.split('|', 1)
            cluster_id = _hl.md5(key.encode()).hexdigest()[:8]
            clusters.append({
                'cluster_id': cluster_id,
                'issue_type': issue_type,
                'date': day,
                'player_count': len(machines),
                'players': [{'machine_name': e['machine_name'], 'scan_id': e['id']}
                            for e in entries if (e['machine_id'] or e['machine_name']) in machines],
                'scan_ids': list({e['id'] for e in entries}),
            })

        clusters.sort(key=lambda c: -c['player_count'])
        return jsonify({'clusters': clusters[:20], 'total_groups': len(clusters)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# PACK 39 â€” Super Admin Panel API (/aspers-sa/api/*)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#
# Endpoints dedicados al panel /aspers-sa para que el dueÃ±o tenga control
# completo sobre la IA y las operaciones de la plataforma SIN depender de
# tener cuenta de staff activa. Todos protegidos por la sesiÃ³n existente
# admin_subscriptions_required.
#
# ComposiciÃ³n:
#   /overview              â†’ KPIs globales (revenue, scans, hacks, FP rate, drift)
#   /ai-health             â†’ mÃ©tricas P/R/F1/drift + retrain flag + suggestion
#   /staff-trust           â†’ ranking trust con username
#   /staff-trust/confirm   â†’ confirma decisiÃ³n post-facto (correct/wrong)
#   /cooldowns             â†’ empresas con threshold_bump activo
#   /cooldowns/reset       â†’ resetear cooldown de una empresa
#   /learned-patterns      â†’ patterns auto-aprendidos (hack)
#   /learned-patterns/<id> â†’ DELETE para borrar pattern manualmente
#   /repeat-offenders      â†’ top jugadores reincidentes
#   /audit-log             â†’ Ãºltimas 100 acciones de staff
#   /system-info           â†’ versiÃ³n, env (masked), DB info, modules availability
#   /maintenance/dryrun    â†’ preview del mantenimiento
#   /maintenance/run       â†’ ejecuta mantenimiento (con notify_discord opcional)
#   /learn-fp/suggestions  â†’ top FP candidatos
#   /learn-fp/apply        â†’ aplica un fragment como learn-fp
#   /scans/recent          â†’ Ãºltimos 50 scans (para feed live)
#   /companies/<id>/health â†’ salud agregada de una empresa puntual
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def _sa_required(f):
    """Wrapper local para devolver JSON 401 en endpoints SA-API.
    El `admin_subscriptions_required` global devuelve 401 OK pero queremos
    tambiÃ©n un mensaje consistente."""
    from functools import wraps as _wraps
    @_wraps(f)
    def _w(*a, **kw):
        if not session.get('admin_subscriptions'):
            return jsonify({'error': 'No autorizado', 'sa_login_required': True}), 401
        return f(*a, **kw)
    return _w


def _sa_count(cursor, sql, params=()):
    """Helper para SELECT COUNT(*) que devuelve int sin reventar."""
    try:
        cursor.execute(sql, params)
        row = cursor.fetchone()
        if not row:
            return 0
        v = _row_get(row, 0, list(row.keys())[0]) if hasattr(row, 'keys') else row[0]
        return int(v or 0)
    except Exception:
        return 0


def _sa_interval_clause(field: str, days: int) -> tuple:
    """Devuelve dos clÃ¡usulas (PG, SQLite) para WHERE field >= now - N days.
    Usar try/except afuera para alternar entre dialectos."""
    return (
        f"{field} >= CURRENT_TIMESTAMP - INTERVAL '{int(days)} days'",
        f"{field} >= datetime('now', '-{int(days)} days')",
    )


def _sa_dual_count(cursor, sql_pg: str, sql_sqlite: str, params=()) -> int:
    """Intenta query PG, si falla fallback a SQLite."""
    try:
        cursor.execute(sql_pg, params)
    except Exception:
        try:
            cursor.execute(sql_sqlite, params)
        except Exception:
            return 0
    row = cursor.fetchone()
    if not row:
        return 0
    try:
        v = _row_get(row, 0, list(row.keys())[0]) if hasattr(row, 'keys') else row[0]
        return int(v or 0)
    except Exception:
        return 0


@app.route('/aspers-sa/api/overview', methods=['GET'])
@_sa_required
def sa_api_overview():
    """KPIs globales: revenue, empresas, usuarios, scans 24h/7d/30d,
    hacks, cleans, pendings, FP rate, drift IA, top empresas por volumen."""
    out = {
        'revenue_monthly':        0.0,
        'companies_total':        0,
        'companies_active':       0,
        'companies_expired':      0,
        'users_total':            0,
        'users_active':           0,
        'scans_24h':              0,
        'scans_7d':               0,
        'scans_30d':              0,
        'scans_total':            0,
        'hacks_30d':              0,
        'cleans_30d':             0,
        'pending_total':          0,
        'fp_rate_30d':            None,
        'drift_score':            None,
        'top_companies_30d':      [],
        'last_scan_at':           None,
        'machines_unique':        0,
        'players_unique':         0,
        'verdicts_total':         0,
        'autolearn_active':       0,
        'cooldowns_active':       0,
        'staff_with_trust':       0,
        'modules': {
            'ai_trust':     _AI_TRUST_AVAILABLE,
            'ai_quality':   _AI_QUALITY_AVAILABLE,
            'ai_autolearn': _AI_AUTOLEARN_AVAILABLE,
            'ai_maint':     _AI_MAINT_AVAILABLE,
        },
    }
    try:
        from auth import list_companies as _lc, list_users as _lu
        companies = _lc() or []
        users     = _lu() or []
        out['companies_total']   = len(companies)
        out['users_total']       = len(users)
        out['users_active']      = sum(1 for u in users if u.get('is_active'))
        rev = 0.0
        for c in companies:
            try:
                price = float(c.get('subscription_price') or 0)
            except Exception:
                price = 0.0
            status = (c.get('subscription_status') or '').lower()
            if status == 'active' and price > 0:
                rev += price
                out['companies_active'] += 1
            elif status == 'active':
                out['companies_active'] += 1
            elif status == 'expired':
                out['companies_expired'] += 1
        out['revenue_monthly'] = round(rev, 2)
    except Exception as e:
        print(f'[sa.overview.companies] {e}')

    try:
        with get_api_db_cursor() as cur:
            out['scans_total'] = _sa_count(cur, 'SELECT COUNT(*) FROM scans')
            out['scans_24h']   = _sa_dual_count(
                cur,
                "SELECT COUNT(*) FROM scans WHERE started_at >= CURRENT_TIMESTAMP - INTERVAL '1 day'",
                "SELECT COUNT(*) FROM scans WHERE started_at >= datetime('now', '-1 day')",
            )
            out['scans_7d']    = _sa_dual_count(
                cur,
                "SELECT COUNT(*) FROM scans WHERE started_at >= CURRENT_TIMESTAMP - INTERVAL '7 days'",
                "SELECT COUNT(*) FROM scans WHERE started_at >= datetime('now', '-7 days')",
            )
            out['scans_30d']   = _sa_dual_count(
                cur,
                "SELECT COUNT(*) FROM scans WHERE started_at >= CURRENT_TIMESTAMP - INTERVAL '30 days'",
                "SELECT COUNT(*) FROM scans WHERE started_at >= datetime('now', '-30 days')",
            )
            out['hacks_30d']   = _sa_dual_count(
                cur,
                "SELECT COUNT(*) FROM scans WHERE verdict = 'hack' AND verdict_at >= CURRENT_TIMESTAMP - INTERVAL '30 days'",
                "SELECT COUNT(*) FROM scans WHERE verdict = 'hack' AND verdict_at >= datetime('now', '-30 days')",
            )
            out['cleans_30d']  = _sa_dual_count(
                cur,
                "SELECT COUNT(*) FROM scans WHERE verdict = 'clean' AND verdict_at >= CURRENT_TIMESTAMP - INTERVAL '30 days'",
                "SELECT COUNT(*) FROM scans WHERE verdict = 'clean' AND verdict_at >= datetime('now', '-30 days')",
            )
            out['pending_total'] = _sa_count(
                cur,
                "SELECT COUNT(*) FROM scans WHERE verdict IS NULL OR verdict = '' OR verdict = 'pending'"
            )
            out['verdicts_total'] = _sa_count(
                cur,
                "SELECT COUNT(*) FROM scans WHERE verdict IN ('clean','hack')"
            )
            out['machines_unique'] = _sa_count(
                cur,
                "SELECT COUNT(DISTINCT machine_id) FROM scans WHERE machine_id IS NOT NULL AND machine_id != ''"
            )
            out['players_unique'] = _sa_count(
                cur,
                "SELECT COUNT(DISTINCT LOWER(minecraft_username)) FROM scans WHERE minecraft_username IS NOT NULL AND minecraft_username != ''"
            )

            try:
                cur.execute("SELECT MAX(started_at) FROM scans")
                r = cur.fetchone()
                if r:
                    v = _row_get(r, 0, list(r.keys())[0]) if hasattr(r, 'keys') else r[0]
                    out['last_scan_at'] = str(v) if v else None
            except Exception:
                pass

            # Top empresas por volumen 30d
            try:
                try:
                    cur.execute(
                        "SELECT company_id, COUNT(*) AS n, "
                        "  SUM(CASE WHEN verdict='hack' THEN 1 ELSE 0 END) AS hacks "
                        "FROM scans "
                        "WHERE started_at >= CURRENT_TIMESTAMP - INTERVAL '30 days' "
                        "  AND company_id IS NOT NULL "
                        "GROUP BY company_id ORDER BY COUNT(*) DESC LIMIT 10"
                    )
                except Exception:
                    cur.execute(
                        "SELECT company_id, COUNT(*) AS n, "
                        "  SUM(CASE WHEN verdict='hack' THEN 1 ELSE 0 END) AS hacks "
                        "FROM scans "
                        "WHERE started_at >= datetime('now', '-30 days') "
                        "  AND company_id IS NOT NULL "
                        "GROUP BY company_id ORDER BY COUNT(*) DESC LIMIT 10"
                    )
                rows = cur.fetchall() or []
                cmap = {}
                try:
                    from auth import list_companies as _lc2
                    for c in (_lc2() or []):
                        cmap[c.get('id')] = c.get('name')
                except Exception:
                    pass
                for r in rows:
                    cid = _row_get(r, 0, 'company_id')
                    n   = int(_row_get(r, 1, 'n') or 0)
                    h   = int(_row_get(r, 2, 'hacks') or 0)
                    out['top_companies_30d'].append({
                        'company_id':   cid,
                        'company_name': cmap.get(cid, f'company_{cid}'),
                        'scans':        n,
                        'hacks':        h,
                        'hack_rate':    round(h / n, 3) if n > 0 else 0.0,
                    })
            except Exception as e:
                print(f'[sa.overview.top_companies] {e}')

            # Cooldowns activos
            if _AI_TRUST_AVAILABLE:
                try:
                    _ai_trust.ensure_trust_tables(cur)
                    out['cooldowns_active'] = _sa_count(
                        cur,
                        'SELECT COUNT(*) FROM company_fp_cooldown WHERE threshold_bump > 0'
                    )
                    out['staff_with_trust'] = _sa_count(
                        cur,
                        'SELECT COUNT(*) FROM staff_trust WHERE verdicts_total > 0'
                    )
                except Exception:
                    pass

            # Patterns auto-learned activos
            if _AI_AUTOLEARN_AVAILABLE:
                try:
                    _ai_autolearn.ensure_autolearn_table(cur)
                    out['autolearn_active'] = _sa_count(
                        cur,
                        'SELECT COUNT(*) FROM learned_hack_patterns WHERE decay_score > 0.20 AND confidence > 0.30'
                    )
                except Exception:
                    pass

            # Drift y FP rate (de ai_quality si estÃ¡ disponible)
            if _AI_QUALITY_AVAILABLE:
                try:
                    m = _ai_quality.get_quality_metrics(cur, company_id=None, since_days=30)
                    out['drift_score'] = m.get('drift_score')
                    fp = m.get('fp', 0)
                    tn = m.get('tn', 0)
                    if (fp + tn) > 0:
                        out['fp_rate_30d'] = round(fp / (fp + tn), 3)
                except Exception:
                    pass
    except Exception as e:
        print(f'[sa.overview] {e}')

    return jsonify(out), 200


@app.route('/aspers-sa/api/ai-health', methods=['GET'])
@_sa_required
def sa_api_ai_health():
    """AI Health: P/R/F1/drift, retrain flag, suggestion, top FP candidatos."""
    if not _AI_QUALITY_AVAILABLE:
        return jsonify({'available': False}), 200
    try:
        since_days = max(7, min(365, int(request.args.get('since_days', 30))))
    except Exception:
        since_days = 30
    company_id = request.args.get('company_id', type=int)
    out = {'available': True}
    try:
        with get_api_db_cursor() as cur:
            metrics = _ai_quality.get_quality_metrics(
                cur, company_id=company_id, since_days=since_days
            )
            out['metrics']    = metrics
            out['suggestion'] = _ai_quality.suggest_threshold_adjustment(metrics)
            verdicts_since = _sa_count(
                cur,
                "SELECT COUNT(*) FROM scans WHERE verdict IN ('clean','hack') AND ensemble_data IS NOT NULL"
            )
            out['retrain'] = _ai_quality.should_retrain_rf(
                metrics, last_train_at=None, verdicts_since_train=verdicts_since
            )
            out['fp_candidates'] = _ai_quality.suggest_learn_fp_candidates(
                cur, company_id=company_id, limit=15
            )
        return jsonify(out), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/aspers-sa/api/staff-trust', methods=['GET'])
@_sa_required
def sa_api_staff_trust():
    """Ranking de staff_trust enriquecido con username."""
    if not _AI_TRUST_AVAILABLE:
        return jsonify({'available': False, 'rows': []}), 200
    try:
        with get_api_db_cursor() as cur:
            _ai_trust.ensure_trust_tables(cur)
            cur.execute(
                'SELECT user_id, verdicts_total, agreements, disagreements, '
                'overturns_to_clean, overturns_to_hack, confirmed_correct, '
                'confirmed_wrong, trust_score, updated_at, last_verdict_at '
                'FROM staff_trust ORDER BY trust_score DESC, verdicts_total DESC '
                'LIMIT 200'
            )
            rows = cur.fetchall() or []
        out = []
        try:
            from auth import list_users as _lu
            user_map = {u.get('id'): u for u in (_lu() or [])}
        except Exception:
            user_map = {}
        for r in rows:
            uid = _row_get(r, 0, 'user_id')
            u = user_map.get(uid) or {}
            out.append({
                'user_id':            uid,
                'username':           u.get('username') or f'user_{uid}',
                'company_id':         u.get('company_id'),
                'roles':              u.get('roles') or [],
                'verdicts_total':     int(_row_get(r, 1, 'verdicts_total')     or 0),
                'agreements':         int(_row_get(r, 2, 'agreements')         or 0),
                'disagreements':      int(_row_get(r, 3, 'disagreements')      or 0),
                'overturns_to_clean': int(_row_get(r, 4, 'overturns_to_clean') or 0),
                'overturns_to_hack':  int(_row_get(r, 5, 'overturns_to_hack')  or 0),
                'confirmed_correct':  int(_row_get(r, 6, 'confirmed_correct')  or 0),
                'confirmed_wrong':    int(_row_get(r, 7, 'confirmed_wrong')    or 0),
                'trust_score':        float(_row_get(r, 8, 'trust_score')      or 50.0),
                'updated_at':         str(_row_get(r, 9, 'updated_at')         or ''),
                'last_verdict_at':    str(_row_get(r, 10, 'last_verdict_at')   or ''),
            })
        return jsonify({'available': True, 'rows': out, 'count': len(out)}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/aspers-sa/api/staff-trust/confirm', methods=['POST'])
@_sa_required
def sa_api_staff_trust_confirm():
    """Confirma o desmiente decisiÃ³n post-facto del staff (pesa doble)."""
    if not _AI_TRUST_AVAILABLE:
        return jsonify({'error': 'ai_trust no cargado'}), 503
    data = request.get_json(silent=True) or {}
    target = data.get('user_id')
    was_correct = bool(data.get('was_correct', False))
    if not target:
        return jsonify({'error': 'user_id requerido'}), 400
    try:
        with get_api_db_cursor() as cur:
            _ai_trust.confirm_staff_decision(cur, int(target), was_correct)
        return jsonify({'ok': True}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/aspers-sa/api/cooldowns', methods=['GET'])
@_sa_required
def sa_api_cooldowns():
    """Lista de empresas con threshold_bump activo o reciente."""
    if not _AI_TRUST_AVAILABLE:
        return jsonify({'available': False, 'rows': []}), 200
    try:
        with get_api_db_cursor() as cur:
            _ai_trust.ensure_trust_tables(cur)
            cur.execute(
                'SELECT company_id, fp_count_24h, overturn_count_24h, '
                'threshold_bump, cooldown_until, last_event_at, updated_at '
                'FROM company_fp_cooldown '
                'ORDER BY threshold_bump DESC, last_event_at DESC '
                'LIMIT 200'
            )
            rows = cur.fetchall() or []
        out = []
        try:
            from auth import list_companies as _lc
            cmap = {c.get('id'): c.get('name') for c in (_lc() or [])}
        except Exception:
            cmap = {}
        for r in rows:
            cid = _row_get(r, 0, 'company_id')
            out.append({
                'company_id':         cid,
                'company_name':       cmap.get(cid, f'company_{cid}'),
                'fp_count_24h':       int(_row_get(r, 1, 'fp_count_24h')       or 0),
                'overturn_count_24h': int(_row_get(r, 2, 'overturn_count_24h') or 0),
                'threshold_bump':     int(_row_get(r, 3, 'threshold_bump')     or 0),
                'cooldown_until':     str(_row_get(r, 4, 'cooldown_until')     or ''),
                'last_event_at':      str(_row_get(r, 5, 'last_event_at')      or ''),
                'updated_at':         str(_row_get(r, 6, 'updated_at')         or ''),
            })
        return jsonify({'available': True, 'rows': out, 'count': len(out)}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/aspers-sa/api/cooldowns/reset', methods=['POST'])
@_sa_required
def sa_api_cooldown_reset():
    """Reset manual del cooldown de una empresa puntual."""
    if not _AI_TRUST_AVAILABLE:
        return jsonify({'error': 'ai_trust no cargado'}), 503
    data = request.get_json(silent=True) or {}
    cid = data.get('company_id')
    if not cid:
        return jsonify({'error': 'company_id requerido'}), 400
    try:
        with get_api_db_cursor() as cur:
            _ai_trust.ensure_trust_tables(cur)
            ph = _ai_trust._ph(cur)
            cur.execute(
                f'UPDATE company_fp_cooldown SET '
                f'  fp_count_24h = 0, overturn_count_24h = 0, '
                f'  threshold_bump = 0, updated_at = CURRENT_TIMESTAMP '
                f'WHERE company_id = {ph}',
                (int(cid),)
            )
            try:
                _ai_trust._invalidate_cooldown(int(cid))
            except Exception:
                pass
        return jsonify({'ok': True}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/aspers-sa/api/learned-patterns', methods=['GET'])
@_sa_required
def sa_api_learned_patterns():
    """Patterns auto-aprendidos (hack) ordenados por confidence."""
    if not _AI_AUTOLEARN_AVAILABLE:
        return jsonify({'available': False, 'rows': []}), 200
    try:
        with get_api_db_cursor() as cur:
            _ai_autolearn.ensure_autolearn_table(cur)
            cur.execute(
                'SELECT id, pattern_kind, pattern_value, confidence, '
                'hit_count, confirmed_count, learned_from_scan_id, '
                'learned_by, learned_at, last_hit_at, decay_score '
                'FROM learned_hack_patterns '
                'ORDER BY confidence DESC, confirmed_count DESC LIMIT 300'
            )
            rows = cur.fetchall() or []
        out = []
        for r in rows:
            out.append({
                'id':                   _row_get(r, 0, 'id'),
                'pattern_kind':         _row_get(r, 1, 'pattern_kind'),
                'pattern_value':        _row_get(r, 2, 'pattern_value'),
                'confidence':           float(_row_get(r, 3, 'confidence') or 0.0),
                'hit_count':            int(_row_get(r, 4, 'hit_count') or 0),
                'confirmed_count':      int(_row_get(r, 5, 'confirmed_count') or 0),
                'learned_from_scan_id': _row_get(r, 6, 'learned_from_scan_id'),
                'learned_by':           _row_get(r, 7, 'learned_by'),
                'learned_at':           str(_row_get(r, 8, 'learned_at') or ''),
                'last_hit_at':          str(_row_get(r, 9, 'last_hit_at') or ''),
                'decay_score':          float(_row_get(r, 10, 'decay_score') or 1.0),
            })
        return jsonify({'available': True, 'rows': out, 'count': len(out)}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/aspers-sa/api/learned-patterns/<int:pid>', methods=['DELETE'])
@_sa_required
def sa_api_delete_pattern(pid):
    """Borra un pattern auto-aprendido (tÃ­picamente FP que se colÃ³)."""
    if not _AI_AUTOLEARN_AVAILABLE:
        return jsonify({'error': 'ai_autolearn no cargado'}), 503
    try:
        with get_api_db_cursor() as cur:
            _ai_autolearn.ensure_autolearn_table(cur)
            ph = _ai_autolearn._ph(cur) if hasattr(_ai_autolearn, '_ph') else '?'
            cur.execute(f'DELETE FROM learned_hack_patterns WHERE id = {ph}', (int(pid),))
        try:
            if hasattr(_ai_autolearn, '_invalidate_active_cache'):
                _ai_autolearn._invalidate_active_cache()
        except Exception:
            pass
        return jsonify({'ok': True, 'deleted_id': int(pid)}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/aspers-sa/api/repeat-offenders', methods=['GET'])
@_sa_required
def sa_api_repeat_offenders():
    """Top jugadores reincidentes (>=2 hacks en N dÃ­as). Global o por empresa."""
    if not _AI_MAINT_AVAILABLE:
        return jsonify({'available': False, 'rows': []}), 200
    try:
        since = max(7, min(730, int(request.args.get('since_days', 90))))
        limit = max(5, min(100, int(request.args.get('limit', 25))))
    except Exception:
        since, limit = 90, 25
    cid = request.args.get('company_id', type=int)
    try:
        with get_api_db_cursor() as cur:
            rows = _ai_maint.get_top_repeat_offenders(
                cur, company_id=cid, since_days=since, limit=limit
            )
        return jsonify({
            'available': True, 'rows': rows, 'count': len(rows),
            'since_days': since, 'company_id': cid,
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/aspers-sa/api/audit-log', methods=['GET'])
@_sa_required
def sa_api_audit_log():
    """Ãšltimas 100 acciones de staff (audit log)."""
    try:
        limit = max(10, min(500, int(request.args.get('limit', 100))))
    except Exception:
        limit = 100
    out = []
    try:
        with get_api_db_cursor() as cur:
            try:
                cur.execute(
                    'SELECT id, user_id, action, target_scan_id, detail, timestamp '
                    'FROM staff_audit_log ORDER BY timestamp DESC LIMIT ' + str(limit)
                )
                rows = cur.fetchall() or []
            except Exception:
                rows = []
            user_map = {}
            try:
                from auth import list_users as _lu
                user_map = {u.get('id'): u.get('username') for u in (_lu() or [])}
            except Exception:
                pass
            for r in rows:
                uid = _row_get(r, 1, 'user_id')
                out.append({
                    'id':              _row_get(r, 0, 'id'),
                    'user_id':         uid,
                    'username':        user_map.get(uid, f'user_{uid}' if uid else 'system'),
                    'action':          _row_get(r, 2, 'action'),
                    'target_scan_id':  _row_get(r, 3, 'target_scan_id'),
                    'detail':          _row_get(r, 4, 'detail'),
                    'timestamp':       str(_row_get(r, 5, 'timestamp') or ''),
                })
        return jsonify({'rows': out, 'count': len(out)}), 200
    except Exception as e:
        return jsonify({'error': str(e), 'rows': []}), 500


@app.route('/aspers-sa/api/system-info', methods=['GET'])
@_sa_required
def sa_api_system_info():
    """VersiÃ³n, env (masked), DB info, mÃ³dulos disponibles, uptime aproximado."""
    import sys as _sys
    import platform as _plat
    out = {
        'argus_version':  _ARGUS_VERSION,
        'python_version': _sys.version.split()[0],
        'platform':       f'{_plat.system()} {_plat.release()}',
        'modules': {
            'ai_trust':     _AI_TRUST_AVAILABLE,
            'ai_quality':   _AI_QUALITY_AVAILABLE,
            'ai_autolearn': _AI_AUTOLEARN_AVAILABLE,
            'ai_maint':     _AI_MAINT_AVAILABLE,
        },
        'db_engine':      'postgres' if _USE_PG else ('mysql' if _USE_MYSQL else 'sqlite'),
        'is_render':      bool(IS_RENDER),
        'env_masked':     {},
        'session_login_at': session.get('admin_subscriptions_login_at', ''),
    }
    interesting_keys = [
        'DATABASE_URL', 'API_URL', 'API_KEY', 'SECRET_KEY',
        'DISCORD_DEPLOY_WEBHOOK', 'DISCORD_AI_HEALTH_WEBHOOK', 'DISCORD_INVITE_URL',
        'SUPER_ADMIN_USER', 'SUPER_ADMIN_PASS',
        'RENDER', 'FLASK_ENV', 'PORT',
    ]
    for k in interesting_keys:
        v = os.environ.get(k)
        if v is None:
            out['env_masked'][k] = None
        elif len(v) <= 8:
            out['env_masked'][k] = '*' * len(v)
        else:
            out['env_masked'][k] = v[:4] + '*' * (len(v) - 8) + v[-4:]
    try:
        with get_api_db_cursor() as cur:
            tables = ['scans', 'scan_results', 'staff_trust', 'company_fp_cooldown',
                      'learned_hack_patterns', 'learned_patterns', 'staff_audit_log',
                      'verdict_history', 'evidence_fingerprints', 'companies', 'users']
            out['table_counts'] = {}
            for t in tables:
                try:
                    cur.execute(f'SELECT COUNT(*) FROM {t}')
                    r = cur.fetchone()
                    if r:
                        v = _row_get(r, 0, list(r.keys())[0]) if hasattr(r, 'keys') else r[0]
                        out['table_counts'][t] = int(v or 0)
                except Exception:
                    out['table_counts'][t] = None
    except Exception:
        out['table_counts'] = {}
    return jsonify(out), 200


@app.route('/aspers-sa/api/maintenance/dryrun', methods=['GET'])
@_sa_required
def sa_api_maint_dryrun():
    if not _AI_MAINT_AVAILABLE:
        return jsonify({'available': False}), 200
    try:
        with get_api_db_cursor() as cur:
            report = _ai_maint.run_maintenance(cur, dry_run=True)
        return jsonify({'available': True, 'report': report, 'dry_run': True}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/aspers-sa/api/maintenance/run', methods=['POST'])
@_sa_required
def sa_api_maint_run():
    """Ejecuta mantenimiento real. body: {notify_discord: bool, include_metrics: bool}"""
    if not _AI_MAINT_AVAILABLE:
        return jsonify({'error': 'ai_maintenance no cargado'}), 503
    body = request.get_json(silent=True) or {}
    notify_discord  = bool(body.get('notify_discord', False))
    include_metrics = bool(body.get('include_metrics', True))
    out = {'ok': True}
    try:
        with get_api_db_cursor() as cur:
            report = _ai_maint.run_maintenance(cur, dry_run=False)
            out['report'] = report
            metrics_block = None
            if include_metrics and _AI_QUALITY_AVAILABLE:
                try:
                    metrics_block = {
                        'metrics':    _ai_quality.get_quality_metrics(cur, since_days=90),
                    }
                    metrics_block['suggestion'] = _ai_quality.suggest_threshold_adjustment(
                        metrics_block['metrics'])
                    vs = _sa_count(
                        cur,
                        "SELECT COUNT(*) FROM scans WHERE verdict IN ('clean','hack') AND ensemble_data IS NOT NULL"
                    )
                    metrics_block['retrain'] = _ai_quality.should_retrain_rf(
                        metrics_block['metrics'], last_train_at=None, verdicts_since_train=vs
                    )
                    out['metrics'] = metrics_block
                except Exception as _em:
                    print(f'[sa.maint.metrics] {_em}')
        if notify_discord:
            try:
                wh = _ai_maint.send_health_webhook(out.get('report'), metrics=out.get('metrics'))
                out['webhook'] = wh
            except Exception as _ew:
                out['webhook'] = {'sent': False, 'error': str(_ew)}
        return jsonify(out), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/aspers-sa/api/learn-fp/suggestions', methods=['GET'])
@_sa_required
def sa_api_learn_fp_suggestions():
    if not _AI_QUALITY_AVAILABLE:
        return jsonify({'available': False, 'rows': []}), 200
    cid = request.args.get('company_id', type=int)
    try:
        limit = max(5, min(50, int(request.args.get('limit', 25))))
    except Exception:
        limit = 25
    try:
        with get_api_db_cursor() as cur:
            rows = _ai_quality.suggest_learn_fp_candidates(
                cur, company_id=cid, limit=limit
            )
        return jsonify({'available': True, 'rows': rows, 'count': len(rows)}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/aspers-sa/api/scans/recent', methods=['GET'])
@_sa_required
def sa_api_scans_recent():
    """Ãšltimos N scans para feed live."""
    try:
        limit = max(5, min(200, int(request.args.get('limit', 30))))
    except Exception:
        limit = 30
    out = []
    try:
        with get_api_db_cursor() as cur:
            try:
                cur.execute(
                    'SELECT id, machine_name, minecraft_username, company_id, '
                    '  status, verdict, risk_score, started_at, completed_at '
                    'FROM scans ORDER BY id DESC LIMIT ' + str(limit)
                )
                rows = cur.fetchall() or []
            except Exception:
                rows = []
            cmap = {}
            try:
                from auth import list_companies as _lc
                cmap = {c.get('id'): c.get('name') for c in (_lc() or [])}
            except Exception:
                pass
            for r in rows:
                cid = _row_get(r, 3, 'company_id')
                out.append({
                    'id':                 _row_get(r, 0, 'id'),
                    'machine_name':       _row_get(r, 1, 'machine_name') or '',
                    'minecraft_username': _row_get(r, 2, 'minecraft_username') or '',
                    'company_id':         cid,
                    'company_name':       cmap.get(cid, ''),
                    'status':             _row_get(r, 4, 'status') or '',
                    'verdict':            _row_get(r, 5, 'verdict') or '',
                    'risk_score':         int(_row_get(r, 6, 'risk_score') or 0),
                    'started_at':         str(_row_get(r, 7, 'started_at') or ''),
                    'completed_at':       str(_row_get(r, 8, 'completed_at') or ''),
                })
        return jsonify({'rows': out, 'count': len(out)}), 200
    except Exception as e:
        return jsonify({'error': str(e), 'rows': []}), 500


@app.route('/aspers-sa/api/scans/timeseries', methods=['GET'])
@_sa_required
def sa_api_scans_timeseries():
    """Serie temporal de scans por dÃ­a (Ãºltimos N dÃ­as) para sparkline."""
    try:
        days = max(7, min(90, int(request.args.get('days', 30))))
    except Exception:
        days = 30
    series = []
    try:
        with get_api_db_cursor() as cur:
            # Buckets por fecha (PG: DATE_TRUNC, SQLite: date())
            try:
                cur.execute(
                    "SELECT DATE_TRUNC('day', started_at)::date AS d, "
                    "  COUNT(*) AS scans, "
                    "  SUM(CASE WHEN verdict='hack' THEN 1 ELSE 0 END) AS hacks "
                    "FROM scans "
                    f"WHERE started_at >= CURRENT_TIMESTAMP - INTERVAL '{int(days)} days' "
                    "GROUP BY DATE_TRUNC('day', started_at) "
                    "ORDER BY d ASC"
                )
            except Exception:
                cur.execute(
                    "SELECT date(started_at) AS d, "
                    "  COUNT(*) AS scans, "
                    "  SUM(CASE WHEN verdict='hack' THEN 1 ELSE 0 END) AS hacks "
                    "FROM scans "
                    f"WHERE started_at >= datetime('now', '-{int(days)} days') "
                    "GROUP BY date(started_at) "
                    "ORDER BY d ASC"
                )
            rows = cur.fetchall() or []
            for r in rows:
                series.append({
                    'date':  str(_row_get(r, 0, 'd') or ''),
                    'scans': int(_row_get(r, 1, 'scans') or 0),
                    'hacks': int(_row_get(r, 2, 'hacks') or 0),
                })
        return jsonify({'series': series, 'days': days}), 200
    except Exception as e:
        return jsonify({'error': str(e), 'series': []}), 500


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Pack 40 â€” Bonus pre-anuncio:
#   * /aspers-sa/api/companies/<id>/health (deep-dive por empresa)
#   * /aspers-sa/api/export/<kind>.csv     (export CSV de las tablas)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•


@app.route('/aspers-sa/api/oracle-stats', methods=['GET'])
@_sa_required
def sa_api_oracle_stats():
    """Oracle AI: decision counts by period, action breakdown, auto-labels, recent decisions."""
    oracle_available = True
    try:
        import argus_ai_oracle as _ao  # noqa: F401
    except ImportError:
        oracle_available = False

    out = {
        'oracle_available': oracle_available,
        'decisions_24h': 0, 'decisions_7d': 0, 'decisions_30d': 0,
        'auto_labels_total': 0,
        'action_counts': {},
        'recent': [],
    }
    try:
        with get_api_db_cursor() as cur:
            for key, days in [('decisions_24h', 1), ('decisions_7d', 7), ('decisions_30d', 30)]:
                out[key] = _sa_dual_count(
                    cur,
                    f"SELECT COUNT(*) FROM ai_decisions_log WHERE created_at >= CURRENT_TIMESTAMP - INTERVAL '{int(days)} days'",
                    f"SELECT COUNT(*) FROM ai_decisions_log WHERE created_at >= datetime('now', '-{int(days)} days')"
                )

            try:
                cur.execute(
                    "SELECT action, COUNT(*) AS cnt FROM ai_decisions_log "
                    "WHERE created_at >= CURRENT_TIMESTAMP - INTERVAL '30 days' "
                    "GROUP BY action ORDER BY cnt DESC"
                )
            except Exception:
                try:
                    cur.execute(
                        "SELECT action, COUNT(*) AS cnt FROM ai_decisions_log "
                        "WHERE created_at >= datetime('now', '-30 days') "
                        "GROUP BY action ORDER BY cnt DESC"
                    )
                except Exception:
                    pass
            rows = cur.fetchall() or []
            for r in rows:
                action = str(_row_get(r, 0, 'action') or '')
                cnt_val = _row_get(r, 1, 'cnt')
                out['action_counts'][action] = int(cnt_val or 0)

            out['auto_labels_total'] = _sa_dual_count(
                cur,
                "SELECT COUNT(*) FROM ai_auto_labels",
                "SELECT COUNT(*) FROM ai_auto_labels"
            )

            try:
                cur.execute(
                    "SELECT player_name, score, confidence, action, created_at "
                    "FROM ai_decisions_log ORDER BY created_at DESC LIMIT 20"
                )
                rows = cur.fetchall() or []
                out['recent'] = [{
                    'player':     str(_row_get(r, 0, 'player_name') or ''),
                    'score':      float(_row_get(r, 1, 'score') or 0),
                    'confidence': float(_row_get(r, 2, 'confidence') or 0),
                    'action':     str(_row_get(r, 3, 'action') or ''),
                    'created_at': str(_row_get(r, 4, 'created_at') or ''),
                } for r in rows]
            except Exception:
                pass
    except Exception as e:
        out['error'] = str(e)

    return jsonify(out), 200


@app.route('/aspers-sa/api/companies/<int:cid>/health', methods=['GET'])
@_sa_required
def sa_api_company_health(cid):
    """Deep-dive de UNA empresa: scans, hacks/cleans/pendings, top players,
    cooldown, mÃ©tricas IA propias, top FP candidatos para ESTA empresa."""
    out = {'company_id': cid}
    try:
        from auth import list_companies as _lc
        cmap = {c.get('id'): c for c in (_lc() or [])}
        c = cmap.get(cid) or {}
        out['name']               = c.get('name') or f'company_{cid}'
        out['contact_email']      = c.get('contact_email')
        out['subscription_status']= c.get('subscription_status')
        out['subscription_price'] = float(c.get('subscription_price') or 0)
        out['max_users']          = c.get('max_users')
        out['max_admins']         = c.get('max_admins')
        out['current_users']      = c.get('current_users')
    except Exception:
        pass
    try:
        with get_api_db_cursor() as cur:
            ph = '%s'  # PG por defecto; SQLite acepta tambiÃ©n con _sa_dual_count si fuera necesario
            try:
                cur.execute(f"SELECT COUNT(*) FROM scans WHERE company_id = {ph}", (cid,))
                r = cur.fetchone()
                out['scans_total'] = int(_row_get(r, 0, list(r.keys())[0]) if r and hasattr(r,'keys') else (r[0] if r else 0) or 0)
            except Exception:
                cur.execute("SELECT COUNT(*) FROM scans WHERE company_id = ?", (cid,))
                r = cur.fetchone()
                out['scans_total'] = int(r[0] if r else 0)
            # Verdicts breakdown
            for verdict, key in [('hack','hacks'), ('clean','cleans')]:
                try:
                    cur.execute(
                        "SELECT COUNT(*) FROM scans WHERE company_id = %s AND verdict = %s",
                        (cid, verdict)
                    )
                    r = cur.fetchone()
                    out[key] = int(_row_get(r, 0, list(r.keys())[0]) if r and hasattr(r,'keys') else (r[0] if r else 0) or 0)
                except Exception:
                    cur.execute(
                        "SELECT COUNT(*) FROM scans WHERE company_id = ? AND verdict = ?",
                        (cid, verdict)
                    )
                    r = cur.fetchone()
                    out[key] = int(r[0] if r else 0)
            try:
                cur.execute(
                    "SELECT COUNT(*) FROM scans WHERE company_id = %s AND (verdict IS NULL OR verdict = '' OR verdict = 'pending')",
                    (cid,)
                )
                r = cur.fetchone()
                out['pendings'] = int(_row_get(r, 0, list(r.keys())[0]) if r and hasattr(r,'keys') else (r[0] if r else 0) or 0)
            except Exception:
                cur.execute(
                    "SELECT COUNT(*) FROM scans WHERE company_id = ? AND (verdict IS NULL OR verdict = '' OR verdict = 'pending')",
                    (cid,)
                )
                r = cur.fetchone()
                out['pendings'] = int(r[0] if r else 0)
            # Cooldown
            if _AI_TRUST_AVAILABLE:
                try:
                    out['cooldown'] = _ai_trust.get_company_cooldown(cur, cid)
                except Exception:
                    out['cooldown'] = None
            # Quality metrics propias
            if _AI_QUALITY_AVAILABLE:
                try:
                    m = _ai_quality.get_quality_metrics(cur, company_id=cid, since_days=90)
                    out['ai_metrics']    = m
                    out['ai_suggestion'] = _ai_quality.suggest_threshold_adjustment(m)
                except Exception:
                    pass
                try:
                    out['fp_candidates'] = _ai_quality.suggest_learn_fp_candidates(
                        cur, company_id=cid, limit=10
                    )
                except Exception:
                    pass
            # Top players
            if _AI_MAINT_AVAILABLE:
                try:
                    out['top_offenders'] = _ai_maint.get_top_repeat_offenders(
                        cur, company_id=cid, since_days=180, limit=10
                    )
                except Exception:
                    pass
        return jsonify(out), 200
    except Exception as e:
        return jsonify({'error': str(e), **out}), 500


@app.route('/aspers-sa/api/export/<kind>.csv', methods=['GET'])
@_sa_required
def sa_api_export_csv(kind):
    """Export CSV de las tablas del panel SuperAdmin.
    kinds soportados: companies | users | trust | cooldowns | patterns |
                      offenders | audit | recent-scans
    """
    import csv as _csv
    import io as _io
    from flask import Response as _Resp

    buf = _io.StringIO()
    w = _csv.writer(buf, lineterminator='\n')
    rows_count = 0

    try:
        if kind == 'companies':
            from auth import list_companies as _lc
            cs = _lc() or []
            w.writerow(['id', 'name', 'contact_email', 'subscription_status',
                        'subscription_price', 'max_users', 'max_admins',
                        'current_users', 'subscription_end_date', 'created_at'])
            for c in cs:
                w.writerow([
                    c.get('id'), c.get('name'), c.get('contact_email'),
                    c.get('subscription_status'),
                    float(c.get('subscription_price') or 0),
                    c.get('max_users'), c.get('max_admins'),
                    c.get('current_users'),
                    c.get('subscription_end_date'),
                    c.get('created_at'),
                ])
                rows_count += 1

        elif kind == 'users':
            from auth import list_users as _lu, list_companies as _lc
            us = _lu() or []
            cmap = {c.get('id'): c.get('name') for c in (_lc() or [])}
            w.writerow(['id', 'username', 'email', 'company_id', 'company_name',
                        'roles', 'is_active', 'last_login', 'created_at'])
            for u in us:
                roles_str = ','.join(u.get('roles') or [])
                w.writerow([
                    u.get('id'), u.get('username'), u.get('email'),
                    u.get('company_id'), cmap.get(u.get('company_id'), ''),
                    roles_str, bool(u.get('is_active')),
                    u.get('last_login'), u.get('created_at'),
                ])
                rows_count += 1

        elif kind == 'trust':
            if not _AI_TRUST_AVAILABLE:
                return jsonify({'error': 'ai_trust no cargado'}), 503
            with get_api_db_cursor() as cur:
                _ai_trust.ensure_trust_tables(cur)
                cur.execute(
                    'SELECT user_id, verdicts_total, agreements, disagreements, '
                    'overturns_to_clean, overturns_to_hack, confirmed_correct, '
                    'confirmed_wrong, trust_score, updated_at '
                    'FROM staff_trust ORDER BY trust_score DESC'
                )
                rows = cur.fetchall() or []
                user_map = {}
                try:
                    from auth import list_users as _lu
                    user_map = {u.get('id'): u.get('username') for u in (_lu() or [])}
                except Exception:
                    pass
                w.writerow(['user_id', 'username', 'verdicts_total', 'agreements',
                            'disagreements', 'overturns_to_clean', 'overturns_to_hack',
                            'confirmed_correct', 'confirmed_wrong', 'trust_score',
                            'updated_at'])
                for r in rows:
                    uid = _row_get(r, 0, 'user_id')
                    w.writerow([
                        uid, user_map.get(uid, f'user_{uid}'),
                        _row_get(r, 1, 'verdicts_total') or 0,
                        _row_get(r, 2, 'agreements') or 0,
                        _row_get(r, 3, 'disagreements') or 0,
                        _row_get(r, 4, 'overturns_to_clean') or 0,
                        _row_get(r, 5, 'overturns_to_hack') or 0,
                        _row_get(r, 6, 'confirmed_correct') or 0,
                        _row_get(r, 7, 'confirmed_wrong') or 0,
                        float(_row_get(r, 8, 'trust_score') or 50.0),
                        str(_row_get(r, 9, 'updated_at') or ''),
                    ])
                    rows_count += 1

        elif kind == 'cooldowns':
            if not _AI_TRUST_AVAILABLE:
                return jsonify({'error': 'ai_trust no cargado'}), 503
            with get_api_db_cursor() as cur:
                _ai_trust.ensure_trust_tables(cur)
                cur.execute(
                    'SELECT company_id, fp_count_24h, overturn_count_24h, '
                    'threshold_bump, cooldown_until, last_event_at '
                    'FROM company_fp_cooldown'
                )
                rows = cur.fetchall() or []
                cmap = {}
                try:
                    from auth import list_companies as _lc
                    cmap = {c.get('id'): c.get('name') for c in (_lc() or [])}
                except Exception:
                    pass
                w.writerow(['company_id', 'company_name', 'fp_count_24h',
                            'overturn_count_24h', 'threshold_bump',
                            'cooldown_until', 'last_event_at'])
                for r in rows:
                    cid = _row_get(r, 0, 'company_id')
                    w.writerow([
                        cid, cmap.get(cid, f'company_{cid}'),
                        _row_get(r, 1, 'fp_count_24h') or 0,
                        _row_get(r, 2, 'overturn_count_24h') or 0,
                        _row_get(r, 3, 'threshold_bump') or 0,
                        str(_row_get(r, 4, 'cooldown_until') or ''),
                        str(_row_get(r, 5, 'last_event_at') or ''),
                    ])
                    rows_count += 1

        elif kind == 'patterns':
            if not _AI_AUTOLEARN_AVAILABLE:
                return jsonify({'error': 'ai_autolearn no cargado'}), 503
            with get_api_db_cursor() as cur:
                _ai_autolearn.ensure_autolearn_table(cur)
                cur.execute(
                    'SELECT id, pattern_kind, pattern_value, confidence, '
                    'hit_count, confirmed_count, learned_from_scan_id, '
                    'learned_by, learned_at, last_hit_at, decay_score '
                    'FROM learned_hack_patterns ORDER BY confidence DESC'
                )
                rows = cur.fetchall() or []
                w.writerow(['id', 'pattern_kind', 'pattern_value', 'confidence',
                            'hit_count', 'confirmed_count', 'learned_from_scan_id',
                            'learned_by', 'learned_at', 'last_hit_at', 'decay_score'])
                for r in rows:
                    w.writerow([
                        _row_get(r, 0, 'id'),
                        _row_get(r, 1, 'pattern_kind'),
                        _row_get(r, 2, 'pattern_value'),
                        float(_row_get(r, 3, 'confidence') or 0.0),
                        _row_get(r, 4, 'hit_count') or 0,
                        _row_get(r, 5, 'confirmed_count') or 0,
                        _row_get(r, 6, 'learned_from_scan_id'),
                        _row_get(r, 7, 'learned_by'),
                        str(_row_get(r, 8, 'learned_at') or ''),
                        str(_row_get(r, 9, 'last_hit_at') or ''),
                        float(_row_get(r, 10, 'decay_score') or 1.0),
                    ])
                    rows_count += 1

        elif kind == 'offenders':
            if not _AI_MAINT_AVAILABLE:
                return jsonify({'error': 'ai_maintenance no cargado'}), 503
            try:
                since = max(7, min(730, int(request.args.get('since_days', 90))))
            except Exception:
                since = 90
            with get_api_db_cursor() as cur:
                rows = _ai_maint.get_top_repeat_offenders(
                    cur, company_id=None, since_days=since, limit=200
                )
            w.writerow(['minecraft_username', 'hacks', 'max_risk', 'last_hack', 'since_days'])
            for r in rows:
                w.writerow([r.get('minecraft_username'), r.get('hacks'),
                            r.get('max_risk'), r.get('last_hack'), since])
                rows_count += 1

        elif kind == 'audit':
            with get_api_db_cursor() as cur:
                try:
                    cur.execute(
                        'SELECT id, user_id, action, target_scan_id, detail, timestamp '
                        'FROM staff_audit_log ORDER BY timestamp DESC LIMIT 1000'
                    )
                    rows = cur.fetchall() or []
                except Exception:
                    rows = []
                user_map = {}
                try:
                    from auth import list_users as _lu
                    user_map = {u.get('id'): u.get('username') for u in (_lu() or [])}
                except Exception:
                    pass
                w.writerow(['id', 'timestamp', 'user_id', 'username', 'action',
                            'target_scan_id', 'detail'])
                for r in rows:
                    uid = _row_get(r, 1, 'user_id')
                    w.writerow([
                        _row_get(r, 0, 'id'),
                        str(_row_get(r, 5, 'timestamp') or ''),
                        uid, user_map.get(uid, f'user_{uid}' if uid else 'system'),
                        _row_get(r, 2, 'action'),
                        _row_get(r, 3, 'target_scan_id'),
                        _row_get(r, 4, 'detail'),
                    ])
                    rows_count += 1

        elif kind == 'recent-scans':
            try:
                limit = max(10, min(2000, int(request.args.get('limit', 500))))
            except Exception:
                limit = 500
            with get_api_db_cursor() as cur:
                try:
                    cur.execute(
                        'SELECT id, machine_name, minecraft_username, company_id, '
                        'status, verdict, risk_score, started_at, completed_at '
                        'FROM scans ORDER BY id DESC LIMIT ' + str(limit)
                    )
                    rows = cur.fetchall() or []
                except Exception:
                    rows = []
                cmap = {}
                try:
                    from auth import list_companies as _lc
                    cmap = {c.get('id'): c.get('name') for c in (_lc() or [])}
                except Exception:
                    pass
                w.writerow(['id', 'machine_name', 'minecraft_username',
                            'company_id', 'company_name', 'status', 'verdict',
                            'risk_score', 'started_at', 'completed_at'])
                for r in rows:
                    cid = _row_get(r, 3, 'company_id')
                    w.writerow([
                        _row_get(r, 0, 'id'),
                        _row_get(r, 1, 'machine_name'),
                        _row_get(r, 2, 'minecraft_username'),
                        cid, cmap.get(cid, ''),
                        _row_get(r, 4, 'status'),
                        _row_get(r, 5, 'verdict'),
                        _row_get(r, 6, 'risk_score') or 0,
                        str(_row_get(r, 7, 'started_at') or ''),
                        str(_row_get(r, 8, 'completed_at') or ''),
                    ])
                    rows_count += 1

        else:
            return jsonify({'error': f'kind desconocido: {kind}'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    csv_data = buf.getvalue()
    fname = f'argus_sa_export_{kind}_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    return _Resp(
        '\ufeff' + csv_data,  # BOM para Excel
        mimetype='text/csv; charset=utf-8',
        headers={
            'Content-Disposition': f'attachment; filename="{fname}"',
            'X-Rows-Count': str(rows_count),
        },
    )


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Pack 42 â€” Aislamiento entre empresas: gestiÃ³n de staff huÃ©rfanos
# (legacy con company_id NULL) desde el SuperAdmin.
# Antes cualquier admin de empresa podÃ­a "adoptar" huÃ©rfanos a un clic, lo
# que permitÃ­a robar staff de otras empresas o de la pool individual. Ahora
# solo el SuperAdmin puede asignarlos, eligiendo explÃ­citamente la empresa
# destino (o null para mantenerlos como individuales).
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

@app.route('/aspers-sa/api/orphan-staff', methods=['GET'])
@_sa_required
def sa_api_orphan_staff_list():
    """Lista usuarios staff con company_id NULL (huÃ©rfanos) y todas las
    empresas disponibles, para poder asignar manualmente desde el panel SA.
    """
    try:
        from auth import list_users as _lu, list_companies as _lc
        users = _lu() or []
        companies = _lc() or []
        adoptable = {r for r in STAFF_ROLE_HIERARCHY if r != 'owner'}
        orphans = []
        for u in users:
            if u.get('company_id') is not None:
                continue
            roles = u.get('roles') or []
            if not any(r in adoptable for r in roles):
                continue
            orphans.append({
                'id': u.get('id'),
                'username': u.get('username'),
                'email': u.get('email', ''),
                'roles': roles,
                'staff_role': get_staff_role(u),
                'is_active': u.get('is_active', True),
                'created_at': str(u.get('created_at', '')),
            })
        comp_list = [
            {'id': c.get('id'), 'name': c.get('name')}
            for c in companies
        ]
        return jsonify({
            'orphans': orphans,
            'companies': comp_list,
            'total': len(orphans),
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/aspers-sa/api/orphan-staff/assign', methods=['POST'])
@_sa_required
def sa_api_orphan_staff_assign():
    """Asigna uno o varios staff huÃ©rfanos a una empresa concreta.
    Body JSON: { "user_ids": [int, ...], "target_company_id": int|null }
    Si target_company_id es null, los deja explÃ­citamente como individuales
    (no cambia nada Ãºtil, pero permite consultar el caso). Si no es null,
    debe existir en la BD.
    """
    data = request.json or {}
    raw_ids = data.get('user_ids') or []
    if not isinstance(raw_ids, list) or not raw_ids:
        return jsonify({'error': 'user_ids debe ser lista no vacÃ­a'}), 400
    try:
        user_ids = [int(x) for x in raw_ids]
    except Exception:
        return jsonify({'error': 'user_ids debe contener enteros'}), 400

    target_company_id = data.get('target_company_id')
    if target_company_id is not None:
        try:
            target_company_id = int(target_company_id)
        except Exception:
            return jsonify({'error': 'target_company_id invÃ¡lido'}), 400
        from auth import get_company_by_id as _gc
        if not _gc(target_company_id):
            return jsonify({'error': f'Empresa {target_company_id} no existe'}), 404

    try:
        from auth import _auth_cursor, _ph
        ph = _ph()
        updated = 0
        skipped = []
        with _auth_cursor() as cursor:
            for uid in user_ids:
                target = get_user_by_id(uid)
                if not target:
                    skipped.append({'id': uid, 'reason': 'not_found'})
                    continue
                cur_cid = target.get('company_id')
                if cur_cid == target_company_id:
                    skipped.append({'id': uid, 'reason': 'already_assigned'})
                    continue
                if cur_cid is not None and target_company_id is not None:
                    skipped.append({'id': uid, 'reason': 'in_other_company', 'company_id': cur_cid})
                    continue
                cursor.execute(
                    f'UPDATE users SET company_id = {ph} WHERE id = {ph}',
                    (target_company_id, uid)
                )
                updated += 1
        return jsonify({
            'success': True,
            'updated': updated,
            'skipped': skipped,
            'target_company_id': target_company_id,
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Pack 40 — Control Imperial: permisos totales + God Mode

def _sa_imperial_flags():
    """Lee flags de plataforma."""
    try:
        import sa_permissions as _sap
        with get_api_db_cursor() as cur:
            return _sap.get_platform_flags(cur)
    except Exception:
        return {}


@app.route('/aspers-sa/api/permissions/catalog', methods=['GET'])
@_sa_required
def sa_api_permissions_catalog():
    from sa_permissions import catalog_response
    return jsonify(catalog_response()), 200


@app.route('/aspers-sa/api/permissions/users', methods=['GET'])
@_sa_required
def sa_api_permissions_users():
    import sa_permissions as _sap
    from auth import list_users as _lu, list_companies as _lc
    users = _lu() or []
    cmap = {c.get('id'): c.get('name') for c in (_lc() or [])}
    out = []
    try:
        with get_api_db_cursor() as cur:
            _sap.ensure_sa_permission_tables(cur, use_pg=_USE_PG or _USE_MYSQL)
            for u in users:
                ov = _sap.get_user_overrides(cur, u['id'])
                eff = _sap.effective_permissions(u, ov)
                out.append({
                    'id': u['id'],
                    'username': u['username'],
                    'email': u.get('email'),
                    'roles': eff['roles'],
                    'is_active': u.get('is_active', True),
                    'company_id': u.get('company_id'),
                    'company_name': cmap.get(u.get('company_id'), '—'),
                    'power_level': eff['power_level'],
                    'permission_count': eff['effective_count'],
                    'override_count': len(ov),
                    'last_login': u.get('last_login'),
                })
    except Exception as e:
        return jsonify({'error': str(e), 'users': []}), 500
    out.sort(key=lambda x: (-x['power_level'], x['username'].lower()))
    return jsonify({'users': out, 'count': len(out)}), 200


@app.route('/aspers-sa/api/permissions/users/<int:uid>', methods=['GET'])
@_sa_required
def sa_api_permissions_user_detail(uid):
    import sa_permissions as _sap
    from auth import list_companies as _lc
    user = get_user_by_id(uid)
    if not user:
        return jsonify({'error': 'Usuario no encontrado'}), 404
    with get_api_db_cursor() as cur:
        ov = _sap.get_user_overrides(cur, uid)
        eff = _sap.effective_permissions(user, ov)
    cmap = {c.get('id'): c.get('name') for c in (_lc() or [])}
    return jsonify({
        'user': {
            'id': user['id'],
            'username': user['username'],
            'email': user.get('email'),
            'is_active': user.get('is_active', True),
            'company_id': user.get('company_id'),
            'company_name': cmap.get(user.get('company_id')),
            'created_at': user.get('created_at'),
            'last_login': user.get('last_login'),
        },
        'permissions': eff,
        'companies': [{'id': c.get('id'), 'name': c.get('name')} for c in (_lc() or [])],
    }), 200


@app.route('/aspers-sa/api/permissions/users/<int:uid>/roles', methods=['PUT'])
@_sa_required
def sa_api_permissions_set_roles(uid):
    import json as _json
    import sa_permissions as _sap
    data = request.get_json(silent=True) or {}
    roles = data.get('roles')
    if not isinstance(roles, list) or not roles:
        return jsonify({'error': 'roles debe ser lista no vacía'}), 400
    allowed = {'user', 'empresa', 'staff', 'helper', 'moderador', 'admin', 'administrador', 'owner'}
    clean = []
    for r in roles:
        r = str(r).strip().lower()
        if r in allowed and r not in clean:
            clean.append(r)
    if not clean:
        return jsonify({'error': 'Ningún rol válido'}), 400
    if not get_user_by_id(uid):
        return jsonify({'error': 'Usuario no encontrado'}), 404
    try:
        from auth import _auth_cursor, _ph
        ph = _ph()
        with _auth_cursor() as cursor:
            cursor.execute(
                f'UPDATE users SET roles = {ph} WHERE id = {ph}',
                (_json.dumps(clean), uid),
            )
        with get_api_db_cursor() as cur:
            _sap.log_imperial_action(
                cur, 'user.set_roles', target_type='user', target_id=uid,
                detail=f'roles={clean}', ip=request.remote_addr,
            )
        user = get_user_by_id(uid)
        with get_api_db_cursor() as cur:
            ov = _sap.get_user_overrides(cur, uid)
        return jsonify({'ok': True, 'roles': clean, 'permissions': _sap.effective_permissions(user, ov)}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/aspers-sa/api/permissions/users/<int:uid>/overrides', methods=['PUT'])
@_sa_required
def sa_api_permissions_set_overrides(uid):
    import sa_permissions as _sap
    if not get_user_by_id(uid):
        return jsonify({'error': 'Usuario no encontrado'}), 404
    data = request.get_json(silent=True) or {}
    overrides = data.get('overrides') or {}
    if not isinstance(overrides, dict):
        return jsonify({'error': 'overrides debe ser objeto'}), 400
    try:
        with get_api_db_cursor() as cur:
            saved = _sap.set_user_overrides(cur, uid, overrides)
            _sap.log_imperial_action(
                cur, 'user.set_overrides', target_type='user', target_id=uid,
                detail=str(saved)[:500], ip=request.remote_addr,
            )
        user = get_user_by_id(uid)
        return jsonify({'ok': True, 'overrides': saved, 'permissions': _sap.effective_permissions(user, saved)}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/aspers-sa/api/permissions/users/<int:uid>', methods=['PATCH'])
@_sa_required
def sa_api_permissions_patch_user(uid):
    import sa_permissions as _sap
    from auth import hash_password, _auth_cursor, _ph
    target = get_user_by_id(uid)
    if not target:
        return jsonify({'error': 'Usuario no encontrado'}), 404
    data = request.get_json(silent=True) or {}
    updates = []
    params = []
    ph = _ph()
    if 'is_active' in data:
        updates.append(f'is_active = {ph}')
        params.append(bool(data['is_active']))
    if 'email' in data:
        updates.append(f'email = {ph}')
        params.append((data.get('email') or '').strip() or None)
    if 'company_id' in data:
        cid = data.get('company_id')
        if cid is not None:
            from auth import get_company_by_id as _gc
            if cid and not _gc(int(cid)):
                return jsonify({'error': 'Empresa no existe'}), 404
            updates.append(f'company_id = {ph}')
            params.append(int(cid) if cid else None)
    new_password = (data.get('password') or '').strip()
    if new_password:
        if len(new_password) < 6:
            return jsonify({'error': 'Contraseña mínimo 6 caracteres'}), 400
        updates.append(f'password_hash = {ph}')
        params.append(hash_password(new_password))
    if not updates:
        return jsonify({'error': 'Nada que actualizar'}), 400
    params.append(uid)
    try:
        with _auth_cursor() as cursor:
            cursor.execute(
                f"UPDATE users SET {', '.join(updates)} WHERE id = {ph}",
                tuple(params),
            )
        with get_api_db_cursor() as cur:
            _sap.log_imperial_action(
                cur, 'user.patch', target_type='user', target_id=uid,
                detail=','.join([u.split('=')[0].strip() for u in updates]),
                ip=request.remote_addr,
            )
        return jsonify({'ok': True, 'user': get_user_by_id(uid)}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/aspers-sa/api/permissions/users/create', methods=['POST'])
@_sa_required
def sa_api_permissions_create_user():
    import sa_permissions as _sap
    from auth import create_user
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    password = (data.get('password') or '').strip()
    if not username or not password:
        return jsonify({'error': 'username y password requeridos'}), 400
    roles = data.get('roles') or ['user']
    company_id = data.get('company_id')
    if company_id is not None:
        company_id = int(company_id)
    result = create_user(
        username=username,
        password=password,
        email=(data.get('email') or '').strip() or None,
        roles=roles,
        company_id=company_id,
        created_by=None,
    )
    if not result.get('success'):
        return jsonify({'error': result.get('error', 'Error')}), 400
    uid = result.get('user_id')
    with get_api_db_cursor() as cur:
        _sap.log_imperial_action(
            cur, 'user.create', target_type='user', target_id=uid,
            detail=f'username={username} roles={roles}', ip=request.remote_addr,
        )
    return jsonify({'ok': True, 'user_id': uid}), 201


@app.route('/aspers-sa/api/god-mode/flags', methods=['GET', 'PUT'])
@_sa_required
def sa_api_god_mode_flags():
    import sa_permissions as _sap
    if request.method == 'GET':
        with get_api_db_cursor() as cur:
            flags = _sap.get_platform_flags(cur)
        return jsonify({'flags': flags, 'definitions': _sap.GOD_MODE_FLAGS}), 200
    data = request.get_json(silent=True) or {}
    updates = data.get('flags') or data
    if not isinstance(updates, dict):
        return jsonify({'error': 'flags debe ser objeto'}), 400
    try:
        with get_api_db_cursor() as cur:
            flags = _sap.set_platform_flags(cur, updates)
            _sap.log_imperial_action(
                cur, 'god_mode.update', target_type='platform',
                detail=str(updates)[:500], ip=request.remote_addr,
            )
        return jsonify({'ok': True, 'flags': flags}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/aspers-sa/api/permissions/users/<int:uid>/impersonate', methods=['POST'])
@_sa_required
def sa_api_impersonate_user(uid):
    import sa_permissions as _sap
    user = get_user_by_id(uid)
    if not user:
        return jsonify({'error': 'Usuario no encontrado'}), 404
    if not user.get('is_active', True):
        return jsonify({'error': 'Usuario inactivo'}), 400
    token = _sap.create_impersonate_token(uid, user['username'])
    with get_api_db_cursor() as cur:
        _sap.log_imperial_action(
            cur, 'user.impersonate', target_type='user', target_id=uid,
            detail=user['username'], ip=request.remote_addr,
        )
    base = request.url_root.rstrip('/')
    return jsonify({
        'ok': True,
        'token': token,
        'url': f'{base}/aspers-sa/impersonate/{token}',
        'expires_in': 300,
        'username': user['username'],
    }), 200


@app.route('/aspers-sa/impersonate/<token>')
def sa_impersonate_consume(token):
    import sa_permissions as _sap
    if not session.get('admin_subscriptions'):
        return redirect('/aspers-sa')
    data = _sap.consume_impersonate_token(token)
    if not data:
        flash('Token de impersonación inválido o expirado', 'error')
        return redirect('/aspers-sa#poder')
    user = get_user_by_id(data['user_id'])
    if not user:
        flash('Usuario ya no existe', 'error')
        return redirect('/aspers-sa#poder')
    session['user_id'] = user['id']
    session['username'] = user['username']
    session['roles'] = user.get('roles') or []
    session['company_id'] = user.get('company_id')
    session['impersonated_by_sa'] = True
    flash(f"Sesión abierta como {user['username']} (Imperial)", 'ok')
    return redirect('/panel')


@app.route('/aspers-sa/api/imperial-audit', methods=['GET'])
@_sa_required
def sa_api_imperial_audit():
    import sa_permissions as _sap
    limit = max(10, min(200, int(request.args.get('limit', 50))))
    rows = []
    try:
        with get_api_db_cursor() as cur:
            _sap.ensure_sa_permission_tables(cur)
            try:
                cur.execute(
                    'SELECT id, action, target_type, target_id, detail, ip_address, created_at '
                    'FROM sa_imperial_audit ORDER BY id DESC LIMIT %s',
                    (limit,),
                )
            except Exception:
                cur.execute(
                    'SELECT id, action, target_type, target_id, detail, ip_address, created_at '
                    'FROM sa_imperial_audit ORDER BY id DESC LIMIT ?',
                    (limit,),
                )
            for r in cur.fetchall() or []:
                rows.append({
                    'id': _row_get(r, 0, 'id'),
                    'action': _row_get(r, 1, 'action'),
                    'target_type': _row_get(r, 2, 'target_type'),
                    'target_id': _row_get(r, 3, 'target_id'),
                    'detail': _row_get(r, 4, 'detail'),
                    'ip': _row_get(r, 5, 'ip_address'),
                    'created_at': str(_row_get(r, 6, 'created_at') or ''),
                })
    except Exception as e:
        return jsonify({'error': str(e), 'rows': []}), 500
    return jsonify({'rows': rows, 'count': len(rows)}), 200


@app.route('/api/platform/flags', methods=['GET'])
def api_public_platform_flags():
    flags = _sa_imperial_flags()
    return jsonify({
        'maintenance_mode': bool(flags.get('maintenance_mode')),
        'panel_readonly': bool(flags.get('panel_readonly')),
        'announcement_banner': (flags.get('announcement_banner') or '').strip(),
    }), 200


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Fin Pack 39 â€” Super Admin Panel API
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Hotfix Pack 41 â€” arrancar init_db_async() AQUÃ, AHORA que TODAS las
# funciones del mÃ³dulo estÃ¡n definidas (get_api_db_cursor en ~1091,
# _ensure_plugin_keys_schema en ~2203, _notify_new_deploy en ~113, etc).
# Antes el .start() vivÃ­a en lÃ­nea ~373 y arrancaba el thread durante el
# import del mÃ³dulo, antes de que esas defs existieran. Eso provocaba
# NameError: name 'get_api_db_cursor' is not defined en cada deploy y
# rompÃ­a TODAS las migraciones (short_code, download_links, hack_blacklist,
# ensemble_data, plugin_keys schema) mÃ¡s la notificaciÃ³n a Discord.
# Esto se ejecuta cuando gunicorn importa el mÃ³dulo (no requiere __main__).
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
threading.Thread(target=init_db_async, daemon=True).start()


# ──────────────────────────────────────────────────────────────────────
#  Pack 45: background jobs ML
# ──────────────────────────────────────────────────────────────────────

def _ml_background_loop():
    """
    Loop daemon que corre cada 10min:
      1. Lista companies activas con decisiones recientes
      2. Por cada company: ejecuta auto-labeling pipelines
      3. Re-entrena modelos si hay suficiente data nueva
      4. Modelo global (company_id=0) se re-entrena con bootstrap+todo el feedback

    Se inicia tras un delay de 90s para que la BD este lista.
    """
    import time as _t
    print("[ml_bg] thread iniciado, primer run en 90s")
    _t.sleep(90)
    # Primera corrida — bootstrap global del modelo si no existe
    try:
        with get_api_db_cursor() as cursor:
            cursor.execute("SELECT COUNT(*) AS c FROM ai_model_state WHERE company_id = 0")
            r = cursor.fetchone()
            r = dict(r) if not isinstance(r, dict) else r
            if not r or int(r.get('c') or 0) == 0:
                print("[ml_bg] modelo global no existe, training inicial...")
                result = _train_models_for(0, triggered_by='bootstrap')
                print(f"[ml_bg] bootstrap train result: "
                      f"logreg={(result.get('logreg') or {}).get('accuracy')}, "
                      f"knn={(result.get('knn') or {}).get('size')}, "
                      f"samples_real={result.get('samples_real')}")
    except Exception as e:
        print(f"[ml_bg] bootstrap error: {e}")

    # Loop principal
    while True:
        try:
            _t.sleep(600)  # 10 min entre iteraciones
            companies: list[int] = [0]  # global siempre
            try:
                with get_api_db_cursor() as cursor:
                    cursor.execute(
                        "SELECT DISTINCT company_id FROM ai_decisions_log "
                        "WHERE created_at > CURRENT_TIMESTAMP - INTERVAL '7 days'"
                        if _USE_PG else
                        "SELECT DISTINCT company_id FROM ai_decisions_log "
                        "WHERE created_at > datetime('now', '-7 days')"
                    )
                    for r in cursor.fetchall() or []:
                        r = dict(r) if not isinstance(r, dict) else r
                        cid = int(r.get('company_id') or 0)
                        if cid and cid not in companies:
                            companies.append(cid)
            except Exception as e:
                print(f"[ml_bg] error listando companies: {e}")

            for cid in companies:
                # 1) Auto-labeling sobre decisiones pendientes
                try:
                    al_result = _run_auto_labeling_for(cid, limit=200)
                    print(f"[ml_bg] auto-label company={cid}: "
                          f"processed={al_result.get('decisions_processed')} "
                          f"created={al_result.get('labels_created')}")
                except Exception as e:
                    print(f"[ml_bg] auto-label company={cid} error: {e}")

                # 2) Re-entrenar si vale la pena (hay feedback/auto-labels nuevos)
                try:
                    train_result = _train_models_for(cid, triggered_by='cron')
                    lr = train_result.get('logreg') or {}
                    print(f"[ml_bg] retrain company={cid}: "
                          f"acc={lr.get('accuracy')} samples={train_result.get('samples_real')}+{train_result.get('samples_synthetic')}")
                except Exception as e:
                    print(f"[ml_bg] retrain company={cid} error: {e}")
        except Exception as e:
            print(f"[ml_bg] loop error: {e}")
            _t.sleep(60)


threading.Thread(target=_ml_background_loop, daemon=True).start()


# ──────────────────────────────────────────────────────────────────────
#  Pack 46: Daily brief notifier (cada 24h, mid-noche)
# ──────────────────────────────────────────────────────────────────────

def _daily_brief_loop():
    """
    Cada 24h aprox (3:00 AM hora del server), genera el brief del día
    para cada empresa con actividad y lo persiste para que el panel lo
    muestre + notifica via Discord webhook si esta configurado.
    """
    import time as _t
    print("[daily_brief] thread iniciado, primer brief en ~3h")
    _t.sleep(60 * 60 * 3)  # esperar 3h tras boot
    while True:
        try:
            import argus_ai_assistant as _A
            with get_api_db_cursor() as cursor:
                # Listar companies con decisiones en ultimas 24h
                interval_sql = ("CURRENT_TIMESTAMP - INTERVAL '24 hours'"
                                if _USE_PG else "datetime('now', '-24 hours')")
                cursor.execute(
                    f"SELECT DISTINCT company_id FROM ai_decisions_log "
                    f"WHERE created_at > {interval_sql}"
                )
                companies = []
                for r in cursor.fetchall() or []:
                    r = dict(r) if not isinstance(r, dict) else r
                    cid = int(r.get('company_id') or 0)
                    if cid:
                        companies.append(cid)
                if not companies:
                    companies = [0]  # generar al menos el global
                for cid in companies:
                    stats = _get_daily_stats_for_assistant(cursor, cid, days=1)
                    brief = _A.daily_brief(stats)
                    # Guardar como "decision sintetica" para que aparezca
                    # en el log de decisiones del panel
                    try:
                        cursor.execute(
                            f"INSERT INTO ai_decisions_log "
                            f"(company_id, player_uuid, player_name, score, confidence, "
                            f"action, reasoning, evidence_json, triggered_by) "
                            f"VALUES ({_PH},{_PH},{_PH},0,0,'brief',{_PH},{_PH},'daily_brief_cron')",
                            (cid, 'system', 'Argus AI Brief', brief, json.dumps(stats))
                        )
                    except Exception as e:
                        print(f"[daily_brief] insert error company={cid}: {e}")
                    print(f"[daily_brief] generado para company={cid}: "
                          f"{stats.get('evaluations_count')} evals, "
                          f"{stats.get('bans_count')} bans")
        except Exception as e:
            print(f"[daily_brief] loop error: {e}")
        _t.sleep(60 * 60 * 24)  # 24h


threading.Thread(target=_daily_brief_loop, daemon=True).start()

try:
    from argus_admin_api import register_argus_admin_routes as _register_argus_admin
    _register_argus_admin(
        app,
        get_api_db_cursor=get_api_db_cursor,
        row_get=_row_get,
        use_pg=_USE_PG,
        is_panel_owner_fn=_is_panel_owner,
    )
    print('[boot] ArgusAdmin API registrada (/api/argus-admin/v1/*)')
except Exception as _argus_admin_boot_err:
    print(f'[boot] argus_admin_api no disponible: {_argus_admin_boot_err}')

try:
    from sa_imperial_api import register_sa_imperial_routes as _register_sa_imperial
    _register_sa_imperial(
        app,
        get_api_db_cursor=get_api_db_cursor,
        row_get=_row_get,
        sa_required_fn=_sa_required,
        get_user_by_id_fn=get_user_by_id,
    )
    print('[boot] Imperial API v2 registrada (/aspers-sa/api/v2/*)')
except Exception as _sa_imperial_boot_err:
    print(f'[boot] sa_imperial_api no disponible: {_sa_imperial_boot_err}')


if __name__ == '__main__':
    _port = int(os.environ.get('PORT', '8080'))
    _host = '127.0.0.1' if _is_local_dev() and not IS_RENDER else '0.0.0.0'
    _debug = os.environ.get('FLASK_DEBUG', '1').strip().lower() in ('1', 'true', 'yes')
    _reload = _debug and not (_is_local_dev() and not IS_RENDER)
    print("Iniciando aplicacion web ASPERS Projects...")
    print(f"API: {API_BASE_URL}")
    print(f"BD:  {'PostgreSQL (DATABASE_URL)' if os.environ.get('DATABASE_URL') else 'SQLite local'}")
    if _is_local_dev() and not IS_RENDER:
        print(f"Modo local privado → http://127.0.0.1:{_port}/panel")
        print("Login: pestaña Individual o Empresa (misma cuenta en local).")
        print("Los cambios de codigo NO suben solos a Render: git push → deploy.")
    elif not IS_RENDER:
        print("Tip: copia web_app/.env.local.example → .env.local y usa BAT/INICIAR_PANEL_LOCAL.bat")
        print("Legacy API separada: http://localhost:5000 (INICIAR_SISTEMA_COMPLETO.bat)")
    if socketio is not None:
        socketio.run(app, host=_host, port=_port, debug=_debug, use_reloader=_reload)
    else:
        app.run(host=_host, port=_port, debug=_debug, use_reloader=_reload)

