"""
Bot de Discord para Argus Projects.
Corre en un thread dentro de app.py si DISCORD_TOKEN está configurado.

Variables de entorno requeridas:
  DISCORD_TOKEN   — token del bot
  DISCORD_GUILD   — ID del servidor (guild) donde se registran los slash commands
  DISCORD_CHANNEL — ID del canal donde se notifican scans nuevos (opcional)

Requiere: pip install discord.py>=2.3
"""
import os
import threading
import asyncio
import logging

log = logging.getLogger('discord_bot')

try:
    import discord
    from discord import app_commands
    DISCORD_AVAILABLE = True
except ImportError:
    DISCORD_AVAILABLE = False
    log.warning('[Discord] discord.py no está instalado. Bot desactivado.')

DISCORD_TOKEN   = os.environ.get('DISCORD_TOKEN', '')
DISCORD_GUILD   = os.environ.get('DISCORD_GUILD', '')
DISCORD_CHANNEL = os.environ.get('DISCORD_CHANNEL', '')

_bot_instance = None
_bot_loop     = None
_bot_thread   = None

# ── Intents & client ─────────────────────────────────────────────────────────

def _make_bot():
    if not DISCORD_AVAILABLE:
        return None

    intents = discord.Intents.default()
    intents.guilds = True
    client = discord.Client(intents=intents)
    tree   = app_commands.CommandTree(client)

    guild_obj = discord.Object(id=int(DISCORD_GUILD)) if DISCORD_GUILD.isdigit() else None

    # ── /scan ────────────────────────────────────────────────────────────────
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
                    f'''SELECT id, machine_name, username, status, verdict, created_at
                        FROM scans
                        WHERE LOWER(machine_name) LIKE {_PH} OR LOWER(username) LIKE {_PH}
                        ORDER BY id DESC LIMIT 1''',
                    (f'%{jugador.lower()}%', f'%{jugador.lower()}%')
                )
                row = cursor.fetchone()
            if not row:
                await interaction.followup.send(f'❌ No se encontró ningún scan para **{jugador}**.')
                return
            scan_id      = _row_get(row, 0, 'id')
            machine_name = _row_get(row, 1, 'machine_name') or 'N/A'
            username     = _row_get(row, 2, 'username') or 'N/A'
            status       = _row_get(row, 3, 'status') or '?'
            verdict      = _row_get(row, 4, 'verdict') or 'pendiente'
            created_at   = str(_row_get(row, 5, 'created_at') or '')[:19]
            color = (
                discord.Color.red()   if verdict == 'hacks'  else
                discord.Color.green() if verdict == 'clean'  else
                discord.Color.yellow()
            )
            embed = discord.Embed(
                title=f'Scan #{scan_id} — {machine_name}',
                color=color,
                description=f'**Username:** {username}\n**Estado:** {status}\n**Veredicto:** {verdict}\n**Fecha:** {created_at}',
            )
            embed.set_footer(text='Argus Projects')
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(f'⚠️ Error: {e}')

    # ── /veredicto ────────────────────────────────────────────────────────────
    @tree.command(
        name='veredicto',
        description='Cambia el veredicto de un scan',
        guild=guild_obj,
    )
    @app_commands.describe(
        scan_id='ID numérico del scan',
        veredicto='hacks | clean | pending',
        razon='Razón del veredicto',
    )
    async def cmd_veredicto(interaction: discord.Interaction, scan_id: int, veredicto: str, razon: str = ''):
        await interaction.response.defer(ephemeral=True)
        veredicto = veredicto.strip().lower()
        if veredicto not in ('hacks', 'clean', 'pending'):
            await interaction.followup.send('❌ Veredicto debe ser `hacks`, `clean` o `pending`.')
            return
        try:
            from app import get_api_db_cursor, _PH
            with get_api_db_cursor() as cursor:
                cursor.execute(
                    f'''UPDATE scans SET verdict = {_PH}, verdict_reason = {_PH},
                        verdict_by = {_PH}, verdict_at = NOW()
                        WHERE id = {_PH}''',
                    (veredicto, razon, f'Discord:{interaction.user.name}', scan_id)
                )
                cursor.execute(
                    f'''INSERT INTO verdict_history (scan_id, verdict, reason, changed_by)
                        VALUES ({_PH}, {_PH}, {_PH}, {_PH})''',
                    (scan_id, veredicto, razon, f'Discord:{interaction.user.name}')
                )
            await interaction.followup.send(f'✅ Scan #{scan_id} → **{veredicto}**')
        except Exception as e:
            await interaction.followup.send(f'⚠️ Error: {e}')

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
                total = cursor.fetchone()
                total = list(total.values())[0] if hasattr(total, 'keys') else total[0]
                cursor.execute("SELECT COUNT(*) FROM scans WHERE verdict = 'hacks'")
                hacks = cursor.fetchone()
                hacks = list(hacks.values())[0] if hasattr(hacks, 'keys') else hacks[0]
                cursor.execute("SELECT COUNT(*) FROM scans WHERE verdict = 'clean'")
                clean = cursor.fetchone()
                clean = list(clean.values())[0] if hasattr(clean, 'keys') else clean[0]
            embed = discord.Embed(
                title='Argus Projects — Estadísticas',
                color=discord.Color.blurple(),
                description=(
                    f'**Total scans:** {total}\n'
                    f'**Con hacks:** {hacks} 🔴\n'
                    f'**Limpios:** {clean} 🟢\n'
                    f'**Pendientes:** {total - hacks - clean} 🟡'
                ),
            )
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(f'⚠️ Error: {e}')

    @client.event
    async def on_ready():
        log.info(f'[Discord] Bot conectado como {client.user}')
        if guild_obj:
            await tree.sync(guild=guild_obj)
            log.info('[Discord] Slash commands sincronizados.')

    return client


