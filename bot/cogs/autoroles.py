"""Cog autoroles — paneles persistentes con botones para self-assign de roles.

Comandos:
    /autorole-create   Crea un panel nuevo con titulo, descripcion y N roles.
                       Estilo: 'buttons' (hasta 25 botones) o 'select' (menu).
    /autorole-add      Agrega un rol a un panel existente.
    /autorole-remove   Quita un rol de un panel existente.
    /autorole-delete   Elimina el panel completo.
    /autorole-list     Lista los paneles del servidor.

Persistencia: bot_autorole_panels.role_data guarda JSON con la lista de roles.
Las views se registran al arrancar (custom_id estable -> sobreviven reinicios).
"""
from __future__ import annotations

import json
import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from .. import config, db, utils

log = logging.getLogger("bot.cogs.autoroles")

MAX_ROLES_BUTTONS = 25
MAX_ROLES_SELECT = 25
PANEL_CUSTOM_ID_PREFIX = "argus:autorole:"


# ═════════════════════════════════════════════════════════════════════════
# Views dinamicos
# ═════════════════════════════════════════════════════════════════════════

class AutoroleButton(discord.ui.Button):
    def __init__(self, role_id: int, label: str, emoji: Optional[str] = None):
        super().__init__(
            label=label[:80],
            style=discord.ButtonStyle.secondary,
            emoji=emoji,
            custom_id=f"{PANEL_CUSTOM_ID_PREFIX}btn:{role_id}",
        )
        self.role_id = role_id

    async def callback(self, interaction: discord.Interaction):
        await _toggle_role(interaction, self.role_id)


class AutoroleButtonsView(discord.ui.View):
    def __init__(self, roles: list[dict]):
        super().__init__(timeout=None)
        for r in roles[:MAX_ROLES_BUTTONS]:
            self.add_item(AutoroleButton(
                role_id=int(r["role_id"]),
                label=r.get("label") or "Rol",
                emoji=r.get("emoji"),
            ))


class AutoroleSelect(discord.ui.Select):
    def __init__(self, roles: list[dict], message_id: int):
        options = [
            discord.SelectOption(
                label=(r.get("label") or "Rol")[:100],
                value=str(r["role_id"]),
                description=(r.get("description") or "")[:100] or None,
                emoji=r.get("emoji"),
            )
            for r in roles[:MAX_ROLES_SELECT]
        ]
        super().__init__(
            placeholder="Elige uno o varios roles...",
            min_values=0,
            max_values=len(options),
            options=options,
            custom_id=f"{PANEL_CUSTOM_ID_PREFIX}sel:{message_id}",
        )
        self.role_ids = {int(r["role_id"]) for r in roles}

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        if not guild or not isinstance(interaction.user, discord.Member):
            return
        member = interaction.user
        chosen_ids = {int(v) for v in self.values}
        added: list[discord.Role] = []
        removed: list[discord.Role] = []
        for rid in self.role_ids:
            role = guild.get_role(rid)
            if not role:
                continue
            has_it = role in member.roles
            if rid in chosen_ids and not has_it:
                try:
                    await member.add_roles(role, reason="autorole select")
                    added.append(role)
                except discord.Forbidden:
                    pass
            elif rid not in chosen_ids and has_it:
                try:
                    await member.remove_roles(role, reason="autorole select")
                    removed.append(role)
                except discord.Forbidden:
                    pass
        msg_parts = []
        if added:
            msg_parts.append(f"➕ {', '.join(r.mention for r in added)}")
        if removed:
            msg_parts.append(f"➖ {', '.join(r.mention for r in removed)}")
        await interaction.response.send_message(
            "\n".join(msg_parts) or "Sin cambios.",
            ephemeral=True,
        )


class AutoroleSelectView(discord.ui.View):
    def __init__(self, roles: list[dict], message_id: int):
        super().__init__(timeout=None)
        self.add_item(AutoroleSelect(roles, message_id))


async def _toggle_role(interaction: discord.Interaction, role_id: int):
    guild = interaction.guild
    if not guild or not isinstance(interaction.user, discord.Member):
        return
    role = guild.get_role(role_id)
    if not role:
        await interaction.response.send_message(
            embed=utils.error_embed("Ese rol ya no existe."), ephemeral=True
        )
        return
    if role in interaction.user.roles:
        try:
            await interaction.user.remove_roles(role, reason="autorole toggle")
            await interaction.response.send_message(
                embed=utils.info_embed(f"➖ Quitado: {role.mention}"),
                ephemeral=True,
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=utils.error_embed("No tengo permisos para quitarte ese rol."),
                ephemeral=True,
            )
    else:
        try:
            await interaction.user.add_roles(role, reason="autorole toggle")
            await interaction.response.send_message(
                embed=utils.success_embed(f"➕ Asignado: {role.mention}"),
                ephemeral=True,
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=utils.error_embed("No tengo permisos para darte ese rol."),
                ephemeral=True,
            )


# ═════════════════════════════════════════════════════════════════════════
# Cog
# ═════════════════════════════════════════════════════════════════════════

