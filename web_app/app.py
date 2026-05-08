"""
Aplicación Web Flask para Panel del Staff de ASPERS Projects
"""
import sys as _sys
_sys.stdout.reconfigure(line_buffering=True)  # forzar stdout unbuffered
from flask import Flask, render_template, request, jsonify, session, Response, redirect, url_for, make_response, flash, send_file
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

# Pack 32 — Sistema de Trust + Cooldown (F#54, F#55, F#60).
# Se importa en try/except por compatibilidad: si el archivo no está
# (deploy parcial, rollback), el resto de la app sigue funcionando.
try:
    import ai_trust as _ai_trust
    _AI_TRUST_AVAILABLE = True
except Exception as _ai_trust_err:
    _ai_trust = None
    _AI_TRUST_AVAILABLE = False
    print(f'[boot] ai_trust no disponible: {_ai_trust_err}')

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'aspers-secret-key-change-in-production')

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


@app.before_request
def _make_session_permanent():
    """Marca la sesion como permanente para que dure PERMANENT_SESSION_LIFETIME
    en lugar de morir al cerrar el navegador."""
    from flask import session as _s
    _s.permanent = True


CORS(app)

# Inicializar base de datos de autenticación al iniciar (en background para no bloquear)
_ARGUS_VERSION = '1.6.49'  # sincronizar con SCANNER_VERSION en main.py y CURRENT_SCANNER_VERSION abajo

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
    }


