"""
Bot de Discord para Argus Projects.
Corre en un thread dentro de app.py si DISCORD_TOKEN está configurado.

Variables de entorno requeridas:
  DISCORD_TOKEN      — token del bot
  DISCORD_GUILD      — ID del servidor (guild) donde se registran los slash commands
  DISCORD_CHANNEL    — ID del canal de notificaciones (nuevo scan, veredictos)
  DISCORD_STAFF_ROLE — Nombre o ID del rol de staff (restringe /ss y /veredicto)

Requiere: pip install discord.py>=2.3
"""
import os
import json
import threading
import asyncio
import logging
import secrets
import datetime

log = logging.getLogger('discord_bot')

_DATABASE_URL = os.environ.get('DATABASE_URL', '').replace('postgres://', 'postgresql://', 1)

try:
    import discord
    from discord import app_commands
    DISCORD_AVAILABLE = True
except ImportError:
    DISCORD_AVAILABLE = False
    print('[Discord] ⚠️ discord.py no está instalado. Bot desactivado.')

DISCORD_TOKEN      = os.environ.get('DISCORD_TOKEN', '')
DISCORD_GUILD      = os.environ.get('DISCORD_GUILD', '')
DISCORD_CHANNEL    = os.environ.get('DISCORD_CHANNEL', '')
DISCORD_STAFF_ROLE = os.environ.get('DISCORD_STAFF_ROLE', '')  # nombre o ID del rol de staff

_bot_instance = None
_bot_loop     = None
_bot_thread   = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _has_staff_role(member: 'discord.Member') -> bool:
    """Devuelve True si el miembro tiene el rol de staff configurado."""
    if not DISCORD_STAFF_ROLE:
        return True  # sin restricción configurada, todos pueden
    for role in member.roles:
        if role.name == DISCORD_STAFF_ROLE or str(role.id) == DISCORD_STAFF_ROLE:
            return True
    return False


async def _send_to_channel(bot_instance, channel_id: int, embed: 'discord.Embed'):
    """Envía un embed al canal de notificaciones."""
    try:
        channel = bot_instance.get_channel(channel_id)
        if channel is None:
            channel = await bot_instance.fetch_channel(channel_id)
        await channel.send(embed=embed)
    except Exception as e:
        print(f'[Discord] ⚠️ Error enviando al canal {channel_id}: {e}')


# ── Bot factory ───────────────────────────────────────────────────────────────

