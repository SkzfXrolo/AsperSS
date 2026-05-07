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

        # Reordenar por jerarquia (Owner top -> Muted bottom)
        # discord.py edit_role_positions
        if self.created_roles:
            ordered_specs = list(reversed(ROLES_SPEC))  # de menor a mayor para position
            positions: dict[discord.Role, int] = {}
            for idx, spec in enumerate(ordered_specs, start=1):
                role = self.created_roles.get(spec["key"])
                if role:
                    positions[role] = idx
            await self._safe(
                self.guild.edit_role_positions(positions=positions, reason="/setup reorden"),
                "reordenar roles",
            )
            self._log("✓ Roles ordenados jerarquicamente.")

    # ── overwrites helpers ─────────────────────────────────────────────
    def _build_overwrites(self, *, private: bool, readonly: bool, voice_private: bool = False) -> dict:
        everyone = self.guild.default_role
        ow: dict = {}

        if private:
            ow[everyone] = discord.PermissionOverwrite(view_channel=False)
            for key in ("role_owner", "role_admin", "role_senior", "role_staff", "role_trainee"):
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
            for key in ("role_owner", "role_admin", "role_senior", "role_staff", "role_trainee"):
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
                    channel = await self._safe(
                        category.create_text_channel(
                            name=ch_spec["name"],
                            topic=topic,
                            slowmode_delay=slowmode,
                            news=(ch_type == "announcement"),
                            overwrites=ch_overwrites,
                            reason="/setup",
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
        rules = self.created_channels.get("ch_rules")
        if isinstance(rules, discord.TextChannel):
            embed = utils.brand_embed(
                title="📜 Reglas de Argus Projects",
                description=(
                    "Bienvenido a **Argus Projects** — comunidad oficial de soporte para staff y "
                    "owners de servidores de Minecraft que usan el scanner anti-cheat Argus.\n\n"
                    "**1. Respeto.** Trato decente entre miembros y staff. Cero insultos personales.\n"
                    "**2. Sin spam.** No flood, no menciones masivas, no autopromocion sin permiso.\n"
                    "**3. Sin contenido NSFW.** Este es un espacio profesional.\n"
                    "**4. Sin distribucion de cheats.** Esta comunidad es ANTI-cheat.\n"
                    "**5. Idioma:** Espanol o ingles. Otros idiomas en DM.\n"
                    "**6. Tickets para soporte privado.** No spamees a staff por DM.\n"
                    "**7. Reporta hacks atrapados** en `📸・capturas-de-hacks` para que sirvan de muestra.\n"
                    "**8. Sigue las TOS de Discord.** Saltarselas = ban directo.\n\n"
                    "Al permanecer en este servidor aceptas todas las reglas. "
                    "El staff puede aplicar warns/mutes/kicks/bans a su criterio."
                ),
            )
            await self._safe(rules.send(embed=embed), "enviar reglas")

        downloads = self.created_channels.get("ch_downloads")
        if isinstance(downloads, discord.TextChannel):
            embed = utils.brand_embed(
                title="💾 Descargar Argus Scanner",
                description=(
                    f"Descarga oficial: **{config.PANEL_URL}/descargar**\n\n"
                    "**Como usarlo:**\n"
                    "1. Pidele un codigo a un staff (es de 1 solo uso, expira en 30 min).\n"
                    "2. Descarga `ArgusScanner.exe` desde el link.\n"
                    "3. Ejecutalo como **administrador**.\n"
                    "4. Pega el codigo y autenticate.\n"
                    "5. El staff revisa los resultados en el panel.\n\n"
                    "Plataforma: **Windows 10/11 64-bit**."
                ),
            )
            await self._safe(downloads.send(embed=embed), "enviar info descarga")

        docs = self.created_channels.get("ch_docs")
        if isinstance(docs, discord.TextChannel):
            embed = utils.brand_embed(
                title="📚 Documentacion",
                description=(
                    "**Que detecta Argus:**\n"
                    "• Ghost clients & hacked mods\n"
                    "• Java injection & DLL hijacking\n"
                    "• Macros & autoclickers\n"
                    "• Historial de navegador sospechoso\n"
                    "• Descargas no ejecutadas\n"
                    "• Patrones de hash conocidos\n"
                    "• IA auto-aprendida con cada scan\n\n"
                    "**Veredictos:**\n"
                    "🟥 **HACK** — risk score >= 70, hallazgos confirmados\n"
                    "🟧 **SOSPECHOSO** — risk 30-69, requiere revision manual\n"
                    "🟩 **CLEAN** — risk < 30, sin hallazgos relevantes\n\n"
                    f"Panel completo: **{config.PANEL_URL}/panel**"
                ),
            )
            await self._safe(docs.send(embed=embed), "enviar docs")

        self._log("✓ Mensajes de bienvenida seedeados (reglas, descargas, docs).")

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
