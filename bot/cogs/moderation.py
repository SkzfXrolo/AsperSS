"""Cog moderation — warns, mutes, kicks, bans, strikes y logs.

Comandos staff:
    /warn      anade un warn al historial; si supera threshold, escala.
    /warns     muestra warns activos de un usuario.
    /unwarn    desactiva (soft delete) un warn por id.
    /mute      timeout de Discord (nativo) por duracion ('10m','2h',etc).
    /unmute    quita el timeout.
    /kick      expulsa.
    /ban       banea (con opcion delete-message-days).
    /unban     desbanea por id.
    /clear     borra los ultimos N mensajes (default 50, max 200).
    /modlog    muestra historial completo de un usuario.

Sistema de strikes (escalada automatica al alcanzar warns):
    3 warns activos → mute 1h
    5 warns activos → kick
    7 warns activos → ban

Todas las acciones se loguean a #logs-moderacion (configurado por /setup).
"""
from __future__ import annotations

import datetime as dt
import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from .. import config, db, utils

log = logging.getLogger("bot.cogs.moderation")


def _get_channel(guild: discord.Guild, key: str) -> Optional[discord.TextChannel]:
    cid = db.get_setting(guild.id, key)
    if not cid:
        return None
    try:
        ch = guild.get_channel(int(cid))
        return ch if isinstance(ch, discord.TextChannel) else None
    except (TypeError, ValueError):
        return None


async def _log_action(
    guild: discord.Guild,
    *,
    action: str,
    user: discord.abc.User,
    moderator: discord.abc.User,
    reason: str,
    duration: Optional[dt.timedelta] = None,
    extra: str = "",
) -> None:
    """Persiste en bot_modlog y postea embed al canal de logs."""
    try:
        with db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO bot_modlog (guild_id, user_id, moderator_id, action, reason, duration)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (guild.id, user.id, moderator.id, action, reason or None, duration),
            )
    except Exception:
        log.exception("[Mod] No se pudo persistir modlog")

    log_ch = _get_channel(guild, "ch_log_mod")
    if log_ch is None:
        return

    color_map = {
        "warn":   0xFEE75C,
        "mute":   0xE67E22,
        "unmute": 0x57F287,
        "kick":   0xED4245,
        "ban":    0x992D22,
        "unban":  0x57F287,
        "clear":  0x9B59B6,
    }
    icon_map = {
        "warn": "⚠", "mute": "🔇", "unmute": "🔊",
        "kick": "👢", "ban": "🔨", "unban": "🕊", "clear": "🧹",
    }
    color = color_map.get(action, config.BRAND_COLOR)
    icon = icon_map.get(action, "🛡")

    embed = utils.brand_embed(
        title=f"{icon} {action.upper()}",
        description=(
            f"**Usuario:** {user.mention} (`{user.id}`)\n"
            f"**Moderador:** {moderator.mention}\n"
            f"**Razon:** {reason or '*(sin razon)*'}"
            + (f"\n**Duracion:** {utils.humanize_delta(duration)}" if duration else "")
            + (f"\n{extra}" if extra else "")
        ),
        color=color,
    )
    if hasattr(user, "display_avatar"):
        embed.set_thumbnail(url=user.display_avatar.url)
    try:
        await log_ch.send(embed=embed)
    except Exception:
        log.exception("[Mod] No se pudo enviar embed al canal de logs")


def _count_active_warns(guild_id: int, user_id: int) -> int:
    with db.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) AS c FROM bot_warns WHERE guild_id = %s AND user_id = %s AND active = TRUE",
            (guild_id, user_id),
        )
        row = cur.fetchone()
    return int(row["c"]) if row else 0


# ═════════════════════════════════════════════════════════════════════════
# Cog
# ═════════════════════════════════════════════════════════════════════════

