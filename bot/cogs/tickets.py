"""Cog tickets — sistema de soporte inteligente con triage automatico.

Flujo:
  1. Staff publica panel con /ticket-panel.
  2. Usuario elige categoria del select menu -> bot crea canal privado.
  3. Bot postea mensaje guiado con preguntas especificas de la categoria.
  4. Bot taguea el rol correcto segun la categoria:
       soporte   -> Staff
       scanner   -> Developer + Staff
       compra    -> Admin + Owner
       denuncia  -> Senior Staff + Staff
       otro      -> Staff
  5. on_message en el ticket: si el usuario describe el problema, el bot
     escanea contra ticket_faq.json con keywords. Si match -> postea
     respuesta automatica con botones [Resuelto / Necesito humano].
  6. Botones persistentes en cada ticket:
        🔒 Cerrar    -> modal con razon (opcional) -> transcript + cierre
        🙋 Reclamar  -> el staff se marca como responsable
        📈 Escalar   -> modal con motivo -> IA clasifica y pingea rol adecuado

Comandos:
    /ticket-panel              Publica el panel publico (staff).
    /ticket-add @user          Anade alguien al ticket actual.
    /ticket-remove @user       Quita.
    /tickets [@user]           Historial de tickets de un usuario.
"""
from __future__ import annotations

import datetime as dt
import io
import json
import logging
import re
from pathlib import Path
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from .. import config, db, utils

log = logging.getLogger("bot.cogs.tickets")


_FAQ_PATH = Path(__file__).resolve().parent.parent / "data" / "ticket_faq.json"


TICKET_CATEGORIES = [
    {"value": "soporte",   "label": "Soporte tecnico",        "emoji": "🛠"},
    {"value": "scanner",   "label": "Problema con Argus Scanner", "emoji": "💻"},
    {"value": "compra",    "label": "Pago / Cliente Pro",     "emoji": "💳"},
    {"value": "denuncia",  "label": "Denuncia / reporte",     "emoji": "🚨"},
    {"value": "otro",      "label": "Otro",                   "emoji": "📋"},
]


# ─── Mapping de quien recibe ping segun categoria ────────────────────────
# El orden de las keys es de mas alto a mas bajo (primero los principales).
ROLE_KEYS_BY_CATEGORY: dict[str, list[str]] = {
    "soporte":   ["role_staff", "role_trainee"],
    "scanner":   ["role_dev", "role_staff"],
    "compra":    ["role_admin", "role_owner"],
    "denuncia":  ["role_senior", "role_staff"],
    "otro":      ["role_staff"],
}

# ─── Preguntas guiadas por categoria ─────────────────────────────────────
GUIDED_QUESTIONS: dict[str, dict] = {
    "soporte": {
        "title": "🛠 Soporte tecnico",
        "questions": [
            "1. ¿Cual es el problema en una frase?",
            "2. ¿Que estabas haciendo cuando ocurrio?",
            "3. ¿Que pasa exactamente? ¿Mensaje de error?",
            "4. ¿Probaste reiniciar / actualizar / reinstalar?",
        ],
    },
    "scanner": {
        "title": "💻 Problema con Argus Scanner",
        "questions": [
            "1. ¿Que version del scanner usas? (en la primera linea cuando arranca)",
            "2. ¿Sistema operativo y antivirus instalado?",
            "3. ¿Lo ejecutaste como administrador?",
            "4. **Sube captura del error** o del scan en cuestion (machine_name + scan_id).",
            "5. Si es falso positivo: ¿que hallazgo especifico crees que esta mal?",
        ],
    },
    "compra": {
        "title": "💳 Pago / Cliente Pro",
        "questions": [
            "1. ¿Que producto / suscripcion te interesa?",
            "2. ¿Metodo de pago preferido? (PayPal / transferencia / crypto)",
            "3. Si es renovacion: ¿desde que email pagaste antes?",
            "4. ¿Algun descuento / promocion que te haya llegado?",
        ],
    },
    "denuncia": {
        "title": "🚨 Denuncia / reporte",
        "questions": [
            "1. **Usuario denunciado** (mention o ID).",
            "2. **Capturas de pantalla** del incidente (sin pruebas no se sanciona).",
            "3. **Fecha aproximada** del incidente.",
            "4. **Tu version de los hechos** (resumen claro).",
            "5. (Opcional) Testigos que vieron lo mismo.",
        ],
    },
    "otro": {
        "title": "📋 Ticket general",
        "questions": [
            "1. Describi tu problema o consulta con todo el detalle posible.",
            "2. Si aplica, capturas de pantalla.",
        ],
    },
}