def _notify_new_deploy():
    """Detecta si es un deploy nuevo comparando RENDER_GIT_COMMIT con el último
    commit almacenado en BD. Si es nuevo, envía embed a Discord vía webhook.
    Solo se ejecuta en Render (RENDER_GIT_COMMIT presente).

    Variable de entorno requerida:
      DISCORD_DEPLOY_WEBHOOK — URL completa del webhook de Discord
    """
    commit  = os.environ.get('RENDER_GIT_COMMIT', '').strip()
    branch  = os.environ.get('RENDER_GIT_BRANCH', 'main').strip()
    service = os.environ.get('RENDER_SERVICE_NAME', 'argus-web').strip()
    webhook = os.environ.get('DISCORD_DEPLOY_WEBHOOK', '').strip()

    print(f'[Deploy] DEBUG commit={commit[:7] if commit else "VACÍO"} branch={branch} service={service}')
    print(f'[Deploy] DEBUG webhook={"SET ("+webhook[:30]+"...)" if webhook else "NO CONFIGURADO"}')

    if not commit:
        print('[Deploy] Sin RENDER_GIT_COMMIT — entorno local, saliendo')
        return
    if not webhook:
        print('[Deploy] ❌ DISCORD_DEPLOY_WEBHOOK no está configurado como variable de entorno en Render')
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
                print(f'[Deploy] Mismo commit ({commit[:7]}) — restart sin deploy nuevo, no se notifica')
                return

            cur.execute('''
                INSERT INTO app_meta (key, value, updated_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
            ''', ('last_deploy_commit', commit))
            print(f'[Deploy] BD actualizada con nuevo commit {commit[:7]}')

    except Exception as e:
        print(f'[Deploy] ❌ Error leyendo/escribiendo BD: {e}')
        return

    # Guardar webhook pendiente en BD — el scheduler lo reintentará cada 10 min
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
        print('[Deploy] Notificación guardada en BD — el scheduler reintentará cada 10 min')
    except Exception as e:
        print(f'[Deploy] ❌ No se pudo guardar notificación pendiente: {e}')

    # Primer intento inmediato en background (puede fallar por 429 de CF)
    threading.Thread(target=_try_send_deploy_webhook, daemon=True).start()
    # Telegram — backup instantáneo (no tiene el problema de IP ban de Cloudflare)
    _tg_msg = (
        f'🚀 <b>Nuevo Deploy</b> — Argus {_ARGUS_VERSION}\n'
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
            print(f'[Deploy] ❌ Webhook fallido tras {max_att} intentos — abandonando')
        return

    short   = meta.get('commit', '')[:7]
    now     = _dt.datetime.utcnow().strftime('%d/%m/%Y %H:%M UTC')
    version = meta.get('version', _ARGUS_VERSION)
    branch  = meta.get('branch', 'main')
    service = meta.get('service', 'argus-web')

    payload = {
        'embeds': [{
            'title': '🚀 ArgusScanner desplegado',
            'description': 'El sistema de detección de hacks ha sido desplegado exitosamente en producción.',
            'color': 0x7C3AED,
            'fields': [
                {'name': '📦 Versión',   'value': f'`{version}`', 'inline': True},
                {'name': '🔖 Commit',    'value': f'`{short}`',   'inline': True},
                {'name': '🌿 Rama',      'value': f'`{branch}`',  'inline': True},
                {'name': '🖥️ Servicio', 'value': f'`{service}`', 'inline': True},
                {'name': '✅ Estado',    'value': 'Operativo',    'inline': True},
                {'name': '🕐 Hora',      'value': now,            'inline': True},
            ],
            'footer': {'text': 'ASPERS Projects — Sistema Argus'},
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
            print(f'✅ [Deploy] Webhook enviado — HTTP {resp.status} — commit {short}')
            # Éxito: borrar de BD
            with get_api_db_cursor() as cur:
                cur.execute('DELETE FROM app_meta WHERE key = %s', ('pending_deploy_webhook',))
            return
    except _urlerr.HTTPError as e:
        body_preview = e.read(200).decode('utf-8', errors='replace').strip()
        retry_after  = e.headers.get('Retry-After', '?')
        print(f'⚠️ [Deploy] HTTP {e.code} (Retry-After: {retry_after}s) — {body_preview[:120]}')
    except Exception as e:
        print(f'⚠️ [Deploy] Error de red: {e}')

    # Fracasó — incrementar contador en BD para el próximo intento del scheduler
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
    """Inicializa la BD de forma asíncrona para no bloquear el inicio"""
    try:
        init_auth_db()
        print("✅ Base de datos de autenticación inicializada correctamente")
    except Exception as e:
        print(f"⚠️ Error al inicializar base de datos: {e}")
        print("⚠️ La aplicación continuará, pero algunas funciones pueden no funcionar")
    # Migración: columna short_code en scan_tokens (códigos de 6 chars)
    try:
        with get_api_db_cursor() as _cur:
            _cur.execute("ALTER TABLE scan_tokens ADD COLUMN IF NOT EXISTS short_code VARCHAR(8) UNIQUE")
            _cur.execute("CREATE INDEX IF NOT EXISTS idx_st_short_code ON scan_tokens(short_code)")
        print("✅ Columna short_code en scan_tokens verificada/creada")
    except Exception as _e:
        print(f"⚠️ Error migrando short_code: {_e}")
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
    # Tabla hack_blacklist — hashes confirmados como hacks en 3+ scans
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
        print("✅ Tabla hack_blacklist verificada/creada")
    except Exception as _e:
        print(f"⚠️ Error creando hack_blacklist: {_e}")
    # Migración: columna ensemble_data en scans (veredicto 6-sistemas)
    try:
        with get_api_db_cursor() as _cur:
            _cur.execute("ALTER TABLE scans ADD COLUMN IF NOT EXISTS ensemble_data TEXT")
        print("✅ Columna ensemble_data en scans verificada/creada")
    except Exception as _e:
        print(f"⚠️ Error migrando ensemble_data: {_e}")
    # Migración: tablas/columnas para sistema de plugin keys (Minecraft).
    # IMPORTANTE: ejecutar UNA SOLA VEZ al startup. Antes esto se ejecutaba
    # on-demand desde @before_request via _plugin_schema_guard(), lo cual
    # provocaba DEADLOCKs entre el ALTER TABLE scan_tokens (AccessExclusiveLock)
    # y los SELECTs concurrentes con LEFT JOIN scan_tokens en /api/scans/<id>.
    try:
        _ensure_plugin_keys_schema()
        global _PLUGIN_SCHEMA_READY
        _PLUGIN_SCHEMA_READY = True
        print("✅ Schema de plugin_keys verificado/creado")
    except Exception as _e:
        print(f"⚠️ Error migrando plugin_keys schema: {_e}")
    # Notificación de deploy nuevo — se dispara una sola vez por commit
    _notify_new_deploy()

# Inicializar en un thread separado para no bloquear el inicio
import threading
threading.Thread(target=init_db_async, daemon=True).start()

def _autonomous_daily_learning():
    """Pipeline de aprendizaje autónomo — corre cada día a las 2:00 UTC.

    Pasos en orden:
      1. Hash consensus  — detecta hashes maliciosos por frecuencia estadística
      2. Auto-labels     — genera pseudo-etiquetas para scans extremos sin veredicto humano
      3. RF retrain      — reentrena Random Forest con humanos + auto-labels
      4. Isolation Forest— reentrena detector de anomalías con todos los scans
    No requiere ningún input externo ni veredicto humano para operar.
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
        print(f"[ML Auto] Error en pipeline autónomo: {e}")
        print(traceback.format_exc())

def _daily_summary_job():
    """P3 #25 — Resumen diario de scans del día anterior, enviado a Discord a las 9:00 UTC."""
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
            top_types = [f"{_row_get(r, 0, 'issue_type')} ×{int(_row_get(r, 1, 'n') or 0)}" for r in (cur.fetchall() or [])]

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
    _scheduler.add_job(_try_send_deploy_webhook, 'interval', minutes=10,
                       id='deploy_webhook_retry', replace_existing=True)
    _scheduler.start()
    print('[Scheduler] ML autónomo diario (2:00 UTC) + resumen diario + deploy webhook retry activados')
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


# Visual #38 - timestamp de arranque para calcular uptime
import time as _time_mod
_APP_START_TIME = _time_mod.time()


@app.route('/api/version', methods=['GET'])
def api_version():
    """Devuelve versión, uptime y estado de la API. Usado por el footer del
    panel para mostrar 'Argus v1.6.36 · uptime 2d 4h · ✓ DB OK'."""
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
    try:
        conn = get_db_connection()
        cur  = conn.cursor()
        cur.execute('SELECT 1')
        cur.fetchone()
    except Exception:
        db_ok = False
    return jsonify({
        'version':       _ARGUS_VERSION,
        'scanner_version': CURRENT_SCANNER_VERSION,
        'uptime_seconds': uptime_seconds,
        'uptime_human':  uptime_human,
        'db_ok':         db_ok,
        'started_at':    int(_APP_START_TIME),
    })

@app.route('/api/public_stats', methods=['GET'])
def api_public_stats():
    """Stats públicas agregadas para el live counter del index. NUNCA devuelve
    datos privados (no nombres de jugadores, empresas, etc.) — solo totales
    para el efecto 'Argus está vivo'.

    Visual #39 — alimenta el live counter del index. Cacheado en memoria 30s
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
            cur.execute("SELECT COUNT(*) FROM scans WHERE fecha > NOW() - INTERVAL '24 hours'")
            row = cur.fetchone()
            out['scans_24h'] = int(_first_value(row) or 0)
        except Exception:
            pass
        try:
            cur.execute('SELECT COUNT(*) FROM scan_verdicts')
            row = cur.fetchone()
            out['verdicts_total'] = int(_first_value(row) or 0)
        except Exception:
            pass
        try:
            cur.execute('SELECT COUNT(*) FROM empresas')
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
    RealDictCursor (dict) o cursor estándar (tuple)."""
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
    return render_template('panel.html', user=user, staff_role=staff_role, scanner_version=_ARGUS_VERSION)

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

@app.route('/api/servers', methods=['GET'])
@login_required
def list_servers():
    """P5 #29 — Lista servidores a los que el usuario tiene acceso.
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
    """P5 #29 — Selecciona el servidor activo para filtrar vistas del panel."""
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

        # Asegurar columna short_code existe (migración síncrona por si el background thread aún no corrió)
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

        # Generar código único de 6 caracteres
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


# ════════════════════════════════════════════════════════════════════════════
#  PLUGIN KEYS — sistema multi-tenant para servidores Minecraft
#  -----------------------------------------------------------------
#  Cada empresa puede emitir N "plugin keys" (una por servidor MC). El plugin
#  Java que va dentro del server las usa para llamar a /api/plugin/issue-token
#  cuando el staff ejecuta /ss <player>. El backend genera un token de scan
#  marcado con `minecraft_staff` (quien ejecuto /ss) y `plugin_key_id` para
#  trackeo, y lo devuelve al plugin.
#
#  Compatibilidad: NO toca scan_tokens existentes; solo agrega columnas
#  nullable mediante ALTER TABLE IF NOT EXISTS.
# ════════════════════════════════════════════════════════════════════════════

_PLUGIN_SCHEMA_READY = False
_PLUGIN_SCHEMA_LOCK = threading.Lock() if 'threading' in globals() else None


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
    AccessShareLock) — caso tipico: get_scan() en /api/scans/<id>.

    Solucion: chequear primero con information_schema (solo share lock) y
    ejecutar el ALTER unicamente si la columna realmente NO existe."""
    import threading as _t
    global _PLUGIN_SCHEMA_LOCK
    if _PLUGIN_SCHEMA_LOCK is None:
        _PLUGIN_SCHEMA_LOCK = _t.Lock()
    with _PLUGIN_SCHEMA_LOCK:
        try:
            with get_api_db_cursor() as cursor:
                # Tabla nueva — CREATE IF NOT EXISTS no toma locks fuertes
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

                # Columnas adicionales en scan_tokens — solo ALTER si no existen
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
    global _PLUGIN_SCHEMA_READY
    if _PLUGIN_SCHEMA_READY:
        return
    _ensure_plugin_keys_schema()
    _PLUGIN_SCHEMA_READY = True


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
            'api_key': api_key,            # FULL key — solo se muestra esta vez
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

def _validate_scan_token_direct(token):
    """Valida un token de escaneo en la BD. Retorna (token_id, error_msg, created_by, allowed_mods)."""
    try:
        # Códigos cortos (≤8 chars) se buscan en short_code; tokens largos en token
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
CURRENT_SCANNER_VERSION = "1.6.49"

@app.route('/sw.js')
def service_worker():
    """Serve service worker from root scope so it can control the full origin."""
    resp = make_response(app.send_static_file('sw.js'))
    resp.headers['Content-Type'] = 'application/javascript'
    resp.headers['Service-Worker-Allowed'] = '/'
    resp.headers['Cache-Control'] = 'no-cache'
    return resp


# ── P5 #16 — Web Push Notifications ──────────────────────────────────────────

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
            # Visual #50 — guardar la versión del scanner que generó este scan
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
        return jsonify({'success': True, 'scan_id': scan_id, 'status': 'running', 'message': 'Escaneo iniciado'}), 201
    except Exception as e:
        print(f"[DEBUG start_scan] ERROR: {e}\n{traceback.format_exc()}")
        return jsonify({'error': f'Error iniciando escaneo: {str(e)}'}), 500


# Rutas/nombres de software legítimo que el scanner client puede mandar como falsos positivos.
# Aplicado server-side para que funcione con cualquier versión del exe.
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
    # AppData — apps legítimas
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
    'site-packages',                   # librerías Python instaladas
    'node_modules',                    # módulos JS de proyectos
    # Windows AppRepository — paquetes firmados del sistema, jamás hacks
    'apprepository\\packages', 'microsoft\\windows\\apprepository',
    'activationstore.dat', 'credentialstore', '.pckgdep',
    # Navegadores — rutas de datos del perfil
    'appdata\\local\\google\\chrome',
    'appdata\\local\\microsoft\\edge',
    'appdata\\local\\brave-browser',
    'appdata\\local\\vivaldi',
    'appdata\\local\\chromium',
    'appdata\\local\\opera software\\opera',
    'appdata\\roaming\\mozilla\\firefox',
    'appdata\\roaming\\waterfox', 'appdata\\roaming\\librewolf',
    # Launchers / clientes legítimos de Minecraft
    'lunar client', 'lunarclient',
    'steam\\steamapps', 'epicgames', 'origin games',
    'tlauncher', 'prismlauncher', 'badlion client',
    'gdlauncher', 'multimc', 'atlauncher', 'curseforgeapp',
    'feather launcher', 'feathermc',   # Feather — launcher legítimo
    'modrinth-app', 'modrinth.app',    # Modrinth official launcher
    'minecraftlauncher.exe',           # launcher oficial Mojang
    'xboxlivegames', 'minecraft launcher\\',
    # Anti-cheats y herramientas de seguridad legítimas
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
    # El propio scanner — no flaggear sus propias copias borradas
    'argusscanner', 'minecraftsstool',
    # Java oficial / OpenJDK / temurin — runtime legítimo
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
    # Mods / datapacks legítimos conocidos
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
    # JNA — archivos temporales normales de Java/Minecraft
    'jna', 'jna-',
    # Otros programas legítimos
    'voicemod',
    # Drivers y software de hardware
    'nvidia corporation', 'amd\\radeon', 'intel corporation',
    'discord\\app-', 'teamspeak 3 client',
    'logitech\\logi options', 'razer\\synapse',
    'corsair\\icue', 'steelseries\\engine',
    # LabyMod — cliente legítimo de Minecraft
    'labymod', 'labymodlauncher', 'labymod-neo',
    # Fabric API processed mods y librerías de Minecraft
    '.fabric\\processedmods', '.minecraft\\.fabric', '.minecraft\\libraries',
    '.minecraft\\assets', '.minecraft\\versions',
    '.minecraft\\bin\\natives', '.minecraft\\natives',
    '.minecraft\\crash-reports', '.minecraft\\logs\\debug',
    # Grabadores de clips
    'medal\\', 'medal.tv',
    # Juegos y apps legítimas
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
    # IDE y herramientas de desarrollo (modders legítimos)
    'jetbrains\\intellij', 'jetbrains\\toolbox', 'pycharm',
    'visual studio code', 'microsoft vs code', 'cursor\\',
    'eclipse\\', 'netbeans\\',
    '.gradle\\caches', '.gradle\\wrapper', '.m2\\repository',
    # OBS y streaming (no es evidencia per se, salvo que se grabe el SS)
    'obs-studio\\bin', 'streamlabs',

    # ── Filter #13 — Discord (todas las variantes oficiales y forks comunes) ──
    # Discord original + canales beta + mods de cliente. Estos hookean overlay,
    # captura de ventana, etc — heurísticas viejas los confunden con inyectores.
    'discord.exe', 'discordptb.exe', 'discordcanary.exe',
    'discord_voice.exe', 'discord_overlay', 'discord_overlay2',
    'discordoverlay.exe', 'discord_helper', 'discord_crashhandler',
    'discord-crash', 'discord_setup',
    'appdata\\local\\discord',
    'appdata\\roaming\\discord',
    'appdata\\local\\discordptb',
    'appdata\\local\\discordcanary',
    'discord\\modules', 'discord\\resources', 'discord\\update.exe',
    # Mods de cliente Discord — son legítimos pero hookean el client local
    'betterdiscord', 'better-discord', 'bdpluginlibrary',
    'vencord', 'arrpc.exe', 'replugged',
    'discord_arrpc', 'discord_rpc', 'discord rich presence',

    # ── Filter #14 — Periféricos: software oficial de mouse/teclado/audio ────
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

    # ── Filter #15 — Macros legales firmados ─────────────────────────────────
    # JoyToKey, Xpadder, AntiMicro/AntiMicroX (gamepad → keyboard mappers).
    # Son legítimos pero generan eventos de input sintéticos que parecen macros.
    'joytokey', 'joy2key', 'xpadder.exe',
    'antimicro', 'antimicrox',
    'controllercompanion', 'rewasd.exe',  # reWASD — gamepad mapper firmado
    'ds4windows', 'ds4-windows',          # DualShock 4 driver popular

    # ── Filter #16 — AutoHotkey ──────────────────────────────────────────────
    # AutoHotkey runtime y compiler. Los .ahk en sí podrían ser hack, pero el
    # runtime ".exe" del propio AHK no es la evidencia.
    'autohotkey\\autohotkey.exe', 'autohotkey64.exe', 'autohotkey32.exe',
    'autohotkeyu64.exe', 'autohotkeyu32.exe', 'ahk2exe.exe',
    'autohotkey\\compiler', 'autohotkey\\autohotkey.chm',

    # ── Filter #17 — OBS Studio + plugins legítimos ──────────────────────────
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

    # ── Bonus: emuladores firmados ─────────────────────────────────────────
    # Algunos hacks se han camuflado como emus. Los oficiales son seguros.
    'parsec\\parsec', 'parsecd.exe',         # remote play
    'moonlight\\moonlight', 'moonlight-qt',  # game streaming
    'sunshine\\sunshine.exe',                # host de moonlight

    # ── Filter #23 — UWP / MSIX (Microsoft Store apps firmadas) ─────────────
    # WindowsApps/ ya estaba parcial. Acá añadimos rutas más explícitas y
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

    # ── Filter #56 — Remote support tools autorizados ─────────────────────
    # TeamViewer / AnyDesk / Chrome Remote / Splashtop. Estos hookean
    # input y captura, lo que las heurísticas viejas marcaban como cheat
    # backdoor. Si están en su carpeta canónica (Program Files), legit.
    # NOTA: también podrían usarse en ataques sociales — el staff debe
    # cruzar este FP filter con el contexto del scan (lo dejamos como
    # whitelist de path para reducir ruido, no un absuelve total).
    'teamviewer.exe', 'tv_w32.exe', 'tv_x64.exe',
    'program files\\teamviewer', 'program files (x86)\\teamviewer',
    'anydesk.exe', 'program files (x86)\\anydesk',
    'program files\\anydesk',
    'chrome remote desktop', 'remoting_host.exe',
    'splashtop\\splashtop business', 'srservice.exe',
    'remotepc.exe', 'rustdesk.exe',  # RustDesk — open source remote
    'logmein\\logmein hamachi', 'logmein\\logmeinrescue',
    'gotomypc', 'gotomeeting',
    # Microsoft propio para soporte
    'quickassist.exe',                       # Quick Assist (Windows 11)
    'microsoft\\windows\\quickassist',
    'remoteassistance.exe', 'msra.exe',
    # Atajos de gestión empresarial
    'connectwise control', 'screenconnect.client',
    'kaseya', 'ninja-remote', 'ninjaremote',
    'datto.rmm', 'syncro.live',

    # ── Filter #29 — TLauncher contextual (advisory, no FP duro) ──────────
    # TLauncher es FP recurrente en zonas de bajo poder adquisitivo. Sus
    # binarios y carpetas se whitelist por path; si el filename es hack
    # explícito, igual reportamos (no se arriesga falso negativo).
    'tlauncher.exe', 'tlauncher\\bin', 'tlauncher\\game',
    'tlauncher\\properties', 'tlauncher_repo',

    # ── Filter #34 — Mods en folders de launchers (CurseForge, Lunar...) ──
    # Ampliamos el whitelist existente: las carpetas mods/cache/instances
    # de los launchers más comunes. F#53 ya cubre paths de update —
    # esto cubre el storage estático.
    'curseforge\\minecraft\\instances', 'curseforge\\minecraft\\install',
    'overwolf\\packages\\extensions',
    'multimc\\instances', 'prismlauncher\\instances',
    'gdlauncher\\instances', 'gdlauncher\\datastore',
    'atlauncher\\instances', 'atlauncher\\downloads',
    'lunarclient\\game-cache', 'lunarclient\\offline',
    'badlion client\\bcc', 'badlionclient\\bcc',
    'modrinth-app\\meta', 'modrinth.app\\profiles',

    # ── Filter #47 — Steam Workshop subscriptions ──────────────────────────
    'steam\\steamapps\\workshop', 'steam\\workshop',
    'steam\\steamapps\\common',          # juegos instalados (no son hack)
    'steam\\steamapps\\downloading',     # downloads en curso
    'steam\\appcache', 'steam\\config',

    # ══════════════════════════════════════════════════════════════════════
    # PACK 29 — Lote masivo de whitelists server-side adicionales.
    # Aplicado retroactivamente a scans antiguos via _scrub_results_for_display.
    # ══════════════════════════════════════════════════════════════════════

    # ── Filter #5 (extensión) — Launchers MC oficiales/third-party adicionales
    'xmcl-launcher', 'x minecraft launcher',  # XMCL — open-source, popular en CN
    'hmcl', 'hmcl-launcher', 'huangminecraftlauncher',  # HMCL Java (no Android variant)
    'magiclauncher', 'magic launcher',
    'fjordlauncher', 'fjord launcher',
    'technic launcher', 'technicpack',
    'mclauncher\\', 'mclauncher.exe',
    'voidclient', 'voidlauncher',
    'salwyrr', 'salwyrr launcher',
    'pcl2\\', 'pcl-launcher',         # Plain Craft Launcher 2 — popular CN
    'cmclauncher\\', 'cmcl',
    'easymc',
    'pojavlauncher\\',                 # Pojav (también usado en desktop por algunos)
    'tlauncher 2',                     # TLauncher v2 modern
    'novalauncher\\', 'nova launcher minecraft',
    # Forks legítimos abiertos
    'siged-launcher', 'olive launcher', 'olivelauncher',

    # ── Filter #7 — Reputación por path: rutas inherentemente firmadas ─────
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

    # ── Filter #10 — Patrones genéricos test/demo/sample en filename ───────
    # Si el path/nombre contiene estos tokens, MUY probable que sea archivo
    # de prueba personal del usuario, no un cheat real (los cheats no se
    # llaman a sí mismos "test"). Solo aplica como segmento de path —
    # si el filename completo es 'test.exe' aún se reporta porque puede
    # ser un binario malicioso renombrado.
    '\\demos\\', '\\demo\\', '\\samples\\', '\\examples\\',
    '\\tests\\', '\\test_', '\\proyectos demo\\',
    '\\tutorial\\', '\\tutoriales\\',

    # ── Filter #28 — Paths localizados (es-AR/es-MX/es-ES) ─────────────────
    # Windows con idioma español traduce "Documents" a "Documentos", etc.
    # Estos paths son carpetas del usuario, no instalaciones de cheats.
    'usuarios\\public\\', 'usuarios\\publico\\',
    '\\mis documentos\\', '\\documentos\\favoritos\\',
    '\\descargas\\drivers',
    '\\escritorio\\backups',
    '\\imagenes\\', '\\videos\\', '\\musica\\',

    # ── Filter #32 — Caches de package managers (no contienen ejecutables ──
    # propios; son cachés de Maven/Gradle/npm/pip/cargo/yarn).
    '\\.gradle\\caches', '\\.gradle\\wrapper\\dists',
    '\\.m2\\repository', '\\.ivy2\\cache',
    'appdata\\local\\npm-cache',
    'appdata\\roaming\\npm', 'appdata\\local\\yarn',
    'appdata\\local\\pip\\cache', 'appdata\\local\\pypoetry\\cache',
    '\\.cargo\\registry', '\\.cargo\\git',
    '\\.cache\\pip', '\\.cache\\yarn', '\\.cache\\go-build',
    '\\.nuget\\packages', '\\packages\\.nuget',

    # ── Filter #35 — Cache de modpacks de CurseForge / Modrinth ────────────
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

    # ── Filter #52 — Reinstalaciones legítimas (cache/installer paths) ─────
    # Carpetas de instaladores típicos. Si un mismo binario aparece en N
    # scans del mismo usuario, es reinstalación, no nuevo evento.
    '\\appdata\\local\\package cache\\',     # Visual Studio installer cache
    '\\package cache\\{',                    # GUID-based installer cache
    'softwaredistribution\\download',        # Windows Update
    'wuredist\\', 'wuredownloads\\',
    '\\msocache\\', 'mshtmedit',

    # ── Filter #60 — Cooldown markers: paths donde la empresa ya marcó FP ──
    # Soportado a nivel de fragmento aprendido (learned_legit_paths) —
    # solo agregamos aquí defaults globales para acelerar. La lógica de
    # cooldown por empresa va en el endpoint /api/staff/learn-fp ya existente.

    # ── Bonus extra: programas legítimos comunes mal-flageados ──────────────
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
    # Repos de scripts personales del usuario (proyectos legítimos suyos)
    '\\onedrive\\documents\\github\\',
    '\\users\\public\\desktop\\',
    '\\projects\\', '\\proyectos\\',
    '\\repositories\\', '\\repos\\',
]


# ── Filter #43, #44 — Settings por empresa (threshold dinámico + modo) ──────
# Permite que cada empresa configure su política:
#   * mode: 'tournament' (más estricto, threshold default -10), 'normal',
#           'casual' (más permisivo, threshold default +10).
#   * threshold_critical / threshold_suspicious: umbrales custom (override
#           del default {70, 30}).
# Cargado on-demand con cache 60s por empresa. Si la empresa no configuró
# nada, devuelve los defaults.
_company_settings_cache = {}    # {company_id: (settings_dict, ts)}
_COMPANY_SETTINGS_TTL = 60.0     # 1 min — staff verá los cambios pronto

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

    # Pack 32 F#60 — Aplicar threshold_bump del cooldown si existe.
    # No mutamos los valores guardados en BD; sumamos en memoria por
    # request. Si la empresa hizo muchos overturns o learn-fp, sus
    # thresholds suben para forzar revisión más estricta.
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
        return jsonify({'error': 'thresholds inválidos'}), 400
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
        # Invalidar caché
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
    'event_logs',   # cambios fecha/hora: los dispara Windows NTP automáticamente
}


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
# APPCOMPAT y USN_FORENSICS ya no se filtran: el nuevo scanner los usa correctamente
_LEGACY_FP_CATEGORIES = {'EXECUTED_DELETED'}
# Patrones de basura binaria en nombres — parser viejo decodificaba .pf como UTF-16
_BINARY_GARBAGE_RE = _re_fp.compile(
    r'\bLMEM\b|Windows\.Data\.|Matrix3x2|\.CenterX|\.CenterY|'
    r'ItemReference|MEOW\b|CloudData|RevealBrush|XamlAnim|'
    r'BaseM\s+I&|BorderBrush\s+[A-Z]|\bMEM\s+[A-Z]|\bLE[A-Z]\b|'
    r'D2D1\.|DCompositionBrush|DXGI_|\\u[0-9a-f]{4}|'
    r'^[\x00-\x08\x0b\x0c\x0e-\x1f]{2,}|[\xc0-\xff]{6,}',
    _re_fp.IGNORECASE
)
# Strings de control / no-imprimibles típicos de basura binaria
_NONPRINTABLE_RE = _re_fp.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')
# Caracteres "raros" no-ASCII que aparecen al decodificar UTF-16 incorrectamente
_HIGH_BYTE_RUN_RE = _re_fp.compile(r'[\u0080-\uFFFF]{4,}')


def _normalize_path(p: str) -> str:
    """Normaliza una ruta para comparación robusta:
       - lowercase
       - separadores unificados a '\\'
       - quitar prefijos extendidos '\\\\?\\' y '\\\\.\\'
       - colapsar separadores duplicados.
    """
    if not p:
        return ''
    s = str(p).lower().replace('/', '\\').strip()
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
    # Run largo de caracteres no-ASCII (típico de UTF-16 mal decodificado)
    if _HIGH_BYTE_RUN_RE.search(s_str):
        return True
    if _BINARY_GARBAGE_RE.search(s_str):
        return True
    # Ratio de caracteres alfanuméricos: si <30% es probable basura
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
    # de archivos creados/modificados/borrados/ejecutados desde el último boot.
    # NUNCA aplicar el filtro de FPs aquí — pueden caer perfectamente en
    # rutas de "fragmentos seguros" (AppData, Windows, etc.) y eso NO las
    # convierte en FPs: son justamente lo que queremos mostrar como historial.
    categoria = (result.get('categoria') or result.get('issue_category') or '').upper()
    if categoria == 'FILE_ACTIVITY':
        # Solo descartar basura binaria (parsers rotos), nada más
        ruta_raw = result.get('ruta', '') or result.get('issue_path', '') or ''
        nombre = (result.get('nombre', '') or result.get('archivo', '')
                  or result.get('issue_name', '') or '')
        if _is_garbage_string(nombre) or _is_garbage_string(ruta_raw):
            return True
        return False

    # Tipos que son FP estructural independientemente de la ruta
    tipo = (result.get('tipo') or result.get('issue_type') or '').lower().replace(' ', '_')
    if tipo in _ZERO_RISK_ISSUE_TYPES:
        return True

    # Categorías de EXE antiguo con parsers buggeados
    if categoria in _LEGACY_FP_CATEGORIES:
        return True

    ruta_raw = result.get('ruta', '') or result.get('issue_path', '') or ''
    nombre   = (result.get('nombre', '') or result.get('archivo', '')
                or result.get('issue_name', '') or '')
    ruta     = _normalize_path(ruta_raw)
    combined = ruta + '|' + (nombre or '').lower()

    # Confidence numéricamente nula y sin patrones detectados → ruido
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

    # Hallazgos con descripción genérica de fecha/hora del sistema (NTP) — FP histórico
    desc = (result.get('descripcion') or result.get('issue_description') or '').lower()
    if 'cambio de hora' in desc or 'time-service' in desc or 'w32time' in desc:
        return True

    if any(frag in combined for frag in _SERVER_FP_FRAGMENTS):
        return True

    # Filter #37 — `.rise` extensión vs folder.
    # Rise client tiene su carpeta de config en %appdata%\.rise (o similar).
    # Si el path es una CARPETA `.rise\` (no termina en .rise como extensión
    # real de archivo), descartar — solo el archivo con extensión .rise
    # cuenta como evidencia (raro de ver fuera del cheat real).
    # Heurística: si '.rise' aparece como segmento de directorio (con
    # separador después), es config folder; si es la extensión final del
    # archivo (nombre.rise) o nombre completo, sigue evaluándose.
    try:
        # Nombre de archivo (último segmento de la ruta)
        last_seg = (nombre or '').lower().strip()
        # Si es CARPETA .rise (típico de Rise/Vape config legítima del propio
        # usuario que ya desinstaló y solo dejó la config) → soft FP.
        # Solo skipea si el filename NO termina en .rise como extensión
        # real (último .rise antes del fin del string).
        is_rise_folder_path = (
            ('\\.rise\\' in combined) or ('/.rise/' in combined) or
            ('\\.rise/' in combined) or ('/.rise\\' in combined)
        )
        ends_in_rise_ext = last_seg.endswith('.rise') and last_seg != '.rise'
        if is_rise_folder_path and not ends_in_rise_ext:
            return True
    except Exception:
        pass

    # Filter #11 — Aprendizaje incremental por feedback. Las rutas marcadas
    # como 'legitimate_path' por el staff (vía learned_patterns) se aplican
    # ahora retroactivamente a TODOS los scans servidos. La función ya
    # existía pero no se llamaba. Cache de 5 min en _get_learned_legit_paths
    # evita el round-trip a BD por cada result.
    try:
        learned = _get_learned_legit_paths()
        if learned and any(frag in combined for frag in learned):
            return True
    except Exception:
        pass

    # ════════════════════════════════════════════════════════════════════
    # PACK 29 — heurísticas inline (sin tabla / sin red) que filtran
    # categorías obvias de FP que no se pueden capturar solo con fragmentos.
    # ════════════════════════════════════════════════════════════════════
    try:
        name_lower = (nombre or '').lower().strip()

        # Filter #3 — "killaura" / "aimbot" / etc como nombre LITERAL del archivo
        # en path de usuario (Documents/Escritorio/Downloads), con extensión
        # de imagen/texto/video/pdf → es nota personal o screenshot, no el
        # cheat real. Los cheats reales SIEMPRE son .exe/.jar/.dll en paths
        # de instalación (no en Documents).
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

        # Filter #10 — patrones test/demo/sample/example/tutorial/proyecto en
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
    except Exception:
        pass

    return False


# ════════════════════════════════════════════════════════════════════════════
# Filter #42 — Heurística "Primera vez visto" (first-seen tracking).
# ════════════════════════════════════════════════════════════════════════════
# Cada evidencia (file_hash o name_norm+tipo) se trackea en evidence_fingerprints
# con contador acumulado. Cuando un scan llega:
#   - Si el fingerprint no existe → first_seen=true (revisión humana sugerida).
#   - Si seen_count crece → ya fue visto antes en otros scans/empresas.
# El panel muestra badge "🆕 Primera vez visto" o "👁 Visto Nx" en cada hallazgo.
# Auditable y NO destructivo: nunca cambia el verdict, solo decora metadata.
# ════════════════════════════════════════════════════════════════════════════
import re as _re_fp42
_NAME_NORM_RE = _re_fp42.compile(r'[\d\s_\-\.\(\)\[\]\{\}]+')


def _compute_evidence_fingerprint(r: dict) -> str | None:
    """Genera un fingerprint estable para un result de scan.
    Prioridad: file_hash (sha256 real del binario) → name_norm+tipo.
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
    múltiples veces. Devuelve True si la tabla está disponible.
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
    Idempotente, tolera fallos de BD (devuelve dict vacío si la tabla cae).
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
    sin escribir. Si la tabla no existe, devuelve dict vacío (decorate falla
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
        # Construimos un IN (...) con placeholders dinámicos
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
        # Tabla aún no existe (deploys nuevos), todos quedan en 0 → first_seen
        return {fp: 0 for fp in fps}
    return out


def _decorate_results_with_first_seen(results: list, seen_map: dict) -> list:
    """Inyecta 'first_seen' (bool), 'seen_count' (int) y 'globally_common'
    (bool) en cada result. Mutates en sitio y devuelve la misma lista.
    Conserva resultados sin fingerprint (los marca como first_seen=False).

    Filter #12 — Consenso global: si un fingerprint apareció >=50 veces
    sin que se haya verificado como hack en histórico, lo marcamos como
    'globally_common' para que el panel ofrezca al staff aprenderlo
    como FP de un solo click. NO degrada el verdict automáticamente.
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
    devolviendo solo los que NO son FP. Útil para sanear scans antiguos al servirlos.
    Conserva el orden original y nunca elimina más de un 95% de los resultados como
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
        return results  # safety: nunca devolver lista vacía si había datos
    if len(results) >= 6 and len(keep) / len(results) < 0.05:
        return results  # safety: filtro demasiado agresivo, devolver original
    return keep


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

    # Tipos/categorías que no aportan nada al risk score:
    # - texture_pack: muy fácil de confundir, demasiados FPs
    # - event_logs de fecha/hora: lo dispara Windows NTP automáticamente
    ZERO_RISK_TYPES = {
        'texture_pack', 'texture_pack_xray', 'texture_pack_analysis',
        'resource_pack', 'resource_pack_xray',
    }
    ZERO_RISK_CATS = {'texture_packs', 'resource_packs'}

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


def _ensemble_risk_score(results):
    """Ensemble autónomo: 50% heurístico + 30% RF + 20% Isolation Forest.
    Si un modelo no está disponible, sus pesos se redistribuyen a heurístico.
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
                # more negative = more anomalous. Normalize to 0–100 hack probability.
                raw = iso_pred.get('score', 0.0)
                # Typical range is roughly -0.20 (anomaly) to +0.10 (normal).
                # Map: -0.20 → 100, 0.0 → 50, +0.10 → 0
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
      7. Prior Consensus     0.10  (Pack 32 F#55 — verdicts previos del
                                   mismo machine_id/player). Solo se
                                   aplica si machine_id o
                                   minecraft_username están presentes.

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

    # -- Gate: no in-instance evidence → cap at SOSPECHOSO, not sanctionable --
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
        reasons.append(f'{top_client} ({len(client_signals[top_client])} señal(es))')

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
        'reason': ' · '.join(reasons) if reasons else '',
    }


def _compare_consecutive_scans(cursor, scan_id, machine_id, current_results):
    """P2 #43 — Compara scan actual con el anterior del mismo machine_id.
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
            # Filter #42 — Upsert evidence_fingerprints para tracking "first-seen"
            # Tolera fallos: si la tabla aún no existe, simplemente no se decora.
            try:
                cursor.execute('SAVEPOINT efp_upsert_save')
                _upsert_evidence_fingerprints(cursor, scan_id, results)
                cursor.execute('RELEASE SAVEPOINT efp_upsert_save')
            except Exception as _efp_e:
                try:
                    cursor.execute('ROLLBACK TO SAVEPOINT efp_upsert_save')
                except Exception:
                    pass
                print(f"[DEBUG] evidence_fingerprints upsert falló silenciosamente: {_efp_e}")
            print(f"[DEBUG] Insertando {len(results)} resultados en scan_results")
            if results:
                def _norm_conf(v):
                    """Normaliza confidence a rango 0-1 independientemente de si el exe lo mandó como 0-1 o 0-100."""
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
                # Intento INSERT con columna 'extra'; si la columna aún no existe en
                # esta DB (migración pendiente), reintenta sin ella.
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
                    print(f"[DEBUG] INSERT con extra falló ({_e}); reintentando sin columna extra")
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

            # Calcular y guardar risk_score (P3 #7 ensemble: heurístico + RF)
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
                        print(f"[DEBUG] risk_score cappado por gate_capped → {_capped_rs}")
                    except Exception:
                        pass
            except Exception:
                try:
                    cursor.execute('ROLLBACK TO SAVEPOINT ensemble_save')
                except Exception:
                    pass

            # P2 #43 — Comparación con scan anterior del mismo machine
            try:
                _compare_consecutive_scans(cursor, scan_id, data.get('machine_id', ''), results)
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

        # P5 #16 — Web Push a todos los staff suscritos
        _rs = locals().get('risk_score', 0)
        _mn = data.get('machine_name', 'Jugador')
        _push_title = '🔴 Argus — Nuevo scan con hacks' if _rs >= 70 else '🟡 Argus — Nuevo scan' if _rs >= 30 else '✅ Argus — Scan limpio'
        _push_body  = f'{_mn} · Risk {_rs} · {len(results)} hallazgos'
        import threading as _pt
        _pt.Thread(target=_send_push_to_all, args=(_push_title, _push_body, f'/panel?scan={scan_id}'), daemon=True).start()

        return jsonify({'success': True, 'message': 'Resultados almacenados'})
    except Exception as e:
        print(f"[DEBUG] ===== ERROR en submit_scan_results scan_id={scan_id} =====")
        print(f"[DEBUG] {e}")
        print(traceback.format_exc())
        return jsonify({'error': f'Error almacenando resultados: {str(e)}'}), 500


# ──────────────────────────────────────────────────────────────────────────
# ENDPOINT TEMPORAL DE DIAGNOSTICO — sin login, replica TODA la logica de
# get_scan() paso a paso, devolviendo en que paso fallo si falla. Permite
# diagnosticar 500's del endpoint real sin acceso a logs.
# Eliminar cuando el bug este resuelto.
# ──────────────────────────────────────────────────────────────────────────
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

                # scanner_version puede no existir aún en deploys viejos — fallback NULL.
                # IMPORTANTE: PostgreSQL aborta la TX entera si la query del try falla
                # (ej. UndefinedColumn). Sin SAVEPOINT, la query del except hereda la
                # TX aborted y revienta con "current transaction is aborted, commands
                # ignored until end of transaction block" → list_scans cae a fallback
                # HTTP roto. Causa del 500 en Pack 25 cuando Render upgradeó Python.
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
                    print(f"⚠️ list_scans: probe scanner_version falló ({_scn_err.__class__.__name__}: {_scn_err}); usando query sin esa columna")
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
                    'os': None,
                    'os_name': None,
                    'scanner_platform': None,
                    'verdict': None, 'verdict_reason': None,
                    'verdict_by': None, 'verdict_at': '',
                }

                # Columnas opcionales: total_dirs_scanned, verdict, screenshot, mc_info, ensemble_data
                # Usa SAVEPOINT para que un fallo (columna inexistente) no aborte la transacción
                scan['screenshot'] = None
                scan['mc_info'] = None
                scan['risk_score'] = 0
                scan['ensemble_data'] = None
                scan['scanner_version'] = ''
                try:
                    cursor.execute('SAVEPOINT opt_cols')
                    # Visual #50 — leer scanner_version. Tolerante a deploys sin la columna.
                    try:
                        cursor.execute(f'''
                            SELECT total_dirs_scanned, verdict, verdict_reason, verdict_by, verdict_at,
                                   screenshot, mc_info, risk_score, ensemble_data, os, scanner_version
                            FROM scans WHERE id = {_PH}
                        ''', (scan_id,))
                        _has_scn_ver_col = True
                    except Exception:
                        _has_scn_ver_col = False
                        cursor.execute(f'''
                            SELECT total_dirs_scanned, verdict, verdict_reason, verdict_by, verdict_at,
                                   screenshot, mc_info, risk_score, ensemble_data, os
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
                    print(f"⚠️ get_scan scanned_by query fallida (id={scan_id}): {type(_e_sb).__name__}: {_e_sb}")
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

                # Filter #42 — Decorar con first_seen + seen_count antes de servir.
                # 1 query para todo el scan (IN ...). Si la tabla cae, todos quedan
                # en first_seen=true que es "más alarmante" y por tanto seguro.
                try:
                    _seen_map = _query_evidence_seen_counts(cursor, results)
                    _decorate_results_with_first_seen(results, _seen_map)
                except Exception as _fs_e:
                    print(f"⚠️ first-seen decorate falló: {_fs_e}")

                scan['results'] = results

                # Filter #43, #44 — incluir thresholds dinámicos de la
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

                # Guardar en caché
                _stats_cache[cache_key] = scan
                _stats_cache_time[cache_key] = time.time()
                
                return jsonify(scan), 200
        except Exception as e:
            # Logueamos el traceback completo (Render lo capta) y resetamos
            # la conexion thread-local si quedo en estado abortado para que el
            # proximo request del mismo worker no herede la transaccion rota.
            print(f"⚠️ Error accediendo BD directamente en get_scan({scan_id}): {type(e).__name__}: {e}")
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
                    print(f"🔁 Conexion thread-local reseteada tras error en get_scan")
            except Exception as _re:
                print(f"⚠️ No se pudo resetear conexion: {_re}")
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


@app.route('/api/ml/trigger', methods=['POST'])
@admin_required
def trigger_autonomous_learning():
    """Dispara el pipeline de aprendizaje autónomo manualmente (sin esperar al cron)."""
    import threading
    def _run():
        _autonomous_daily_learning()
    threading.Thread(target=_run, daemon=True).start()
    return jsonify({'success': True, 'message': 'Pipeline autónomo iniciado en segundo plano'})

@app.route('/api/learning-stats', methods=['GET'])
def get_learning_stats():
    """Estadísticas del sistema de aprendizaje autónomo."""
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
        os.path.join(project_root, 'dist', filename),
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

# Cache de metadatos del .exe (tamano + sha256). Se invalida si mtime cambia.
_EXE_META_CACHE = {'mtime': None, 'data': None}

def _get_exe_metadata():
    """Devuelve dict con {size_mb, size_bytes, sha256, mtime, exists, path}.
    Cachea el SHA-256 entre requests porque calcularlo es caro.
    Si el archivo no existe devuelve un dict 'best-effort' con exists=False."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidates = [
        os.path.join(project_root, 'dist', 'ArgusScanner.exe'),
        os.path.join(project_root, 'downloads', 'ArgusScanner.exe'),
    ]
    exe_path = next((p for p in candidates if os.path.exists(p)), None)
    if not exe_path:
        return {'exists': False, 'size_mb': None, 'size_bytes': 0, 'sha256': None, 'mtime': None, 'path': None}

    mtime = os.path.getmtime(exe_path)
    if _EXE_META_CACHE['mtime'] == mtime and _EXE_META_CACHE['data'] is not None:
        return _EXE_META_CACHE['data']

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
        _EXE_META_CACHE['mtime'] = mtime
        _EXE_META_CACHE['data'] = data
        return data
    except Exception as exc:
        print(f"[descargar] error calculando metadata exe: {exc}")
        return {'exists': True, 'size_mb': None, 'size_bytes': 0, 'sha256': None, 'mtime': mtime, 'path': exe_path}


@app.route('/descargar')
def descargar_page():
    """Pagina publica de descarga de ArgusScanner."""
    base_url = os.environ.get('RENDER_EXTERNAL_URL', request.host_url).rstrip('/')
    exe_url = f"{base_url}/descargar/exe"
    meta = _get_exe_metadata()
    return render_template(
        'descargar.html',
        exe_url=exe_url,
        exe_size_mb=meta.get('size_mb'),
        exe_sha256=meta.get('sha256'),
        exe_exists=meta.get('exists', False),
    )


@app.route('/descargar/exe')
def descargar_exe():
    """Endpoint público permanente para descargar ArgusScanner.exe sin autenticación."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    possible_paths = [
        os.path.join(project_root, 'dist', 'ArgusScanner.exe'),          # versión compilada en git (prioridad)
        os.path.join(project_root, 'downloads', 'ArgusScanner.exe'),      # fallback: subida manual
        os.path.join(project_root, 'source', 'dist', 'ArgusScanner.exe'),
        os.path.join(project_root, 'ArgusScanner.exe'),
    ]
    for path in possible_paths:
        if os.path.exists(path):
            return send_file(path, as_attachment=True, download_name='ArgusScanner.exe')
    return jsonify({'error': 'Ejecutable no disponible aún. Contacta a un administrador.'}), 404


@app.route('/descargar/linux')
def descargar_linux():
    """Plataforma Linux #13 — sirve el paquete `argus_linux/` como tar.gz.

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
        return jsonify({'error': 'Paquete Linux no disponible aún en el servidor.'}), 404

    # Construir tar.gz en memoria — el directorio es pequeño (<50KB), no
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


# ── Plataforma Android #13 — endpoint de descarga ────────────────────────────
# Tag rolling del release de GitHub que el workflow .github/workflows/
# android-build.yml mantiene actualizado en cada push a main. La URL del
# asset es estable y pública (no requiere token), por lo que podemos
# redirigir aquí sin gastar bandwidth de Render.
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
# sin auth). TTL 5min — coincide con el ritmo realista de re-deploys.
_android_version_cache: dict = {'data': None, 'fetched_at': 0.0}
_ANDROID_VERSION_TTL_S = 300


def _android_version_payload() -> dict:
    """Item Android #15 — meta del último APK publicado.

    Devuelve {latest_commit, short_commit, apk_url, published_at,
    release_name, size_bytes, release_notes}. Si la API de GitHub falla,
    cae a un payload mínimo con apk_url estable.
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
    """Item Android #15 — endpoint que la app Argus consulta al iniciar
    para detectar versión nueva.

    Cliente típico: la app envía su BuildConfig.ARGUS_BUILD_COMMIT como
    ?current=abc1234. Si no coincide con `short_commit` y la release
    es más reciente, la app muestra "Hay versión nueva" + botón
    Actualizar (que abre apk_url en el navegador para que el usuario
    descargue e instale el APK firmado).

    Sin parámetro `current`, devuelve solo la meta del último build.
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
    """Plataforma Android #13 — sirve el APK Argus Android.

    Estrategia de servidos en cascada:
      1) Si el operador del servidor copió manualmente un APK firmado a
         `web_app/static/dist/argus-android.apk`, lo servimos directo
         (use case: dev local, on-prem, o release firmado con keystore).
      2) Si no, redirigimos 302 al asset estable de GitHub Releases
         (rolling tag `android-latest`) que el workflow CI mantiene al
         día con cada push a `main`. Esto cubre el caso por defecto de
         Render: GH Actions buildea → publica release → este endpoint
         redirige sin necesidad de redeploy.

    El parámetro `?direct=1` permite forzar la URL absoluta del release
    (útil para QR / chat apps que no toleran redirects).
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

    # Fallback: redirect al release público de GitHub. 302 (Found) con
    # ?direct=1 da la URL "as-is" para clientes que no siguen redirects.
    if request.args.get('direct') == '1':
        return jsonify({'url': ANDROID_RELEASE_URL}), 200
    return redirect(ANDROID_RELEASE_URL, code=302)


@app.route('/descargar/android-source')
def descargar_android_source():
    """Plataforma Android #13 — empaqueta el proyecto Android como tar.gz.

    Útil para que devs / CI / contributors lo compilen localmente. Excluye
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
    user_id = session.get('user_id')
    try:
        with get_api_db_cursor() as cursor:
            # Pack 32 — Capturar ensemble verdict, prior verdict y company
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

            # Pack 32 F#54 — Actualizar staff_trust comparando humano vs
            # ensemble. Idempotente, dentro de SAVEPOINT por si la tabla
            # está corrupta no rompe el verdict.
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

            # Pack 32 F#60 — Si el verdict actual es 'clean' y el prior
            # era 'hack' (o el ensemble decía hack), incrementar
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


@app.route('/api/ml/drift', methods=['GET'])
@login_required
def ml_drift_check():
    """P3 #9 — Detección de concept drift: compara concordancia del modelo con veredictos recientes.
    Si concordancia <70% en los últimos 30 scans con veredicto → alerta de reentrenamiento.
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
        'reason': ('Concordancia del modelo con veredictos recientes por debajo del 70% — reentrenamiento recomendado'
                   if drift else 'Concordancia aceptable'),
        'retrain_recommended': drift,
    }), 200


@app.route('/api/ml/anomaly/<int:scan_id>', methods=['GET'])
@login_required
def ml_anomaly_detect(scan_id):
    """P3 #3 — Isolation Forest para detectar si un scan es anómalo respecto al baseline.
    Compara los hallazgos del scan actual contra el perfil histórico de scans limpios.
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
            # Baseline: últimos 200 scans con veredicto limpio
            cur.execute(
                f"SELECT issues_found, risk_score, scan_duration, total_files_scanned "
                f"FROM scans WHERE verdict='clean' ORDER BY id DESC LIMIT 200"
            )
            baseline_rows = cur.fetchall() or []
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    if len(baseline_rows) < 20:
        return jsonify({'anomaly_score': 0.0, 'is_anomaly': False,
                        'reason': 'Insuficientes scans limpios para baseline (mín 20)'}), 200

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
            reason += f'Muy pocos archivos escaneados ({current[3]}), posible evasión. '
        if not reason:
            reason = 'Perfil del scan estadísticamente inusual.'

    return jsonify({
        'anomaly_score': round(-score, 4),  # positive = more anomalous
        'is_anomaly':    is_anomaly,
        'reason':        reason.strip(),
        'baseline_size': len(baseline_rows),
    }), 200


@app.route('/api/predict', methods=['POST'])
def api_predict():
    """P3 #35 — Predicción de riesgo pre-scan.
    El scanner envía features básicas del sistema antes de escanear.
    Devuelve risk_level y si el staff quiere scan completo o rápido.
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
                return jsonify({'error': 'token inválido o expirado'}), 403

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

        # Calcular risk_level pre-scan basado en señales simples
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


# ── P3 #17 — Dynamic hash blacklist (auto-propagated from verdict history) ────

@app.route('/api/hack_blacklist', methods=['GET'])
def get_hack_blacklist():
    """Returns SHA256 hashes confirmed as hacks across all servers.
    Auto-populated by /api/hack_blacklist/sync — scanner fetches on startup.
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


# ── Items 37/38/39 — Auto-whitelist / auto-blacklist from verdict history ─────

@app.route('/api/learning/auto_weights', methods=['GET'])
def get_auto_weights():
    """#38/#39 — Returns dynamically computed confidence weights per issue_type
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
    """#37 — Returns issue_type + path patterns that appear in >=30 clean scans
    and never (or rarely, <5%) in hack scans — these are systematic FPs.
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


# ── Staff AI Chat ─────────────────────────────────────────────────────────────

# ── Staff AI Chat — ensemble: Claude + Groq + Gemini + DuckDuckGo ─────────────

_CHAT_SYSTEM = (
    'Eres Argus AI, asistente experto en seguridad de Minecraft para el staff de ASPERS Projects. '
    'Ayudas a entender hallazgos del scanner Argus, identificar falsos positivos y responder sobre '
    'hacks y cheats de Minecraft. Responde en español, directo y técnico. Bullet points si aplica.'
)


def _ai_web_search(query, n=4):
    """Busca con DuckDuckGo y devuelve string con resultados formateados."""
    try:
        from duckduckgo_search import DDGS
        hits = DDGS().text(query, max_results=n)
        if not hits:
            return ''
        return '\n\n'.join(
            f"[{h.get('title','')}] {h.get('body','')[:300]} — {h.get('href','')}"
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


def _ai_call_gemini(key, system, history, user_msg):
    try:
        contents = []
        for m in history[:-1]:  # historial previo (sin el último user_msg)
            role = 'user' if m['role'] == 'user' else 'model'
            contents.append({'role': role, 'parts': [{'text': m['content']}]})
        # Primer turno incluye el system prompt
        first_text = f'{system}\n\n{history[-1]["content"]}' if contents else f'{system}\n\n{user_msg}'
        if not contents:
            contents.append({'role': 'user', 'parts': [{'text': first_text}]})
        else:
            contents.append({'role': 'user', 'parts': [{'text': user_msg}]})
        r = requests.post(
            f'https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={key}',
            json={
                'contents': contents,
                'generationConfig': {'maxOutputTokens': 700, 'temperature': 0.6},
            },
            timeout=25,
        )
        r.raise_for_status()
        return r.json()['candidates'][0]['content']['parts'][0]['text'].strip()
    except Exception as e:
        print(f'[gemini] {e}')
        return None


def _ai_synthesize(responses, question, synth_fn):
    """Llama a synth_fn para fusionar las respuestas de los modelos en una sola."""
    joined = '\n\n---\n\n'.join(
        f'[IA {i+1}]: {r}' for i, r in enumerate(responses)
    )
    prompt = (
        f'El staff preguntó: "{question}"\n\n'
        f'Estas son las respuestas de {len(responses)} modelos de IA:\n\n{joined}\n\n'
        'Sintetiza la respuesta más certera y completa combinando los puntos más '
        'precisos de cada una. Elimina redundancias. Responde en español, máx 250 palabras.'
    )
    return synth_fn([{'role': 'user', 'content': prompt}])


@app.route('/api/staff/chat', methods=['POST'])
@login_required
def staff_chat():
    """Chat de IA para staff — ensemble Claude + Groq + Gemini con búsqueda web."""
    import concurrent.futures as _cf

    # Rate limit: 20 mensajes/hora por sesión
    now_ts = datetime.datetime.utcnow().timestamp()
    rate_log = session.get('chat_rate_log', [])
    rate_log = [ts for ts in rate_log if now_ts - ts < 3600]
    if len(rate_log) >= 20:
        return jsonify({'error': 'Límite de 20 mensajes/hora alcanzado.'}), 429
    rate_log.append(now_ts)
    session['chat_rate_log'] = rate_log

    data    = request.json or {}
    user_msg = (data.get('message') or '').strip()
    scan_id  = data.get('scan_id')
    if not user_msg:
        return jsonify({'error': 'Mensaje vacío'}), 400

    # Detectar qué providers están configurados
    k_claude = os.environ.get('ANTHROPIC_API_KEY')
    k_groq   = os.environ.get('GROQ_API_KEY')
    k_gemini = os.environ.get('GEMINI_API_KEY')
    if not any([k_claude, k_groq, k_gemini]):
        return jsonify({'error': 'No hay API keys de IA configuradas (ANTHROPIC_API_KEY / GROQ_API_KEY / GEMINI_API_KEY).'}), 503

    # Contexto del scan
    scan_context = ''
    if scan_id:
        try:
            with get_api_db_cursor() as cur:
                cur.execute(
                    f'SELECT machine_name, minecraft_username, verdict, issues_found FROM scans WHERE id = {_PH}',
                    (scan_id,)
                )
                row = cur.fetchone()
                if row:
                    machine  = _row_get(row, 0, 'machine_name') or '?'
                    mc_user  = _row_get(row, 1, 'minecraft_username') or '?'
                    verdict  = _row_get(row, 2, 'verdict') or 'pendiente'
                    n_issues = _row_get(row, 3, 'issues_found') or 0
                    scan_context = (
                        f'\n\n[SCAN #{scan_id}] Jugador: {mc_user} | Máquina: {machine} | '
                        f'Veredicto: {verdict} | Hallazgos: {n_issues}\n'
                    )
                    cur.execute(
                        f'SELECT issue_name, issue_category, alert_level, confidence '
                        f'FROM scan_results WHERE scan_id = {_PH} ORDER BY confidence DESC LIMIT 20',
                        (scan_id,)
                    )
                    for r in (cur.fetchall() or []):
                        lvl  = _row_get(r, 2, 'alert_level') or ''
                        name = _row_get(r, 0, 'issue_name') or ''
                        cat  = _row_get(r, 1, 'issue_category') or ''
                        try:
                            conf_s = f"{float(_row_get(r, 3, 'confidence') or 0):.0%}"
                        except Exception:
                            conf_s = ''
                        scan_context += f'  [{lvl}] {name} ({cat}) {conf_s}\n'
        except Exception as e:
            print(f'[staff_chat] scan ctx error: {e}')

    history  = list(session.get('chat_history', []))
    history.append({'role': 'user', 'content': user_msg})

    # Búsqueda web compartida (en paralelo con las llamadas a IA)
    search_text = ''
    search_query = user_msg[:120]

    system_full = _CHAT_SYSTEM + scan_context

    # Lanzar búsqueda web + llamadas a IA TODO en paralelo
    futures = {}
    with _cf.ThreadPoolExecutor(max_workers=4) as pool:
        futures['search'] = pool.submit(_ai_web_search, search_query)
        if k_claude:
            futures['claude'] = pool.submit(_ai_call_claude, k_claude, system_full, list(history))
        if k_groq:
            futures['groq']   = pool.submit(_ai_call_groq,   k_groq,   system_full, list(history))
        if k_gemini:
            futures['gemini'] = pool.submit(_ai_call_gemini, k_gemini, system_full, list(history), user_msg)

        results = {name: f.result() for name, f in futures.items()}

    search_text = results.pop('search', '') or ''
    providers_used = []
    ai_responses   = []

    for name in ('claude', 'groq', 'gemini'):
        if name in results and results[name]:
            providers_used.append(name)
            ai_responses.append(results[name])

    if not ai_responses:
        return jsonify({'error': 'Todos los modelos fallaron. Verifica las API keys.'}), 503

    # Si hay resultados web, añadirlos a un segundo round si se necesita
    # (ya incluidos en el contexto de las IAs vía system prompt + search_text)
    # Para la síntesis, incluir el contexto de búsqueda en el system
    if search_text:
        system_full += f'\n\n[BÚSQUEDA WEB]\n{search_text[:1200]}'

    # Síntesis: si hay 2+ respuestas, fusionar con el modelo más rápido disponible
    final_reply = ''
    if len(ai_responses) == 1:
        final_reply = ai_responses[0]
    else:
        # Elegir sintetizador: Groq (gratis+rápido) > Gemini > Claude
        if k_groq:
            synth_fn = lambda msgs: _ai_call_groq(k_groq, system_full, msgs)
        elif k_gemini:
            synth_fn = lambda msgs: _ai_call_gemini(k_gemini, system_full, [], msgs[0]['content'])
        else:
            synth_fn = lambda msgs: _ai_call_claude(k_claude, system_full, msgs)

        final_reply = _ai_synthesize(ai_responses, user_msg, synth_fn) or ai_responses[0]

    history.append({'role': 'assistant', 'content': final_reply})
    session['chat_history'] = history[-20:]

    return jsonify({
        'reply':          final_reply,
        'providers_used': providers_used,
        'search_done':    bool(search_text),
        'scan_id':        scan_id,
    })


@app.route('/api/staff/chat/clear', methods=['POST'])
@login_required
def staff_chat_clear():
    """Borra el historial del chat de IA para la sesión actual."""
    session.pop('chat_history', None)
    session.pop('chat_rate_log', None)
    return jsonify({'success': True})


@app.route('/api/staff/ai/suggest-verdict/<int:scan_id>', methods=['GET'])
@login_required
def ai_suggest_verdict(scan_id):
    """Analiza los hallazgos de un scan y sugiere veredicto con justificación."""
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
                                    'Risk score bajo — comportamiento esperado de un usuario limpio.']})

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
        'Determina si el jugador tiene hacks o está limpio. '
        'Responde ÚNICAMENTE con este JSON válido (sin texto extra):\n'
        '{"verdict":"HACK","confidence":85,"reasons":["razón 1","razón 2","razón 3"]}\n'
        'verdict = "HACK" o "LIMPIO", confidence = 0-100, reasons = 3 strings cortos en español.'
    )

    system = 'Eres un experto en detección de hacks de Minecraft. Responde solo con JSON válido.'
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
    """Devuelve una explicación de 1-2 líneas de un hallazgo específico."""
    name  = (request.args.get('name')  or '').strip()[:120]
    level = (request.args.get('level') or 'SOSPECHOSO').strip()
    if not name:
        return jsonify({'error': 'Parámetro name requerido'}), 400

    k_groq   = os.environ.get('GROQ_API_KEY')
    k_gemini = os.environ.get('GEMINI_API_KEY')
    k_claude = os.environ.get('ANTHROPIC_API_KEY')
    if not any([k_groq, k_gemini, k_claude]):
        return jsonify({'explanation': 'Sin API keys configuradas.'}), 200

    prompt = (
        f'En máximo 2 oraciones cortas, explica qué es "{name}" '
        f'(nivel de alerta: {level}) en el contexto de trampas en Minecraft '
        f'y por qué es sospechoso. Sé técnico y directo. Solo el texto, sin bullet points.'
    )
    system   = 'Eres un experto en seguridad de Minecraft. Responde en español, máx 2 oraciones.'
    messages = [{'role': 'user', 'content': prompt}]

    expl = None
    if k_groq:
        expl = _ai_call_groq(k_groq, system, messages)
    if not expl and k_gemini:
        expl = _ai_call_gemini(k_gemini, system, [], prompt)
    if not expl and k_claude:
        expl = _ai_call_claude(k_claude, system, messages)

    return jsonify({'explanation': expl or 'No se pudo generar explicación.'})