class Autoroles(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        await self._restore_panels()

    async def _restore_panels(self) -> None:
        """Re-registra las views de todos los paneles guardados al arrancar."""
        try:
            with db.cursor() as cur:
                cur.execute(
                    "SELECT message_id, style, role_data FROM bot_autorole_panels"
                )
                rows = cur.fetchall()
            for r in rows:
                try:
                    roles = json.loads(r["role_data"])
                except Exception:
                    continue
                if r["style"] == "select":
                    self.bot.add_view(AutoroleSelectView(roles, int(r["message_id"])))
                else:
                    self.bot.add_view(AutoroleButtonsView(roles))
            log.info("[Autoroles] %d paneles persistentes registrados", len(rows))
        except Exception:
            log.exception("[Autoroles] Error restaurando paneles")

    # ── /autorole-create ───────────────────────────────────────────────
    @app_commands.command(
        name="autorole-create",
        description="Crea un panel con botones de roles auto-asignables.",
    )
    @app_commands.default_permissions(manage_roles=True)
    @app_commands.describe(
        titulo="Titulo del embed",
        descripcion="Descripcion del panel",
        roles="Roles separados por coma (ej: @notificaciones, @trivia, @gaming)",
        estilo="buttons (hasta 25 botones) o select (menu desplegable)",
    )
    @app_commands.choices(
        estilo=[
            app_commands.Choice(name="buttons", value="buttons"),
            app_commands.Choice(name="select", value="select"),
        ]
    )
    async def create(
        self,
        interaction: discord.Interaction,
        titulo: str,
        descripcion: str,
        roles: str,
        estilo: app_commands.Choice[str] = None,  # type: ignore[assignment]
    ):
        guild = interaction.guild
        if not guild or not isinstance(interaction.channel, discord.TextChannel):
            return

        # Parsear roles (mentions o nombres)
        parsed: list[dict] = []
        for tok in roles.split(","):
            tok = tok.strip()
            if not tok:
                continue
            role: Optional[discord.Role] = None
            if tok.startswith("<@&") and tok.endswith(">"):
                try:
                    role = guild.get_role(int(tok[3:-1]))
                except ValueError:
                    pass
            else:
                role = utils.get_role_by_name(guild, tok)
            if role:
                parsed.append({"role_id": role.id, "label": role.name})

        if not parsed:
            await interaction.response.send_message(
                embed=utils.error_embed("No reconoci ningun rol valido."),
                ephemeral=True,
            )
            return
        if len(parsed) > 25:
            await interaction.response.send_message(
                embed=utils.error_embed("Maximo 25 roles por panel."),
                ephemeral=True,
            )
            return

        style = (estilo.value if estilo else "buttons")
        embed = utils.brand_embed(title=titulo, description=descripcion)

        # Enviar mensaje
        message = await interaction.channel.send(
            embed=embed,
            view=(AutoroleButtonsView(parsed) if style == "buttons" else AutoroleSelectView(parsed, 0)),
        )

        # Si es select, recrear la view con el msg id real (el custom_id usa el msg id)
        if style == "select":
            view = AutoroleSelectView(parsed, message.id)
            await message.edit(view=view)

        # Persistir
        with db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO bot_autorole_panels
                    (guild_id, channel_id, message_id, title, description, style, role_data)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (guild.id, interaction.channel.id, message.id, titulo, descripcion,
                 style, json.dumps(parsed)),
            )

        await interaction.response.send_message(
            embed=utils.success_embed(f"Panel creado con {len(parsed)} rol(es), estilo `{style}`."),
            ephemeral=True,
        )

    # ── /autorole-list ─────────────────────────────────────────────────
    @app_commands.command(
        name="autorole-list",
        description="Lista los paneles de autoroles del servidor.",
    )
    @app_commands.default_permissions(manage_roles=True)
    async def list_panels(self, interaction: discord.Interaction):
        guild = interaction.guild
        if not guild:
            return
        with db.cursor() as cur:
            cur.execute(
                """
                SELECT id, channel_id, message_id, title, style, role_data
                FROM bot_autorole_panels WHERE guild_id = %s
                ORDER BY id DESC
                """,
                (guild.id,),
            )
            rows = cur.fetchall()
        if not rows:
            await interaction.response.send_message(
                embed=utils.info_embed("No hay paneles."),
                ephemeral=True,
            )
            return
        lines = []
        for r in rows:
            try:
                roles = json.loads(r["role_data"])
                count = len(roles)
            except Exception:
                count = 0
            lines.append(
                f"`#{r['id']}` · **{r['title']}** ({r['style']}, {count} roles)\n"
                f"  → <#{r['channel_id']}> · msg `{r['message_id']}`"
            )
        await interaction.response.send_message(
            embed=utils.brand_embed(
                title="🎭 Paneles de autoroles",
                description="\n\n".join(lines),
            ),
            ephemeral=True,
        )

    # ── /autorole-delete ───────────────────────────────────────────────
    @app_commands.command(
        name="autorole-delete",
        description="Elimina un panel de autoroles por su ID.",
    )
    @app_commands.default_permissions(manage_roles=True)
    async def delete_panel(self, interaction: discord.Interaction, panel_id: int):
        guild = interaction.guild
        if not guild:
            return
        with db.cursor() as cur:
            cur.execute(
                "SELECT channel_id, message_id FROM bot_autorole_panels WHERE id = %s AND guild_id = %s",
                (panel_id, guild.id),
            )
            row = cur.fetchone()
            if not row:
                await interaction.response.send_message(
                    embed=utils.error_embed(f"No existe panel `#{panel_id}`."),
                    ephemeral=True,
                )
                return
            cur.execute("DELETE FROM bot_autorole_panels WHERE id = %s", (panel_id,))

        # Borrar mensaje real
        try:
            ch = guild.get_channel(int(row["channel_id"]))
            if isinstance(ch, discord.TextChannel):
                msg = await ch.fetch_message(int(row["message_id"]))
                await msg.delete()
        except Exception:
            pass

        await interaction.response.send_message(
            embed=utils.success_embed(f"Panel `#{panel_id}` eliminado."),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Autoroles(bot))
