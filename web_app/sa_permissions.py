"""
Control Imperial — catálogo de permisos, overrides por usuario y God Mode flags.

Solo consumido desde /aspers-sa (sesión admin_subscriptions).
"""
from __future__ import annotations

import json
import os
import secrets
import time
from datetime import datetime, timezone

# ── Catálogo de capacidades ───────────────────────────────────────────────────

PERMISSION_CATALOG: list[dict] = [
    {'key': 'scans.view', 'label': 'Ver scans', 'category': 'Scans', 'icon': '◉', 'danger': False},
    {'key': 'scans.export', 'label': 'Exportar scans', 'category': 'Scans', 'icon': '↓', 'danger': False},
    {'key': 'scans.delete', 'label': 'Eliminar scans', 'category': 'Scans', 'icon': '✕', 'danger': True},
    {'key': 'verdicts.change', 'label': 'Cambiar veredicto', 'category': 'Veredictos', 'icon': '⚖', 'danger': False},
    {'key': 'verdicts.bulk', 'label': 'Veredictos masivos', 'category': 'Veredictos', 'icon': '▦', 'danger': True},
    {'key': 'verdicts.override_ai', 'label': 'Override IA', 'category': 'Veredictos', 'icon': '◐', 'danger': False},
    {'key': 'staff.manage', 'label': 'Gestionar staff', 'category': 'Staff', 'icon': '◈', 'danger': False},
    {'key': 'staff.tokens', 'label': 'Tokens registro', 'category': 'Staff', 'icon': '🔴', 'danger': False},
    {'key': 'staff.trust', 'label': 'Staff trust', 'category': 'Staff', 'icon': '★', 'danger': False},
    {'key': 'staff.audit', 'label': 'Audit log', 'category': 'Staff', 'icon': '⏱', 'danger': False},
    {'key': 'company.manage', 'label': 'Config empresa', 'category': 'Empresa', 'icon': '▣', 'danger': False},
    {'key': 'company.billing', 'label': 'Facturación', 'category': 'Empresa', 'icon': '$', 'danger': False},
    {'key': 'company.cross', 'label': 'Ver todas empresas', 'category': 'Empresa', 'icon': '◎', 'danger': True},
    {'key': 'ai.patterns', 'label': 'Patterns IA', 'category': 'Inteligencia', 'icon': '◭', 'danger': False},
    {'key': 'ai.maintenance', 'label': 'Mantenimiento IA', 'category': 'Inteligencia', 'icon': '⚒', 'danger': True},
    {'key': 'ai.health', 'label': 'Salud IA', 'category': 'Inteligencia', 'icon': '◐', 'danger': False},
    {'key': 'ai.oracle', 'label': 'AI Oracle', 'category': 'Inteligencia', 'icon': '◎', 'danger': False},
    {'key': 'system.users', 'label': 'CRUD usuarios', 'category': 'Sistema', 'icon': '◉', 'danger': True},
    {'key': 'system.impersonate', 'label': 'Impersonar', 'category': 'Sistema', 'icon': '👁', 'danger': True},
    {'key': 'system.god_mode', 'label': 'God Mode', 'category': 'Sistema', 'icon': '⚡', 'danger': True},
    {'key': 'system.config', 'label': 'Config plataforma', 'category': 'Sistema', 'icon': '▤', 'danger': True},
]

ALL_PERMISSION_KEYS = [p['key'] for p in PERMISSION_CATALOG]

ROLE_LABELS = {
    'user': 'Usuario',
    'empresa': 'Empresa',
    'staff': 'Staff',
    'helper': 'Helper',
    'moderador': 'Moderador',
    'admin': 'Admin global',
    'administrador': 'Admin empresa',
    'owner': 'Owner',
    'imperial': 'Imperial (SA)',
}