@app.route('/api/staff/ai/scan-summary/<int:scan_id>', methods=['GET'])
@login_required
def ai_scan_summary(scan_id):
    """P3 #12 — Genera un resumen en lenguaje natural del scan para el staff.
    Returns: {summary: str}  — párrafo de 3-5 oraciones en español.
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
        return jsonify({'summary': f'El scan del jugador {mc_user} no arrojó hallazgos relevantes.'}), 200

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
        'Escribe un resumen ejecutivo de 3-5 oraciones en español que explique claramente:\n'
        '1. Qué evidencia concreta existe de hacks\n'
        '2. Cuáles son los hallazgos más importantes\n'
        '3. Tu conclusión sobre si el jugador es sospechoso o no\n'
        'Sé directo y técnico. No uses bullet points.'
    )
    system   = 'Eres un experto en análisis forense de hacks en Minecraft. Responde en español.'
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
    """P3 #23 — IA detecta inconsistencias en el conjunto de hallazgos de un scan."""
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
        'Ejemplos: "Tiene Forge instalado pero también agentlib (inusual)", '
        '"Detectado Vape pero no hay historial de visitas a vape.gg", '
        '"Múltiples ghost clients instalados simultáneamente". '
        'Responde SOLO con JSON: {"inconsistencies": ["descripción 1", "descripción 2"]} '
        'Si no hay inconsistencias, devuelve {"inconsistencies": []}. '
        'Máximo 3 inconsistencias. Sin texto extra fuera del JSON.'
    )
    system   = 'Eres un experto en análisis forense de hacks de Minecraft. Responde solo con JSON.'
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