# ── Notification helper ───────────────────────────────────────────────────────

def notify_new_scan(scan_id: int, machine_name: str, username: str):
    """Called from app.py when a new scan arrives — sends a message to DISCORD_CHANNEL."""
    if not DISCORD_AVAILABLE or not _bot_instance or not DISCORD_CHANNEL:
        return
    if not DISCORD_CHANNEL.isdigit():
        return
    channel_id = int(DISCORD_CHANNEL)

    async def _send():
        try:
            channel = _bot_instance.get_channel(channel_id)
            if channel is None:
                channel = await _bot_instance.fetch_channel(channel_id)
            embed = discord.Embed(
                title=f'🔔 Nuevo scan — #{scan_id}',
                color=discord.Color.orange(),
                description=(
                    f'**Máquina:** {machine_name}\n'
                    f'**Username:** {username}\n'
                    f'Usa `/veredicto {scan_id} hacks|clean` para marcar veredicto.'
                ),
            )
            await channel.send(embed=embed)
        except Exception as e:
            log.warning(f'[Discord] Error enviando notificación: {e}')

    if _bot_loop and not _bot_loop.is_closed():
        asyncio.run_coroutine_threadsafe(_send(), _bot_loop)


# ── Launcher ─────────────────────────────────────────────────────────────────

def start_bot_thread():
    """Start the Discord bot in a background daemon thread."""
    global _bot_instance, _bot_loop, _bot_thread

    if not DISCORD_AVAILABLE:
        return
    if not DISCORD_TOKEN:
        log.info('[Discord] DISCORD_TOKEN no configurado, bot desactivado.')
        return

    def _run():
        global _bot_instance, _bot_loop
        _bot_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_bot_loop)
        _bot_instance = _make_bot()
        if _bot_instance:
            _bot_loop.run_until_complete(_bot_instance.start(DISCORD_TOKEN))

    _bot_thread = threading.Thread(target=_run, daemon=True, name='discord-bot')
    _bot_thread.start()
    log.info('[Discord] Bot thread iniciado.')