# Matriz rol → permisos base
ROLE_PERMISSIONS: dict[str, set[str]] = {
    'user': {'scans.view'},
    'empresa': {'scans.view', 'scans.export'},
    'staff': {'scans.view', 'scans.export'},
    'helper': {'scans.view', 'scans.export', 'staff.tokens'},
    'moderador': {
        'scans.view', 'scans.export', 'verdicts.change', 'verdicts.override_ai',
        'staff.audit', 'staff.tokens',
    },
    'admin': {
        'scans.view', 'scans.export', 'scans.delete', 'verdicts.change', 'verdicts.bulk',
        'verdicts.override_ai', 'staff.manage', 'staff.tokens', 'staff.trust', 'staff.audit',
        'company.cross', 'ai.patterns', 'ai.maintenance', 'ai.health', 'ai.oracle',
        'system.users',
    },
    'administrador': {
        'scans.view', 'scans.export', 'verdicts.change', 'staff.manage', 'staff.tokens',
        'company.manage', 'company.billing', 'ai.health',
    },
    'owner': set(ALL_PERMISSION_KEYS) - {'system.god_mode', 'system.impersonate'},
    'imperial': set(ALL_PERMISSION_KEYS),
}

MATRIX_ROLES = ['helper', 'moderador', 'admin', 'administrador', 'owner', 'imperial']

GOD_MODE_FLAGS: list[dict] = [
    {
        'key': 'maintenance_mode',
        'label': 'Modo mantenimiento',
        'desc': 'Bloquea nuevos scans del .exe. Mensaje custom al cliente.',
        'icon': '🔧',
        'danger': True,
        'default': False,
    },
    {
        'key': 'registrations_frozen',
        'label': 'Registros congelados',
        'desc': 'Nadie puede registrarse con token aunque sea válido.',
        'icon': '❄',
        'danger': False,
        'default': False,
    },
    {
        'key': 'scanner_uploads_paused',
        'label': 'Uploads pausados',
        'desc': 'Rechaza POST /api/scans/<id>/results (subida de resultados).',
        'icon': '⏸',
        'danger': True,
        'default': False,
    },
    {
        'key': 'ai_autolearn_off',
        'label': 'Auto-learn OFF',
        'desc': 'La IA deja de aprender patterns nuevos automáticamente.',
        'icon': '◭',
        'danger': False,
        'default': False,
    },
    {
        'key': 'oracle_disabled',
        'label': 'Oracle desactivado',
        'desc': 'El módulo AI Oracle no emite decisiones automáticas.',
        'icon': '◎',
        'danger': False,
        'default': False,
    },
    {
        'key': 'panel_readonly',
        'label': 'Panel solo lectura',
        'desc': 'Staff puede ver pero no cambiar veredictos ni notas.',
        'icon': '🔒',
        'danger': True,
        'default': False,
    },
    {
        'key': 'announcement_banner',
        'label': 'Banner global',
        'desc': 'Texto mostrado en /panel para todos (vacío = oculto).',
        'icon': '📢',
        'danger': False,
        'default': '',
        'type': 'text',
    },
]

_IMPERSONATE_TOKENS: dict[str, dict] = {}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_server_db() -> bool:
    """True en PostgreSQL/MySQL (Render); False en SQLite local."""
    try:
        from auth import USE_POSTGRESQL, USE_MYSQL
        if USE_POSTGRESQL or USE_MYSQL:
            return True
    except Exception:
        pass
    url = (os.environ.get('DATABASE_URL') or '').lower()
    return url.startswith('postgres') or 'mysql' in url