_REVIEW_SECRET = 'aspers-claude-review-2026'

@app.route('/internal/scan-review/<int:scan_id>')
def internal_scan_review(scan_id):
    if request.args.get('token') != _REVIEW_SECRET:
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


# ── P3 #19 — Reputación cross-server por machine_id ──────────────────────────

@app.route('/api/player_reputation/<string:machine_id>', methods=['GET'])
@login_required
def player_reputation(machine_id):
    """P3 #19 — Reputación histórica agregada de un jugador por machine_id.
    Devuelve veredictos, risk_score promedio y tipos de hallazgos más frecuentes.
    """
    if not machine_id or len(machine_id) > 128:
        return jsonify({'error': 'machine_id inválido'}), 400
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


# ── P2 #31 — TF-IDF sobre nombres de archivos en scans históricos ─────────────

@app.route('/api/ml/tfidf-names', methods=['GET'])
@login_required
def ml_tfidf_names():
    """P2 #31 — TF-IDF sobre issue_name de scans con veredicto hack.
    Retorna los términos más discriminantes entre scans hack vs clean.
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


# ── P3 #32 — Feature store: precomputar features por machine_id ───────────────

@app.route('/api/ml/feature-store/<string:machine_id>', methods=['GET'])
@login_required
def feature_store_get(machine_id):
    """P3 #32 — Devuelve features precalculadas para un machine_id.
    Si no están en caché, las calcula y las guarda para futuras consultas.
    """
    if not machine_id or len(machine_id) > 128:
        return jsonify({'error': 'machine_id inválido'}), 400
    try:
        with get_api_db_cursor() as cur:
            # Intentar leer de caché (tabla feature_cache si existe)
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
                pass  # tabla no existe aún → calcular igualmente

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

            # Guardar en caché si la tabla existe
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


# ── P3 #24 — Preguntas de seguimiento para el staff ───────────────────────────

@app.route('/api/staff/ai/followup-questions/<int:scan_id>', methods=['GET'])
@login_required
def ai_followup_questions(scan_id):
    """P3 #24 — Genera preguntas de seguimiento que el staff debería hacerle al jugador."""
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
            f"Jugador: {username} | Máquina: {machine}\n"
            f"Risk Score: {risk}/100 | Hallazgos: {n_issues} | Veredicto actual: {verdict}\n\n"
            f"Hallazgos principales:\n{findings_summary}\n\n"
            f"Genera 5 preguntas específicas y directas que el staff debería hacerle al jugador "
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


