"""
Discord HTTP Interactions — sin gateway, sin rate-limit de Cloudflare.
Discord envía POST a /discord/interactions; respondemos directamente.

Env vars:
  DISCORD_PUBLIC_KEY  — Developer Portal → General Information → Public Key
  DISCORD_TOKEN       — bot token (REST: DMs, registrar comandos)
  DISCORD_APP_ID      — Application ID (Developer Portal → General Information)
  DISCORD_GUILD       — Guild ID del servidor
  DISCORD_STAFF_ROLE  — ID del rol de staff
  DISCORD_WEBHOOK_URL — URL del webhook del canal de notificaciones
"""
import os
import threading
import secrets
import datetime

import requests

try:
    from nacl.signing import VerifyKey
    _NACL_OK = True
except ImportError:
    _NACL_OK = False
    print('[Discord] ⚠️ PyNaCl no instalado — verificación de firma desactivada')

PUBLIC_KEY   = os.environ.get('DISCORD_PUBLIC_KEY', '')
BOT_TOKEN    = os.environ.get('DISCORD_TOKEN', '')
APP_ID       = os.environ.get('DISCORD_APP_ID', '')
GUILD_ID     = os.environ.get('DISCORD_GUILD', '')
STAFF_ROLE   = os.environ.get('DISCORD_STAFF_ROLE', '')
WEBHOOK_URL  = os.environ.get('DISCORD_WEBHOOK_URL', '')

API = 'https://discord.com/api/v10'


def _h():
    return {'Authorization': f'Bot {BOT_TOKEN}', 'Content-Type': 'application/json'}


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


# ── Slash command registration ─────────────────────────────────────────────

_COMMANDS = [
    {
        'name': 'scan',
        'description': 'Muestra el último scan de un jugador',
        'options': [{'name': 'jugador', 'description': 'Nombre de máquina o username', 'type': 3, 'required': True}],
    },
    {
        'name': 'stats',
        'description': 'Estadísticas globales del panel',
        'options': [],
    },
    {
        'name': 'veredicto',
        'description': 'Cambia el veredicto de un scan (requiere rol de staff)',
        'options': [
            {'name': 'scan_id',   'description': 'ID del scan',            'type': 4, 'required': True},
            {'name': 'veredicto', 'description': 'hack | clean | pending', 'type': 3, 'required': True},
            {'name': 'razon',     'description': 'Razón del veredicto',    'type': 3, 'required': True},
        ],
    },
    {
        'name': 'ss',
        'description': 'Screen Share — crea token y lo envía por DM (staff)',
        'options': [{'name': 'jugador', 'description': '@mention del jugador', 'type': 6, 'required': True}],
    },
]


def register_commands():
    """Registra slash commands via REST. Se llama una vez al arrancar."""
    if not BOT_TOKEN or not APP_ID:
        print('[Discord] ⚠️ DISCORD_TOKEN o DISCORD_APP_ID no configurados — comandos no registrados')
        return
    url = (f'{API}/applications/{APP_ID}/guilds/{GUILD_ID}/commands'
           if GUILD_ID else f'{API}/applications/{APP_ID}/commands')
    try:
        r = requests.put(url, headers=_h(), json=_COMMANDS, timeout=15)
        if r.ok:
            print(f'[Discord] ✅ {len(_COMMANDS)} slash commands registrados')
        else:
            print(f'[Discord] ⚠️ Error registrando comandos: {r.status_code} {r.text[:200]}')
    except Exception as e:
        print(f'[Discord] Error registrando comandos: {e}')


# ── Webhook notifications ──────────────────────────────────────────────────

def send_webhook(payload: dict):
    """Envía una notificación por webhook (fire-and-forget en background thread)."""
    if not WEBHOOK_URL:
        return
    def _send():
        try:
            requests.post(WEBHOOK_URL, json=payload, timeout=10)
        except Exception as e:
            print(f'[Discord] Error webhook: {e}')
    threading.Thread(target=_send, daemon=True).start()