def ensure_sa_permission_tables(cursor, *, use_pg=None):
    """Crea tablas de flags y overrides si no existen."""
    if use_pg is None:
        use_pg = _is_server_db()
    if use_pg:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sa_platform_flags (
                flag_key    VARCHAR(64) PRIMARY KEY,
                flag_value  TEXT NOT NULL DEFAULT '',
                updated_at  TIMESTAMP DEFAULT NOW()
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sa_user_permission_overrides (
                user_id         INTEGER NOT NULL,
                permission_key  VARCHAR(64) NOT NULL,
                mode            VARCHAR(8) NOT NULL CHECK (mode IN ('grant', 'deny')),
                updated_at      TIMESTAMP DEFAULT NOW(),
                PRIMARY KEY (user_id, permission_key)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sa_imperial_audit (
                id          SERIAL PRIMARY KEY,
                action      VARCHAR(80) NOT NULL,
                target_type VARCHAR(32),
                target_id   VARCHAR(64),
                detail      TEXT,
                ip_address  VARCHAR(45),
                created_at  TIMESTAMP DEFAULT NOW()
            )
        ''')
    else:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sa_platform_flags (
                flag_key    TEXT PRIMARY KEY,
                flag_value  TEXT NOT NULL DEFAULT '',
                updated_at  TEXT DEFAULT (datetime('now'))
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sa_user_permission_overrides (
                user_id         INTEGER NOT NULL,
                permission_key  TEXT NOT NULL,
                mode            TEXT NOT NULL CHECK (mode IN ('grant', 'deny')),
                updated_at      TEXT DEFAULT (datetime('now')),
                PRIMARY KEY (user_id, permission_key)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sa_imperial_audit (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                action      TEXT NOT NULL,
                target_type TEXT,
                target_id   TEXT,
                detail      TEXT,
                ip_address  TEXT,
                created_at  TEXT DEFAULT (datetime('now'))
            )
        ''')


def _parse_bool(val) -> bool:
    if isinstance(val, bool):
        return val
    if val is None:
        return False
    s = str(val).strip().lower()
    return s in ('1', 'true', 'yes', 'on')


def get_platform_flags(cursor) -> dict:
    ensure_sa_permission_tables(cursor)
    out = {}
    for f in GOD_MODE_FLAGS:
        key = f['key']
        if f.get('type') == 'text':
            out[key] = f.get('default', '')
        else:
            out[key] = bool(f.get('default', False))
    try:
        cursor.execute('SELECT flag_key, flag_value FROM sa_platform_flags')
        for row in cursor.fetchall():
            k = row[0] if not hasattr(row, 'keys') else row['flag_key']
            v = row[1] if not hasattr(row, 'keys') else row['flag_value']
            meta = next((x for x in GOD_MODE_FLAGS if x['key'] == k), None)
            if meta and meta.get('type') == 'text':
                out[k] = v or ''
            else:
                out[k] = _parse_bool(v)
    except Exception:
        pass
    return out


def set_platform_flags(cursor, updates: dict) -> dict:
    ensure_sa_permission_tables(cursor)
    allowed = {f['key'] for f in GOD_MODE_FLAGS}
    current = get_platform_flags(cursor)
    for key, val in (updates or {}).items():
        if key not in allowed:
            continue
        meta = next(x for x in GOD_MODE_FLAGS if x['key'] == key)
        if meta.get('type') == 'text':
            stored = str(val or '')[:500]
            current[key] = stored
        else:
            stored = 'true' if _parse_bool(val) else 'false'
            current[key] = _parse_bool(val)
        try:
            cursor.execute(
                'INSERT INTO sa_platform_flags (flag_key, flag_value, updated_at) VALUES (%s, %s, %s) '
                'ON CONFLICT (flag_key) DO UPDATE SET flag_value = EXCLUDED.flag_value, updated_at = EXCLUDED.updated_at',
                (key, stored, _utc_now()),
            )
        except Exception:
            cursor.execute(
                'INSERT OR REPLACE INTO sa_platform_flags (flag_key, flag_value, updated_at) VALUES (?, ?, ?)',
                (key, stored, _utc_now()),
            )
    return current


def is_flag_active(cursor, key: str) -> bool:
    flags = get_platform_flags(cursor)
    val = flags.get(key)
    if isinstance(val, str) and key == 'announcement_banner':
        return bool(val.strip())
    return bool(val)


def get_user_overrides(cursor, user_id: int) -> dict[str, str]:
    ensure_sa_permission_tables(cursor)
    out: dict[str, str] = {}
    try:
        cursor.execute(
            'SELECT permission_key, mode FROM sa_user_permission_overrides WHERE user_id = %s',
            (user_id,),
        )
    except Exception:
        cursor.execute(
            'SELECT permission_key, mode FROM sa_user_permission_overrides WHERE user_id = ?',
            (user_id,),
        )
    for row in cursor.fetchall() or []:
        pk = row[0] if not hasattr(row, 'keys') else row['permission_key']
        mode = row[1] if not hasattr(row, 'keys') else row['mode']
        if pk in ALL_PERMISSION_KEYS and mode in ('grant', 'deny'):
            out[pk] = mode
    return out


def set_user_overrides(cursor, user_id: int, overrides: dict[str, str]) -> dict[str, str]:
    ensure_sa_permission_tables(cursor)
    clean: dict[str, str] = {}
    for k, v in (overrides or {}).items():
        if k in ALL_PERMISSION_KEYS and v in ('grant', 'deny'):
            clean[k] = v
    try:
        cursor.execute('DELETE FROM sa_user_permission_overrides WHERE user_id = %s', (user_id,))
    except Exception:
        cursor.execute('DELETE FROM sa_user_permission_overrides WHERE user_id = ?', (user_id,))
    for k, v in clean.items():
        try:
            cursor.execute(
                'INSERT INTO sa_user_permission_overrides (user_id, permission_key, mode, updated_at) '
                'VALUES (%s, %s, %s, %s)',
                (user_id, k, v, _utc_now()),
            )
        except Exception:
            cursor.execute(
                'INSERT INTO sa_user_permission_overrides (user_id, permission_key, mode, updated_at) '
                'VALUES (?, ?, ?, ?)',
                (user_id, k, v, _utc_now()),
            )
    return clean


def role_permissions_from_user(user: dict) -> set[str]:
    roles = user.get('roles') or []
    if isinstance(roles, str):
        try:
            roles = json.loads(roles)
        except Exception:
            roles = [roles]
    perms: set[str] = set()
    for role in roles:
        perms |= ROLE_PERMISSIONS.get(role, set())
    if 'admin' in roles:
        perms |= ROLE_PERMISSIONS.get('admin', set())
    return perms


def effective_permissions(user: dict, overrides: dict[str, str] | None = None) -> dict:
    base = role_permissions_from_user(user)
    ov = overrides or {}
    granted = set(base)
    for k, mode in ov.items():
        if mode == 'grant':
            granted.add(k)
        elif mode == 'deny':
            granted.discard(k)
    roles = user.get('roles') or []
    if isinstance(roles, str):
        try:
            roles = json.loads(roles)
        except Exception:
            roles = [roles]
    return {
        'roles': roles,
        'base_count': len(base),
        'effective': sorted(granted),
        'effective_count': len(granted),
        'overrides': ov,
        'power_level': _power_level(granted, roles),
    }


def _power_level(perms: set[str], roles: list) -> int:
    score = len(perms)
    if 'admin' in roles:
        score += 20
    if 'owner' in roles:
        score += 30
    if 'system.god_mode' in perms:
        score += 50
    return min(100, score)


def permission_matrix() -> list[dict]:
    rows = []
    for perm in PERMISSION_CATALOG:
        row = {'key': perm['key'], 'label': perm['label'], 'category': perm['category'], 'roles': {}}
        for role in MATRIX_ROLES:
            row['roles'][role] = perm['key'] in ROLE_PERMISSIONS.get(role, set())
        rows.append(row)
    return rows


def catalog_response() -> dict:
    return {
        'permissions': PERMISSION_CATALOG,
        'roles': [{'key': r, 'label': ROLE_LABELS.get(r, r)} for r in MATRIX_ROLES],
        'matrix': permission_matrix(),
        'god_flags': GOD_MODE_FLAGS,
        'assignable_roles': [
            'user', 'empresa', 'staff', 'helper', 'moderador', 'admin', 'administrador', 'owner',
        ],
    }


def log_imperial_action(cursor, action: str, *, target_type=None, target_id=None, detail='', ip=None):
    ensure_sa_permission_tables(cursor)
    try:
        cursor.execute(
            'INSERT INTO sa_imperial_audit (action, target_type, target_id, detail, ip_address, created_at) '
            'VALUES (%s, %s, %s, %s, %s, %s)',
            (action[:80], target_type, str(target_id) if target_id is not None else None,
             (detail or '')[:800], ip, _utc_now()),
        )
    except Exception:
        cursor.execute(
            'INSERT INTO sa_imperial_audit (action, target_type, target_id, detail, ip_address, created_at) '
            'VALUES (?, ?, ?, ?, ?, ?)',
            (action[:80], target_type, str(target_id) if target_id is not None else None,
             (detail or '')[:800], ip, _utc_now()),
        )


def create_impersonate_token(user_id: int, username: str) -> str:
    token = secrets.token_urlsafe(32)
    _IMPERSONATE_TOKENS[token] = {
        'user_id': user_id,
        'username': username,
        'expires': time.time() + 300,
    }
    # prune old
    now = time.time()
    for k in list(_IMPERSONATE_TOKENS.keys()):
        if _IMPERSONATE_TOKENS[k]['expires'] < now:
            del _IMPERSONATE_TOKENS[k]
    return token


def consume_impersonate_token(token: str) -> dict | None:
    data = _IMPERSONATE_TOKENS.pop(token, None)
    if not data or data['expires'] < time.time():
        return None
    return data