def _load_faq() -> dict:
    try:
        return json.loads(_FAQ_PATH.read_text(encoding="utf-8"))
    except Exception:
        log.exception("[Tickets] Error cargando FAQ")
        return {}


def _staff_role_ids_for_category(guild: discord.Guild, category: str) -> list[int]:
    """Devuelve IDs de roles a pingear segun la categoria."""
    keys = ROLE_KEYS_BY_CATEGORY.get(category, ["role_staff"])
    ids: list[int] = []
    for key in keys:
        rid = db.get_setting(guild.id, key)
        if rid:
            try:
                ids.append(int(rid))
            except ValueError:
                pass
    return ids


def _all_staff_role_ids(guild: discord.Guild) -> list[int]:
    """Todos los roles staff (para overwrites de visibilidad del canal)."""
    ids: list[int] = []
    for key in ("role_owner", "role_admin", "role_dev", "role_senior", "role_staff", "role_trainee"):
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


def _faq_match(category: str, message_text: str) -> Optional[dict]:
    """Busca en el FAQ una respuesta que coincida con keywords del mensaje.
    Devuelve la entrada {title, answer} o None.
    """
    faq = _load_faq()
    entries = faq.get(category) or []
    text_low = message_text.lower()
    best: Optional[dict] = None
    best_score = 0
    for entry in entries:
        score = sum(1 for kw in entry.get("keywords", []) if kw.lower() in text_low)
        if score > best_score:
            best_score = score
            best = entry
    return best if best_score > 0 else None


# ─── IA heuristica para escalada ────────────────────────────────────────
# Clasifica el motivo escrito por el staff y decide a que rol pingear.
ESCALATION_KEYWORDS: dict[str, list[str]] = {
    "role_dev": [
        # Tecnico / scanner / codigo
        "bug", "exploit", "falso positivo", "false positive", "deteccion",
        "detección", "scanner", "exe", "no abre", "no funciona", "crashea",
        "crash", "se cierra", "no inicia", "version", "actualiza", "hash",
        "log", "stacktrace", "traceback", "panel", "api", "endpoint",
        "deploy", "render", "base de datos", "postgres", "sql", "migration",
        "firewall", "antivirus bloquea", "smartscreen", "token expir",
        "auth fall", "config", "yaml", "json invalido",
    ],
    "role_admin": [
        # Pagos / negocio / suscripciones
        "pago", "factura", "suscripcion", "suscripción", "cliente pro",
        "cobro", "paypal", "transferencia", "refund", "reembolso", "compra",
        "billing", "plan", "upgrade", "downgrade", "cancelar suscrip",
        "renovar", "renovacion", "renovación", "promo", "descuento",
        "partnership", "patrocinio", "colaboracion", "colaboración",
    ],
    "role_owner": [
        # Estrategico / casos extremos / decisiones de proyecto
        "abuso de poder", "corrupcion", "corrupción",
        "denuncia contra staff", "denuncia contra admin",
        "denuncia a un admin", "denuncia a admin", "leak", "filtracion",
        "filtración", "amenaza grave", "decision importante",
        "decisión importante", "asunto legal", "legal", "demanda",
        "doxx confirmado", "owner", "estrategia", "vision del proyecto",
        "visión del proyecto", "rumbo del proyecto",
    ],
    "role_senior": [
        # Moderacion compleja
        "denuncia", "reincidente", "reincidencia", "ban permanente",
        "multiple", "múltiple", "investigacion", "investigación",
        "caso grave", "raid", "alt account", "evasion", "evasión",
        "discusion compleja", "discusión compleja", "moderacion delicada",
        "moderación delicada", "screenshare conflictivo",
    ],
}

ROLE_LABELS = {
    "role_owner":  "👑 Owner",
    "role_admin":  "🛡 Admin",
    "role_dev":    "💻 Developer",
    "role_senior": "⚖ Senior Staff",
    "role_staff":  "🔍 Staff",
}


