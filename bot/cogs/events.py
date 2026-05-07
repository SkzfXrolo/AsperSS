"""Cog events — sorteos, torneos y eventos programados.

Comandos:
    /sorteo <duracion> <premio> [ganadores=1]
        Crea un sorteo. La gente reacciona con 🎉 o usa el boton "Participar".
        Cuando expira, el bot anuncia ganadores.
    /sorteo-end <id>     Finaliza un sorteo antes de tiempo.
    /sorteo-reroll <id>  Sortea de nuevo (mismo pool de participantes).
    /sorteo-list         Lista sorteos activos.
    /event-create        Evento generico (titulo, descripcion, fecha, premio).
    /event-list          Lista eventos.

Tasks loop cada 30s revisa eventos pendientes y los finaliza si expiraron.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging
import random
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks

from .. import config, db, utils

log = logging.getLogger("bot.cogs.events")


# ═════════════════════════════════════════════════════════════════════════
# View persistente del sorteo
# ═════════════════════════════════════════════════════════════════════════

class GiveawayView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Participar",
        style=discord.ButtonStyle.success,
        emoji="🎉",
        custom_id="argus:giveaway:join",
    )
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.message or not interaction.guild:
            return
        # Buscar evento por message_id
        with db.cursor() as cur:
            cur.execute(
                "SELECT id, ends_at, finished, title FROM bot_events WHERE message_id = %s AND guild_id = %s",
                (interaction.message.id, interaction.guild.id),
            )
            ev = cur.fetchone()
        if not ev:
            await interaction.response.send_message(
                "Sorteo no encontrado.", ephemeral=True
            )
            return
        if ev["finished"]:
            await interaction.response.send_message(
                "Este sorteo ya finalizo.", ephemeral=True
            )
            return
        if dt.datetime.utcnow() >= ev["ends_at"]:
            await interaction.response.send_message(
                "Este sorteo ya cerro.", ephemeral=True
            )
            return
        # Toggle participacion
        with db.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM bot_event_participants WHERE event_id = %s AND user_id = %s",
                (ev["id"], interaction.user.id),
            )
            already = cur.fetchone() is not None
            if already:
                cur.execute(
                    "DELETE FROM bot_event_participants WHERE event_id = %s AND user_id = %s",
                    (ev["id"], interaction.user.id),
                )
                msg = "❌ Saliste del sorteo."
            else:
                cur.execute(
                    "INSERT INTO bot_event_participants (event_id, user_id) VALUES (%s, %s)",
                    (ev["id"], interaction.user.id),
                )
                msg = "✅ Estas participando."
            cur.execute(
                "SELECT COUNT(*) AS c FROM bot_event_participants WHERE event_id = %s",
                (ev["id"],),
            )
            count = int(cur.fetchone()["c"])
        await interaction.response.send_message(
            f"{msg} Total: **{count}** participantes.", ephemeral=True
        )


# ═════════════════════════════════════════════════════════════════════════
# Cog
# ═════════════════════════════════════════════════════════════════════════

class Events(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        bot.add_view(GiveawayView())
        self.check_events.start()

    def cog_unload(self) -> None:
        self.check_events.cancel()

    # ── Background task ────────────────────────────────────────────────
    @tasks.loop(seconds=30)
    async def check_events(self):
        try:
            with db.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, guild_id, channel_id, message_id, title, prize, winner_count
                    FROM bot_events
                    WHERE finished = FALSE AND ends_at <= NOW()
                    """
                )
                rows = cur.fetchall()
            for r in rows:
                await self._finalize_event(int(r["id"]))
        except Exception:
            log.exception("[Events] Error en check_events")

    @check_events.before_loop
    async def _before(self):
        await self.bot.wait_until_ready()

    async def _finalize_event(self, event_id: int):
        with db.cursor() as cur:
            cur.execute(
                """
                SELECT guild_id, channel_id, message_id, title, prize, winner_count
                FROM bot_events WHERE id = %s
                """,
                (event_id,),
            )
            ev = cur.fetchone()
            if not ev:
                return
            cur.execute(
                "SELECT user_id FROM bot_event_participants WHERE event_id = %s",
                (event_id,),
            )
            participants = [int(r["user_id"]) for r in cur.fetchall()]
            cur.execute("UPDATE bot_events SET finished = TRUE WHERE id = %s", (event_id,))

        guild = self.bot.get_guild(int(ev["guild_id"]))
        if not guild:
            return
        channel = guild.get_channel(int(ev["channel_id"]))
        if not isinstance(channel, discord.TextChannel):
            return

        if not participants:
            await channel.send(embed=utils.warning_embed(
                f"😔 Sorteo **{ev['title']}** finalizo sin participantes.",
                title="Sorteo terminado",
            ))
            return

        winner_count = min(int(ev["winner_count"]), len(participants))
        winners = random.sample(participants, winner_count)
        winners_mentions = ", ".join(f"<@{w}>" for w in winners)

        with db.cursor() as cur:
            cur.execute(
                "UPDATE bot_events SET winners = %s WHERE id = %s",
                (json.dumps(winners), event_id),
            )

        await channel.send(
            content=winners_mentions,
            embed=utils.success_embed(
                f"🎉 ¡Felicidades a {winners_mentions}!\n\n"
                f"**Premio:** {ev['prize']}\n"
                f"**Sorteo:** {ev['title']}\n"
                f"**Participantes totales:** {len(participants)}",
                title=f"🏆 Sorteo finalizado · #{event_id}",
            ),
        )

        # Editar mensaje original
        try:
            msg = await channel.fetch_message(int(ev["message_id"]))
            embed = msg.embeds[0] if msg.embeds else discord.Embed()
            embed.title = "🎉 Sorteo FINALIZADO"
            embed.color = discord.Color(0x57F287)
            embed.description = (
                (embed.description or "") + f"\n\n**Ganadores:** {winners_mentions}"
            )
            await msg.edit(embed=embed, view=None)
        except Exception:
            pass

    # ── /sorteo ────────────────────────────────────────────────────────
    @app_commands.command(name="sorteo", description="Crea un sorteo.")
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.describe(
        duracion="Duracion: 10m, 1h, 1d, etc.",
        premio="Que se gana?",
        ganadores="Cantidad de ganadores (default 1)",
    )
    async def sorteo(
        self,
        interaction: discord.Interaction,
        duracion: str,
        premio: str,
        ganadores: app_commands.Range[int, 1, 50] = 1,
    ):
        if not interaction.guild or not isinstance(interaction.channel, discord.TextChannel):
            return
        delta = utils.parse_duration(duracion)
        if not delta:
            await interaction.response.send_message(
                embed=utils.error_embed("Duracion invalida (ejemplos: `10m`, `2h`, `1d`)."),
                ephemeral=True,
            )
            return
        ends_at = dt.datetime.utcnow() + delta

        embed = utils.brand_embed(
            title="🎉 SORTEO",
            description=(
                f"**Premio:** {premio}\n"
                f"**Ganadores:** {ganadores}\n"
                f"**Termina:** <t:{int(ends_at.timestamp())}:R> (<t:{int(ends_at.timestamp())}:F>)\n\n"
                f"Click en **Participar** para entrar."
            ),
        )
        view = GiveawayView()
        message = await interaction.channel.send(embed=embed, view=view)

        with db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO bot_events
                    (guild_id, channel_id, message_id, type, title, prize, winner_count, created_by, ends_at)
                VALUES (%s, %s, %s, 'giveaway', %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (interaction.guild.id, interaction.channel.id, message.id,
                 f"Sorteo de {premio}", premio, int(ganadores),
                 interaction.user.id, ends_at),
            )
            row = cur.fetchone()

        await interaction.response.send_message(
            embed=utils.success_embed(f"Sorteo `#{row['id']}` creado."),
            ephemeral=True,
        )

    # ── /sorteo-end ────────────────────────────────────────────────────
    @app_commands.command(name="sorteo-end", description="Finaliza un sorteo ahora.")
    @app_commands.default_permissions(manage_guild=True)
    async def sorteo_end(self, interaction: discord.Interaction, sorteo_id: int):
        if not interaction.guild:
            return
        with db.cursor() as cur:
            cur.execute(
                "SELECT finished FROM bot_events WHERE id = %s AND guild_id = %s",
                (sorteo_id, interaction.guild.id),
            )
            row = cur.fetchone()
        if not row:
            await interaction.response.send_message(
                embed=utils.error_embed("Sorteo no encontrado."), ephemeral=True
            )
            return
        if row["finished"]:
            await interaction.response.send_message(
                embed=utils.warning_embed("Ya finalizo."), ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True)
        await self._finalize_event(sorteo_id)
        await interaction.followup.send(
            embed=utils.success_embed(f"Sorteo `#{sorteo_id}` finalizado."),
            ephemeral=True,
        )

    # ── /sorteo-reroll ─────────────────────────────────────────────────
    @app_commands.command(name="sorteo-reroll", description="Sortea ganadores de nuevo.")
    @app_commands.default_permissions(manage_guild=True)
    async def reroll(self, interaction: discord.Interaction, sorteo_id: int):
        if not interaction.guild:
            return
        with db.cursor() as cur:
            cur.execute(
                """
                SELECT channel_id, prize, winner_count, finished, title
                FROM bot_events WHERE id = %s AND guild_id = %s
                """,
                (sorteo_id, interaction.guild.id),
            )
            ev = cur.fetchone()
            if not ev:
                await interaction.response.send_message(
                    embed=utils.error_embed("Sorteo no encontrado."), ephemeral=True
                )
                return
            if not ev["finished"]:
                await interaction.response.send_message(
                    embed=utils.error_embed("Aun no finalizo."), ephemeral=True
                )
                return
            cur.execute(
                "SELECT user_id FROM bot_event_participants WHERE event_id = %s",
                (sorteo_id,),
            )
            participants = [int(r["user_id"]) for r in cur.fetchall()]
        if not participants:
            await interaction.response.send_message(
                embed=utils.warning_embed("Sin participantes."), ephemeral=True
            )
            return
        wc = min(int(ev["winner_count"]), len(participants))
        winners = random.sample(participants, wc)
        mentions = ", ".join(f"<@{w}>" for w in winners)
        channel = interaction.guild.get_channel(int(ev["channel_id"]))
        if isinstance(channel, discord.TextChannel):
            await channel.send(
                content=mentions,
                embed=utils.success_embed(
                    f"🎲 ¡Reroll! Nuevos ganadores: {mentions}\n**Premio:** {ev['prize']}",
                    title=f"Sorteo #{sorteo_id} · reroll",
                ),
            )
        await interaction.response.send_message(
            embed=utils.success_embed("Reroll enviado."), ephemeral=True
        )

    # ── /sorteo-list ───────────────────────────────────────────────────
    @app_commands.command(name="sorteo-list", description="Lista sorteos activos.")
    @app_commands.default_permissions(manage_guild=True)
    async def sorteo_list(self, interaction: discord.Interaction):
        if not interaction.guild:
            return
        with db.cursor() as cur:
            cur.execute(
                """
                SELECT id, title, prize, winner_count, ends_at, channel_id
                FROM bot_events
                WHERE guild_id = %s AND finished = FALSE AND type = 'giveaway'
                ORDER BY ends_at
                """,
                (interaction.guild.id,),
            )
            rows = cur.fetchall()
        if not rows:
            await interaction.response.send_message(
                embed=utils.info_embed("No hay sorteos activos."), ephemeral=True
            )
            return
        lines = []
        for r in rows:
            lines.append(
                f"`#{r['id']}` **{r['title']}** ({r['winner_count']}w)\n"
                f"  → <#{r['channel_id']}> · termina <t:{int(r['ends_at'].timestamp())}:R>"
            )
        await interaction.response.send_message(
            embed=utils.brand_embed(
                title="🎉 Sorteos activos",
                description="\n\n".join(lines),
            ),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Events(bot))