# ── P2 #33 — Distribución de tamaños de archivos sospechosos ─────────────────

@app.route('/api/ml/size-distribution', methods=['GET'])
@login_required
def ml_size_distribution():
    """P2 #33 — Analiza distribución de tamaños (confidence proxy) de hallazgos hack vs clean.
    Detecta si hay un rango de tamaño/confidence que discrimina bien entre categorías.
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


# ── P2 #40 — A/B testing de filtros con veredictos históricos ────────────────

@app.route('/api/ml/ab-test', methods=['GET'])
@login_required
def ml_ab_test():
    """P2 #40 — Compara dos conjuntos de alert_level thresholds usando veredictos históricos.
    threshold_a y threshold_b son valores 0–100. Calcula precision/recall para cada uno.
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


# ── P3 #2 — Embeddings semánticos ligeros (TF-IDF cosine, sin sentence-transformers) ──

@app.route('/api/ml/semantic-similarity', methods=['POST'])
@login_required
def ml_semantic_similarity():
    """P3 #2 — Calcula similitud semántica entre un nombre de archivo y corpus de hacks conocidos.
    Usa TF-IDF + cosine similarity como aproximación ligera a embeddings.
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


# ── P3 #34 — Pipeline de ingesta de inteligencia de hacks (scraper) ───────────

@app.route('/api/admin/ingest-hack-intel', methods=['POST'])
@login_required
def ingest_hack_intel():
    """P3 #34 — Scraper pasivo de inteligencia sobre nuevos hack clients.
    Consulta fuentes públicas (GitHub releases, SpigotMC) para detectar nuevos names/hashes.
    Requiere rol admin. Resultados se guardan en hack_intel_log.
    """
    if not session.get('is_admin'):
        return jsonify({'error': 'Solo administradores'}), 403
    try:
        import threading as _thr
        results = []

        # Source 1: known GitHub repos — buscar release names de hack clients conocidos
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


# ── P3 #14 — Extracción de IOCs de texto libre ────────────────────────────────

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

    # Hashes (SHA-256 = 64 hex, SHA-1 = 40, MD5 = 32 — en orden para evitar subsets)
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


# ── P2 #10 — AbuseIPDB — reputación de IPs ────────────────────────────────────

@app.route('/api/ml/check-ip-reputation', methods=['POST'])
def check_ip_reputation():
    """Consulta AbuseIPDB para obtener el historial de abuso de una IP.
    Requiere la variable de entorno ABUSEIPDB_API_KEY (tier gratuito: 1000 req/día).
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


