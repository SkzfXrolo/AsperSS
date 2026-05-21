"""
API ArgusAdmin — SuperAdmin de escritorio (token + huella de voz).
Independiente del panel web; conecta con Render.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from functools import wraps

from flask import jsonify, request

_PH = '%s'
_USE_PG = False


def _init_db_helpers(app):
    global _USE_PG
    try:
        from app import _USE_PG as pg  # noqa: circular at runtime after app load
        _USE_PG = pg
    except Exception:
        _USE_PG = 'postgresql' in (os.environ.get('DATABASE_URL') or '').lower()


def _secret() -> bytes:
    s = (os.environ.get('ARGUS_ADMIN_JWT_SECRET') or os.environ.get('SECRET_KEY') or '').strip()
    if not s:
        raise ValueError('ARGUS_ADMIN_JWT_SECRET o SECRET_KEY requerido')
    return s.encode('utf-8')


def _panel_owner_usernames() -> set[str]:
    raw = (os.environ.get('ARGUS_PANEL_OWNER_USERNAMES') or 'arefy_admin,arefy').strip().lower()
    return {p.strip() for p in raw.split(',') if p.strip()}


def _is_panel_owner_user(user) -> bool:
    if not user:
        return False
    return (user.get('username') or '').strip().lower() in _panel_owner_usernames()


def _token_issue(user_id: int, device_id: str, *, voice_ok: bool, hours: int = 8) -> str:
    exp = int(time.time()) + hours * 3600
    payload = json.dumps({
        'uid': int(user_id),
        'exp': exp,
        'dev': (device_id or '')[:64],
        'v': 1 if voice_ok else 0,
    }, separators=(',', ':'))
    sig = hmac.new(_secret(), payload.encode('utf-8'), hashlib.sha256).hexdigest()
    blob = base64.urlsafe_b64encode(f'{payload}|{sig}'.encode('utf-8')).decode('ascii')
    return blob


def _token_verify(token: str, device_id: str, *, require_voice: bool = True) -> dict | None:
    try:
        raw = base64.urlsafe_b64decode(token.encode('ascii')).decode('utf-8')
        payload, sig = raw.rsplit('|', 1)
        expect = hmac.new(_secret(), payload.encode('utf-8'), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expect, sig):
            return None
        data = json.loads(payload)
        if int(data.get('exp') or 0) < int(time.time()):
            return None
        if (data.get('dev') or '') != (device_id or '')[:64]:
            return None
        if require_voice and not int(data.get('v') or 0):
            return None
        return data
    except Exception:
        return None


def register_argus_admin_routes(app, *, get_api_db_cursor, row_get, use_pg=False, is_panel_owner_fn=None):
    """Registra rutas /api/argus-admin/v1/* en la app Flask."""
    global _USE_PG
    _USE_PG = bool(use_pg)
    owner_check = is_panel_owner_fn or _is_panel_owner_user

    def _ensure_schema():
        try:
            with get_api_db_cursor() as cur:
                if _USE_PG:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS argus_admin_devices (
                            id SERIAL PRIMARY KEY,
                            user_id INTEGER NOT NULL,
                            device_id VARCHAR(128) NOT NULL,
                            voice_fp_hash VARCHAR(128),
                            assistant_settings TEXT,
                            phrase_label VARCHAR(64) DEFAULT 'desbloqueo argus',
                            enrolled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            last_unlock_at TIMESTAMP,
                            UNIQUE(user_id, device_id)
                        )
                    """)
                else:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS argus_admin_devices (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id INTEGER NOT NULL,
                            device_id TEXT NOT NULL,
                            voice_fp_hash TEXT,
                            assistant_settings TEXT,
                            phrase_label TEXT DEFAULT 'desbloqueo argus',
                            enrolled_at TEXT DEFAULT CURRENT_TIMESTAMP,
                            last_unlock_at TEXT,
                            UNIQUE(user_id, device_id)
                        )
                    """)
        except Exception as e:
            app.logger.warning('[argus-admin] schema: %s', e)

    def _device_header() -> str:
        return (request.headers.get('X-Argus-Admin-Device') or '').strip()[:128]

    def _require_admin_token(require_voice=True):
        def deco(f):
            @wraps(f)
            def wrapped(*args, **kwargs):
                tok = (request.headers.get('X-Argus-Admin-Token') or '').strip()
                dev = _device_header()
                if not tok or not dev:
                    return jsonify({'error': 'Token o device_id faltante'}), 401
                data = _token_verify(tok, dev, require_voice=require_voice)
                if not data:
                    return jsonify({'error': 'Token inválido o voz no verificada'}), 401
                request.argus_admin_uid = int(data['uid'])
                request.argus_admin_device = dev
                return f(*args, **kwargs)
            return wrapped
        return deco

    @app.route('/api/argus-admin/v1/status', methods=['GET'])
    def argus_admin_status():
        return jsonify({
            'product': 'ArgusAdmin',
            'voice_gate': True,
            'owner_usernames_configured': bool(_panel_owner_usernames()),
            'render': bool(os.environ.get('RENDER')),
        })

    @app.route('/api/argus-admin/v1/login', methods=['POST'])
    def argus_admin_login():
        """Usuario + contraseña del owner (misma cuenta del panel). Sin token de voz aún."""
        data = request.get_json(silent=True) or {}
        username = (data.get('username') or '').strip()
        password = (data.get('password') or '')
        device_id = (data.get('device_id') or '').strip()[:128]
        if not username or not password or not device_id:
            return jsonify({'error': 'username, password y device_id requeridos'}), 400
        from auth import authenticate_user
        user, err = authenticate_user(username, password)
        if err or not user:
            return jsonify({'error': err or 'Credenciales inválidas'}), 401
        if not owner_check(user):
            return jsonify({'error': 'Solo el owner del panel puede usar ArgusAdmin'}), 403
        _ensure_schema()
        token = _token_issue(user['id'], device_id, voice_ok=False, hours=1)
        return jsonify({
            'token': token,
            'user_id': user['id'],
            'username': user.get('username'),
            'needs_voice_enroll': True,
            'message': 'Registrá tu voz antes del desbloqueo completo.',
        })

    @app.route('/api/argus-admin/v1/voice/enroll', methods=['POST'])
    @_require_admin_token(require_voice=False)
    def argus_admin_voice_enroll():
        data = request.get_json(silent=True) or {}
        fp_hash = (data.get('fingerprint_hash') or '').strip()
        extra = data.get('fingerprint_hashes') or []
        hashes: list[str] = []
        if fp_hash and len(fp_hash) >= 32:
            hashes.append(fp_hash)
        for h in extra if isinstance(extra, list) else []:
            hs = (h or '').strip()
            if len(hs) >= 32 and hs not in hashes:
                hashes.append(hs)
        if not hashes:
            return jsonify({'error': 'fingerprint_hash inválido'}), 400
        stored = ','.join(hashes)[:2000]
        uid = request.argus_admin_uid
        dev = request.argus_admin_device
        _ensure_schema()
        try:
            with get_api_db_cursor() as cur:
                if _USE_PG:
                    cur.execute(
                        f"""INSERT INTO argus_admin_devices (user_id, device_id, voice_fp_hash)
                            VALUES ({_PH}, {_PH}, {_PH})
                            ON CONFLICT (user_id, device_id)
                            DO UPDATE SET voice_fp_hash = EXCLUDED.voice_fp_hash, enrolled_at = CURRENT_TIMESTAMP""",
                        (uid, dev, stored),
                    )
                else:
                    cur.execute(
                        f"""INSERT OR REPLACE INTO argus_admin_devices
                            (user_id, device_id, voice_fp_hash, enrolled_at)
                            VALUES ({_PH}, {_PH}, {_PH}, datetime('now'))""",
                        (uid, dev, stored),
                    )
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        return jsonify({'success': True, 'enrolled': True})

    @app.route('/api/argus-admin/v1/voice/unlock', methods=['POST'])
    def argus_admin_voice_unlock():
        """Tras verificar huella local, obtiene token con voice_ok=1."""
        data = request.get_json(silent=True) or {}
        username = (data.get('username') or '').strip()
        password = (data.get('password') or '')
        device_id = (data.get('device_id') or '').strip()[:128]
        fp_hash = (data.get('fingerprint_hash') or '').strip()
        if not all([username, password, device_id, fp_hash]):
            return jsonify({'error': 'Datos incompletos'}), 400
        from auth import authenticate_user
        user, err = authenticate_user(username, password)
        if err or not user or not owner_check(user):
            return jsonify({'error': 'Acceso denegado'}), 401
        _ensure_schema()
        try:
            with get_api_db_cursor() as cur:
                cur.execute(
                    f"""SELECT voice_fp_hash FROM argus_admin_devices
                        WHERE user_id = {_PH} AND device_id = {_PH}""",
                    (user['id'], device_id),
                )
                row = cur.fetchone()
            stored = ''
            if row:
                stored = row_get(row, 0, 'voice_fp_hash') if hasattr(row, 'keys') else (row[0] or '')
            allowed: set[str] = set()
            if stored:
                if ',' in stored:
                    allowed.update(h.strip() for h in stored.split(',') if h.strip())
                else:
                    allowed.add(stored.strip())
            if not allowed or fp_hash not in allowed:
                return jsonify({
                    'error': 'Voz no registrada en el servidor. Abrí ArgusAdmin y usá «Regrabar voz».',
                }), 403
            with get_api_db_cursor() as cur:
                cur.execute(
                    f"""UPDATE argus_admin_devices SET last_unlock_at = CURRENT_TIMESTAMP
                        WHERE user_id = {_PH} AND device_id = {_PH}""",
                    (user['id'], device_id),
                )
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        token = _token_issue(user['id'], device_id, voice_ok=True, hours=12)
        return jsonify({
            'token': token,
            'unlocked': True,
            'expires_hours': 12,
            'permissions': _admin_permissions(),
        })

    @app.route('/api/argus-admin/v1/overview', methods=['GET'])
    @_require_admin_token(require_voice=True)
    def argus_admin_overview():
        """KPIs SuperAdmin — requiere token con voz verificada."""
        out = {'source': 'argus-admin', 'kpis': {}}
        scans_sql = (
            "SELECT COUNT(*) FROM scans WHERE started_at >= NOW() - INTERVAL '1 day'"
            if _USE_PG
            else "SELECT COUNT(*) FROM scans WHERE started_at >= datetime('now', '-1 day')"
        )
        try:
            with get_api_db_cursor() as cur:
                for label, sql in (
                    ('companies', 'SELECT COUNT(*) FROM companies'),
                    ('users', 'SELECT COUNT(*) FROM users'),
                    ('scans_24h', scans_sql),
                ):
                    try:
                        cur.execute(sql)
                        r = cur.fetchone()
                        out['kpis'][label] = int(row_get(r, 0, list(r.keys())[0] if r else 0) or 0)
                    except Exception:
                        out['kpis'][label] = None
        except Exception as e:
            out['error'] = str(e)
        out['permissions'] = _admin_permissions()
        out['sa_panel_url'] = '/aspers-sa'
        return jsonify(out)

    @app.route('/api/argus-admin/v1/config', methods=['GET', 'PUT'])
    @_require_admin_token(require_voice=True)
    def argus_admin_config():
        """Config que Argus Assistant puede leer/escribir (assistant_settings en JSON)."""
        uid = request.argus_admin_uid
        _ensure_schema()
        dev = request.argus_admin_device
        if request.method == 'GET':
            with get_api_db_cursor() as cur:
                cfg = _load_assistant_settings_db(cur, uid, dev, row_get)
            return jsonify({'config': cfg})
        data = request.json or {}
        cfg = data.get('config') if isinstance(data.get('config'), dict) else data
        if not isinstance(cfg, dict):
            return jsonify({'error': 'config debe ser objeto JSON'}), 400
        with get_api_db_cursor() as cur:
            _save_assistant_settings_db(cur, uid, dev, cfg)
        return jsonify({'success': True, 'config': cfg})


def _admin_permissions() -> list[str]:
    return [
        'sa.overview',
        'sa.companies',
        'sa.users',
        'sa.maintenance',
        'sa.ai_weights',
        'sa.audit',
        'scanner.version',
        'platform.config',
        'assistant.config.write',
    ]


def _load_assistant_settings_db(cursor, user_id: int, device_id: str, row_get) -> dict:
    default = {
        'api_url': (os.environ.get('RENDER_EXTERNAL_URL') or 'https://asperss.onrender.com').rstrip('/'),
        'phrase': 'desbloqueo argus',
        'assistant_can_edit': True,
    }
    try:
        cursor.execute(
            f'SELECT assistant_settings FROM argus_admin_devices WHERE user_id = {_PH} AND device_id = {_PH}',
            (user_id, device_id),
        )
        row = cursor.fetchone()
        if not row:
            return default
        raw = row_get(row, 0, 'assistant_settings') if hasattr(row, 'keys') else row[0]
        if not raw:
            return default
        merged = dict(default)
        merged.update(json.loads(raw) if isinstance(raw, str) else raw)
        return merged
    except Exception:
        return default


def _save_assistant_settings_db(cursor, user_id: int, device_id: str, cfg: dict) -> None:
    blob = json.dumps(cfg, ensure_ascii=False)
    if _USE_PG:
        cursor.execute(
            f"""UPDATE argus_admin_devices SET assistant_settings = {_PH}
                WHERE user_id = {_PH} AND device_id = {_PH}""",
            (blob, user_id, device_id),
        )
    else:
        cursor.execute(
            f"""UPDATE argus_admin_devices SET assistant_settings = {_PH}
                WHERE user_id = {_PH} AND device_id = {_PH}""",
            (blob, user_id, device_id),
        )
