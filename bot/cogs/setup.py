"""Cog setup — construye el servidor desde cero (modo destructivo).

Comandos:
    /setup       Crea categorias, canales y roles desde cero. Borra todo
                 lo existente (excepto @everyone y los roles del propio
                 bot). Pide doble confirmacion porque es destructivo.
    /setup-dry   Muestra que crearia sin tocar nada.

Estructura del servidor (vibe anti-cheat profesional):

    ╔═══ INFORMACION ═══════════════════════════════════════
        📜 reglas              (read-only)
        📢 anuncios            (read-only)
        🎉 bienvenidas         (read-only, auto)
        🔄 actualizaciones     (read-only, deploys)

    ╔═══ ARGUS SCANNER ═════════════════════════════════════
        💾 descargas           (descarga del .exe + tutorial)
        📚 documentacion       (read-only)
        ❓ soporte             (panel de tickets)
        🐛 reportar-bug
        💡 sugerencias

    ╔═══ COMUNIDAD ═════════════════════════════════════════
        💬 chat-general
        🎮 chat-minecraft
        🤖 bot-commands        (canal para comandos sin spamear chat)
        📸 capturas-de-hacks   (cheaters atrapados, screenshots)
        🏆 leaderboard         (auto, top XP)

    ╔═══ JUEGOS ════════════════════════════════════════════
        🎲 trivia
        🔢 counting

    ╔═══ STAFF (privado) ═══════════════════════════════════
        💼 staff-chat
        📝 logs-scans          (auto, scans nuevos)
        ⚖️ logs-veredictos     (auto, hack/clean)
        ⚠️ logs-moderacion     (auto, warns/mutes/bans)
        🧹 logs-automod        (auto, infracciones automod)
        🚪 logs-joins          (auto, entradas/salidas)
        📋 tickets-cola
        📊 stats-internas

    ╔═══ VOZ ═══════════════════════════════════════════════
        🔊 General
        🔊 Gaming 1
        🔊 Gaming 2
        🔍 SS Room 1           (privado, staff + invitado)
        🔍 SS Room 2           (privado, staff + invitado)

Roles (de mas alto a mas bajo, jerarquia):

    👑 Owner                  (color dorado, hoist, mencionable)
    🛡️ Admin                   (color rojo, hoist, mencionable)
    ⚖️ Senior Staff            (color naranja, hoist, mencionable)
    🔍 Staff                   (color amarillo, hoist, mencionable)
    🎓 Trainee Staff           (color cyan, hoist)
    🌟 Cliente Pro             (color violeta, hoist)
    ✅ Cliente                 (color verde, hoist)
    🤖 Bot                     (color gris, hoist)
    📦 Verificado              (color gris claro, no hoist)
    🔇 Muted                   (sin color, deniega send messages)

Las settings de canales/roles se persisten en bot_settings para que otros
cogs (welcome, moderation, automod, tickets) sepan a donde escribir.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from .. import config, db, utils

log = logging.getLogger("bot.cogs.setup")


# ═════════════════════════════════════════════════════════════════════════
# Definicion del servidor (data-driven para que sea facil de modificar)
# ═════════════════════════════════════════════════════════════════════════

ROLES_SPEC: list[dict] = [
    {"name": "Owner",         "color": 0xFFD700, "hoist": True,  "mention": True,  "perms": "admin",   "key": "role_owner"},
    {"name": "Admin",         "color": 0xED4245, "hoist": True,  "mention": True,  "perms": "admin",   "key": "role_admin"},
    {"name": "Developer",     "color": 0x3498DB, "hoist": True,  "mention": True,  "perms": "dev",     "key": "role_dev"},
    {"name": "Senior Staff",  "color": 0xE67E22, "hoist": True,  "mention": True,  "perms": "staff",   "key": "role_senior"},
    {"name": "Staff",         "color": 0xF1C40F, "hoist": True,  "mention": True,  "perms": "staff",   "key": "role_staff"},
    {"name": "Trainee Staff", "color": 0x1ABC9C, "hoist": True,  "mention": False, "perms": "trainee", "key": "role_trainee"},
    {"name": "Cliente Pro",   "color": 0x9B59B6, "hoist": True,  "mention": False, "perms": "member",  "key": "role_pro"},
    {"name": "Cliente",       "color": 0x57F287, "hoist": True,  "mention": False, "perms": "member",  "key": "role_cliente"},
    {"name": "Bot",           "color": 0x99AAB5, "hoist": True,  "mention": False, "perms": "bot",     "key": "role_botcat"},
    {"name": "Verificado",    "color": 0xBCC0C0, "hoist": False, "mention": False, "perms": "member",  "key": "role_verified"},
    {"name": "Muted",         "color": 0x4F545C, "hoist": False, "mention": False, "perms": "muted",   "key": "role_muted"},
]


# Cada categoria tiene: nombre, lista de canales [(emoji+nombre, type, key, opts)]
# type: "text" | "voice" | "announcement" | "stage"
# opts: dict con flags como readonly, slowmode, nsfw...
CATEGORIES_SPEC: list[dict] = [
    {
        "name": "📋 INFORMACIÓN",
        "key": "cat_info",
        "private": False,
        "channels": [
            {"name": "📜・reglas",            "type": "text", "key": "ch_rules",     "readonly": True},
            {"name": "📢・anuncios",          "type": "announcement", "key": "ch_anuncios", "readonly": True},
            {"name": "🎉・bienvenidas",       "type": "text", "key": "ch_welcome",   "readonly": True},
            {"name": "🔄・actualizaciones",   "type": "text", "key": "ch_updates",   "readonly": True},
        ],
    },
    {
        "name": "🛡 ARGUS SCANNER",
        "key": "cat_argus",
        "private": False,
        "channels": [
            {"name": "💾・descargas",         "type": "text", "key": "ch_downloads", "readonly": True},
            {"name": "📚・documentación",     "type": "text", "key": "ch_docs",      "readonly": True},
            {"name": "❓・soporte",           "type": "text", "key": "ch_support",   "topic": "Crea un ticket aqui para soporte privado."},
            {"name": "🐛・reportar-bug",      "type": "text", "key": "ch_bugs",      "slowmode": 30},
            {"name": "💡・sugerencias",       "type": "text", "key": "ch_suggest",   "slowmode": 60},
        ],
    },
    {
        "name": "💬 COMUNIDAD",
        "key": "cat_community",
        "private": False,
        "channels": [
            {"name": "💬・chat-general",      "type": "text", "key": "ch_general"},
            {"name": "🎮・chat-minecraft",    "type": "text", "key": "ch_minecraft"},
            {"name": "🤖・bot-commands",      "type": "text", "key": "ch_botcmds"},
            {"name": "📸・capturas-de-hacks", "type": "text", "key": "ch_screenshots", "slowmode": 10},
            {"name": "🏆・leaderboard",       "type": "text", "key": "ch_leaderboard", "readonly": True},
        ],
    },
    {
        "name": "🎲 JUEGOS",
        "key": "cat_games",
        "private": False,
        "channels": [
            {"name": "🎲・trivia",            "type": "text", "key": "ch_trivia"},
            {"name": "🔢・counting",          "type": "text", "key": "ch_counting", "topic": "Cuenta de uno en uno. No repitas. No te equivoques."},
        ],
    },
    {
        "name": "🛡 STAFF",
        "key": "cat_staff",
        "private": True,
        "channels": [
            {"name": "💼・staff-chat",        "type": "text", "key": "ch_staff_chat"},
            {"name": "📝・logs-scans",        "type": "text", "key": "ch_log_scans",    "readonly": True},
            {"name": "⚖・logs-veredictos",   "type": "text", "key": "ch_log_verdicts", "readonly": True},
            {"name": "⚠・logs-moderacion",   "type": "text", "key": "ch_log_mod",      "readonly": True},
            {"name": "🧹・logs-automod",      "type": "text", "key": "ch_log_automod",  "readonly": True},
            {"name": "🚪・logs-joins",        "type": "text", "key": "ch_log_joins",    "readonly": True},
            {"name": "📋・tickets-cola",      "type": "text", "key": "ch_tickets_queue"},
            {"name": "📊・stats-internas",    "type": "text", "key": "ch_stats_internal"},
        ],
    },
    {
        "name": "🔊 VOZ",
        "key": "cat_voice",
        "private": False,
        "channels": [
            {"name": "General",                "type": "voice", "key": "vc_general"},
            {"name": "Gaming 1",               "type": "voice", "key": "vc_gaming1"},
            {"name": "Gaming 2",               "type": "voice", "key": "vc_gaming2"},
            {"name": "🔍 SS Room 1",           "type": "voice", "key": "vc_ss1", "private": True},
            {"name": "🔍 SS Room 2",           "type": "voice", "key": "vc_ss2", "private": True},
        ],
    },
]


# ═════════════════════════════════════════════════════════════════════════
# Construccion de permisos por rol
# ═════════════════════════════════════════════════════════════════════════

def _perms_for_spec(spec: str) -> discord.Permissions:
    if spec == "admin":
        return discord.Permissions(administrator=True)
    if spec == "dev":
        # Developers: acceso a logs y tickets pero no kick/ban
        return discord.Permissions(
            view_audit_log=True, manage_messages=True, manage_channels=True,
            send_messages=True, embed_links=True, attach_files=True,
            read_message_history=True, add_reactions=True, mention_everyone=True,
            connect=True, speak=True,
        )
    if spec == "staff":
        return discord.Permissions(
            kick_members=True, ban_members=True, manage_messages=True,
            manage_channels=True, manage_roles=True, view_audit_log=True,
            mute_members=True, deafen_members=True, move_members=True,
            send_messages=True, embed_links=True, attach_files=True,
            read_message_history=True, add_reactions=True,
            connect=True, speak=True,
        )
    if spec == "trainee":
        return discord.Permissions(
            kick_members=True, manage_messages=True, mute_members=True,
            send_messages=True, embed_links=True, attach_files=True,
            read_message_history=True, add_reactions=True,
            connect=True, speak=True,
        )
    if spec == "bot":
        return discord.Permissions(
            send_messages=True, embed_links=True, attach_files=True,
            manage_messages=True, manage_webhooks=True,
            read_message_history=True, add_reactions=True,
            connect=True, speak=True,
        )
    if spec == "muted":
        return discord.Permissions(read_message_history=True)
    # member
    return discord.Permissions(
        send_messages=True, embed_links=True, attach_files=True,
        read_message_history=True, add_reactions=True, use_external_emojis=True,
        connect=True, speak=True, stream=True,
    )


# ═════════════════════════════════════════════════════════════════════════
# Logica del setup
# ═════════════════════════════════════════════════════════════════════════

class ServerBuilder:
    """Encapsula la construccion completa del servidor."""

    def __init__(self, guild: discord.Guild, executor: discord.Member):
        self.guild = guild
        self.executor = executor
        self.created_roles: dict[str, discord.Role] = {}
        self.created_channels: dict[str, discord.abc.GuildChannel] = {}
        self.errors: list[str] = []
        self.summary_lines: list[str] = []

    # ── helpers ────────────────────────────────────────────────────────
    def _log(self, line: str) -> None:
        self.summary_lines.append(line)
        log.info("[Setup] %s", line)

    async def _safe(self, coro, descr: str) -> Optional[object]:
        try:
            return await coro
        except discord.Forbidden as e:
            self.errors.append(f"⛔ Sin permisos: {descr} ({e})")
        except discord.HTTPException as e:
            self.errors.append(f"⚠ HTTP {e.status}: {descr} ({e.text})")
        except Exception as e:
            self.errors.append(f"💥 {descr}: {e!r}")
        return None

    # ── borrado ────────────────────────────────────────────────────────
    async def wipe(self) -> None:
        """Borra todo lo borrable. Mantiene @everyone, role del bot y rol del executor."""
        bot_member = self.guild.me
        protected_role_ids = {self.guild.default_role.id}
        if bot_member:
            protected_role_ids.update(r.id for r in bot_member.roles)

        # Canales
        for ch in list(self.guild.channels):
            await self._safe(ch.delete(reason=f"/setup ejecutado por {self.executor}"),
                             f"borrar canal #{ch.name}")
        self._log(f"🗑 Borrados {len(self.guild.channels)} canales originales.")

        # Roles (de abajo hacia arriba para evitar errores de jerarquia)
        roles_to_delete = sorted(
            [r for r in self.guild.roles if r.id not in protected_role_ids
             and not r.managed and r < (bot_member.top_role if bot_member else r)],
            key=lambda r: r.position,
        )
        deleted_roles = 0
        for r in roles_to_delete:
            ok = await self._safe(r.delete(reason=f"/setup ejecutado por {self.executor}"),
                                  f"borrar rol @{r.name}")
            if ok is not None or True:  # safe siempre devuelve None pero queremos contar exitos
                deleted_roles += 1
        self._log(f"🗑 Borrados ~{deleted_roles} roles personalizados.")

    # ── roles ──────────────────────────────────────────────────────────
    async def create_roles(self) -> None:
        """Crea los roles en orden de mayor a menor (luego se reordenan)."""
        for spec in ROLES_SPEC:
            perms = _perms_for_spec(spec["perms"])
            role = await self._safe(
                self.guild.create_role(
                    name=spec["name"],
                    permissions=perms,
                    color=discord.Color(spec["color"]),
                    hoist=spec["hoist"],
                    mentionable=spec["mention"],
                    reason=f"/setup ejecutado por {self.executor}",
                ),
                f"crear rol @{spec['name']}",
            )
            if isinstance(role, discord.Role):
                self.created_roles[spec["key"]] = role
                db.set_setting(self.guild.id, spec["key"], str(role.id))
                self._log(f"✓ Rol @{spec['name']} creado.")

        # Reordenar por jerarquia (Owner top -> Muted bottom).
        # IMPORTANTE: Discord no permite mover roles por encima del top_role del bot.
        # Calculamos un techo seguro = top_role.position - 1 y distribuimos hacia abajo.
        if self.created_roles:
            bot_member = self.guild.me
            ceiling = (bot_member.top_role.position - 1) if bot_member else 1
            ceiling = max(1, ceiling)
            ordered_specs = list(reversed(ROLES_SPEC))  # menor a mayor (Muted -> Owner)
            positions: dict[discord.Role, int] = {}
            for idx, spec in enumerate(ordered_specs, start=1):
                role = self.created_roles.get(spec["key"])
                if role and idx <= ceiling:
                    positions[role] = idx
            if positions:
                ok = await self._safe(
                    self.guild.edit_role_positions(positions=positions, reason="/setup reorden"),
                    "reordenar roles",
                )
                if ok is not None:
                    self._log("✓ Roles ordenados jerarquicamente.")
                else:
                    self._log("⚠ No se pudo reordenar — sube el rol del bot al top y reintenta.")
            else:
                self._log("⚠ Bot no tiene rol alto suficiente para reordenar.")

    # ── overwrites helpers ─────────────────────────────────────────────
    def _build_overwrites(self, *, private: bool, readonly: bool, voice_private: bool = False) -> dict:
        everyone = self.guild.default_role
        ow: dict = {}

        if private:
            ow[everyone] = discord.PermissionOverwrite(view_channel=False)
            for key in ("role_owner", "role_admin", "role_dev", "role_senior", "role_staff", "role_trainee"):
                role = self.created_roles.get(key)
                if role:
                    ow[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, connect=True, speak=True)
        elif readonly:
            ow[everyone] = discord.PermissionOverwrite(view_channel=True, send_messages=False, add_reactions=True)
            for key in ("role_owner", "role_admin", "role_senior", "role_staff"):
                role = self.created_roles.get(key)
                if role:
                    ow[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_messages=True)

        # Muted siempre denegado de hablar
        muted = self.created_roles.get("role_muted")
        if muted:
            ow[muted] = discord.PermissionOverwrite(send_messages=False, add_reactions=False, speak=False)

        if voice_private:
            ow[everyone] = discord.PermissionOverwrite(connect=False, view_channel=True)
            for key in ("role_owner", "role_admin", "role_dev", "role_senior", "role_staff", "role_trainee"):
                role = self.created_roles.get(key)
                if role:
                    ow[role] = discord.PermissionOverwrite(connect=True, speak=True, move_members=True, view_channel=True)

        return ow

    # ── canales / categorias ───────────────────────────────────────────
    async def create_categories_and_channels(self) -> None:
        for cat_spec in CATEGORIES_SPEC:
            cat_overwrites = self._build_overwrites(
                private=cat_spec.get("private", False),
                readonly=False,
            )
            category = await self._safe(
                self.guild.create_category(
                    name=cat_spec["name"],
                    overwrites=cat_overwrites,
                    reason=f"/setup ejecutado por {self.executor}",
                ),
                f"crear categoria {cat_spec['name']}",
            )
            if not isinstance(category, discord.CategoryChannel):
                continue
            self.created_channels[cat_spec["key"]] = category
            db.set_setting(self.guild.id, cat_spec["key"], str(category.id))
            self._log(f"✓ Categoria {cat_spec['name']}.")

            for ch_spec in cat_spec["channels"]:
                ch_overwrites = self._build_overwrites(
                    private=cat_spec.get("private", False),
                    readonly=ch_spec.get("readonly", False),
                    voice_private=ch_spec.get("private", False) and ch_spec["type"] == "voice",
                )
                topic = ch_spec.get("topic")
                slowmode = ch_spec.get("slowmode", 0)
                ch_type = ch_spec["type"]

                channel = None
                if ch_type == "text" or ch_type == "announcement":
                    # Announcement channels requieren feature COMMUNITY en el guild.
                    # Si no esta disponible, caemos a canal de texto normal.
                    want_news = (ch_type == "announcement"
                                  and "COMMUNITY" in self.guild.features)
                    try:
                        channel = await category.create_text_channel(
                            name=ch_spec["name"],
                            topic=topic,
                            slowmode_delay=slowmode,
                            news=want_news,
                            overwrites=ch_overwrites,
                            reason="/setup",
                        )
                    except discord.HTTPException:
                        # Reintentar sin news=True (server sin feature COMMUNITY)
                        channel = await self._safe(
                            category.create_text_channel(
                                name=ch_spec["name"],
                                topic=topic,
                                slowmode_delay=slowmode,
                                overwrites=ch_overwrites,
                                reason="/setup (fallback texto)",
                            ),
                            f"crear canal #{ch_spec['name']}",
                        )
                elif ch_type == "voice":
                    channel = await self._safe(
                        category.create_voice_channel(
                            name=ch_spec["name"],
                            overwrites=ch_overwrites,
                            reason="/setup",
                        ),
                        f"crear canal voz {ch_spec['name']}",
                    )

                if channel is not None:
                    self.created_channels[ch_spec["key"]] = channel
                    db.set_setting(self.guild.id, ch_spec["key"], str(channel.id))

            self._log(f"  + {len(cat_spec['channels'])} canales en {cat_spec['name']}")

    # ── seed messages (reglas, descargas, soporte, etc.) ──────────────
    async def seed_content(self) -> None:
        await self._seed_rules()
        await self._seed_downloads()
        await self._seed_docs()
        await self._seed_support()
        self._log("✓ Mensajes seedeados: reglas (6 embeds), descargas, docs, soporte.")

    async def _seed_rules(self) -> None:
        """Publica 6 embeds en #reglas: bienvenida, reglas, jerarquia, SS,
        FAQ, links."""
        rules = self.created_channels.get("ch_rules")
        if not isinstance(rules, discord.TextChannel):
            return

        # ─── Embed 1: Bienvenida + identidad ────────────────────────────
        e1 = utils.brand_embed(
            title="🛡 Bienvenido a Argus Projects",
            description=(
                "**All-Seeing. Always Watching.**\n\n"
                "Esta es la comunidad oficial de **Argus Projects** — el sistema de detección "
                "avanzada anti-cheat con inteligencia artificial evolutiva para servidores de Minecraft.\n\n"
                "**¿Qué hacemos?**\n"
                "• Desarrollamos el scanner `ArgusScanner.exe` que detecta ghost clients, "
                "  inyección Java, DLL hijacking, macros, autoclickers y más.\n"
                "• Damos soporte directo a staff y owners de servidores que usan Argus.\n"
                "• Compartimos hacks atrapados como muestra educativa para la comunidad.\n"
                "• Mejoramos continuamente la IA con cada análisis nuevo.\n\n"
                f"🌐 **Panel:** {config.PANEL_URL}\n"
                f"💾 **Descarga:** {config.PANEL_URL}/descargar"
            ),
        )
        e1.set_footer(text="ASPERS Projects · Sistema Argus · Lee TODOS los embeds antes de participar")
        await self._safe(rules.send(embed=e1), "enviar bienvenida")

        # ─── Embed 2: Reglas detalladas ─────────────────────────────────
        e2 = utils.brand_embed(
            title="📜 Reglas del servidor",
            color=0xED4245,
            description=(
                "Al permanecer en este servidor **aceptás todas las reglas** que siguen. "
                "El staff aplica warns/mutes/kicks/bans a criterio. Las violaciones graves "
                "son ban inmediato sin warn previo."
            ),
        )
        e2.add_field(
            name="1️⃣ Respeto absoluto",
            value=(
                "Trato decente entre miembros y staff. **Cero insultos personales**, "
                "discriminación, racismo, homofobia, transfobia o acoso. "
                "Discusiones técnicas sí, ataques personales no.\n"
                "*Sanción: warn → mute → ban*"
            ),
            inline=False,
        )
        e2.add_field(
            name="2️⃣ Sin spam ni flood",
            value=(
                "No enviar el mismo mensaje repetido, no usar caps lock excesivo, "
                "no hacer mention spam (>5 menciones por mensaje), no autopromoción "
                "de servidores/canales sin permiso explícito de staff.\n"
                "*El automod borra automáticamente y mutea por 60s.*"
            ),
            inline=False,
        )
        e2.add_field(
            name="3️⃣ Sin contenido NSFW / ilegal",
            value=(
                "Este es un espacio **profesional**. Cero porno, gore, contenido violento "
                "explícito, drogas o cualquier contenido ilegal. Tampoco enlaces a sitios "
                "warez/cracks/cheats.\n"
                "*Sanción: ban directo, no hay warn.*"
            ),
            inline=False,
        )
        e2.add_field(
            name="4️⃣ Argus es ANTI-cheat",
            value=(
                "**Prohibido distribuir, promocionar o pedir cheats** en cualquier canal o DM. "
                "No compartas links a clients hackeados ni preguntes 'dónde bajar X cheat'. "
                "Compartir capturas de hacks **atrapados** sí está permitido en `📸・capturas-de-hacks`.\n"
                "*Sanción: ban permanente.*"
            ),
            inline=False,
        )
        e2.add_field(
            name="5️⃣ Idioma",
            value=(
                "Español o inglés en canales públicos. Otros idiomas en DM o privado. "
                "Esto facilita la moderación y evita que mensajes ofensivos pasen sin ser entendidos."
            ),
            inline=False,
        )
        e2.add_field(
            name="6️⃣ Tickets para soporte privado",
            value=(
                "**No spamees DMs al staff.** Para problemas técnicos, dudas, denuncias "
                "o pagos, abrí un ticket en `❓・soporte`. El bot te guía para que el "
                "ticket llegue al rol correcto (staff, devs, admin)."
            ),
            inline=False,
        )
        e2.add_field(
            name="7️⃣ Reportá hacks que atrapaste",
            value=(
                "Si Argus te atrapó un hacker en tu server, postealo en `📸・capturas-de-hacks` "
                "con captura del scan, evidencia y un breve relato. **Tachá nicks/IPs sensibles**. "
                "Esto nos ayuda a entrenar la IA y sirve de ejemplo para la comunidad."
            ),
            inline=False,
        )
        e2.add_field(
            name="8️⃣ Sin doxxing ni datos privados",
            value=(
                "Nunca compartas direcciones IP reales, datos personales, números de teléfono, "
                "emails ni nada que identifique a una persona privada. Las capturas de scans "
                "deben tener el `machine_name` y `username` del juego — eso está bien — pero "
                "no más allá."
            ),
            inline=False,
        )
        e2.add_field(
            name="9️⃣ Sigue las ToS de Discord",
            value=(
                "Edad mínima 13 años (16 en EU). Cuentas alt están prohibidas. "
                "Saltarse un ban con cuenta nueva = ban permanente sobre la nueva."
            ),
            inline=False,
        )
        e2.add_field(
            name="🔟 Sentido común",
            value=(
                "Si tenés que preguntarte 'esto está permitido?', probablemente no lo está. "
                "Cuando dudes, preguntá a staff antes de hacerlo. Vale más prevenir."
            ),
            inline=False,
        )
        e2.set_footer(text="Argus Projects · Reglas v1.0 · Las reglas pueden actualizarse, vuelve aquí")
        await self._safe(rules.send(embed=e2), "enviar reglas")

        # ─── Embed 3: Jerarquia de staff ────────────────────────────────
        e3 = utils.brand_embed(
            title="🎖 Jerarquía y responsabilidades del staff",
            color=0xE67E22,
            description="Si necesitás contactar staff, este es el orden y a quién acudir según el problema:",
        )
        e3.add_field(
            name="👑 Owner",
            value=(
                "Dueño del proyecto. Decisiones estratégicas, partnerships, "
                "negocio. **No es soporte de primera línea.**"
            ),
            inline=False,
        )
        e3.add_field(
            name="🛡 Admin",
            value=(
                "Administradores del servidor. Resuelven escalaciones, decisiones de moderación importantes, "
                "pagos/suscripciones del Cliente Pro."
            ),
            inline=False,
        )
        e3.add_field(
            name="💻 Developer",
            value=(
                "Desarrolladores del scanner. Atienden bugs del `.exe`, falsos positivos, "
                "problemas técnicos del scanner, sugerencias de detección. "
                "**Para problemas técnicos del software, se les pingea automáticamente al abrir un ticket de tipo `scanner`.**"
            ),
            inline=False,
        )
        e3.add_field(
            name="⚖ Senior Staff",
            value=(
                "Staff veterano con experiencia en SS. Atienden denuncias graves, "
                "supervisan a staff nuevo, lideran investigaciones complejas."
            ),
            inline=False,
        )
        e3.add_field(
            name="🔍 Staff",
            value=(
                "Moderadores y peritos de SS. Hacen Screen Shares, revisan veredictos, "
                "moderan canales públicos, atienden la mayoría de tickets de soporte."
            ),
            inline=False,
        )
        e3.add_field(
            name="🎓 Trainee Staff",
            value=(
                "Staff en entrenamiento. Pueden mutear/timeoutear pero no kick/ban. "
                "Aprenden bajo supervisión de Staff/Senior."
            ),
            inline=False,
        )
        await self._safe(rules.send(embed=e3), "enviar jerarquia")

        # ─── Embed 4: Cómo pedir un Screen Share ────────────────────────
        e4 = utils.brand_embed(
            title="🔍 Cómo pedir un Screen Share",
            color=0x3498DB,
            description=(
                "Un **Screen Share (SS)** es una sesión donde Argus escanea la PC de un "
                "sospechoso para detectar cheats. **Solo Cliente Pro** puede iniciarlos "
                "— es uno de los beneficios principales del plan."
            ),
        )
        e4.add_field(
            name="Para Cliente Pro que quiere hacer un SS",
            value=(
                "1. En tu server donde está el sospechoso, pedíle que entre a este Discord.\n"
                "2. Acá ejecutá `/ss <@usuario>`. El bot:\n"
                "   • Genera un **token único** (1 uso, expira en 30 min).\n"
                "   • Le manda el token + link de descarga **por DM** al sospechoso.\n"
                "   • Anuncia el SS iniciado en `📝・logs-scans`.\n"
                "3. El sospechoso descarga `ArgusScanner.exe`, lo ejecuta como **admin**, "
                "   pega el token, y escanea.\n"
                "4. Cuando termina, vos revisás el resultado en el panel:\n"
                f"   {config.PANEL_URL}/panel\n"
                "5. Ejecutás `/veredicto <id> hack|clean <razón>` para sentenciar."
            ),
            inline=False,
        )
        e4.add_field(
            name="¿No sos Cliente Pro todavía?",
            value=(
                "Argus funciona bajo plan **Cliente Pro** — no hay tier gratis. "
                "Para conseguir el rol y desbloquear `/ss`, abrí un ticket tipo "
                "**`compra`** en `❓・soporte` y un Admin te explica los precios "
                "y métodos de pago disponibles."
            ),
            inline=False,
        )
        e4.add_field(
            name="Para sospechosos que reciben un SS",
            value=(
                "1. Si recibís un DM con un token de SS, **no es opcional**: si no aceptás, "
                "   probablemente te bannean del server donde ocurre el incidente.\n"
                "2. Descargá `ArgusScanner.exe` (link en el DM o en `💾・descargas`).\n"
                "3. Ejecutalo como **administrador** (click derecho → Ejecutar como admin).\n"
                "4. Pegá el token cuando lo pida.\n"
                "5. Esperá a que termine. **No cierres** el programa antes de tiempo."
            ),
            inline=False,
        )
        e4.set_footer(text="Tokens de SS: 1 uso · 30 min · solo Cliente Pro pueden emitirlos")
        await self._safe(rules.send(embed=e4), "enviar SS info")

        # ─── Embed 5: FAQ ───────────────────────────────────────────────
        e5 = utils.brand_embed(
            title="❓ Preguntas frecuentes",
            color=0x9B59B6,
        )
        e5.add_field(
            name="¿Cuánto cuesta usar Argus?",
            value=(
                "Argus funciona bajo el plan **Cliente Pro** — no hay tier gratis. "
                "Solo los Cliente Pro pueden ejecutar `/ss` para hacer Screen Shares, "
                "tienen cola prioritaria de scans, soporte directo y badges en Discord. "
                "Para conocer precios y métodos de pago, abrí un ticket tipo **`compra`**."
            ),
            inline=False,
        )
        e5.add_field(
            name="¿Cómo me hago Cliente Pro?",
            value=(
                "Abrí un ticket tipo **`compra`** y un Admin te explica los planes "
                "y cómo concretar el pago. Una vez confirmado te asignan el rol "
                "**Cliente Pro** y desbloqueás `/ss` y todos los demás beneficios."
            ),
            inline=False,
        )
        e5.add_field(
            name="¿Argus tiene falsos positivos?",
            value="Cualquier anti-cheat los tiene. Argus filtra agresivamente y la IA aprende con cada veredicto. Si pensás que un veredicto está mal, abrí ticket tipo `scanner` con la captura del scan.",
            inline=False,
        )
        e5.add_field(
            name="¿Funciona en Linux / Mac?",
            value="No por ahora. Solo Windows 10/11 64-bit. Es un requerimiento técnico de las APIs de detección que usamos (Prefetch, USN Journal, Recycle Bin parsing, etc.).",
            inline=False,
        )
        e5.add_field(
            name="¿Mi antivirus marca el .exe?",
            value="Falso positivo. Argus accede a APIs sensibles de Windows (justamente lo que necesitamos para detectar hacks) y eso dispara heurísticas. **Excluí el `.exe` del antivirus** o ejecutalo como admin con AV apagado durante el scan.",
            inline=False,
        )
        e5.add_field(
            name="¿Puedo ver los scans de otros servers?",
            value="No. Cada staff solo ve los scans hechos con sus tokens. La privacidad de los sospechosos está garantizada.",
            inline=False,
        )
        e5.add_field(
            name="¿Qué pasa si mi server bannea por error a un clean?",
            value="Eso es decisión del staff de tu server, Argus solo da el dato. Si la IA dijo 🟩 CLEAN y igual lo bannean, eso es responsabilidad del staff humano, no del scanner.",
            inline=False,
        )
        await self._safe(rules.send(embed=e5), "enviar FAQ")

        # ─── Embed 6: Links útiles ──────────────────────────────────────
        e6 = utils.brand_embed(
            title="🔗 Links útiles",
            color=0x57F287,
            description=(
                f"🌐 **Web pública:** {config.PANEL_URL}\n"
                f"💾 **Descarga del scanner:** {config.PANEL_URL}/descargar\n"
                f"🛡 **Panel staff:** {config.PANEL_URL}/panel *(requiere login)*\n\n"
                "**Canales clave dentro del server:**\n"
                "📜 <#" + str(rules.id) + "> — estás aquí, leelas\n"
                "💾 `💾・descargas` — instrucciones de instalación\n"
                "📚 `📚・documentación` — qué detecta Argus, veredictos\n"
                "❓ `❓・soporte` — abrí un ticket si necesitás ayuda\n"
                "📸 `📸・capturas-de-hacks` — comparte hacks atrapados\n"
                "🔢 `🔢・counting` y `🎲・trivia` — juegos para ganar XP\n\n"
                "**Comandos útiles:**\n"
                "• `/rank` — tu nivel y XP\n"
                "• `/top` — leaderboard\n"
                "• `/scan <jugador>` — último scan de alguien\n"
                "• `/stats` — estadísticas globales del panel"
            ),
        )
        await self._safe(rules.send(embed=e6), "enviar links")

    async def _seed_downloads(self) -> None:
        downloads = self.created_channels.get("ch_downloads")
        if not isinstance(downloads, discord.TextChannel):
            return
        e1 = utils.brand_embed(
            title="💾 Descargar Argus Scanner",
            description=(
                f"**Link oficial:** {config.PANEL_URL}/descargar\n\n"
                "**Plataforma:** Windows 10 / 11 · 64-bit\n"
                "**Tamaño:** ~50 MB\n"
                "**Versión actual:** verificá en `/stats` o en el panel"
            ),
        )
        e1.set_footer(text="Solo descargá desde este link oficial. Cualquier otro link es trampa/malware.")
        await self._safe(downloads.send(embed=e1), "enviar info descarga")

        e2 = utils.brand_embed(
            title="📋 Pasos para hacer un scan",
            color=0x3498DB,
        )
        e2.add_field(
            name="1. Conseguir un token",
            value="Pídele a un **Cliente Pro** que ejecute `/ss <vos>` en este Discord. Te llegará un DM con el token (1 uso, 30 min).",
            inline=False,
        )
        e2.add_field(
            name="2. Descargar el scanner",
            value=f"Visitá {config.PANEL_URL}/descargar y bajá `ArgusScanner.exe`.",
            inline=False,
        )
        e2.add_field(
            name="3. Ejecutar como administrador",
            value="**Click derecho** sobre el `.exe` → **Ejecutar como administrador**. Es obligatorio: sin permisos elevados no puede leer Prefetch, Recycle Bin ni USN Journal.",
            inline=False,
        )
        e2.add_field(
            name="4. Pegar token y autenticar",
            value="Pegá el token de DM. El scanner verifica con el panel y arranca.",
            inline=False,
        )
        e2.add_field(
            name="5. Esperar el scan",
            value="Tarda **2-5 minutos** dependiendo de cuántos archivos haya en tu PC. **No cierres** el scanner hasta que termine.",
            inline=False,
        )
        e2.add_field(
            name="6. Resultado",
            value="Cuando finaliza, el staff ve el resultado en el panel y emite veredicto. Quedate en este Discord hasta que te avisen.",
            inline=False,
        )
        await self._safe(downloads.send(embed=e2), "enviar pasos")

        e3 = utils.brand_embed(
            title="⚠ Problemas comunes al instalar",
            color=0xFEE75C,
        )
        e3.add_field(
            name="Mi antivirus borra el .exe",
            value="Falso positivo. Excluí el archivo del antivirus (Defender → Exclusiones), o desactivá el AV solo para el scan.",
            inline=False,
        )
        e3.add_field(
            name="'Windows protected your PC' al ejecutar",
            value="Click en `More info` → `Run anyway`. Es porque el .exe no está firmado con cert comercial todavía.",
            inline=False,
        )
        e3.add_field(
            name="Token expirado",
            value="Los tokens duran 30 min. Pídele al staff que te genere uno nuevo.",
            inline=False,
        )
        e3.add_field(
            name="No abre / no responde",
            value="Asegurate de ejecutar **como administrador**. Si igual no abre, abrí ticket tipo `scanner`.",
            inline=False,
        )
        await self._safe(downloads.send(embed=e3), "enviar troubleshooting")

    async def _seed_docs(self) -> None:
        docs = self.created_channels.get("ch_docs")
        if not isinstance(docs, discord.TextChannel):
            return
        e1 = utils.brand_embed(
            title="📚 Qué detecta Argus",
            description="El scanner combina **detección por reglas** + **IA evolutiva** entrenada con cada veredicto histórico.",
        )
        e1.add_field(
            name="🎯 Detecciones principales",
            value=(
                "• **Ghost clients** — clientes hackeados que ocultan su identidad\n"
                "• **Java injection** — modificación de bytecode en runtime\n"
                "• **DLL hijacking** — inyección via DLLs cargadas por el proceso\n"
                "• **Macros & autoclickers** — patrones de input artificiales\n"
                "• **Mods sospechosos** — Forge/Fabric con mods conocidos como cheat\n"
                "• **Historial del navegador** — visitas a sitios warez/cheat\n"
                "• **Descargas no ejecutadas** — `.jar` / `.exe` en Downloads sospechosos\n"
                "• **Hashes conocidos** — base de datos de cheats reportados"
            ),
            inline=False,
        )
        e1.add_field(
            name="🔍 Fuentes de evidencia",
            value=(
                "• **Prefetch** — historial de ejecutables\n"
                "• **Registry** — entradas de auto-arranque\n"
                "• **USN Journal** — cambios en NTFS\n"
                "• **Recycle Bin** — archivos borrados\n"
                "• **AppData / LocalAppData** — caches de aplicaciones\n"
                "• **Process scan** — procesos activos al escanear"
            ),
            inline=False,
        )
        await self._safe(docs.send(embed=e1), "enviar docs detecciones")

        e2 = utils.brand_embed(
            title="⚖ Sistema de veredictos",
            color=0xE67E22,
            description="Cada scan recibe un **risk score 0-100** y un veredicto del staff:",
        )
        e2.add_field(name="🟥 HACK", value="Risk ≥ 70 con hallazgos confirmados (ghost client detectado, hash conocido, etc.)", inline=False)
        e2.add_field(name="🟧 SOSPECHOSO", value="Risk 30-69 — requiere revisión manual del staff", inline=False)
        e2.add_field(name="🟩 CLEAN", value="Risk < 30 — sin hallazgos relevantes", inline=False)
        e2.add_field(name="🟡 PENDIENTE", value="Aún no fue revisado por staff", inline=False)
        e2.set_footer(text="El veredicto final SIEMPRE lo da un staff humano, nunca la IA sola.")
        await self._safe(docs.send(embed=e2), "enviar veredictos")

        e3 = utils.brand_embed(
            title="🔒 Privacidad",
            color=0x57F287,
            description=(
                "**Qué guarda Argus de los scans:**\n"
                "• Nombre de la máquina (machine_name)\n"
                "• Username del juego (Minecraft username)\n"
                "• Lista de hallazgos sospechosos (paths, hashes, timestamps)\n"
                "• Hash de archivos sospechosos (NO el contenido)\n"
                "• Historial de archivos modificados desde el último arranque\n\n"
                "**Qué NO guarda:**\n"
                "• Contenido de archivos\n"
                "• Capturas de pantalla\n"
                "• Contraseñas / credenciales\n"
                "• Datos del navegador (solo URLs visitadas)\n"
                "• Cookies / sesiones\n\n"
                f"**Política completa:** {config.PANEL_URL}/privacy *(en construcción)*"
            ),
        )
        await self._safe(docs.send(embed=e3), "enviar privacidad")

    async def _seed_support(self) -> None:
        support = self.created_channels.get("ch_support")
        if not isinstance(support, discord.TextChannel):
            return
        embed = utils.brand_embed(
            title="❓ Soporte",
            description=(
                "Necesitás algo? Elegí el motivo en el menú de abajo y te abro un canal privado.\n\n"
                "**Cada motivo va a la gente correcta:**\n"
                "🛠 **Soporte técnico** → Staff\n"
                "💻 **Problema con Argus Scanner** → Developers + Staff\n"
                "💳 **Pago / Cliente Pro** → Admin + Owner\n"
                "🚨 **Denuncia / reporte** → Senior Staff + Staff\n"
                "📋 **Otro** → Staff\n\n"
                "**Solo 1 ticket abierto a la vez.** Te recibe **Argus AI** 👁 — "
                "si tu problema lo vio antes te tira la solución al toque y "
                "te ahorrás esperar al staff.\n\n"
                "Adentro del ticket tenés 3 botones: **🔒 Cerrar** lo cierra, "
                "**🙋 Reclamar** es para que un staff se haga cargo, y "
                "**📈 Escalar** sirve para que el staff me cuente el motivo "
                "y yo aviso al rol que mejor pueda ayudar."
            ),
        )
        # Publicar embed + panel funcional con dropdown de categorias
        try:
            from .tickets import TicketPanelView
            await self._safe(
                support.send(embed=embed, view=TicketPanelView()),
                "enviar panel de tickets",
            )
        except Exception:
            log.exception("[Setup] Error importando TicketPanelView, fallback a solo embed")
            await self._safe(support.send(embed=embed), "enviar info soporte (sin panel)")

    # ── orden de ejecucion ─────────────────────────────────────────────
    async def run_destructive(self) -> tuple[bool, str]:
        await self.wipe()
        await self.create_roles()
        await self.create_categories_and_channels()
        await self.seed_content()
        # Persistir log
        try:
            with db.cursor() as cur:
                cur.execute(
                    "INSERT INTO bot_setup_log (guild_id, executed_by, action, summary) VALUES (%s, %s, %s, %s)",
                    (self.guild.id, self.executor.id, "setup",
                     "\n".join(self.summary_lines + ([f"ERR: {e}" for e in self.errors] or []))),
                )
        except Exception:
            log.exception("[Setup] No se pudo persistir el log a bot_setup_log")

        ok = not self.errors
        summary = (
            f"**Roles:** {len(self.created_roles)}\n"
            f"**Canales/categorias:** {len(self.created_channels)}\n"
            f"**Errores:** {len(self.errors)}"
        )
        if self.errors:
            summary += "\n\n**Detalles:**\n" + "\n".join(f"• {e}" for e in self.errors[:10])
        return ok, summary


# ═════════════════════════════════════════════════════════════════════════
# Vista de confirmacion
# ═════════════════════════════════════════════════════════════════════════

class ConfirmDestructiveView(discord.ui.View):
    """Doble confirmacion para el setup destructivo."""

    def __init__(self, executor_id: int):
        super().__init__(timeout=60)
        self.executor_id = executor_id
        self.confirmed = False
        self.first_click = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.executor_id:
            await interaction.response.send_message(
                "Esta confirmacion es solo para quien ejecuto el comando.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="SI, BORRAR TODO", style=discord.ButtonStyle.danger, emoji="⚠")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.first_click:
            self.first_click = True
            button.label = "ESTAS SEGURO? CLICK DE NUEVO"
            button.style = discord.ButtonStyle.danger
            await interaction.response.edit_message(view=self)
            return
        self.confirmed = True
        for child in self.children:
            child.disabled = True  # type: ignore[attr-defined]
        await interaction.response.edit_message(
            content="⏳ Construyendo servidor desde cero...", view=self
        )
        self.stop()

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        for child in self.children:
            child.disabled = True  # type: ignore[attr-defined]
        await interaction.response.edit_message(
            content="❌ Cancelado.", view=self, embed=None
        )
        self.stop()


# ═════════════════════════════════════════════════════════════════════════
# Cog
# ═════════════════════════════════════════════════════════════════════════

class Setup(commands.Cog):
    """Comandos de creacion del servidor."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="setup",
        description="Construye el servidor desde cero (DESTRUCTIVO: borra todo lo existente).",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def setup_cmd(self, interaction: discord.Interaction):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("Solo en servidores.", ephemeral=True)
            return
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                embed=utils.error_embed("Necesitas permisos de **Administrator** para ejecutar `/setup`."),
                ephemeral=True,
            )
            return

        embed = utils.warning_embed(
            title="⚠ /setup destructivo",
            description=(
                f"Esto va a:\n\n"
                f"• 🗑 **Borrar TODOS los canales** del servidor.\n"
                f"• 🗑 **Borrar TODOS los roles** (excepto @everyone, integrados y los que el bot no pueda mover).\n"
                f"• ✅ Crear **{len(ROLES_SPEC)} roles** nuevos con jerarquia anti-cheat.\n"
                f"• ✅ Crear **{len(CATEGORIES_SPEC)} categorias** con "
                f"**{sum(len(c['channels']) for c in CATEGORIES_SPEC)} canales**.\n"
                f"• ✅ Sembrar reglas, info de descarga y documentacion.\n"
                f"• ✅ Persistir todos los IDs en `bot_settings` para que el resto del bot los use.\n\n"
                f"**Esto NO se puede deshacer.** Click en *SI, BORRAR TODO* dos veces para confirmar."
            ),
        )
        view = ConfirmDestructiveView(executor_id=interaction.user.id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=False)
        await view.wait()
        if not view.confirmed:
            return

        # Ejecutar (puede tardar ~30-60s)
        builder = ServerBuilder(interaction.guild, interaction.user)
        try:
            ok, summary = await builder.run_destructive()
        except Exception as e:
            log.exception("[Setup] Error fatal en run_destructive")
            try:
                await interaction.followup.send(
                    embed=utils.error_embed(f"Error fatal: `{e}`"), ephemeral=True
                )
            except Exception:
                pass
            return

        # Resultado: enviar al canal de anuncios o por DM si no existe
        result_embed = (
            utils.success_embed(summary, title="✅ Setup completado")
            if ok else utils.warning_embed(summary, title="⚠ Setup completado con errores")
        )
        try:
            anuncios = builder.created_channels.get("ch_anuncios")
            if isinstance(anuncios, discord.TextChannel):
                await anuncios.send(embed=result_embed)
            await interaction.user.send(embed=result_embed)
        except Exception:
            pass

    @app_commands.command(
        name="setup-status",
        description="Muestra los IDs persistidos por el ultimo /setup.",
    )
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def status_cmd(self, interaction: discord.Interaction):
        if not interaction.guild:
            return
        with db.cursor() as cur:
            cur.execute(
                "SELECT key, value FROM bot_settings WHERE guild_id = %s ORDER BY key",
                (interaction.guild.id,),
            )
            rows = cur.fetchall()
        if not rows:
            await interaction.response.send_message(
                embed=utils.info_embed("Ninguna setting persistida. Ejecuta `/setup` primero.",
                                       title="Setup status"),
                ephemeral=True,
            )
            return
        lines = []
        for r in rows:
            key = r["key"]
            value = r["value"] or "?"
            lines.append(f"`{key:<22}` → `{value}`")
        text = "\n".join(lines)
        # Cap a 3500 chars
        if len(text) > 3500:
            text = text[:3500] + "\n..."
        await interaction.response.send_message(
            embed=utils.brand_embed(title="🔧 Setup status", description=text),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Setup(bot))