def notify_new_scan(scan_id, machine_name, username, risk_score=0, issues_found=0):
    bar   = '🟥' if risk_score >= 70 else '🟧' if risk_score >= 30 else '🟩'
    color = 0xE74C3C if risk_score >= 70 else 0xF39C12 if risk_score >= 30 else 0x2ECC71
    send_webhook({'embeds': [{'title': f'🔔 Nuevo scan — #{scan_id}', 'color': color, 'description':
        f'**Máquina:** {machine_name}\n**Usuario:** {username}\n'
        f'{bar} **Risk score:** {risk_score}/100\n**Hallazgos:** {issues_found}'}]})


def notify_verdict_change(scan_id, machine_name, username, verdict, reason, changed_by):
    color = {'hack': 0xE74C3C, 'clean': 0x2ECC71}.get(verdict, 0x64748B)
    send_webhook({'embeds': [{'title': f'⚖️ Veredicto — Scan #{scan_id}', 'color': color, 'description':
        f'**Máquina:** {machine_name}\n**Usuario:** {username}\n'
        f'**Veredicto:** {verdict.upper()}\n**Razón:** {reason}\n**Por:** {changed_by}'}]})


# ── Internal helpers ───────────────────────────────────────────────────────

def _has_staff(member: dict) -> bool:
    if not STAFF_ROLE:
        return True
    return STAFF_ROLE in member.get('roles', [])


def _opt(options: list, name: str):
    for o in options:
        if o['name'] == name:
            return o.get('value')
    return None


def _followup(app_id: str, token: str, payload: dict):
    try:
        requests.post(f'{API}/webhooks/{app_id}/{token}', json=payload, timeout=10)
    except Exception as e:
        print(f'[Discord] Error followup: {e}')


# ── Command handlers ───────────────────────────────────────────────────────

def _cmd_stats():
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
        return {'type': 4, 'data': {'embeds': [{'title': '📊 ASPERS — Estadísticas', 'color': 0x5865F2, 'fields': [
            {'name': 'Total scans',   'value': str(total),            'inline': True},
            {'name': 'Hoy',           'value': str(today),            'inline': True},
            {'name': 'Con hacks 🔴',  'value': str(hacks),            'inline': True},
            {'name': 'Limpios 🟢',    'value': str(clean),            'inline': True},
            {'name': 'Pendientes 🟡', 'value': str(total-hacks-clean), 'inline': True},
        ]}]}}
    except Exception as e:
        return {'type': 4, 'data': {'content': f'⚠️ Error: {e}', 'flags': 64}}


def _cmd_scan(options: list):
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
            return {'type': 4, 'data': {'content': f'❌ No se encontró ningún scan para **{jugador}**.', 'flags': 64}}

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
        return {'type': 4, 'data': {'embeds': [{'title': f'Scan #{scan_id} — {machine_name}', 'color': color, 'fields': [
            {'name': 'Usuario',    'value': username,              'inline': True},
            {'name': 'Estado',     'value': status,                'inline': True},
            {'name': 'Veredicto',  'value': verdict.upper(),       'inline': True},
            {'name': 'Risk Score', 'value': f'{bar} {risk_score}/100', 'inline': True},
            {'name': 'Hallazgos',  'value': str(issues_found),    'inline': True},
            {'name': 'Fecha',      'value': started_at,           'inline': True},
        ], 'footer': {'text': 'ASPERS'}}]}}
    except Exception as e:
        return {'type': 4, 'data': {'content': f'⚠️ Error: {e}', 'flags': 64}}


def _cmd_veredicto_bg(options, member, app_id, token):
    scan_id  = _opt(options, 'scan_id')
    verdict  = (_opt(options, 'veredicto') or '').strip().lower()
    razon    = _opt(options, 'razon') or ''
    staff_name = member.get('user', {}).get('username', 'staff')
    changed_by = f'Discord:{staff_name}'
    try:
        from app import get_api_db_cursor, _PH, _insert_id, _row_get
        with get_api_db_cursor() as cur:
            cur.execute(
                f'UPDATE scans SET verdict={_PH}, verdict_reason={_PH}, verdict_by={_PH}, verdict_at=NOW() WHERE id={_PH}',
                (verdict, razon, changed_by, scan_id)
            )
            _insert_id(cur,
                f'INSERT INTO verdict_history (scan_id, verdict, reason, changed_by) VALUES ({_PH},{_PH},{_PH},{_PH})',
                (scan_id, verdict, razon, changed_by))
            cur.execute(f'SELECT machine_name, minecraft_username FROM scans WHERE id={_PH}', (scan_id,))
            srow = cur.fetchone()
        machine = (_row_get(srow, 0, 'machine_name') or 'N/A') if srow else 'N/A'
        uname   = (_row_get(srow, 1, 'minecraft_username') or 'N/A') if srow else 'N/A'
        _followup(app_id, token, {'content': f'✅ Scan #{scan_id} → **{verdict.upper()}**', 'flags': 64})
        notify_verdict_change(scan_id, machine, uname, verdict, razon, staff_name)
    except Exception as e:
        _followup(app_id, token, {'content': f'⚠️ Error: {e}', 'flags': 64})