def _classify_escalation(text: str) -> tuple[str, list[str]]:
    """Clasifica el motivo y devuelve (role_key, lista_de_keywords_detectadas).

    Si no detecta nada, default = role_staff.
    """
    text_low = text.lower()
    scores: dict[str, list[str]] = {}
    for role, kws in ESCALATION_KEYWORDS.items():
        matches = [kw for kw in kws if kw in text_low]
        if matches:
            scores[role] = matches
    if not scores:
        return ("role_staff", [])
    # ganador: el que tenga MAS keywords matchadas. Empate -> orden de prioridad
    priority = ["role_owner", "role_admin", "role_dev", "role_senior", "role_staff"]
    best_role = max(
        scores.keys(),
        key=lambda r: (len(scores[r]), -priority.index(r) if r in priority else 0),
    )
    return (best_role, scores[best_role])


# ═════════════════════════════════════════════════════════════════════════
# Views
# ═════════════════════════════════════════════════════════════════════════

class TicketPanelView(discord.ui.View):
    """Panel publico de creacion de tickets."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.select(
        placeholder="Elige el motivo de tu ticket...",
        custom_id="argus:ticket:cat",
        options=[
            discord.SelectOption(
                label=c["label"], value=c["value"], emoji=c["emoji"]
            )
            for c in TICKET_CATEGORIES
        ],
    )
    async def category_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        cog = interaction.client.get_cog("Tickets")
        if cog:
            await cog._open_ticket(interaction, select.values[0])  # type: ignore[attr-defined]


class FAQResolutionView(discord.ui.View):
    """Botones que aparecen tras una respuesta automatica del FAQ."""

    def __init__(self, ticket_id: int, category: str):
        super().__init__(timeout=None)
        self.ticket_id = ticket_id
        self.category = category

    @discord.ui.button(
        label="Esto soluciona mi problema",
        style=discord.ButtonStyle.success,
        emoji="✅",
        custom_id="argus:ticket:faq:resolved",
    )
    async def resolved(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog = interaction.client.get_cog("Tickets")
        if cog:
            await cog._close_logic(interaction, reason="Resuelto via FAQ automatica")  # type: ignore[attr-defined]

    @discord.ui.button(
        label="Necesito ayuda humana",
        style=discord.ButtonStyle.danger,
        emoji="👤",
        custom_id="argus:ticket:faq:human",
    )
    async def need_human(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        if not guild:
            return
        # Pingear los roles correspondientes a la categoria
        role_ids = _staff_role_ids_for_category(guild, self.category)
        mentions = " ".join(f"<@&{rid}>" for rid in role_ids)
        # Deshabilitar los botones para que no se spamee
        for child in self.children:
            child.disabled = True  # type: ignore[attr-defined]
        await interaction.response.edit_message(view=self)
        if interaction.channel:
            await interaction.channel.send(  # type: ignore[union-attr]
                f"{mentions} <@{interaction.user.id}> necesita ayuda humana, la FAQ no le sirvio.",
            )


class CloseTicketModal(discord.ui.Modal, title="🔒 Cerrar ticket"):
    """Modal opcional de razon al cerrar."""
    razon = discord.ui.TextInput(
        label="Razon del cierre (opcional)",
        style=discord.TextStyle.paragraph,
        placeholder="Resuelto, sin actividad, problema solucionado, etc...",
        max_length=300,
        required=False,
    )

    async def on_submit(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("Tickets")
        if cog:
            await cog._close_logic(interaction, reason=str(self.razon.value or ""))  # type: ignore[attr-defined]


class EscalateModal(discord.ui.Modal, title="📈 Escalar ticket"):
    """Modal donde el staff escribe el motivo. La IA decide a quien pingear."""
    motivo = discord.ui.TextInput(
        label="Motivo y contexto",
        style=discord.TextStyle.paragraph,
        placeholder="Describi el problema. La IA va a clasificarlo y elegir el rol mas adecuado a pingear...",
        min_length=15,
        max_length=500,
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("Tickets")
        if cog:
            await cog._escalate_with_ai(interaction, str(self.motivo.value))  # type: ignore[attr-defined]


class CloseTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Cerrar",
        style=discord.ButtonStyle.danger,
        emoji="🔒",
        custom_id="argus:ticket:close",
    )
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CloseTicketModal())

    @discord.ui.button(
        label="Reclamar",
        style=discord.ButtonStyle.primary,
        emoji="🙋",
        custom_id="argus:ticket:claim",
    )
    async def claim_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog = interaction.client.get_cog("Tickets")
        if cog:
            await cog._claim_logic(interaction)  # type: ignore[attr-defined]

    @discord.ui.button(
        label="Escalar (IA)",
        style=discord.ButtonStyle.secondary,
        emoji="📈",
        custom_id="argus:ticket:escalate",
    )
    async def escalate_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not isinstance(interaction.user, discord.Member) or not utils.is_staff(interaction.user):
            await interaction.response.send_message(
                embed=utils.error_embed("Solo staff puede escalar."), ephemeral=True
            )
            return
        await interaction.response.send_modal(EscalateModal())


# ═════════════════════════════════════════════════════════════════════════
# Cog
# ═════════════════════════════════════════════════════════════════════════

class Tickets(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        bot.add_view(TicketPanelView())
        bot.add_view(CloseTicketView())
        # Cache de mensajes del usuario por ticket para evitar disparar FAQ varias veces
        self._faq_fired: set[int] = set()  # channel_ids donde ya disparamos FAQ

    # ── Apertura del ticket ────────────────────────────────────────────
    async def _open_ticket(self, interaction: discord.Interaction, category_value: str) -> None:
        guild = interaction.guild
        if not guild or not isinstance(interaction.user, discord.Member):
            return
        await interaction.response.defer(ephemeral=True)

        category_meta = next(
            (c for c in TICKET_CATEGORIES if c["value"] == category_value),
            {"label": category_value, "emoji": "📋"},
        )

        # 1 ticket activo por usuario
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

        # Crear canal con permisos
        cat = _staff_category(guild)
        all_staff_ids = _all_staff_role_ids(guild)
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, attach_files=True,
                embed_links=True, read_message_history=True,
            ),
        }
        for sid in all_staff_ids:
            role = guild.get_role(sid)
            if role:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True, send_messages=True, manage_messages=True,
                    attach_files=True, embed_links=True, read_message_history=True,
                )

        clean_name = "".join(c if c.isalnum() else "-" for c in interaction.user.name.lower())[:18]
        channel_name = f"{category_meta['emoji']}-{clean_name}"[:32].lstrip("-").rstrip("-")
        try:
            channel = await guild.create_text_channel(
                name=channel_name,
                category=cat,
                overwrites=overwrites,
                topic=f"Ticket de {interaction.user} — {category_meta['label']}",
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

        # Mensaje 1: bienvenida + ping al rol correspondiente
        target_role_ids = _staff_role_ids_for_category(guild, category_value)
        ping = " ".join(f"<@&{rid}>" for rid in target_role_ids if guild.get_role(rid))

        bienvenida = utils.brand_embed(
            title=f"{category_meta['emoji']} Ticket #{ticket_id} — {category_meta['label']}",
            description=(
                f"Hola {interaction.user.mention}, gracias por abrir un ticket.\n\n"
                f"**A quien estoy avisando:** {ping or '(sin staff configurado)'}\n"
                f"**Botones disponibles abajo:**\n"
                f"🔒 **Cerrar** — cierra el ticket (modal con razon)\n"
                f"🙋 **Reclamar** — staff se marca como responsable\n"
                f"📈 **Escalar (IA)** — describe el motivo y la IA elige a quien tagear"
            ),
        )
        await channel.send(content=ping, embed=bienvenida, view=CloseTicketView())

        # Mensaje 2: preguntas guiadas
        guide = GUIDED_QUESTIONS.get(category_value, GUIDED_QUESTIONS["otro"])
        guide_embed = utils.brand_embed(
            title=guide["title"],
            color=0x3498DB,
            description=(
                "Para que el staff pueda ayudarte rapido, **respondé estas preguntas en mensajes "
                "separados** (uno por uno o todos juntos):\n\n"
                + "\n".join(guide["questions"])
                + "\n\n*Mientras escribes, mi IA escanea tu mensaje y te puede sugerir una solucion automatica si tu problema es comun.*"
            ),
        )
        await channel.send(embed=guide_embed)

        await interaction.followup.send(
            embed=utils.success_embed(f"Ticket creado: {channel.mention}"),
            ephemeral=True,
        )

    # ── on_message: FAQ automatica ─────────────────────────────────────
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        if message.channel.id in self._faq_fired:
            return
        # Verificar que sea un canal de ticket activo del propio creador
        with db.cursor() as cur:
            cur.execute(
                "SELECT id, user_id, category FROM bot_tickets WHERE channel_id = %s AND status = 'open'",
                (message.channel.id,),
            )
            ticket = cur.fetchone()
        if not ticket:
            return
        if int(ticket["user_id"]) != message.author.id:
            return  # solo aplicamos FAQ al primer mensaje del CREADOR
        if len(message.content) < 15:
            return  # mensaje muy corto, no escaneamos
        match = _faq_match(ticket["category"], message.content)
        if not match:
            return
        self._faq_fired.add(message.channel.id)
        answer = match["answer"].replace("{panel}", config.PANEL_URL)
        embed = utils.brand_embed(
            title=f"💡 Sugerencia automatica · {match['title']}",
            color=0xFEE75C,
            description=answer + "\n\n*Si esto resuelve tu problema, click en ✅. Si no, click en 👤 para que un humano se haga cargo.*",
        )
        embed.set_footer(text="Argus FAQ · respuesta sugerida por keywords")
        try:
            await message.channel.send(  # type: ignore[union-attr]
                embed=embed,
                view=FAQResolutionView(int(ticket["id"]), ticket["category"]),
            )
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
                "**Categorias y a quien pingean:**\n"
                "🛠 **Soporte tecnico** — Staff\n"
                "💻 **Problema con Argus Scanner** — Developers + Staff\n"
                "💳 **Pago / Cliente Pro** — Admin + Owner\n"
                "🚨 **Denuncia / reporte** — Senior Staff + Staff\n"
                "📋 **Otro** — Staff\n\n"
                "**Solo podes tener 1 ticket abierto a la vez.** "
                "El bot te hace preguntas guiadas y, si tu problema es comun, "
                "te sugiere una solucion automatica antes de involucrar humanos."
            ),
        )
        await interaction.channel.send(embed=embed, view=TicketPanelView())
        await interaction.response.send_message(
            embed=utils.success_embed("Panel publicado."), ephemeral=True
        )

    # ── Logica de Reclamar (boton) ─────────────────────────────────────
    async def _claim_logic(self, interaction: discord.Interaction):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return
        if not utils.is_staff(interaction.user):
            await interaction.response.send_message(
                embed=utils.error_embed("Solo staff puede reclamar tickets."), ephemeral=True
            )
            return
        with db.cursor() as cur:
            cur.execute(
                "SELECT id, user_id FROM bot_tickets WHERE channel_id = %s AND status = 'open'",
                (interaction.channel.id if interaction.channel else 0,),
            )
            tk = cur.fetchone()
        if not tk:
            await interaction.response.send_message(
                embed=utils.error_embed("Este canal no es un ticket activo."), ephemeral=True
            )
            return
        # Verificar si ya esta reclamado
        prev = db.get_setting(interaction.guild.id, f"ticket_claim_{tk['id']}")
        if prev:
            try:
                prev_id = int(prev)
                if prev_id == interaction.user.id:
                    await interaction.response.send_message(
                        embed=utils.warning_embed("Ya reclamaste este ticket."),
                        ephemeral=True,
                    )
                    return
                else:
                    await interaction.response.send_message(
                        embed=utils.warning_embed(
                            f"Este ticket ya fue reclamado por <@{prev_id}>. "
                            f"Si querés tomarlo igual, pedíle al claimer que use `🔒 Cerrar` o que delegue.",
                        ),
                        ephemeral=True,
                    )
                    return
            except ValueError:
                pass
        db.set_setting(interaction.guild.id, f"ticket_claim_{tk['id']}", str(interaction.user.id))
        embed = utils.success_embed(
            f"{interaction.user.mention} se hizo cargo de este ticket. <@{tk['user_id']}>, vas a ser atendido por este staff.",
            title="🙋 Ticket reclamado",
        )
        try:
            await interaction.response.send_message(embed=embed)
        except discord.InteractionResponded:
            await interaction.followup.send(embed=embed)

    # ── Logica de Escalar con IA (modal) ───────────────────────────────
    async def _escalate_with_ai(self, interaction: discord.Interaction, motivo: str):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return
        if not utils.is_staff(interaction.user):
            await interaction.response.send_message(
                embed=utils.error_embed("Solo staff puede escalar."), ephemeral=True
            )
            return
        # Verificar que sea un ticket activo
        with db.cursor() as cur:
            cur.execute(
                "SELECT id, category FROM bot_tickets WHERE channel_id = %s AND status = 'open'",
                (interaction.channel.id if interaction.channel else 0,),
            )
            tk = cur.fetchone()
        if not tk:
            await interaction.response.send_message(
                embed=utils.error_embed("Este canal no es un ticket activo."), ephemeral=True
            )
            return

        # Clasificar con IA
        role_key, matches = _classify_escalation(motivo)
        rid_raw = db.get_setting(interaction.guild.id, role_key)
        # Fallback si el rol elegido no existe en este server
        if not rid_raw and role_key != "role_staff":
            log.info("[Escalate] %s no configurado, fallback a role_staff", role_key)
            role_key = "role_staff"
            rid_raw = db.get_setting(interaction.guild.id, "role_staff")
        if not rid_raw:
            await interaction.response.send_message(
                embed=utils.error_embed("No hay rol staff configurado en este server."),
                ephemeral=True,
            )
            return

        role_label = ROLE_LABELS.get(role_key, role_key)
        if matches:
            ia_explanation = (
                f"**Análisis IA:** {role_label}\n"
                f"**Keywords detectadas:** `{', '.join(matches[:6])}`"
                + (f" *(y {len(matches) - 6} mas)*" if len(matches) > 6 else "")
            )
        else:
            ia_explanation = (
                f"**Análisis IA:** {role_label} *(sin keywords especificas, default por categoria)*"
            )

        embed = utils.warning_embed(
            f"{interaction.user.mention} **escaló** este ticket.\n\n"
            f"**Motivo:**\n>>> {motivo}\n\n"
            f"{ia_explanation}",
            title="📈 Ticket escalado por IA",
        )
        embed.set_footer(text="Argus IA · clasificacion automatica por keywords")
        await interaction.response.send_message(content=f"<@&{rid_raw}>", embed=embed)

    async def _build_transcript(self, channel: discord.TextChannel) -> str:
        lines: list[str] = []
        try:
            async for msg in channel.history(limit=2000, oldest_first=True):
                ts = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
                content = msg.content or ""
                if msg.attachments:
                    content += " " + " ".join(a.url for a in msg.attachments)
                if msg.embeds and not content:
                    content = "[embed: " + (msg.embeds[0].title or "?") + "]"
                lines.append(f"[{ts}] {msg.author}: {content}")
        except Exception:
            log.exception("[Tickets] Error generando transcript")
        return "\n".join(lines)

    async def _close_logic(self, interaction: discord.Interaction, reason: str = ""):
        if not interaction.guild or not isinstance(interaction.channel, discord.TextChannel):
            try:
                await interaction.response.send_message(
                    embed=utils.error_embed("Solo en canales de texto."), ephemeral=True
                )
            except discord.InteractionResponded:
                pass
            return
        with db.cursor() as cur:
            cur.execute(
                "SELECT id, user_id, category, created_at FROM bot_tickets WHERE channel_id = %s AND status = 'open'",
                (interaction.channel.id,),
            )
            ticket = cur.fetchone()
        if not ticket:
            try:
                await interaction.response.send_message(
                    embed=utils.error_embed("Este canal no es un ticket activo."), ephemeral=True
                )
            except discord.InteractionResponded:
                pass
            return

        try:
            await interaction.response.send_message(
                embed=utils.warning_embed("🔒 Cerrando ticket... generando transcript..."),
            )
        except discord.InteractionResponded:
            await interaction.followup.send(
                embed=utils.warning_embed("🔒 Cerrando ticket... generando transcript..."),
            )

        transcript = await self._build_transcript(interaction.channel)

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
        self._faq_fired.discard(interaction.channel.id)
        try:
            await interaction.channel.delete(reason=f"Ticket cerrado por {interaction.user}")
        except discord.Forbidden:
            pass

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
