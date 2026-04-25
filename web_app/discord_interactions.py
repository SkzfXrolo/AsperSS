"""
Discord HTTP Interactions — sin gateway, sin llamadas salientes a Discord.
Discord envía POST a /discord/interactions; respondemos con la respuesta completa.

Env vars:
  DISCORD_PUBLIC_KEY  — Developer Portal → General Information → Public Key
  DISCORD_GUILD       — Guild ID del servidor
  DISCORD_STAFF_ROLE  — ID del rol de staff
"""
import os
import secrets
import datetime

PUBLIC_KEY  = os.environ.get('DISCORD_PUBLIC_KEY', '')
GUILD_ID    = os.environ.get('DISCORD_GUILD', '')
STAFF_ROLE  = os.environ.get('DISCORD_STAFF_ROLE', '')

try:
    from nacl.signing import VerifyKey
    _NACL_OK = True
except ImportError:
    _NACL_OK = False
    print('[Discord] ⚠️ PyNaCl no instalado — verificación de firma desactivada')


# ── Signature verification ─────────────────────────────────────────────────

def verify_signature(signature: str, timestamp: str, body: str) -> bool:
    if not _NACL_OK or not PUBLIC_KEY:
        return False
    try:
        VerifyKey(bytes.fromhex(PUBLIC_KEY)).verify(
            f'{timestamp}{body}'.encode(), bytes.fromhex(signature)
        )
        return True
    except Exception:
        return False


# ── Helpers ────────────────────────────────────────────────────────────────

def _msg(content: str, ephemeral: bool = True) -> dict:
    return {'type': 4, 'data': {'content': content, 'flags': 64 if ephemeral else 0}}


def _embed(embed: dict, ephemeral: bool = False) -> dict:
    return {'type': 4, 'data': {'embeds': [embed], 'flags': 64 if ephemeral else 0}}


def _has_staff(member: dict) -> bool:
    if not STAFF_ROLE:
        return True
    return STAFF_ROLE in member.get('roles', [])


def _opt(options: list, name: str):
    for o in options:
        if o['name'] == name:
            return o.get('value')
    return None


# ── Command handlers ───────────────────────────────────────────────────────

def _cmd_stats() -> dict:
    try:
        from app import get_api_db_cursor
        with get_api_db_cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM scans")
            total = (cur.fetchone() or (0,))[0]
            cur.execute("SELECT COUNT(*) FROM scans WHERE verdict='hack'")
            hacks = (cur.fetchone() or (0,))[0]
            cur.execute("SELECT COUNT(*) FROM scans WHERE verdict='clean'")
            clean = (cur.fetchone() or (0,))[0]
            cur.execute("SELECT COUNT(*) FROM scans WHERE started_at >= NOW() - INTERVAL '24 hours'")
            today = (cur.fetchone() or (0,))[0]
        return _embed({'title': '📊 ASPERS — Estadísticas', 'color': 0x5865F2, 'fields': [
            {'name': 'Total scans',   'value': str(total),             'inline': True},
            {'name': 'Hoy',           'value': str(today),             'inline': True},
            {'name': 'Con hacks 🔴',  'value': str(hacks),             'inline': True},
            {'name': 'Limpios 🟢',    'value': str(clean),             'inline': True},
            {'name': 'Pendientes 🟡', 'value': str(total-hacks-clean), 'inline': True},
        ]})
    except Exception as e:
        return _msg(f'⚠️ Error: {e}')


def _cmd_scan(options: list) -> dict:
    jugador = _opt(options, 'jugador') or ''
    try:
        from app import get_api_db_cursor, _PH, _row_get
        with get_api_db_cursor() as cur:
            cur.execute(
                f'''SELECT id, machine_name, minecraft_username, status, verdict,
                           risk_score, issues_found, started_at
                    FROM scans
                    WHERE LOWER(machine_name) LIKE {_PH} OR LOWER(minecraft_username) LIKE {_PH}
                    ORDER BY id DESC LIMIT 1''',
                (f'%{jugador.lower()}%', f'%{jugador.lower()}%')
            )
            row = cur.fetchone()
        if not row:
            return _msg(f'❌ No se encontró ningún scan para **{jugador}**.')
        scan_id      = _row_get(row, 0, 'id')
        machine_name = _row_get(row, 1, 'machine_name') or 'N/A'
        username     = _row_get(row, 2, 'minecraft_username') or 'N/A'
        status       = _row_get(row, 3, 'status') or '?'
        verdict      = _row_get(row, 4, 'verdict') or 'pendiente'
        risk_score   = int(_row_get(row, 5, 'risk_score') or 0)
        issues_found = int(_row_get(row, 6, 'issues_found') or 0)
        started_at   = str(_row_get(row, 7, 'started_at') or '')[:19]
        color = 0xE74C3C if verdict == 'hack' else 0x2ECC71 if verdict == 'clean' else 0xF39C12
        bar   = '🟥' if risk_score >= 70 else '🟧' if risk_score >= 30 else '🟩'
        return _embed({'title': f'Scan #{scan_id} — {machine_name}', 'color': color,
            'fields': [
                {'name': 'Usuario',    'value': username,              'inline': True},
                {'name': 'Estado',     'value': status,                'inline': True},
                {'name': 'Veredicto',  'value': verdict.upper(),       'inline': True},
                {'name': 'Risk Score', 'value': f'{bar} {risk_score}/100', 'inline': True},
                {'name': 'Hallazgos',  'value': str(issues_found),    'inline': True},
                {'name': 'Fecha',      'value': started_at,           'inline': True},
            ], 'footer': {'text': 'ASPERS'}})
    except Exception as e:
        return _msg(f'⚠️ Error: {e}')


