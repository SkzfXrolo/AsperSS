"""Cog tickets — sistema de soporte privado.

Flujo:
  1. Staff ejecuta /ticket-panel en #soporte (o donde quiera).
  2. Mensaje con embed + boton "Crear ticket" + select de categoria.
  3. Cuando alguien crea: el bot crea un canal privado bajo la categoria
     STAFF, accesible solo para el creador y el staff. Le hace ping al staff.
  4. /close en el canal del ticket -> genera transcript, lo guarda en
     bot_tickets.transcript, postea resumen en #tickets-cola, borra el canal.
  5. Solo 1 ticket activo por usuario.

Comandos:
    /ticket-panel       Publica el panel publico (staff).
    /ticket-add @user   Anade alguien al ticket actual.
    /ticket-remove @user Quita.
    /close [razon]      Cierra el ticket actual (solo en canales de ticket).
    /tickets [@user]    Historial de tickets de un usuario.
"""
from __future__ import annotations

import datetime as dt
import io
import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from .. import config, db, utils

log = logging.getLogger("bot.cogs.tickets")


TICKET_CATEGORIES = [
    {"value": "soporte",   "label": "Soporte tecnico"},
    {"value": "scanner",   "label": "Problema con Argus Scanner"},
    {"value": "compra",    "label": "Pago / Cliente Pro"},
    {"value": "denuncia",  "label": "Denuncia / reporte"},
    {"value": "otro",      "label": "Otro"},
]


def _staff_role_ids(guild: discord.Guild) -> list[int]:
    """Devuelve IDs de los roles staff configurados por /setup."""
    ids: list[int] = []
    for key in ("role_owner", "role_admin", "role_senior", "role_staff", "role_trainee"):
        rid = db.get_setting(guild.id, key)
        if rid:
            try:
                ids.append(int(rid))
            except ValueError:
                pass
    return ids


def _staff_category(guild: discord.Guild) -> Optional[discord.CategoryChannel]:
    cid = db.get_setting(guild.id, "cat_staff")
    if not cid:
        return None
    try:
        ch = guild.get_channel(int(cid))
        return ch if isinstance(ch, discord.CategoryChannel) else None
    except (TypeError, ValueError):
        return None


def _queue_channel(guild: discord.Guild) -> Optional[discord.TextChannel]:
    cid = db.get_setting(guild.id, "ch_tickets_queue")
    if not cid:
        return None
    try:
        ch = guild.get_channel(int(cid))
        return ch if isinstance(ch, discord.TextChannel) else None
    except (TypeError, ValueError):
        return None


# ═════════════════════════════════════════════════════════════════════════
# View del panel
# ═════════════════════════════════════════════════════════════════════════

