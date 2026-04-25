"""
Discord Worker — proceso independiente que corre el bot y procesa la cola de notificaciones.
Se despliega como Background Worker en Render (IP distinta al web app → sin rate limit).

Variables de entorno requeridas:
  DATABASE_URL       — misma que el web app
  DISCORD_TOKEN      — token del bot
  DISCORD_GUILD      — ID del servidor
  DISCORD_CHANNEL    — ID del canal de notificaciones
  DISCORD_STAFF_ROLE — (opcional) rol de staff
"""
import os
import sys
import time
import json
import asyncio
import threading

# stdout sin buffer para que Render muestre los logs inmediatamente
sys.stdout.reconfigure(line_buffering=True)

import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.environ.get('DATABASE_URL', '').replace('postgres://', 'postgresql://', 1)


def get_conn():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor, connect_timeout=10)


def poll_queue(bot_instance, bot_loop):
    """Lee eventos pendientes de discord_queue y los procesa."""
    import discord

    CHANNEL_ID = os.environ.get('DISCORD_CHANNEL', '')
    if not CHANNEL_ID.isdigit():
        return

    channel_id = int(CHANNEL_ID)

    async def send_embed(embed):
        try:
            ch = bot_instance.get_channel(channel_id) or await bot_instance.fetch_channel(channel_id)
            await ch.send(embed=embed)
        except Exception as e:
            print(f'[Worker] Error enviando embed: {e}')

    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT id, event_type, data FROM discord_queue "
            "WHERE processed_at IS NULL ORDER BY created_at LIMIT 20"
        )
        rows = cur.fetchall()
        if not rows:
            cur.close()
            conn.close()
            return

        for row in rows:
            event_id   = row['id']
            event_type = row['event_type']
            data       = row['data'] if isinstance(row['data'], dict) else json.loads(row['data'])

            try:
                if event_type == 'new_scan':
                    risk  = data.get('risk_score', 0)
                    bar   = '🟥' if risk >= 70 else '🟧' if risk >= 30 else '🟩'
                    embed = discord.Embed(
                        title=f'🔔 Nuevo scan — #{data.get("scan_id")}',
                        color=0xE74C3C if risk >= 70 else 0xF39C12 if risk >= 30 else 0x2ECC71,
                        description=(
                            f'**Máquina:** {data.get("machine_name", "N/A")}\n'
                            f'**Usuario:** {data.get("username", "N/A")}\n'
                            f'{bar} **Risk score:** {risk}/100\n'
                            f'**Hallazgos:** {data.get("issues_found", 0)}'
                        ),
                    )
                    asyncio.run_coroutine_threadsafe(send_embed(embed), bot_loop).result(timeout=10)

                elif event_type == 'verdict_change':
                    verdict = data.get('verdict', 'pending')
                    color   = {'hack': 0xE74C3C, 'clean': 0x2ECC71}.get(verdict, 0x64748B)
                    embed   = discord.Embed(
                        title=f'⚖️ Veredicto — Scan #{data.get("scan_id")}',
                        color=color,
                        description=(
                            f'**Máquina:** {data.get("machine_name", "N/A")}\n'
                            f'**Usuario:** {data.get("username", "N/A")}\n'
                            f'**Veredicto:** {verdict.upper()}\n'
                            f'**Razón:** {data.get("reason", "-")}\n'
                            f'**Por:** {data.get("changed_by", "-")}'
                        ),
                    )
                    asyncio.run_coroutine_threadsafe(send_embed(embed), bot_loop).result(timeout=10)

            except Exception as e:
                print(f'[Worker] Error procesando evento {event_id}: {e}')

            # Marcar como procesado aunque haya fallado el envío
            cur.execute(
                "UPDATE discord_queue SET processed_at = NOW() WHERE id = %s",
                (event_id,)
            )

        conn.commit()
        cur.close()
        conn.close()
        print(f'[Worker] {len(rows)} evento(s) procesado(s)')

    except Exception as e:
        print(f'[Worker] Error leyendo cola: {e}')


def run_worker():
    """Loop principal: arranca el bot y hace polling cada 10s."""
    # Importar el bot (reutiliza discord_bot.py para los slash commands)
    import discord
    from discord import app_commands

    TOKEN      = os.environ.get('DISCORD_TOKEN', '')
    GUILD_ID   = os.environ.get('DISCORD_GUILD', '')
    STAFF_ROLE = os.environ.get('DISCORD_STAFF_ROLE', '')

    if not TOKEN:
        print('[Worker] ❌ DISCORD_TOKEN no configurado. Saliendo.')
        sys.exit(1)

    intents         = discord.Intents.default()
    intents.guilds  = True
    intents.members = True
    client = discord.Client(intents=intents)
    tree   = app_commands.CommandTree(client)
    guild_obj = discord.Object(id=int(GUILD_ID)) if GUILD_ID.isdigit() else None

    loop = asyncio.new_event_loop()

    @client.event
    async def on_ready():
        print(f'[Worker] ✅ Bot conectado como {client.user} (ID: {client.user.id})')
        if guild_obj:
            await tree.sync(guild=guild_obj)
            print('[Worker] ✅ Slash commands sincronizados.')

        # Loop de polling en background
        async def _poll_loop():
            while not client.is_closed():
                try:
                    poll_queue(client, loop)
                except Exception as e:
                    print(f'[Worker] Error en poll_loop: {e}')
                await asyncio.sleep(10)

        asyncio.create_task(_poll_loop())

    delay = 10
    for attempt in range(20):
        try:
            asyncio.set_event_loop(loop)
            print(f'[Worker] Intento de conexión #{attempt + 1}...')
            loop.run_until_complete(client.start(TOKEN))
            print('[Worker] Conexión cerrada.')
            break
        except Exception as e:
            err = str(e)
            print(f'[Worker] Error (intento {attempt + 1}): {err[:120]}')
            if '429' in err or '1015' in err or 'rate limit' in err.lower():
                delay = min(delay * 3, 3600)
            else:
                delay = min(delay * 2, 300)
            print(f'[Worker] Reintentando en {delay}s...')
            time.sleep(delay)
            loop = asyncio.new_event_loop()

    print('[Worker] Máximo de reintentos. Saliendo.')


if __name__ == '__main__':
    print('[Worker] 🚀 Discord Worker iniciado.')
    run_worker()