def _cmd_ss_bg(options, resolved, member, app_id, token):
    jugador_id = str(_opt(options, 'jugador') or '')
    users      = resolved.get('users', {})
    target     = users.get(jugador_id, {})
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
        dm_text = (
            f'🎮 **Un moderador ha iniciado un Screen Share contigo.**\n\n'
            f'Ejecuta el scanner y cuando te pida el token, usa este:\n```\n{scan_token}\n```'
            f'\n🔗 Descarga: {panel_url}/download\n⏰ El token expira en **30 minutos**.'
        )
        dm_ok = False
        try:
            r = requests.post(f'{API}/users/@me/channels', headers=_h(), json={'recipient_id': jugador_id}, timeout=10)
            if r.ok:
                r2 = requests.post(f'{API}/channels/{r.json()["id"]}/messages', headers=_h(), json={'content': dm_text}, timeout=10)
                dm_ok = r2.ok
        except Exception:
            pass

        if dm_ok:
            reply = f'✅ Token creado y enviado por DM a **{target_name}**.'
        else:
            reply = f'✅ Token creado.\n⚠️ No se pudo enviar DM. Comparte manualmente:\n```\n{scan_token}\n```'
        _followup(app_id, token, {'content': reply, 'flags': 64})

        send_webhook({'embeds': [{'title': '🔍 SS Iniciado', 'color': 0x3498DB, 'description':
            f'**Staff:** {staff_name}\n**Jugador:** {target_name}\n'
            f'**Token expira:** <t:{int(expires_at.timestamp())}:R>'}]})
    except Exception as e:
        _followup(app_id, token, {'content': f'⚠️ Error: {e}', 'flags': 64})


# ── Main dispatcher ────────────────────────────────────────────────────────

def handle_interaction(data: dict) -> dict:
    t = data.get('type')

    if t == 1:  # PING
        return {'type': 1}

    if t == 2:  # APPLICATION_COMMAND
        name     = data['data']['name']
        options  = data['data'].get('options', [])
        resolved = data['data'].get('resolved', {})
        member   = data.get('member', {})
        app_id   = data.get('application_id', APP_ID)
        token    = data.get('token', '')

        if name == 'stats':
            return _cmd_stats()

        if name == 'scan':
            return _cmd_scan(options)

        if name == 'veredicto':
            if not _has_staff(member):
                return {'type': 4, 'data': {'content': '❌ No tienes el rol de staff.', 'flags': 64}}
            v = (_opt(options, 'veredicto') or '').strip().lower()
            if v not in ('hack', 'clean', 'pending'):
                return {'type': 4, 'data': {'content': '❌ Veredicto debe ser `hack`, `clean` o `pending`.', 'flags': 64}}
            if not _opt(options, 'razon'):
                return {'type': 4, 'data': {'content': '❌ La razón es obligatoria.', 'flags': 64}}
            threading.Thread(target=_cmd_veredicto_bg, args=(options, member, app_id, token), daemon=True).start()
            return {'type': 5, 'data': {'flags': 64}}

        if name == 'ss':
            if not _has_staff(member):
                return {'type': 4, 'data': {'content': '❌ No tienes el rol de staff.', 'flags': 64}}
            threading.Thread(target=_cmd_ss_bg, args=(options, resolved, member, app_id, token), daemon=True).start()
            return {'type': 5, 'data': {'flags': 64}}

    return {'type': 4, 'data': {'content': '❓ Comando desconocido.', 'flags': 64}}