def _make_bot():
    if not DISCORD_AVAILABLE:
        return None

    intents          = discord.Intents.default()
    intents.guilds   = True
    intents.members  = True   # necesario para DMs y lookups de miembros
    client = discord.Client(intents=intents)
    tree   = app_commands.CommandTree(client)

    guild_obj = discord.Object(id=int(DISCORD_GUILD)) if DISCORD_GUILD.isdigit() else None

    # ── /scan ─────────────────────────────────────────────────────────────────
    @tree.command(
        name='scan',
        description='Muestra el último scan de un jugador',
        guild=guild_obj,
    )
    @app_commands.describe(jugador='Nombre de máquina o username del jugador')
    async def cmd_scan(interaction: discord.Interaction, jugador: str):
        await interaction.response.defer(ephemeral=False)
        try:
            from app import get_api_db_cursor, _PH, _row_get
            with get_api_db_cursor() as cursor:
                cursor.execute(
                    f'''SELECT id, machine_name, minecraft_username, status, verdict,
                               risk_score, issues_found, started_at
                        FROM scans
                        WHERE LOWER(machine_name) LIKE {_PH}
                           OR LOWER(minecraft_username) LIKE {_PH}
                        ORDER BY id DESC LIMIT 1''',
                    (f'%{jugador.lower()}%', f'%{jugador.lower()}%')
                )
                row = cursor.fetchone()
            if not row:
                await interaction.followup.send(f'❌ No se encontró ningún scan para **{jugador}**.')
                return
            scan_id      = _row_get(row, 0, 'id')
            machine_name = _row_get(row, 1, 'machine_name') or 'N/A'
            username     = _row_get(row, 2, 'minecraft_username') or 'N/A'
            status       = _row_get(row, 3, 'status') or '?'
            verdict      = _row_get(row, 4, 'verdict') or 'pendiente'
            risk_score   = int(_row_get(row, 5, 'risk_score') or 0)
            issues_found = int(_row_get(row, 6, 'issues_found') or 0)
            started_at   = str(_row_get(row, 7, 'started_at') or '')[:19]
            color = (
                discord.Color.red()    if verdict == 'hack'   else
                discord.Color.green()  if verdict == 'clean'  else
                discord.Color.yellow()
            )
            risk_bar = '🟥' if risk_score >= 70 else '🟧' if risk_score >= 30 else '🟩'
            embed = discord.Embed(
                title=f'Scan #{scan_id} — {machine_name}',
                color=color,
            )
            embed.add_field(name='Usuario',     value=username,      inline=True)
            embed.add_field(name='Estado',      value=status,        inline=True)
            embed.add_field(name='Veredicto',   value=verdict.upper(), inline=True)
            embed.add_field(name='Risk Score',  value=f'{risk_bar} {risk_score}/100', inline=True)
            embed.add_field(name='Hallazgos',   value=str(issues_found), inline=True)
            embed.add_field(name='Fecha',       value=started_at,    inline=True)
            embed.set_footer(text='Argus Projects')
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(f'⚠️ Error: {e}')

    # ── /reputacion ─────────────────────────────────────────────────────────────
    @tree.command(
        name='reputacion',
        description='Reputación anti-cheat de un jugador en la red Argus',
        guild=guild_obj,
    )
    @app_commands.describe(jugador='Nombre de Minecraft del jugador')
    async def cmd_reputacion(interaction: discord.Interaction, jugador: str):
        await interaction.response.defer(ephemeral=False)
        try:
            from app import get_api_db_cursor, _PH, _row_get
            with get_api_db_cursor() as cursor:
                cursor.execute(
                    f'''SELECT verdict, risk_score, started_at FROM scans
                        WHERE LOWER(minecraft_username) = LOWER({_PH}) AND status = {_PH}
                        ORDER BY id DESC LIMIT 100''',
                    (jugador, 'completed')
                )
                rows = cursor.fetchall() or []
            total = len(rows)
            if not total:
                await interaction.followup.send(f'🛰️ Sin registros para **{jugador}** en la red Argus.')
                return
            verdicts = [(_row_get(r, 0, 'verdict') or '').lower() for r in rows]
            risks    = [int(_row_get(r, 1, 'risk_score') or 0) for r in rows]
            last_seen = str(_row_get(rows[0], 2, 'started_at') or '')[:10]
            hacks = verdicts.count('hack')
            clean = verdicts.count('clean')
            hack_rate = hacks / total
            avg_risk = round(sum(risks) / total, 1)
            if hack_rate >= 0.5:
                rep, color = 'ALTO RIESGO 🔴', discord.Color.red()
            elif hack_rate >= 0.2:
                rep, color = 'SOSPECHOSO 🟠', discord.Color.orange()
            else:
                rep, color = 'LIMPIO 🟢', discord.Color.green()
            panel_url = os.environ.get('RENDER_EXTERNAL_URL', 'https://asperss.onrender.com').rstrip('/')
            from urllib.parse import quote as _q
            embed = discord.Embed(
                title=f'🛡️ Reputación — {jugador}',
                description=f'**{rep}**',
                color=color,
                url=f'{panel_url}/reputacion?u={_q(jugador)}',
            )
            embed.add_field(name='Scans',       value=str(total),                 inline=True)
            embed.add_field(name='Hacks 🔴',    value=str(hacks),                 inline=True)
            embed.add_field(name='Limpios 🟢',  value=str(clean),                 inline=True)
            embed.add_field(name='Hack rate',   value=f'{round(hack_rate*100)}%', inline=True)
            embed.add_field(name='Risk prom.',  value=f'{avg_risk}/100',          inline=True)
            embed.add_field(name='Último scan', value=last_seen or 'N/A',         inline=True)
            embed.set_footer(text='Argus Vault · datos agregados de la red')
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(f'⚠️ Error: {e}')

    # ── /buscados ────────────────────────────────────────────────────────────────
    @tree.command(
        name='buscados',
        description='Top de jugadores con más hacks confirmados en la red Argus',
        guild=guild_obj,
    )
    async def cmd_buscados(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)
        try:
            from app import get_api_db_cursor, _PH, _row_get
            with get_api_db_cursor() as cursor:
                try:
                    cursor.execute(
                        "SELECT minecraft_username,"
                        " SUM(CASE WHEN LOWER(verdict)='hack' THEN 1 ELSE 0 END) AS hacks,"
                        " COUNT(*) AS total"
                        " FROM scans"
                        f" WHERE status={_PH} AND minecraft_username IS NOT NULL AND minecraft_username <> ''"
                        " GROUP BY minecraft_username"
                        " ORDER BY hacks DESC, total DESC LIMIT 30",
                        ('completed',)
                    )
                    rows = cursor.fetchall() or []
                except Exception:
                    cursor.execute(
                        "SELECT minecraft_username,"
                        " SUM(CASE WHEN LOWER(verdict)='hack' THEN 1 ELSE 0 END) AS hacks,"
                        " COUNT(*) AS total"
                        " FROM scans"
                        " WHERE minecraft_username IS NOT NULL AND minecraft_username <> ''"
                        " GROUP BY minecraft_username"
                        " ORDER BY hacks DESC, total DESC LIMIT 30"
                    )
                    rows = cursor.fetchall() or []
            players = []
            for r in rows:
                uname = _row_get(r, 0, 'minecraft_username') or ''
                hacks = int(_row_get(r, 1, 'hacks') or 0)
                total = int(_row_get(r, 2, 'total') or 0)
                if not uname or hacks < 1:
                    continue
                players.append((uname, hacks, total))
                if len(players) >= 10:
                    break
            if not players:
                await interaction.followup.send('🛰️ Todavía no hay hacks confirmados en la red.')
                return
            medals = ['🥇', '🥈', '🥉']
            lines = []
            for i, (u, h, t) in enumerate(players):
                rank = medals[i] if i < 3 else f'`#{i+1}`'
                pct = round(h / t * 100) if t else 0
                lines.append(f'{rank} **{u}** — {h} hacks · {t} scans · {pct}%')
            panel_url = os.environ.get('RENDER_EXTERNAL_URL', 'https://asperss.onrender.com').rstrip('/')
            embed = discord.Embed(
                title='🎯 Más buscados — red Argus',
                description='\n'.join(lines),
                color=discord.Color.red(),
                url=f'{panel_url}/reputacion',
            )
            embed.set_footer(text='Argus Vault · top hacks confirmados')
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(f'⚠️ Error: {e}')

    # ── /veredicto ────────────────────────────────────────────────────────────
    @tree.command(
        name='veredicto',
        description='Cambia el veredicto de un scan (requiere rol de staff)',
        guild=guild_obj,
    )
    @app_commands.describe(
        scan_id='ID numérico del scan',
        veredicto='hack | clean | pending',
        razon='Razón del veredicto (obligatoria)',
    )
    async def cmd_veredicto(interaction: discord.Interaction, scan_id: int, veredicto: str, razon: str = ''):
        if not _has_staff_role(interaction.user):
            await interaction.response.send_message(
                '❌ No tienes el rol de staff para usar este comando.', ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        veredicto = veredicto.strip().lower()
        if veredicto not in ('hack', 'clean', 'pending'):
            await interaction.followup.send('❌ Veredicto debe ser `hack`, `clean` o `pending`.')
            return
        if not razon:
            await interaction.followup.send('❌ La razón es obligatoria.')
            return
        try:
            from app import get_api_db_cursor, _PH, _insert_id, _row_get
            changed_by = f'Discord:{interaction.user.name}'
            with get_api_db_cursor() as cursor:
                cursor.execute(
                    f'''UPDATE scans SET verdict = {_PH}, verdict_reason = {_PH},
                        verdict_by = {_PH}, verdict_at = NOW()
                        WHERE id = {_PH}''',
                    (veredicto, razon, changed_by, scan_id)
                )
                _insert_id(
                    cursor,
                    f'INSERT INTO verdict_history (scan_id, verdict, reason, changed_by)'
                    f' VALUES ({_PH},{_PH},{_PH},{_PH})',
                    (scan_id, veredicto, razon, changed_by)
                )
                # Fetch scan info for notification
                cursor.execute(
                    f'SELECT machine_name, minecraft_username FROM scans WHERE id = {_PH}',
                    (scan_id,)
                )
                srow = cursor.fetchone()
            machine  = _row_get(srow, 0, 'machine_name') or 'N/A' if srow else 'N/A'
            username = _row_get(srow, 1, 'minecraft_username') or 'N/A' if srow else 'N/A'
            await interaction.followup.send(f'✅ Scan #{scan_id} → **{veredicto.upper()}**')
            # Notify channel
            if DISCORD_CHANNEL and DISCORD_CHANNEL.isdigit():
                color = (discord.Color.red()   if veredicto == 'hack'  else
                         discord.Color.green()  if veredicto == 'clean' else
                         discord.Color.greyple())
                embed = discord.Embed(
                    title=f'⚖️ Veredicto — Scan #{scan_id}',
                    color=color,
                    description=(
                        f'**Máquina:** {machine}\n'
                        f'**Usuario:** {username}\n'
                        f'**Veredicto:** {veredicto.upper()}\n'
                        f'**Razón:** {razon}\n'
                        f'**Por:** {interaction.user.display_name}'
                    ),
                )
                asyncio.ensure_future(
                    _send_to_channel(client, int(DISCORD_CHANNEL), embed)
                )
        except Exception as e:
            await interaction.followup.send(f'⚠️ Error: {e}')

    # ── /ss ───────────────────────────────────────────────────────────────────
    @tree.command(
        name='ss',
        description='Inicia un Screen Share — crea token y lo envía por DM al jugador',
        guild=guild_obj,
    )
    @app_commands.describe(jugador='@mention del jugador al que hacerle SS')
    async def cmd_ss(interaction: discord.Interaction, jugador: discord.Member):
        if not _has_staff_role(interaction.user):
            await interaction.response.send_message(
                '❌ No tienes el rol de staff para usar este comando.', ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        try:
            from app import get_api_db_cursor, _PH, _insert_id

            scan_token = secrets.token_urlsafe(32)
            expires_at = datetime.datetime.utcnow() + datetime.timedelta(minutes=30)
            created_by = f'Discord:{interaction.user.name}'

            with get_api_db_cursor() as cursor:
                _insert_id(
                    cursor,
                    f'INSERT INTO scan_tokens (token, expires_at, max_uses, created_by, description)'
                    f' VALUES ({_PH},{_PH},{_PH},{_PH},{_PH})',
                    (scan_token, expires_at, 1, created_by, f'SS a {jugador.display_name} vía Discord')
                )

            panel_url    = os.environ.get('RENDER_EXTERNAL_URL', '').rstrip('/')
            download_msg = f'\n🔗 Descarga: {panel_url}/download' if panel_url else ''

            dm_text = (
                f'🎮 **Un moderador ha iniciado un Screen Share contigo.**\n\n'
                f'Ejecuta el scanner y cuando te pida el token, usa este:\n'
                f'```\n{scan_token}\n```'
                f'{download_msg}\n'
                f'⏰ El token expira en **30 minutos**. Ejecútalo cuanto antes.'
            )

            dm_ok = False
            try:
                await jugador.send(dm_text)
                dm_ok = True
            except discord.Forbidden:
                pass

            if dm_ok:
                reply = f'✅ Token creado y enviado por DM a **{jugador.display_name}**.'
            else:
                reply = (
                    f'✅ Token creado para **{jugador.display_name}**.\n'
                    f'⚠️ No se pudo enviar DM (DMs cerrados). Mándale el token manualmente:\n'
                    f'```\n{scan_token}\n```'
                )
            await interaction.followup.send(reply, ephemeral=True)

            # Notify staff channel
            if DISCORD_CHANNEL and DISCORD_CHANNEL.isdigit():
                embed = discord.Embed(
                    title='🔍 SS Iniciado',
                    color=discord.Color.blue(),
                    description=(
                        f'**Staff:** {interaction.user.display_name}\n'
                        f'**Jugador:** {jugador.display_name}\n'
                        f'**Token expira:** <t:{int(expires_at.timestamp())}:R>'
                    ),
                )
                asyncio.ensure_future(
                    _send_to_channel(client, int(DISCORD_CHANNEL), embed)
                )
        except Exception as e:
            log.exception('[Discord] Error en /ss')
            await interaction.followup.send(f'⚠️ Error creando token: {e}', ephemeral=True)

    # ── /stats ────────────────────────────────────────────────────────────────
    @tree.command(
        name='stats',
        description='Muestra estadísticas globales del panel',
        guild=guild_obj,
    )
    async def cmd_stats(interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            from app import get_api_db_cursor
            with get_api_db_cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM scans")
                total = (cursor.fetchone() or (0,))[0]
                cursor.execute("SELECT COUNT(*) FROM scans WHERE verdict = 'hack'")
                hacks = (cursor.fetchone() or (0,))[0]
                cursor.execute("SELECT COUNT(*) FROM scans WHERE verdict = 'clean'")
                clean = (cursor.fetchone() or (0,))[0]
                cursor.execute("SELECT COUNT(*) FROM scans WHERE started_at >= NOW() - INTERVAL '24 hours'")
                today = (cursor.fetchone() or (0,))[0]
            embed = discord.Embed(
                title='📊 Argus Projects — Estadísticas',
                color=discord.Color.blurple(),
            )
            embed.add_field(name='Total scans',   value=str(total),           inline=True)
            embed.add_field(name='Hoy',           value=str(today),           inline=True)
            embed.add_field(name='Con hacks 🔴',  value=str(hacks),           inline=True)
            embed.add_field(name='Limpios 🟢',    value=str(clean),           inline=True)
            embed.add_field(name='Pendientes 🟡', value=str(total-hacks-clean), inline=True)
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(f'⚠️ Error: {e}')

    # ── on_ready ──────────────────────────────────────────────────────────────
    @client.event
    async def on_ready():
        print(f'[Discord] ✅ Bot conectado como {client.user} (ID: {client.user.id})')
        if guild_obj:
            await tree.sync(guild=guild_obj)
            print('[Discord] ✅ Slash commands sincronizados.')
        else:
            print('[Discord] ⚠️ DISCORD_GUILD no configurado — slash commands no sincronizados')

        asyncio.create_task(_queue_poll_loop(client))

    async def _queue_poll_loop(bot):
        """Procesa discord_queue cada 10s desde el mismo event loop del bot."""
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor
        except ImportError:
            print('[Discord] ⚠️ psycopg2 no disponible — queue polling desactivado')
            return

        if not DISCORD_CHANNEL.isdigit():
            print('[Discord] ⚠️ DISCORD_CHANNEL no válido — queue polling desactivado')
            return

        channel_id = int(DISCORD_CHANNEL)
        print('[Discord] 🔄 Queue polling iniciado (cada 10s)')

        while not bot.is_closed():
            try:
                conn = psycopg2.connect(_DATABASE_URL, cursor_factory=RealDictCursor, connect_timeout=10)
                cur  = conn.cursor()
                cur.execute(
                    "SELECT id, event_type, data FROM discord_queue "
                    "WHERE processed_at IS NULL ORDER BY created_at LIMIT 20"
                )
                rows = cur.fetchall()

                for row in rows:
                    event_id   = row['id']
                    event_type = row['event_type']
                    data       = row['data'] if isinstance(row['data'], dict) else json.loads(row['data'])
                    try:
                        ch = bot.get_channel(channel_id) or await bot.fetch_channel(channel_id)
                        if event_type == 'new_scan':
                            risk = data.get('risk_score', 0)
                            bar  = '🟥' if risk >= 70 else '🟧' if risk >= 30 else '🟩'
                            emb  = discord.Embed(
                                title=f'🔔 Nuevo scan — #{data.get("scan_id")}',
                                color=0xE74C3C if risk >= 70 else 0xF39C12 if risk >= 30 else 0x2ECC71,
                                description=(
                                    f'**Máquina:** {data.get("machine_name","N/A")}\n'
                                    f'**Usuario:** {data.get("username","N/A")}\n'
                                    f'{bar} **Risk score:** {risk}/100\n'
                                    f'**Hallazgos:** {data.get("issues_found",0)}'
                                ),
                            )
                            await ch.send(embed=emb)
                        elif event_type == 'verdict_change':
                            verdict = data.get('verdict', 'pending')
                            color   = {'hack': 0xE74C3C, 'clean': 0x2ECC71}.get(verdict, 0x64748B)
                            emb     = discord.Embed(
                                title=f'⚖️ Veredicto — Scan #{data.get("scan_id")}',
                                color=color,
                                description=(
                                    f'**Máquina:** {data.get("machine_name","N/A")}\n'
                                    f'**Usuario:** {data.get("username","N/A")}\n'
                                    f'**Veredicto:** {verdict.upper()}\n'
                                    f'**Razón:** {data.get("reason","-")}\n'
                                    f'**Por:** {data.get("changed_by","-")}'
                                ),
                            )
                            await ch.send(embed=emb)
                    except Exception as e:
                        print(f'[Discord] Error enviando evento {event_id}: {e}')

                    cur.execute("UPDATE discord_queue SET processed_at = NOW() WHERE id = %s", (event_id,))

                if rows:
                    conn.commit()
                    print(f'[Discord] {len(rows)} evento(s) de cola enviados')

                cur.close()
                conn.close()
            except Exception as e:
                print(f'[Discord] Error en queue poll: {e}')

            await asyncio.sleep(10)

    return client


# ── Notification helpers ──────────────────────────────────────────────────────

def _rep_link(username):
    """Link a la reputación pública del jugador (Argus Vault). None si no hay user válido."""
    u = (username or '').strip()
    if not u or u.upper() in ('N/A', 'NO DETECTADO', '—', '-'):
        return None
    from urllib.parse import quote
    base = os.environ.get('RENDER_EXTERNAL_URL', 'https://asperss.onrender.com').rstrip('/')
    return f'{base}/reputacion?u={quote(u)}'


def notify_new_scan(scan_id: int, machine_name: str, username: str,
                    risk_score: int = 0, issues_found: int = 0):
    """Llamado desde app.py cuando llega un scan nuevo."""
    if not DISCORD_AVAILABLE or not _bot_instance or not DISCORD_CHANNEL:
        return
    if not DISCORD_CHANNEL.isdigit():
        return

    risk_bar = '🟥' if risk_score >= 70 else '🟧' if risk_score >= 30 else '🟩'

    async def _send():
        embed = discord.Embed(
            title=f'🔔 Nuevo scan — #{scan_id}',
            color=discord.Color.orange(),
            description=(
                f'**Máquina:** {machine_name}\n'
                f'**Username:** {username}\n'
                f'**Hallazgos:** {issues_found}  |  **Risk:** {risk_bar} {risk_score}/100\n'
                f'Usa `/veredicto {scan_id} hack|clean <razón>` para marcar veredicto.'
            ),
        )
        _link = _rep_link(username)
        if _link:
            embed.add_field(name='🛡️ Reputación', value=f'[Ver historial en Argus Vault]({_link})', inline=False)
        await _send_to_channel(_bot_instance, int(DISCORD_CHANNEL), embed)

    if _bot_loop and not _bot_loop.is_closed():
        asyncio.run_coroutine_threadsafe(_send(), _bot_loop)


def notify_verdict_change(scan_id: int, machine_name: str, username: str,
                           verdict: str, reason: str, changed_by: str):
    """Llamado desde app.py cuando el panel web cambia el veredicto de un scan."""
    if not DISCORD_AVAILABLE or not _bot_instance or not DISCORD_CHANNEL:
        return
    if not DISCORD_CHANNEL.isdigit():
        return

    color_map = {'hack': 0xDC2626, 'clean': 0x10B981, 'pending': 0x64748B}

    async def _send():
        embed = discord.Embed(
            title=f'⚖️ Veredicto — Scan #{scan_id}',
            color=color_map.get(verdict, 0x64748B),
            description=(
                f'**Máquina:** {machine_name}\n'
                f'**Usuario:** {username}\n'
                f'**Veredicto:** {verdict.upper()}\n'
                f'**Razón:** {reason}\n'
                f'**Por:** {changed_by}'
            ),
        )
        _link = _rep_link(username)
        if _link:
            embed.add_field(name='🛡️ Reputación', value=f'[Ver historial en Argus Vault]({_link})', inline=False)
        await _send_to_channel(_bot_instance, int(DISCORD_CHANNEL), embed)

    if _bot_loop and not _bot_loop.is_closed():
        asyncio.run_coroutine_threadsafe(_send(), _bot_loop)


def notify_deploy(commit: str, branch: str, service: str, version: str):
    """Envía notificación de deploy exitoso al canal de Discord.
    Llamado desde app.py al detectar un commit nuevo en RENDER_GIT_COMMIT.
    """
    if not DISCORD_AVAILABLE or not _bot_instance or not DISCORD_CHANNEL:
        return
    if not DISCORD_CHANNEL.isdigit():
        return

    short = commit[:7] if len(commit) >= 7 else commit
    now   = datetime.datetime.utcnow().strftime('%d/%m/%Y %H:%M UTC')

    async def _send():
        embed = discord.Embed(
            title='🚀 ArgusScanner actualizado',
            color=0x7C3AED,
            description=(
                f'El sistema de detección de hacks ha sido desplegado exitosamente '
                f'en el entorno de producción.'
            ),
        )
        embed.add_field(name='📦 Versión',  value=f'`{version}`',        inline=True)
        embed.add_field(name='🔖 Commit',   value=f'`{short}`',           inline=True)
        embed.add_field(name='🌿 Rama',     value=f'`{branch}`',          inline=True)
        embed.add_field(name='🖥️ Servicio', value=f'`{service}`',         inline=True)
        embed.add_field(name='🕐 Hora',     value=now,                    inline=True)
        embed.add_field(name='✅ Estado',   value='Operativo',            inline=True)
        embed.set_footer(text='ASPERS Projects — Sistema Argus')
        await _send_to_channel(_bot_instance, int(DISCORD_CHANNEL), embed)

    if _bot_loop and not _bot_loop.is_closed():
        asyncio.run_coroutine_threadsafe(_send(), _bot_loop)


def notify_daily_summary(date: str, total: int, hacks: int, clean: int,
                         pending: int, avg_risk: float = 0.0, top_types: list = None):
    """P3 #25 — Resumen diario de scans, enviado al canal Discord a las 09:00 UTC."""
    if not DISCORD_AVAILABLE or not _bot_instance or not DISCORD_CHANNEL:
        return
    if not DISCORD_CHANNEL.isdigit():
        return

    hack_rate = f'{hacks/total*100:.1f}%' if total else '0%'
    top_lines = '\n'.join(
        f'  {i+1}. `{t}`' for i, t in enumerate((top_types or [])[:3])
    ) or '  Sin datos'

    async def _send():
        embed = discord.Embed(
            title=f'📋 Resumen diario — {date}',
            color=0x6366F1,
            description=(
                f'**Scans:** {total}  |  **Hacks:** {hacks}  |  **Limpios:** {clean}  |  **Pendientes:** {pending}\n'
                f'**Tasa de detección:** {hack_rate}  |  **Risk score medio:** {avg_risk}/100\n\n'
                f'**Top tipos detectados:**\n{top_lines}'
            ),
        )
        embed.set_footer(text='ASPERS Projects — Argus')
        await _send_to_channel(_bot_instance, int(DISCORD_CHANNEL), embed)

    if _bot_loop and not _bot_loop.is_closed():
        asyncio.run_coroutine_threadsafe(_send(), _bot_loop)


# ── Launcher ──────────────────────────────────────────────────────────────────

def start_bot_thread():
    """Inicia el bot de Discord en un daemon thread."""
    global _bot_instance, _bot_loop, _bot_thread

    if not DISCORD_AVAILABLE:
        return
    print(f'[Discord] DISCORD_AVAILABLE={DISCORD_AVAILABLE} TOKEN_SET={bool(DISCORD_TOKEN)} GUILD={DISCORD_GUILD!r} CHANNEL={DISCORD_CHANNEL!r}')
    if not DISCORD_TOKEN:
        print('[Discord] ❌ DISCORD_TOKEN vacío — bot desactivado. Configurar en Render > Environment.')
        return

    def _run():
        global _bot_instance, _bot_loop
        delay = 10
        for attempt in range(12):
            try:
                _bot_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(_bot_loop)
                _bot_instance = _make_bot()
                if _bot_instance:
                    print(f'[Discord] Intento de conexión #{attempt + 1}...')
                    _bot_loop.run_until_complete(_bot_instance.start(DISCORD_TOKEN))
                print('[Discord] Conexión cerrada limpiamente.')
                return
            except Exception as e:
                err = str(e)
                print(f'[Discord] Error conectando (intento {attempt + 1}): {err[:120]}')
                if '429' in err or 'rate limit' in err.lower() or '1015' in err:
                    delay = min(delay * 3, 3600)
                    print(f'[Discord] Rate limited por Discord/Cloudflare — esperando {delay}s antes de reintentar...')
                else:
                    delay = min(delay * 2, 300)
                    print(f'[Discord] Reintentando en {delay}s...')
                import time as _t
                _t.sleep(delay)
        print('[Discord] Máximo de reintentos alcanzado. Bot desactivado.')

    _bot_thread = threading.Thread(target=_run, daemon=True, name='discord-bot')
    _bot_thread.start()
    print('[Discord] Bot thread iniciado.')
