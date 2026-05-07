"""Cog argus — integracion con el panel web Argus.

Migra los comandos del web_app/discord_bot.py al bot standalone:
  /scan <jugador>           Ultimo scan de un jugador.
  /veredicto <id> <v> <r>   Cambia veredicto desde Discord (staff).
  /ss <jugador>             Crea token de SS y lo manda por DM (Cliente Pro o Admin).
  /stats                    Estadisticas globales del panel.

Ademas: tasks.loop que cada 10s lee discord_queue (creada por el web app)
y publica eventos new_scan / verdict_change al canal #logs-scans (o el
configurado por DISCORD_CHANNEL en .env). Esto reemplaza el queue poller
del worker viejo en Render — al apagar ese worker, el bot local se hace
cargo. Es seguro tenerlos ambos corriendo: cada evento se marca como
procesado tras enviarlo (UPDATE processed_at = NOW()) y solo se levantan
los que tienen processed_at IS NULL.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging
import os
import secrets
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks

from .. import config, db, utils

log = logging.getLogger("bot.cogs.argus")


VERDICT_COLORS = {
    "hack": 0xE74C3C,
    "clean": 0x2ECC71,
    "pending": 0x95A5A6,
}


def _resolve_log_channel(guild: discord.Guild) -> Optional[discord.TextChannel]:
    """Prefiere ch_log_scans (configurado por /setup), fallback a DISCORD_CHANNEL del .env."""
    cid = db.get_setting(guild.id, "ch_log_scans")
    if not cid:
        cid = os.environ.get("DISCORD_CHANNEL", "")
    try:
        ch = guild.get_channel(int(cid))
        return ch if isinstance(ch, discord.TextChannel) else None
    except (TypeError, ValueError):
        return None


# ═════════════════════════════════════════════════════════════════════════
# Cog
# ═════════════════════════════════════════════════════════════════════════

class Argus(commands.Cog):
    """Comandos de integracion con el panel staff."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.poll_queue.start()

    def cog_unload(self) -> None:
        self.poll_queue.cancel()

    # ── /scan ──────────────────────────────────────────────────────────
    @app_commands.command(name="scan", description="Muestra el ultimo scan de un jugador.")
    @app_commands.describe(jugador="Nombre de maquina o username del jugador")
    async def scan_cmd(self, interaction: discord.Interaction, jugador: str):
        await interaction.response.defer()
        try:
            with db.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, machine_name, minecraft_username, status, verdict,
                           risk_score, issues_found, started_at
                    FROM scans
                    WHERE LOWER(machine_name) LIKE %s
                       OR LOWER(minecraft_username) LIKE %s
                    ORDER BY id DESC LIMIT 1
                    """,
                    (f"%{jugador.lower()}%", f"%{jugador.lower()}%"),
                )
                row = cur.fetchone()
            if not row:
                await interaction.followup.send(
                    embed=utils.error_embed(f"No encontre ningun scan para **{jugador}**."),
                )
                return

            verdict = (row["verdict"] or "pending").lower()
            risk = int(row["risk_score"] or 0)
            risk_bar = "🟥" if risk >= 70 else "🟧" if risk >= 30 else "🟩"
            color = VERDICT_COLORS.get(verdict, 0xF1C40F)

            embed = utils.brand_embed(
                title=f"Scan #{row['id']} — {row['machine_name'] or 'N/A'}",
                color=color,
                url=f"{config.PANEL_URL}/panel?scan={row['id']}",
            )
            embed.add_field(name="Usuario",    value=row["minecraft_username"] or "N/A", inline=True)
            embed.add_field(name="Estado",     value=row["status"] or "?",                inline=True)
            embed.add_field(name="Veredicto",  value=verdict.upper(),                     inline=True)
            embed.add_field(name="Risk Score", value=f"{risk_bar} {risk}/100",             inline=True)
            embed.add_field(name="Hallazgos",  value=str(row["issues_found"] or 0),       inline=True)
            embed.add_field(
                name="Fecha",
                value=str(row["started_at"])[:19] if row["started_at"] else "?",
                inline=True,
            )
            await interaction.followup.send(embed=embed)
        except Exception as e:
            log.exception("[Argus] Error en /scan")
            await interaction.followup.send(embed=utils.error_embed(f"Error: `{e}`"))

    # ── /veredicto ─────────────────────────────────────────────────────
    @app_commands.command(name="veredicto", description="(Staff) Cambia el veredicto de un scan.")
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.describe(
        scan_id="ID numerico del scan",
        veredicto="hack | clean | pending",
        razon="Razon (obligatoria)",
    )
    @app_commands.choices(veredicto=[
        app_commands.Choice(name="hack",    value="hack"),
        app_commands.Choice(name="clean",   value="clean"),
        app_commands.Choice(name="pending", value="pending"),
    ])
    async def veredicto_cmd(
        self,
        interaction: discord.Interaction,
        scan_id: int,
        veredicto: app_commands.Choice[str],
        razon: str,
    ):
        if not isinstance(interaction.user, discord.Member) or not utils.is_staff(interaction.user):
            await interaction.response.send_message(
                embed=utils.error_embed("Solo staff."), ephemeral=True
            )
            return
        if not razon.strip():
            await interaction.response.send_message(
                embed=utils.error_embed("La razon es obligatoria."), ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True)
        try:
            changed_by = f"Discord:{interaction.user.name}"
            with db.cursor() as cur:
                cur.execute(
                    """
                    UPDATE scans SET verdict = %s, verdict_reason = %s,
                                     verdict_by = %s, verdict_at = NOW()
                    WHERE id = %s
                    RETURNING machine_name, minecraft_username
                    """,
                    (veredicto.value, razon, changed_by, scan_id),
                )
                srow = cur.fetchone()
                cur.execute(
                    """
                    INSERT INTO verdict_history (scan_id, verdict, reason, changed_by)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (scan_id, veredicto.value, razon, changed_by),
                )
            machine = srow["machine_name"] if srow else "N/A"
            username = srow["minecraft_username"] if srow else "N/A"

            await interaction.followup.send(
                embed=utils.success_embed(
                    f"Scan `#{scan_id}` -> **{veredicto.value.upper()}**"
                ),
                ephemeral=True,
            )

            # Anuncio en canal de veredictos
            if interaction.guild:
                cid = db.get_setting(interaction.guild.id, "ch_log_verdicts")
                ch = None
                if cid:
                    try:
                        ch = interaction.guild.get_channel(int(cid))
                    except (TypeError, ValueError):
                        pass
                if isinstance(ch, discord.TextChannel):
                    embed = utils.brand_embed(
                        title=f"⚖ Veredicto — Scan #{scan_id}",
                        color=VERDICT_COLORS.get(veredicto.value, 0x95A5A6),
                        description=(
                            f"**Maquina:** {machine}\n"
                            f"**Usuario:** {username}\n"
                            f"**Veredicto:** {veredicto.value.upper()}\n"
                            f"**Razon:** {razon}\n"
                            f"**Por:** {interaction.user.display_name}"
                        ),
                        url=f"{config.PANEL_URL}/panel?scan={scan_id}",
                    )
                    await ch.send(embed=embed)
        except Exception as e:
            log.exception("[Argus] Error en /veredicto")
            await interaction.followup.send(
                embed=utils.error_embed(f"Error: `{e}`"), ephemeral=True
            )

    # ── /ss ────────────────────────────────────────────────────────────
    @app_commands.command(name="ss", description="(Cliente Pro) Inicia un Screen Share — crea token y lo envia por DM.")
    @app_commands.describe(jugador="Mention del jugador al que hacer SS")
    async def ss_cmd(self, interaction: discord.Interaction, jugador: discord.Member):
        if not isinstance(interaction.user, discord.Member):
            return
        if not utils.can_use_ss(interaction.user):
            await interaction.response.send_message(
                embed=utils.error_embed(
                    "Este comando es exclusivo para **Cliente Pro**.\n\n"
                    "Argus Projects funciona bajo plan Cliente Pro — no hay tier gratis.\n"
                    "Para conseguir el rol abrí un ticket tipo **`compra`** en `❓・soporte` "
                    "y un Admin te explica precios y métodos de pago.",
                    title="🔒 Solo Cliente Pro",
                ),
                ephemeral=True,
            )
            return
        await interaction.response.defer(ephemeral=True)
        try:
            scan_token = secrets.token_urlsafe(32)
            expires_at = dt.datetime.utcnow() + dt.timedelta(minutes=30)
            created_by = f"Discord:{interaction.user.name}"

            with db.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO scan_tokens (token, expires_at, max_uses, created_by, description)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (scan_token, expires_at, 1, created_by, f"SS a {jugador.display_name} via Discord"),
                )

            dm_text = (
                f"🎮 **Un moderador ha iniciado un Screen Share contigo.**\n\n"
                f"Ejecuta el scanner y cuando te pida el token, usa este:\n"
                f"```\n{scan_token}\n```\n"
                f"🔗 Descarga: {config.PANEL_URL}/descargar\n"
                f"⏰ El token expira en **30 minutos**. Ejecutalo cuanto antes."
            )

            dm_ok = False
            try:
                await jugador.send(dm_text)
                dm_ok = True
            except discord.Forbidden:
                pass

            if dm_ok:
                reply = utils.success_embed(
                    f"Token creado y enviado por DM a **{jugador.display_name}**."
                )
            else:
                reply = utils.warning_embed(
                    f"Token creado para **{jugador.display_name}**.\n"
                    f"⚠ No pude mandarle DM (DMs cerrados). Pasale el token manualmente:\n"
                    f"```\n{scan_token}\n```"
                )
            await interaction.followup.send(embed=reply, ephemeral=True)

            # Anuncio en #logs-scans
            if interaction.guild:
                ch = _resolve_log_channel(interaction.guild)
                if ch:
                    embed = utils.brand_embed(
                        title="🔍 SS iniciado",
                        color=0x3498DB,
                        description=(
                            f"**Staff:** {interaction.user.display_name}\n"
                            f"**Jugador:** {jugador.display_name}\n"
                            f"**Token expira:** <t:{int(expires_at.timestamp())}:R>"
                        ),
                    )
                    await ch.send(embed=embed)
        except Exception as e:
            log.exception("[Argus] Error en /ss")
            await interaction.followup.send(
                embed=utils.error_embed(f"Error creando token: `{e}`"), ephemeral=True
            )

    # ── /stats ─────────────────────────────────────────────────────────
    @app_commands.command(name="stats", description="Estadisticas globales del panel Argus.")
    async def stats_cmd(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            with db.cursor() as cur:
                cur.execute("SELECT COUNT(*) AS c FROM scans")
                total = int(cur.fetchone()["c"])
                cur.execute("SELECT COUNT(*) AS c FROM scans WHERE verdict = 'hack'")
                hacks = int(cur.fetchone()["c"])
                cur.execute("SELECT COUNT(*) AS c FROM scans WHERE verdict = 'clean'")
                clean = int(cur.fetchone()["c"])
                cur.execute("SELECT COUNT(*) AS c FROM scans WHERE started_at >= NOW() - INTERVAL '24 hours'")
                today = int(cur.fetchone()["c"])
                cur.execute("SELECT AVG(risk_score) AS avg FROM scans WHERE risk_score IS NOT NULL")
                row = cur.fetchone()
                avg_risk = float(row["avg"] or 0)
            embed = utils.brand_embed(
                title="📊 Argus Projects · Estadisticas globales",
                url=f"{config.PANEL_URL}/panel",
            )
            embed.add_field(name="Total scans",   value=str(total),  inline=True)
            embed.add_field(name="Ultimas 24h",   value=str(today),  inline=True)
            embed.add_field(name="Avg risk",      value=f"{avg_risk:.1f}/100", inline=True)
            embed.add_field(name="Con hacks 🔴",  value=str(hacks),                inline=True)
            embed.add_field(name="Limpios 🟢",    value=str(clean),                inline=True)
            embed.add_field(name="Pendientes 🟡", value=str(total - hacks - clean), inline=True)
            await interaction.followup.send(embed=embed)
        except Exception as e:
            log.exception("[Argus] Error en /stats")
            await interaction.followup.send(embed=utils.error_embed(f"Error: `{e}`"))

    # ── Queue poller ───────────────────────────────────────────────────
    @tasks.loop(seconds=10)
    async def poll_queue(self):
        """Procesa eventos pendientes de la tabla discord_queue (creada por web app)."""
        try:
            with db.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, event_type, data
                    FROM discord_queue
                    WHERE processed_at IS NULL
                    ORDER BY created_at LIMIT 20
                    """
                )
                rows = cur.fetchall()
            if not rows:
                return

            # Resolver canal por guild (usamos el primer guild conectado)
            guild = self.bot.get_guild(config.DISCORD_GUILD) if config.DISCORD_GUILD else None
            if not guild:
                return
            ch = _resolve_log_channel(guild)
            if not ch:
                return

            for r in rows:
                ev_id = int(r["id"])
                ev_type = r["event_type"]
                data = r["data"] if isinstance(r["data"], dict) else json.loads(r["data"] or "{}")
                try:
                    await self._dispatch_queue_event(ch, ev_type, data)
                except Exception:
                    log.exception("[Argus] Error procesando evento %s", ev_id)
                # Marcar procesado
                with db.cursor() as cur:
                    cur.execute(
                        "UPDATE discord_queue SET processed_at = NOW() WHERE id = %s",
                        (ev_id,),
                    )
        except Exception:
            log.exception("[Argus] Error en poll_queue")

    @poll_queue.before_loop
    async def _before(self):
        await self.bot.wait_until_ready()

    async def _dispatch_queue_event(self, ch: discord.TextChannel, ev_type: str, data: dict):
        if ev_type == "new_scan":
            risk = int(data.get("risk_score", 0))
            bar = "🟥" if risk >= 70 else "🟧" if risk >= 30 else "🟩"
            color = 0xE74C3C if risk >= 70 else 0xF39C12 if risk >= 30 else 0x2ECC71
            scan_id = data.get("scan_id", "?")
            embed = utils.brand_embed(
                title=f"🔔 Nuevo scan — #{scan_id}",
                color=color,
                description=(
                    f"**Maquina:** {data.get('machine_name', 'N/A')}\n"
                    f"**Usuario:** {data.get('username', 'N/A')}\n"
                    f"{bar} **Risk score:** {risk}/100\n"
                    f"**Hallazgos:** {data.get('issues_found', 0)}\n\n"
                    f"`/veredicto {scan_id} hack|clean <razon>` para marcar."
                ),
                url=f"{config.PANEL_URL}/panel?scan={scan_id}",
            )
            await ch.send(embed=embed)
            return

        if ev_type == "verdict_change":
            verdict = data.get("verdict", "pending")
            color = VERDICT_COLORS.get(verdict, 0x95A5A6)
            scan_id = data.get("scan_id", "?")
            embed = utils.brand_embed(
                title=f"⚖ Veredicto — Scan #{scan_id}",
                color=color,
                description=(
                    f"**Maquina:** {data.get('machine_name', 'N/A')}\n"
                    f"**Usuario:** {data.get('username', 'N/A')}\n"
                    f"**Veredicto:** {verdict.upper()}\n"
                    f"**Razon:** {data.get('reason', '-')}\n"
                    f"**Por:** {data.get('changed_by', '-')}"
                ),
                url=f"{config.PANEL_URL}/panel?scan={scan_id}",
            )
            await ch.send(embed=embed)
            return

        if ev_type == "deploy":
            short = (data.get("commit") or "")[:7]
            embed = utils.brand_embed(
                title="🚀 ArgusScanner actualizado",
                color=0x7C3AED,
                description=(
                    "El sistema de deteccion de hacks ha sido desplegado exitosamente "
                    "en el entorno de produccion."
                ),
            )
            embed.add_field(name="📦 Version",  value=f"`{data.get('version', '?')}`", inline=True)
            embed.add_field(name="🔖 Commit",   value=f"`{short}`",                    inline=True)
            embed.add_field(name="🌿 Rama",     value=f"`{data.get('branch', 'main')}`", inline=True)
            embed.add_field(name="🖥 Servicio", value=f"`{data.get('service', '-')}`", inline=True)
            await ch.send(embed=embed)
            return


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Argus(bot))