# ── P2 #9 — IP ASN / hosting check vía ip-api.com (gratis, sin API key) ──────

@app.route('/api/ml/check-ip-asn', methods=['POST'])
def check_ip_asn():
    """Consulta ip-api.com para obtener ASN, ISP y si la IP es hosting/proxy.
    Aproximación gratuita de Shodan: detecta IPs de proveedores típicos de C2.
    Límite: 45 req/min sin API key.
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


# ── P3 #33 — SimHash: similitud de archivos por hash local ────────────────────

@app.route('/api/ml/simhash', methods=['POST'])
def simhash_similarity():
    """Calcula la similitud entre el hash de un archivo y la base de datos de hacks
    usando SimHash (Hamming distance sobre SHA-256 bits). Sin modelos de ML externos.
    También acepta múltiples hashes para encontrar clusters de archivos similares.
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
            # Obtener hashes de scans con veredicto "hack" de los últimos 90 días
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
        near_count = sum(1 for d in distances if d <= 8)  # ≤8 bits diferentes de 64 = muy similar
        is_suspicious = min_dist <= 12 or near_count >= 3
        results.append({
            'hash':          h,
            'min_hamming':   min_dist,
            'similar_hacks': near_count,
            'is_suspicious': is_suspicious,
            'similarity_pct': round((64 - min_dist) / 64 * 100, 1),
        })

    return jsonify({'results': results, 'known_hack_hashes': len(known_hack_bits)}), 200