class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ── /warn ──────────────────────────────────────────────────────────
    @app_commands.command(name="warn", description="Anade un warn a un usuario.")
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.describe(usuario="Miembro a sancionar", razon="Motivo del warn (obligatorio)")
    async def warn_cmd(
        self,
        interaction: discord.Interaction,
        usuario: discord.Member,
        razon: str,
    ):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return
        if not utils.is_staff(interaction.user):
            await interaction.response.send_message(
                embed=utils.error_embed("Solo staff puede usar este comando."), ephemeral=True
            )
            return
        if usuario.bot:
            await interaction.response.send_message(
                embed=utils.error_embed("No puedo warnear bots."), ephemeral=True
            )
            return
        if usuario.top_role >= interaction.user.top_role and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                embed=utils.error_embed("Tu rol no esta por encima del de este usuario."), ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        with db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO bot_warns (guild_id, user_id, moderator_id, reason)
                VALUES (%s, %s, %s, %s) RETURNING id
                """,
                (interaction.guild.id, usuario.id, interaction.user.id, razon),
            )
            row = cur.fetchone()
        warn_id = row["id"] if row else 0

        warn_count = _count_active_warns(interaction.guild.id, usuario.id)

        # DM al sancionado
        try:
            dm_embed = utils.warning_embed(
                title=f"⚠ Has recibido un warn en {interaction.guild.name}",
                description=(
                    f"**Razon:** {razon}\n"
                    f"**Total de warns activos:** {warn_count}\n\n"
                    "Acumular warns lleva a mute, kick o ban automatico. Modera tu comportamiento."
                ),
            )
            await usuario.send(embed=dm_embed)
        except discord.Forbidden:
            pass

        # Escalada
        escalation_msg = ""
        if warn_count >= config.WARN_THRESHOLD_BAN:
            try:
                await usuario.ban(reason=f"Auto: {warn_count} warns acumulados", delete_message_days=0)
                escalation_msg = f"\n🔨 **Ban automatico** aplicado ({warn_count} warns)."
                await _log_action(
                    interaction.guild,
                    action="ban",
                    user=usuario,
                    moderator=interaction.client.user,  # bot
                    reason=f"Auto-escalada: {warn_count} warns activos",
                )
            except discord.Forbidden:
                escalation_msg = f"\n⚠ Deberia banear pero no tengo permisos."
        elif warn_count >= config.WARN_THRESHOLD_KICK:
            try:
                await usuario.kick(reason=f"Auto: {warn_count} warns acumulados")
                escalation_msg = f"\n👢 **Kick automatico** aplicado ({warn_count} warns)."
                await _log_action(
                    interaction.guild,
                    action="kick",
                    user=usuario,
                    moderator=interaction.client.user,
                    reason=f"Auto-escalada: {warn_count} warns activos",
                )
            except discord.Forbidden:
                escalation_msg = f"\n⚠ Deberia expulsar pero no tengo permisos."
        elif warn_count >= config.WARN_THRESHOLD_MUTE:
            duration = dt.timedelta(minutes=config.DEFAULT_MUTE_MINUTES)
            try:
                await usuario.timeout(duration, reason=f"Auto: {warn_count} warns")
                escalation_msg = f"\n🔇 **Mute automatico** aplicado ({utils.humanize_delta(duration)})."
                await _log_action(
                    interaction.guild,
                    action="mute",
                    user=usuario,
                    moderator=interaction.client.user,
                    reason=f"Auto-escalada: {warn_count} warns activos",
                    duration=duration,
                )
            except discord.Forbidden:
                escalation_msg = f"\n⚠ Deberia mutear pero no tengo permisos."

        await _log_action(
            interaction.guild,
            action="warn",
            user=usuario,
            moderator=interaction.user,
            reason=razon,
            extra=f"Warn ID: `{warn_id}` · Activos: **{warn_count}**",
        )

        await interaction.followup.send(
            embed=utils.success_embed(
                f"Warn aplicado a {usuario.mention} (#{warn_id}). "
                f"Activos: **{warn_count}**.{escalation_msg}",
                title="Warn registrado",
            ),
            ephemeral=True,
        )

    # ── /warns ─────────────────────────────────────────────────────────
    @app_commands.command(name="warns", description="Muestra warns activos de un usuario.")
    @app_commands.default_permissions(moderate_members=True)
    async def warns_cmd(self, interaction: discord.Interaction, usuario: discord.Member):
        if not interaction.guild:
            return
        with db.cursor() as cur:
            cur.execute(
                """
                SELECT id, moderator_id, reason, created_at
                FROM bot_warns
                WHERE guild_id = %s AND user_id = %s AND active = TRUE
                ORDER BY created_at DESC
                """,
                (interaction.guild.id, usuario.id),
            )
            rows = cur.fetchall()
        if not rows:
            await interaction.response.send_message(
                embed=utils.success_embed(f"{usuario.mention} no tiene warns activos.", title="Limpio"),
                ephemeral=True,
            )
            return
        lines = []
        for r in rows[:15]:
            mod = interaction.guild.get_member(int(r["moderator_id"]))
            mod_name = mod.display_name if mod else f"id:{r['moderator_id']}"
            ts = r["created_at"].strftime("%Y-%m-%d %H:%M") if r["created_at"] else "?"
            lines.append(f"`#{r['id']}` · **{mod_name}** · {ts}\n  → {r['reason'] or '*(sin razon)*'}")
        embed = utils.warning_embed(
            title=f"⚠ Warns activos de {usuario.display_name}",
            description=(
                f"Total: **{len(rows)}** activos\n\n" + "\n\n".join(lines)
                + (f"\n\n*({len(rows)-15} mas no mostrados)*" if len(rows) > 15 else "")
            ),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /unwarn ────────────────────────────────────────────────────────
    @app_commands.command(name="unwarn", description="Desactiva un warn por su ID.")
    @app_commands.default_permissions(moderate_members=True)
    async def unwarn_cmd(self, interaction: discord.Interaction, warn_id: int):
        if not interaction.guild:
            return
        with db.cursor() as cur:
            cur.execute(
                """
                UPDATE bot_warns SET active = FALSE
                WHERE id = %s AND guild_id = %s AND active = TRUE
                RETURNING user_id
                """,
                (warn_id, interaction.guild.id),
            )
            row = cur.fetchone()
        if not row:
            await interaction.response.send_message(
                embed=utils.error_embed(f"No existe el warn `#{warn_id}` activo en este server."),
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            embed=utils.success_embed(f"Warn `#{warn_id}` desactivado."),
            ephemeral=True,
        )

    # ── /mute ──────────────────────────────────────────────────────────
    @app_commands.command(name="mute", description="Aplica timeout a un usuario.")
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.describe(
        usuario="Miembro a mutear",
        duracion="Duracion: 10m, 2h, 1d12h, 30 (=minutos)",
        razon="Razon del mute",
    )
    async def mute_cmd(
        self,
        interaction: discord.Interaction,
        usuario: discord.Member,
        duracion: str,
        razon: str = "",
    ):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return
        if not utils.is_staff(interaction.user):
            await interaction.response.send_message(
                embed=utils.error_embed("Solo staff."), ephemeral=True
            )
            return
        delta = utils.parse_duration(duracion)
        if not delta:
            await interaction.response.send_message(
                embed=utils.error_embed("Duracion invalida. Ejemplos: `10m`, `2h`, `1d12h`."),
                ephemeral=True,
            )
            return
        if delta.total_seconds() > 28 * 86400:
            await interaction.response.send_message(
                embed=utils.error_embed("Maximo 28 dias (limite de Discord para timeouts)."),
                ephemeral=True,
            )
            return
        try:
            await usuario.timeout(delta, reason=f"{interaction.user}: {razon}")
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=utils.error_embed("No tengo permisos para mutear a este usuario."),
                ephemeral=True,
            )
            return
        await _log_action(
            interaction.guild, action="mute",
            user=usuario, moderator=interaction.user,
            reason=razon, duration=delta,
        )
        await interaction.response.send_message(
            embed=utils.success_embed(
                f"{usuario.mention} muteado por **{utils.humanize_delta(delta)}**."
            ),
            ephemeral=True,
        )

    # ── /unmute ────────────────────────────────────────────────────────
    @app_commands.command(name="unmute", description="Quita el timeout a un usuario.")
    @app_commands.default_permissions(moderate_members=True)
    async def unmute_cmd(self, interaction: discord.Interaction, usuario: discord.Member, razon: str = ""):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return
        try:
            await usuario.timeout(None, reason=f"{interaction.user}: {razon or 'unmute'}")
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=utils.error_embed("No tengo permisos."), ephemeral=True
            )
            return
        await _log_action(
            interaction.guild, action="unmute",
            user=usuario, moderator=interaction.user, reason=razon,
        )
        await interaction.response.send_message(
            embed=utils.success_embed(f"{usuario.mention} ya no esta muteado."),
            ephemeral=True,
        )

    # ── /kick ──────────────────────────────────────────────────────────
    @app_commands.command(name="kick", description="Expulsa a un usuario del servidor.")
    @app_commands.default_permissions(kick_members=True)
    async def kick_cmd(self, interaction: discord.Interaction, usuario: discord.Member, razon: str = ""):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return
        if usuario.top_role >= interaction.user.top_role and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                embed=utils.error_embed("Tu rol no esta por encima del de este usuario."), ephemeral=True
            )
            return
        try:
            await usuario.send(embed=utils.warning_embed(
                f"Has sido **expulsado** de **{interaction.guild.name}**.\n**Razon:** {razon or '(sin razon)'}",
                title="Kick",
            ))
        except discord.Forbidden:
            pass
        try:
            await usuario.kick(reason=f"{interaction.user}: {razon}")
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=utils.error_embed("No tengo permisos para expulsar."), ephemeral=True
            )
            return
        await _log_action(
            interaction.guild, action="kick",
            user=usuario, moderator=interaction.user, reason=razon,
        )
        await interaction.response.send_message(
            embed=utils.success_embed(f"{usuario.mention} expulsado."),
            ephemeral=True,
        )

    # ── /ban ───────────────────────────────────────────────────────────
    @app_commands.command(name="ban", description="Banea a un usuario del servidor.")
    @app_commands.default_permissions(ban_members=True)
    @app_commands.describe(
        usuario="Miembro a banear",
        razon="Razon del ban",
        borrar_dias="Dias de mensajes a borrar (0-7, default 0)",
    )
    async def ban_cmd(
        self,
        interaction: discord.Interaction,
        usuario: discord.Member,
        razon: str = "",
        borrar_dias: app_commands.Range[int, 0, 7] = 0,
    ):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return
        if usuario.top_role >= interaction.user.top_role and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                embed=utils.error_embed("Tu rol no esta por encima del de este usuario."), ephemeral=True
            )
            return
        try:
            await usuario.send(embed=utils.error_embed(
                f"Has sido **baneado** de **{interaction.guild.name}**.\n**Razon:** {razon or '(sin razon)'}",
                title="Ban",
            ))
        except discord.Forbidden:
            pass
        try:
            await usuario.ban(reason=f"{interaction.user}: {razon}", delete_message_days=int(borrar_dias))
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=utils.error_embed("No tengo permisos para banear."), ephemeral=True
            )
            return
        await _log_action(
            interaction.guild, action="ban",
            user=usuario, moderator=interaction.user, reason=razon,
            extra=(f"Mensajes borrados: **{borrar_dias}d**" if borrar_dias else ""),
        )
        await interaction.response.send_message(
            embed=utils.success_embed(f"{usuario.mention} baneado."),
            ephemeral=True,
        )

    # ── /unban ─────────────────────────────────────────────────────────
    @app_commands.command(name="unban", description="Desbanea a un usuario por su ID.")
    @app_commands.default_permissions(ban_members=True)
    async def unban_cmd(self, interaction: discord.Interaction, user_id: str, razon: str = ""):
        if not interaction.guild:
            return
        try:
            uid = int(user_id)
        except ValueError:
            await interaction.response.send_message(
                embed=utils.error_embed("ID invalido."), ephemeral=True
            )
            return
        try:
            user = await interaction.client.fetch_user(uid)
            await interaction.guild.unban(user, reason=f"{interaction.user}: {razon}")
        except discord.NotFound:
            await interaction.response.send_message(
                embed=utils.error_embed("Ese usuario no esta baneado."), ephemeral=True
            )
            return
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=utils.error_embed("No tengo permisos."), ephemeral=True
            )
            return
        await _log_action(
            interaction.guild, action="unban",
            user=user, moderator=interaction.user, reason=razon,
        )
        await interaction.response.send_message(
            embed=utils.success_embed(f"`{user}` (`{uid}`) desbaneado."),
            ephemeral=True,
        )

    # ── /clear ─────────────────────────────────────────────────────────
    @app_commands.command(name="clear", description="Borra los ultimos N mensajes del canal.")
    @app_commands.default_permissions(manage_messages=True)
    @app_commands.describe(
        cantidad="Cantidad (1-200, default 50)",
        usuario="Solo borra mensajes de este usuario (opcional)",
    )
    async def clear_cmd(
        self,
        interaction: discord.Interaction,
        cantidad: app_commands.Range[int, 1, 200] = 50,
        usuario: Optional[discord.Member] = None,
    ):
        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("Solo en canales de texto.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)

        check = (lambda m: m.author.id == usuario.id) if usuario else None
        deleted = await interaction.channel.purge(limit=int(cantidad), check=check)

        await _log_action(
            interaction.guild,  # type: ignore[arg-type]
            action="clear",
            user=usuario or interaction.user,
            moderator=interaction.user,
            reason=f"En #{interaction.channel.name}",
            extra=f"Mensajes borrados: **{len(deleted)}**",
        )
        await interaction.followup.send(
            embed=utils.success_embed(f"🧹 {len(deleted)} mensajes borrados."),
            ephemeral=True,
        )

    # ── /modlog ────────────────────────────────────────────────────────
    @app_commands.command(name="modlog", description="Muestra historial de moderacion de un usuario.")
    @app_commands.default_permissions(moderate_members=True)
    async def modlog_cmd(self, interaction: discord.Interaction, usuario: discord.Member):
        if not interaction.guild:
            return
        with db.cursor() as cur:
            cur.execute(
                """
                SELECT action, moderator_id, reason, duration, created_at
                FROM bot_modlog
                WHERE guild_id = %s AND user_id = %s
                ORDER BY created_at DESC LIMIT 20
                """,
                (interaction.guild.id, usuario.id),
            )
            rows = cur.fetchall()
        if not rows:
            await interaction.response.send_message(
                embed=utils.success_embed(f"{usuario.mention} sin acciones registradas."),
                ephemeral=True,
            )
            return
        icon_map = {"warn": "⚠", "mute": "🔇", "unmute": "🔊", "kick": "👢",
                    "ban": "🔨", "unban": "🕊", "clear": "🧹"}
        lines = []
        for r in rows:
            mod = interaction.guild.get_member(int(r["moderator_id"]))
            mod_name = mod.display_name if mod else f"id:{r['moderator_id']}"
            ts = r["created_at"].strftime("%Y-%m-%d %H:%M") if r["created_at"] else "?"
            icon = icon_map.get(r["action"], "🛡")
            extras = []
            if r["duration"]:
                extras.append(f"{r['duration']}")
            line = f"{icon} **{r['action'].upper()}** · {ts} · por {mod_name}"
            if extras:
                line += " · " + " · ".join(extras)
            if r["reason"]:
                line += f"\n  → {r['reason']}"
            lines.append(line)
        embed = utils.brand_embed(
            title=f"📋 Modlog de {usuario.display_name}",
            description="\n\n".join(lines),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Moderation(bot))