def _cmd_veredicto(options: list, member: dict) -> dict:
    if not _has_staff(member):
        return _msg('❌ No tienes el rol de staff.')
    scan_id = _opt(options, 'scan_id')
    verdict = (_opt(options, 'veredicto') or '').strip().lower()
    razon   = _opt(options, 'razon') or ''
    if verdict not in ('hack', 'clean', 'pending'):
        return _msg('❌ Veredicto debe ser `hack`, `clean` o `pending`.')
    if not razon:
        return _msg('❌ La razón es obligatoria.')
    try:
        from app import get_api_db_cursor, _PH, _insert_id
        staff_name = member.get('user', {}).get('username', 'staff')
        changed_by = f'Discord:{staff_name}'
        with get_api_db_cursor() as cur:
            cur.execute(
                f'UPDATE scans SET verdict={_PH}, verdict_reason={_PH}, verdict_by={_PH}, verdict_at=NOW() WHERE id={_PH}',
                (verdict, razon, changed_by, scan_id)
            )
            _insert_id(cur,
                f'INSERT INTO verdict_history (scan_id, verdict, reason, changed_by) VALUES ({_PH},{_PH},{_PH},{_PH})',
                (scan_id, verdict, razon, changed_by))
        icon = '🔴' if verdict == 'hack' else '🟢' if verdict == 'clean' else '🟡'
        return _msg(f'{icon} Scan **#{scan_id}** → **{verdict.upper()}**\nRazón: {razon}', ephemeral=True)
    except Exception as e:
        return _msg(f'⚠️ Error: {e}')


def _cmd_ss(options: list, resolved: dict, member: dict) -> dict:
    if not _has_staff(member):
        return _msg('❌ No tienes el rol de staff.')
    jugador_id  = str(_opt(options, 'jugador') or '')
    users       = resolved.get('users', {})
    target      = users.get(jugador_id, {})
    target_name = target.get('global_name') or target.get('username', jugador_id)
    staff_name  = member.get('user', {}).get('username', 'staff')
    try:
        from app import get_api_db_cursor, _PH, _insert_id
        scan_token = secrets.token_urlsafe(32)
        expires_at = datetime.datetime.utcnow() + datetime.timedelta(minutes=30)
        with get_api_db_cursor() as cur:
            _insert_id(cur,
                f'INSERT INTO scan_tokens (token, expires_at, max_uses, created_by, description) VALUES ({_PH},{_PH},{_PH},{_PH},{_PH})',
                (scan_token, expires_at, 1, f'Discord:{staff_name}', f'SS a {target_name} vía Discord'))
        panel_url = os.environ.get('RENDER_EXTERNAL_URL', 'https://asperss.onrender.com').rstrip('/')
        return _msg(
            f'✅ Token SS creado para **{target_name}**.\n'
            f'Envíale este token manualmente:\n```\n{scan_token}\n```'
            f'\n🔗 Descarga scanner: {panel_url}/download\n'
            f'⏰ Expira en 30 minutos.',
            ephemeral=True
        )
    except Exception as e:
        return _msg(f'⚠️ Error: {e}')


# ── Main dispatcher ────────────────────────────────────────────────────────

def handle_interaction(data: dict) -> dict:
    t = data.get('type')

    if t == 1:  # PING de verificación de Discord
        return {'type': 1}

    if t == 2:  # APPLICATION_COMMAND
        name     = data['data']['name']
        options  = data['data'].get('options', [])
        resolved = data['data'].get('resolved', {})
        member   = data.get('member', {})

        if name == 'stats':
            return _cmd_stats()
        if name == 'scan':
            return _cmd_scan(options)
        if name == 'veredicto':
            return _cmd_veredicto(options, member)
        if name == 'ss':
            return _cmd_ss(options, resolved, member)

    return _msg('❓ Comando desconocido.')