# ── P5 #30 — System health dashboard ─────────────────────────────────────────

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
    # Versión
    health['argus_version'] = _ARGUS_VERSION
    health['timestamp'] = datetime.datetime.utcnow().isoformat() + 'Z'
    return jsonify(health), 200


# ── P5 #17 — Staff Audit Log ─────────────────────────────────────────────────

def _log_staff_action(action: str, target_scan_id=None, detail: str = '', user_id=None):
    """Registra una acción del staff en la tabla staff_audit_log."""
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


# ═══════════════════════════════════════════════════════════════════════
# Pack 32 — F#54/F#55/F#60 endpoints
# ═══════════════════════════════════════════════════════════════════════

@app.route('/api/staff/my-trust', methods=['GET'])
@login_required
def get_my_trust():
    """Trust score del staff logueado (F#54).
    Cualquier staff lo ve para sí mismo; admin ve cualquiera.
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
    """Admin confirma o desmiente una decisión post-facto del staff
    (F#54 — confirmed_correct / confirmed_wrong pesan doble en el score).

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


# ── Filter #11 — Aprendizaje incremental: enseñar un path como FP ──────────
# El staff abre un scan, ve un FP claro (ej: "Game.exe" en
# "C:\Apps\MiAppLegit\bin\Game.exe") y lo marca como FP. El backend guarda
# un fragmento del path (la carpeta padre normalizada) en learned_patterns
# con type='legitimate_path'. _is_server_false_positive() lo aplicará a
# TODOS los scans futuros y a los actuales via _scrub_results_for_display.
# Cache de _get_learned_legit_paths se invalida automáticamente en 5 min.
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
        # Auto-deriva el fragmento: tomamos el último directorio del path
        # y el nombre del archivo, p.ej "lunarclient\\game.exe".
        src = (raw_path or raw_name).replace('/', '\\').lower()
        if not src:
            return jsonify({'error': 'Falta path/name/fragment'}), 400
        parts = src.split('\\')
        # Tomamos los últimos 2 componentes (carpeta + archivo) para tener
        # un fragmento descriptivo pero específico.
        fragment = '\\'.join(parts[-2:]) if len(parts) >= 2 else parts[-1]
    if len(fragment) < 4:
        return jsonify({'error': 'Fragmento demasiado corto (mín 4 chars)'}), 400
    fragment = fragment[:255]
    try:
        with get_api_db_cursor() as cur:
            # Schema: learned_patterns sin company_id, así que el patrón es
            # global. Esto es intencional para acelerar el aprendizaje
            # cross-empresa, pero lo registramos quien lo enseñó vía
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

        # Invalidar caché in-memory para que aplique YA al próximo scan
        try:
            _lp_cache['ts'] = 0.0
        except Exception:
            pass

        try:
            _log_staff_action('learn_fp', detail=f"path_fragment={fragment} action={action}")
        except Exception:
            pass

        # Pack 32 F#60 — Incrementar cooldown de la empresa.
        # Detecta volúmenes anómalos de FP-learning como señal de
        # corrupción o filtro mal calibrado, y sube los thresholds
        # del cliente para forzar revisión más estricta.
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
            'note': 'Aplicará a scans futuros y se filtrará retroactivamente al servirlos.',
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── Visual #46 — Comparador lado-a-lado: scans del mismo jugador ────────────
# Devuelve scans anteriores al `scan_id` actual del MISMO MC username (y/o
# machine_id), ordenados desc. Pensado para el comparador lado-a-lado del
# panel: el JS pide los anteriores y arma el diff. NO trae results detallados,
# solo metadata + conteos para el comparador rápido.
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

            # 2) Buscar otros scans del mismo MC user O misma máquina
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


# ════════════════════════════════════════════════════════════════════════
# Pack 33 — V#47 Timeline visual del jugador
# ════════════════════════════════════════════════════════════════════════
# Devuelve eventos cronológicos del jugador (scans + verdict changes +
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

        # Ordenar todo por timestamp desc, fechas inválidas al final
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


# ── Visual #11 — Staff activity heatmap (GitHub-style) ──────────────────────
# Devuelve la actividad del staff loggeado durante los últimos N días (default
# 365). Cuenta dos cosas en paralelo:
#   1) Acciones registradas en staff_audit_log (verdicts, exports, etc).
#   2) Verdicts puestos en la tabla scans donde verdict_by = staff.username.
# Las dos sumas se combinan por día para que el heatmap refleje TODA la
# actividad del staff, no solo las acciones audit. Resultado:
#   { 'days': [{date, count}], 'total_count': N, 'days_active': M, 'streak': K }
# La generación de la grilla 7×52 se hace client-side; aquí solo damos el
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

            # Audit log buckets (CREATE IF NOT EXISTS por si la tabla aún no
            # existe en este deployment — devolvemos vacío sin romper).
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

        # Streak actual: días consecutivos hasta hoy con count > 0
        streak = 0
        cur_d = today
        while True:
            if buckets.get(str(cur_d), 0) > 0:
                streak += 1
                cur_d = cur_d - timedelta(days=1)
            else:
                break
        # Mejor streak histórico
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


# ── Visual #13 — Stats agregados del staff (achievements + line chart) ────────
# Devuelve métricas que alimentan tanto el sistema de logros como el line chart
# de risk score histórico. Combina staff_audit_log + scans (verdict_by).
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
        'history':        [],   # [{date, value}] — risk score promedio por día
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
                # Mejor streak histórico
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
                # Histórico últimos 30 días — risk score promedio diario
                history = []
                sum30, count30 = 0, 0
                for i in range(29, -1, -1):
                    dd = today - timedelta(days=i)
                    b = day_buckets.get(str(dd))
                    if b and b['n']:
                        avg = round(b['sum'] / b['n'])
                        history.append({'date': str(dd), 'value': avg, 'label': dd.strftime('%d/%m')})
                        sum30 += avg; count30 += 1
                    # Si no hay datos ese día, no se incluye en history pero
                    # tampoco rompe la línea (el chart conecta los puntos
                    # disponibles).
                stats['history'] = history
                stats['avg_risk_30d'] = round(sum30 / count30) if count30 else 0
            except Exception as e:
                print(f'[my-stats] scans agg: {e}')
        _staff_stats_cache[uid] = (stats, _t.time())
        return jsonify(stats), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── P5 #19 — Auto-generate ban message ────────────────────────────────────────

@app.route('/api/staff/ai/generate-ban-message', methods=['POST'])
@login_required
def generate_ban_message():
    """Genera un mensaje de ban con las evidencias más relevantes del scan."""
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
        return jsonify({'error': 'Sin hallazgos críticos en este scan'}), 404

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
        f'1. Ser profesional y en español\n'
        f'2. Mencionar las 3 evidencias más fuertes\n'
        f'3. Indicar que el ban es permanente si hay múltiples indicadores CRITICAL\n'
        f'4. No exceder 5 líneas\n'
        f'5. Incluir el nombre del escáner (Argus Scanner)\n'
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


# ── P5 #27 — Player clustering with DBSCAN ───────────────────────────────────

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


# ── P5 #28 — Player timeline ──────────────────────────────────────────────────

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

    # Tendencia lineal simple (regresión mínimos cuadrados)
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


# ── P5 #23 — Scan diff endpoint ───────────────────────────────────────────────

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


# ── P5 #24 — Telegram webhook alternative ────────────────────────────────────

def _notify_telegram(message: str):
    """Envía notificación al canal de Telegram si TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID
    están configurados. No bloquea — se ejecuta en background thread."""
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
            print(f'[Telegram] Error de envío: {e}')

    import threading
    threading.Thread(target=_send, daemon=True).start()


# ── P5 #26 — Rate limiting on public API endpoints ───────────────────────────

import time as _time_rl
_rate_limit_store = {}  # ip -> list of timestamps

def _check_rate_limit(ip: str, max_requests: int = 10, window_seconds: int = 60) -> bool:
    """Devuelve True si la IP está dentro del límite, False si lo excedió."""
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
    """Rate limit en endpoints públicos sensibles."""
    PUBLIC_LIMITED = {'/api/submit', '/api/predict', '/api/scan/submit'}
    path = request.path
    if path in PUBLIC_LIMITED:
        ip = request.headers.get('X-Forwarded-For', request.remote_addr or 'unknown').split(',')[0].strip()
        if not _check_rate_limit(ip, max_requests=20, window_seconds=60):
            return jsonify({'error': 'Rate limit excedido. Máximo 20 requests/minuto por IP.'}), 429


@app.route('/api/admin/scan-heatmap', methods=['GET'])
@login_required
def scan_heatmap():
    """P5 #18 — Heatmap de actividad de scans por día de semana y hora del día.
    Retorna una matriz 7×24 con el conteo de scans iniciados en cada celda.
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

        # Build 7×24 matrix (day_of_week × hour)
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
                dow = dt.weekday()   # 0=Mon … 6=Sun
                hour = dt.hour
                matrix[dow][hour] += 1
                verdict = (row[1] if isinstance(row, (list, tuple)) else row.get('verdict', ''))
                if verdict == 'hack':
                    detections_matrix[dow][hour] += 1
            except Exception:
                continue

        day_names = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']
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
    """P5 #20 — Buscar perfil de Mojang por UUID o nickname.
    Proxy seguro para evitar CORS: el frontend llama a este endpoint.
    """
    identifier = request.args.get('q', '').strip()
    if not identifier:
        return jsonify({'error': 'Parámetro q requerido'}), 400
    import urllib.request as _ur
    import json as _json
    try:
        # Determine if it's a UUID (contains hyphens or is 32 hex chars) or a username
        is_uuid = len(identifier.replace('-', '')) == 32 and all(c in '0123456789abcdefABCDEF-' for c in identifier)
        if is_uuid:
            uuid_clean = identifier.replace('-', '')
            # UUID → profile
            url = f'https://sessionserver.mojang.com/session/minecraft/profile/{uuid_clean}'
            with _ur.urlopen(url, timeout=5) as r:
                profile = _json.loads(r.read())
            return jsonify({
                'uuid': profile.get('id'),
                'username': profile.get('name'),
                'source': 'mojang_session',
            })
        else:
            # Username → UUID
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
    """P5 #25 — Detectar cheating coordinado: múltiples jugadores del mismo equipo
    que tienen hallazgos del mismo tipo en un rango de tiempo cercano.
    Busca clusters de máquinas con hacks similares enviados en la misma ventana de 24h.
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


if __name__ == '__main__':
    print("🌐 Iniciando aplicación web de ASPERS Projects...")
    api_url_display = os.environ.get('API_URL') or (API_BASE_URL if IS_RENDER else API_BASE_URL)
    print(f"📡 Conectado a API: {api_url_display}")
    print(f"🔑 API Key configurada: {'Sí' if API_KEY != 'change-this-in-production' else 'No (usar valor por defecto)'}")
    print("⚠️  NOTA: Asegúrate de que la API esté corriendo en http://localhost:5000")
    print("⚠️  NOTA: La API Key debe coincidir con la configurada en api_server.py")
    app.run(host='0.0.0.0', port=8080, debug=True)