class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.select(
        placeholder="Elige el motivo de tu ticket...",
        custom_id="argus:ticket:cat",
        options=[
            discord.SelectOption(label=c["label"], value=c["value"]) for c in TICKET_CATEGORIES
        ],
    )
    async def category_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        guild = interaction.guild
        if not guild or not isinstance(interaction.user, discord.Member):
            return
        await interaction.response.defer(ephemeral=True)
        category_value = select.values[0]
        category_label = next(
            (c["label"] for c in TICKET_CATEGORIES if c["value"] == category_value),
            category_value,
        )

        # Checar 1 ticket activo
        with db.cursor() as cur:
            cur.execute(
                "SELECT id, channel_id FROM bot_tickets WHERE guild_id = %s AND user_id = %s AND status = 'open'",
                (guild.id, interaction.user.id),
            )
            existing = cur.fetchone()
        if existing:
            await interaction.followup.send(
                embed=utils.warning_embed(
                    f"Ya tienes un ticket abierto: <#{existing['channel_id']}>",
                    title="Solo un ticket por usuario",
                ),
                ephemeral=True,
            )
            return

        # Crear canal
        cat = _staff_category(guild)
        staff_ids = _staff_role_ids(guild)
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, attach_files=True,
                embed_links=True, read_message_history=True,
            ),
        }
        for sid in staff_ids:
            role = guild.get_role(sid)
            if role:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True, send_messages=True, manage_messages=True,
                    attach_files=True, embed_links=True, read_message_history=True,
                )

        clean_name = "".join(c if c.isalnum() else "-" for c in interaction.user.name.lower())[:20]
        channel_name = f"ticket-{clean_name}"
        try:
            channel = await guild.create_text_channel(
                name=channel_name,
                category=cat,
                overwrites=overwrites,
                topic=f"Ticket de {interaction.user} — {category_label}",
                reason=f"Ticket creado por {interaction.user}",
            )
        except discord.Forbidden:
            await interaction.followup.send(
                embed=utils.error_embed("No tengo permisos para crear el canal."),
                ephemeral=True,
            )
            return

        # Persistir
        with db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO bot_tickets (guild_id, channel_id, user_id, category)
                VALUES (%s, %s, %s, %s) RETURNING id
                """,
                (guild.id, channel.id, interaction.user.id, category_value),
            )
            ticket_id = cur.fetchone()["id"]

        # Mensaje inicial
        ping = " ".join(f"<@&{sid}>" for sid in staff_ids if guild.get_role(sid))
        embed = utils.brand_embed(
            title=f"🎫 Ticket #{ticket_id} — {category_label}",
            description=(
                f"Hola {interaction.user.mention}, gracias por abrir un ticket.\n"
                f"Por favor describe tu problema con detalle:\n\n"
                f"• Que estabas intentando hacer?\n"
                f"• Que ocurrio? Que esperabas que pasara?\n"
                f"• Capturas / logs si aplica.\n\n"
                f"Un staff te respondera pronto.\n\n"
                f"Para cerrar el ticket, usa **`/close [razon]`**."
            ),
        )
        await channel.send(content=ping, embed=embed, view=CloseTicketView())

        await interaction.followup.send(
            embed=utils.success_embed(f"Ticket creado: {channel.mention}"),
            ephemeral=True,
        )


class CloseTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Cerrar ticket",
        style=discord.ButtonStyle.danger,
        emoji="🔒",
        custom_id="argus:ticket:close",
    )
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog: Optional[Tickets] = interaction.client.get_cog("Tickets")  # type: ignore[assignment]
        if cog:
            await cog._close_logic(interaction, reason="Cerrado por boton")


# ═════════════════════════════════════════════════════════════════════════
# Cog
# ═════════════════════════════════════════════════════════════════════════

class Tickets(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        bot.add_view(TicketPanelView())
        bot.add_view(CloseTicketView())

    async def _build_transcript(self, channel: discord.TextChannel) -> str:
        lines: list[str] = []
        try:
            async for msg in channel.history(limit=2000, oldest_first=True):
                ts = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
                content = msg.content or ""
                if msg.attachments:
                    content += " " + " ".join(a.url for a in msg.attachments)
                lines.append(f"[{ts}] {msg.author}: {content}")
        except Exception:
            log.exception("[Tickets] Error generando transcript")
        return "\n".join(lines)

    async def _close_logic(self, interaction: discord.Interaction, reason: str = ""):
        if not interaction.guild or not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message(
                embed=utils.error_embed("Solo en canales de texto."), ephemeral=True
            )
            return
        with db.cursor() as cur:
            cur.execute(
                "SELECT id, user_id, category, created_at FROM bot_tickets WHERE channel_id = %s AND status = 'open'",
                (interaction.channel.id,),
            )
            ticket = cur.fetchone()
        if not ticket:
            await interaction.response.send_message(
                embed=utils.error_embed("Este canal no es un ticket activo."),
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            embed=utils.warning_embed("🔒 Cerrando ticket... generando transcript..."),
        )

        transcript = await self._build_transcript(interaction.channel)

        # Persistir
        with db.cursor() as cur:
            cur.execute(
                """
                UPDATE bot_tickets
                SET status = 'closed', closed_at = NOW(), closed_by = %s, transcript = %s
                WHERE id = %s
                """,
                (interaction.user.id, transcript[:50000], ticket["id"]),
            )

        # Resumen al canal de cola
        queue = _queue_channel(interaction.guild)
        if queue:
            user = interaction.guild.get_member(int(ticket["user_id"]))
            opened = ticket["created_at"]
            duration = utils.humanize_delta(dt.datetime.utcnow() - opened.replace(tzinfo=None)) if opened else "?"
            embed = utils.brand_embed(
                title=f"🎫 Ticket #{ticket['id']} cerrado",
                description=(
                    f"**Usuario:** {user.mention if user else '?'} (`{ticket['user_id']}`)\n"
                    f"**Categoria:** {ticket['category']}\n"
                    f"**Cerrado por:** {interaction.user.mention}\n"
                    f"**Razon:** {reason or '(sin razon)'}\n"
                    f"**Duracion:** {duration}"
                ),
                color=0x95A5A6,
            )
            try:
                file = discord.File(
                    io.BytesIO(transcript.encode("utf-8")),
                    filename=f"ticket-{ticket['id']}.txt",
                )
                await queue.send(embed=embed, file=file)
            except Exception:
                await queue.send(embed=embed)

        # Borrar canal
        try:
            await interaction.channel.delete(reason=f"Ticket cerrado por {interaction.user}")
        except discord.Forbidden:
            pass

    # ── /ticket-panel ──────────────────────────────────────────────────
    @app_commands.command(name="ticket-panel", description="Publica el panel de tickets en este canal.")
    @app_commands.default_permissions(manage_guild=True)
    async def ticket_panel(self, interaction: discord.Interaction):
        if not isinstance(interaction.channel, discord.TextChannel):
            return
        embed = utils.brand_embed(
            title="🎫 Sistema de soporte",
            description=(
                "Necesitas ayuda? Crea un ticket usando el menu de abajo.\n\n"
                "**Categorias disponibles:**\n"
                "• Soporte tecnico\n"
                "• Problema con Argus Scanner\n"
                "• Pago / Cliente Pro\n"
                "• Denuncia / reporte\n"
                "• Otro\n\n"
                "Solo puedes tener **1 ticket abierto a la vez**. "
                "Un staff te respondera lo antes posible."
            ),
        )
        await interaction.channel.send(embed=embed, view=TicketPanelView())
        await interaction.response.send_message(
            embed=utils.success_embed("Panel publicado."), ephemeral=True
        )

    # ── /close ─────────────────────────────────────────────────────────
    @app_commands.command(name="close", description="Cierra el ticket actual.")
    async def close_cmd(self, interaction: discord.Interaction, razon: str = ""):
        if not isinstance(interaction.user, discord.Member) or not interaction.guild:
            return
        # Permitir si es staff o el creador del ticket
        with db.cursor() as cur:
            cur.execute(
                "SELECT user_id FROM bot_tickets WHERE channel_id = %s AND status = 'open'",
                (interaction.channel.id if interaction.channel else 0,),
            )
            tk = cur.fetchone()
        if not tk:
            await interaction.response.send_message(
                embed=utils.error_embed("Este canal no es un ticket activo."), ephemeral=True
            )
            return
        if not utils.is_staff(interaction.user) and int(tk["user_id"]) != interaction.user.id:
            await interaction.response.send_message(
                embed=utils.error_embed("Solo el creador del ticket o staff pueden cerrarlo."),
                ephemeral=True,
            )
            return
        await self._close_logic(interaction, reason=razon)

    # ── /ticket-add / /ticket-remove ───────────────────────────────────
    @app_commands.command(name="ticket-add", description="Anade un usuario al ticket actual (staff).")
    @app_commands.default_permissions(manage_guild=True)
    async def ticket_add(self, interaction: discord.Interaction, usuario: discord.Member):
        if not isinstance(interaction.channel, discord.TextChannel):
            return
        await interaction.channel.set_permissions(
            usuario,
            view_channel=True, send_messages=True, attach_files=True, read_message_history=True,
            reason=f"ticket-add por {interaction.user}",
        )
        await interaction.response.send_message(
            embed=utils.success_embed(f"{usuario.mention} anadido."),
        )

    @app_commands.command(name="ticket-remove", description="Quita un usuario del ticket actual (staff).")
    @app_commands.default_permissions(manage_guild=True)
    async def ticket_remove(self, interaction: discord.Interaction, usuario: discord.Member):
        if not isinstance(interaction.channel, discord.TextChannel):
            return
        await interaction.channel.set_permissions(
            usuario, overwrite=None,
            reason=f"ticket-remove por {interaction.user}",
        )
        await interaction.response.send_message(
            embed=utils.success_embed(f"{usuario.mention} removido."),
        )

    # ── /tickets ───────────────────────────────────────────────────────
    @app_commands.command(name="tickets", description="Historial de tickets de un usuario.")
    @app_commands.default_permissions(manage_guild=True)
    async def tickets_cmd(self, interaction: discord.Interaction, usuario: Optional[discord.Member] = None):
        if not interaction.guild:
            return
        target = usuario or interaction.user
        with db.cursor() as cur:
            cur.execute(
                """
                SELECT id, category, status, created_at, closed_at
                FROM bot_tickets WHERE guild_id = %s AND user_id = %s
                ORDER BY id DESC LIMIT 15
                """,
                (interaction.guild.id, target.id),
            )
            rows = cur.fetchall()
        if not rows:
            await interaction.response.send_message(
                embed=utils.info_embed(f"{target.mention} no ha abierto tickets.", title="Sin historial"),
                ephemeral=True,
            )
            return
        lines = []
        for r in rows:
            ts = r["created_at"].strftime("%Y-%m-%d %H:%M") if r["created_at"] else "?"
            status = "🟢 abierto" if r["status"] == "open" else "🔴 cerrado"
            lines.append(f"`#{r['id']}` · {status} · `{r['category']}` · {ts}")
        await interaction.response.send_message(
            embed=utils.brand_embed(
                title=f"🎫 Tickets de {target.display_name}",
                description="\n".join(lines),
            ),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Tickets(bot))
