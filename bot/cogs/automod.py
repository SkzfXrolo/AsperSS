"""Cog automod — proteccion automatica del servidor.

Reglas activas (por defecto, configurables via /automod-config):
    spam       — >5 mensajes en 5s del mismo usuario.
    link       — links no permitidos en canales no-staff (excepto Discord/YouTube).
    invite     — invitaciones a otros servidores Discord.
    mention    — >5 menciones en un mismo mensaje.
    caps       — mensajes con >70% mayusculas (y minimo 12 chars).
    word       — palabras prohibidas (lista filtrada por guild).
    raid       — >5 joins en 10s -> activa raid mode (lockdown).

Cuando una regla se dispara:
    1. Borra el mensaje si aplica.
    2. Aplica timeout corto (1 min) si es repetidor.
    3. Loguea infraccion en bot_automod_violations.
    4. Postea embed a #logs-automod.
    5. Si el mismo usuario suma >=3 infracciones en 10 minutos -> mute 1h
       automatico (escalada).

Comandos:
    /automod-config <regla> on|off    Activa/desactiva una regla.
    /automod-status                   Muestra estado actual.
    /automod-add-word <palabra>       Anade palabra al filtro.
    /automod-remove-word <palabra>    Quita palabra del filtro.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging
import re
import time
from collections import defaultdict, deque
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from .. import config, db, utils

log = logging.getLogger("bot.cogs.automod")


# ── Defaults ──────────────────────────────────────────────────────────────
DEFAULT_RULES = {
    "spam":    True,
    "link":    True,
    "invite":  True,
    "mention": True,
    "caps":    True,
    "word":    True,
    "raid":    True,
}

SPAM_THRESHOLD_MSGS = 5
SPAM_WINDOW_SECONDS = 5
MAX_MENTIONS = 5
CAPS_MIN_LEN = 12
CAPS_THRESHOLD = 0.70
RAID_THRESHOLD_JOINS = 5
RAID_WINDOW_SECONDS = 10
ESCALATION_THRESHOLD = 3
ESCALATION_WINDOW_SECONDS = 600
ESCALATION_MUTE = 3600  # 1h

INVITE_RE = re.compile(r"(?:discord\.(?:gg|com/invite)|discord(?:app)?\.com/invite)/[a-zA-Z0-9-]+", re.I)
URL_RE = re.compile(r"https?://[^\s<>]+", re.I)
ALLOWED_DOMAINS = {
    "discord.com", "discord.gg", "discordapp.com",
    "youtube.com", "youtu.be",
    "github.com", "githubusercontent.com",
    "asperss.onrender.com",  # nuestro propio panel
    "minecraft.net", "mojang.com",
}


def _get_rules(guild_id: int) -> dict[str, bool]:
    raw = db.get_setting(guild_id, "automod_rules")
    if not raw:
        return DEFAULT_RULES.copy()
    try:
        d = json.loads(raw)
        return {**DEFAULT_RULES, **{k: bool(v) for k, v in d.items()}}
    except Exception:
        return DEFAULT_RULES.copy()


def _set_rules(guild_id: int, rules: dict[str, bool]) -> None:
    db.set_setting(guild_id, "automod_rules", json.dumps(rules))


def _get_word_filter(guild_id: int) -> set[str]:
    raw = db.get_setting(guild_id, "automod_words") or ""
    return {w.strip().lower() for w in raw.split(",") if w.strip()}


def _set_word_filter(guild_id: int, words: set[str]) -> None:
    db.set_setting(guild_id, "automod_words", ",".join(sorted(words)))


def _get_log_channel(guild: discord.Guild) -> Optional[discord.TextChannel]:
    cid = db.get_setting(guild.id, "ch_log_automod")
    if not cid:
        return None
    try:
        ch = guild.get_channel(int(cid))
        return ch if isinstance(ch, discord.TextChannel) else None
    except (TypeError, ValueError):
        return None


def _is_link_allowed(url: str) -> bool:
    """True si el link es de un dominio permitido."""
    m = re.match(r"https?://([^/]+)/?", url, re.I)
    if not m:
        return False
    host = m.group(1).lower()
    # Quitar puerto
    host = host.split(":")[0]
    # Match exacto o subdominio de un permitido
    for allowed in ALLOWED_DOMAINS:
        if host == allowed or host.endswith("." + allowed):
            return True
    return False


# ═════════════════════════════════════════════════════════════════════════
# Cog
# ═════════════════════════════════════════════════════════════════════════

class Automod(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        # Buffer en memoria por (guild_id, user_id) para anti-spam
        self._msg_buffer: dict[tuple[int, int], deque[float]] = defaultdict(lambda: deque(maxlen=20))
        # Buffer de joins para raid
        self._join_buffer: dict[int, deque[float]] = defaultdict(lambda: deque(maxlen=30))
        # Buffer de violaciones para escalada
        self._viol_buffer: dict[tuple[int, int], deque[float]] = defaultdict(lambda: deque(maxlen=20))
        # Lockdown state por guild
        self._lockdowns: set[int] = set()

    # ── helpers ────────────────────────────────────────────────────────
    async def _record_violation(
        self,
        message: discord.Message,
        rule: str,
        details: str,
    ) -> None:
        guild = message.guild
        if not guild:
            return
        # Persistir
        try:
            with db.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO bot_automod_violations
                        (guild_id, user_id, channel_id, rule, content)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (guild.id, message.author.id, message.channel.id,
                     rule, message.content[:500]),
                )
        except Exception:
            log.exception("[Automod] No se pudo persistir violacion")

        # Embed log
        log_ch = _get_log_channel(guild)
        if log_ch:
            embed = utils.brand_embed(
                title=f"🛡 Automod: {rule.upper()}",
                description=(
                    f"**Usuario:** {message.author.mention} (`{message.author.id}`)\n"
                    f"**Canal:** {message.channel.mention}\n"
                    f"**Detalle:** {details}\n"
                    f"**Mensaje:** ```{message.content[:200]}```"
                ),
                color=0xE67E22,
            )
            try:
                await log_ch.send(embed=embed)
            except Exception:
                pass

        # Escalada
        now = time.time()
        key = (guild.id, message.author.id)
        buf = self._viol_buffer[key]
        buf.append(now)
        recent = sum(1 for t in buf if now - t <= ESCALATION_WINDOW_SECONDS)
        if recent >= ESCALATION_THRESHOLD and isinstance(message.author, discord.Member):
            try:
                await message.author.timeout(
                    dt.timedelta(seconds=ESCALATION_MUTE),
                    reason=f"Automod: {recent} infracciones en {ESCALATION_WINDOW_SECONDS//60}min",
                )
                if log_ch:
                    await log_ch.send(embed=utils.warning_embed(
                        f"🔇 Mute automatico **1h** a {message.author.mention} "
                        f"({recent} infracciones recientes).",
                        title="Escalada automod",
                    ))
                # Resetear buffer para no doble-mutear
                buf.clear()
            except discord.Forbidden:
                pass

    # ── on_message ─────────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        if not isinstance(message.author, discord.Member):
            return
        # Staff bypass
        if utils.is_staff(message.author):
            return

        rules = _get_rules(message.guild.id)

        # ── spam ──────────────────────────────────────────────────────
        if rules.get("spam"):
            now = time.time()
            buf = self._msg_buffer[(message.guild.id, message.author.id)]
            buf.append(now)
            recent_count = sum(1 for t in buf if now - t <= SPAM_WINDOW_SECONDS)
            if recent_count > SPAM_THRESHOLD_MSGS:
                try:
                    await message.delete()
                except discord.NotFound:
                    pass
                except discord.Forbidden:
                    pass
                try:
                    await message.author.timeout(
                        dt.timedelta(seconds=60),
                        reason="Automod: spam",
                    )
                except discord.Forbidden:
                    pass
                await self._record_violation(message, "spam",
                                              f"{recent_count} msgs en {SPAM_WINDOW_SECONDS}s")
                return

        # ── invite ────────────────────────────────────────────────────
        if rules.get("invite"):
            if INVITE_RE.search(message.content):
                try:
                    await message.delete()
                except (discord.NotFound, discord.Forbidden):
                    pass
                await self._record_violation(message, "invite",
                                              "Link de invitacion a otro server")
                return

        # ── link ──────────────────────────────────────────────────────
        if rules.get("link"):
            urls = URL_RE.findall(message.content)
            if urls:
                bad = [u for u in urls if not _is_link_allowed(u)]
                if bad:
                    try:
                        await message.delete()
                    except (discord.NotFound, discord.Forbidden):
                        pass
                    await self._record_violation(message, "link",
                                                  f"{len(bad)} link(s) no permitido(s)")
                    return

        # ── mention ───────────────────────────────────────────────────
        if rules.get("mention"):
            if len(message.mentions) + len(message.role_mentions) > MAX_MENTIONS:
                try:
                    await message.delete()
                except (discord.NotFound, discord.Forbidden):
                    pass
                await self._record_violation(message, "mention",
                                              f"{len(message.mentions) + len(message.role_mentions)} menciones")
                return

        # ── caps ──────────────────────────────────────────────────────
        if rules.get("caps") and len(message.content) >= CAPS_MIN_LEN:
            letters = [c for c in message.content if c.isalpha()]
            if letters:
                ratio = sum(1 for c in letters if c.isupper()) / len(letters)
                if ratio >= CAPS_THRESHOLD:
                    try:
                        await message.delete()
                    except (discord.NotFound, discord.Forbidden):
                        pass
                    await self._record_violation(message, "caps",
                                                  f"{int(ratio*100)}% mayusculas")
                    return

        # ── word filter ───────────────────────────────────────────────
        if rules.get("word"):
            words = _get_word_filter(message.guild.id)
            if words:
                low = message.content.lower()
                hit = next((w for w in words if w in low), None)
                if hit:
                    try:
                        await message.delete()
                    except (discord.NotFound, discord.Forbidden):
                        pass
                    await self._record_violation(message, "word",
                                                  f"Palabra prohibida")
                    return

    # ── on_member_join (raid) ──────────────────────────────────────────
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        rules = _get_rules(member.guild.id)
        if not rules.get("raid"):
            return
        now = time.time()
        buf = self._join_buffer[member.guild.id]
        buf.append(now)
        recent = sum(1 for t in buf if now - t <= RAID_WINDOW_SECONDS)
        if recent >= RAID_THRESHOLD_JOINS and member.guild.id not in self._lockdowns:
            await self._enable_raid_lockdown(member.guild, recent)

    async def _enable_raid_lockdown(self, guild: discord.Guild, joins: int) -> None:
        self._lockdowns.add(guild.id)
        log_ch = _get_log_channel(guild)
        if log_ch:
            await log_ch.send(embed=utils.error_embed(
                f"🚨 **RAID DETECTADO** — {joins} joins en {RAID_WINDOW_SECONDS}s.\n\n"
                "El servidor entra en **lockdown automatico**: nuevos miembros no podran "
                "enviar mensajes hasta que un admin ejecute `/automod-raid-off`.",
                title="Lockdown activado",
            ))
        # Quitar permisos de send a @everyone via permission overwrites en cada canal
        for ch in guild.text_channels:
            try:
                await ch.set_permissions(
                    guild.default_role,
                    send_messages=False,
                    reason="Automod raid lockdown",
                )
            except discord.Forbidden:
                continue

    # ── /automod-raid-off ──────────────────────────────────────────────
    @app_commands.command(
        name="automod-raid-off",
        description="Desactiva el lockdown de raid (admin).",
    )
    @app_commands.default_permissions(administrator=True)
    async def raid_off(self, interaction: discord.Interaction):
        guild = interaction.guild
        if not guild:
            return
        if guild.id not in self._lockdowns:
            await interaction.response.send_message(
                embed=utils.info_embed("No hay lockdown activo."),
                ephemeral=True,
            )
            return
        await interaction.response.defer(ephemeral=True)
        for ch in guild.text_channels:
            try:
                await ch.set_permissions(
                    guild.default_role,
                    overwrite=None,
                    reason="Automod raid lockdown OFF",
                )
            except discord.Forbidden:
                continue
        self._lockdowns.discard(guild.id)
        await interaction.followup.send(
            embed=utils.success_embed("Lockdown desactivado."),
            ephemeral=True,
        )

    # ── /automod-config ────────────────────────────────────────────────
    @app_commands.command(
        name="automod-config",
        description="Activa/desactiva una regla de automod.",
    )
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.describe(
        regla="Nombre de la regla",
        estado="on o off",
    )
    @app_commands.choices(
        regla=[
            app_commands.Choice(name=k, value=k) for k in DEFAULT_RULES
        ],
        estado=[
            app_commands.Choice(name="on", value="on"),
            app_commands.Choice(name="off", value="off"),
        ],
    )
    async def automod_config(
        self,
        interaction: discord.Interaction,
        regla: app_commands.Choice[str],
        estado: app_commands.Choice[str],
    ):
        if not interaction.guild:
            return
        rules = _get_rules(interaction.guild.id)
        rules[regla.value] = (estado.value == "on")
        _set_rules(interaction.guild.id, rules)
        await interaction.response.send_message(
            embed=utils.success_embed(
                f"Regla `{regla.value}` -> **{estado.value.upper()}**."
            ),
            ephemeral=True,
        )

    # ── /automod-status ────────────────────────────────────────────────
    @app_commands.command(
        name="automod-status",
        description="Estado actual del automod.",
    )
    @app_commands.default_permissions(manage_guild=True)
    async def automod_status(self, interaction: discord.Interaction):
        if not interaction.guild:
            return
        rules = _get_rules(interaction.guild.id)
        words = _get_word_filter(interaction.guild.id)
        lines = [f"`{k:<8}` → **{'on' if v else 'off'}**" for k, v in rules.items()]
        word_preview = ", ".join(sorted(words)[:20]) if words else "*(vacio)*"
        if len(words) > 20:
            word_preview += f", ... ({len(words)-20} mas)"
        embed = utils.brand_embed(
            title="🛡 Automod — estado",
            description=(
                "\n".join(lines)
                + f"\n\n**Palabras filtradas ({len(words)}):**\n{word_preview}"
                + (f"\n\n🚨 **Lockdown ACTIVO**" if interaction.guild.id in self._lockdowns else "")
            ),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /automod-add-word ──────────────────────────────────────────────
    @app_commands.command(
        name="automod-add-word",
        description="Anade palabra al filtro (case-insensitive, match parcial).",
    )
    @app_commands.default_permissions(manage_guild=True)
    async def add_word(self, interaction: discord.Interaction, palabra: str):
        if not interaction.guild:
            return
        words = _get_word_filter(interaction.guild.id)
        words.add(palabra.lower().strip())
        _set_word_filter(interaction.guild.id, words)
        await interaction.response.send_message(
            embed=utils.success_embed(f"Palabra anadida. Total: **{len(words)}**."),
            ephemeral=True,
        )

    # ── /automod-remove-word ───────────────────────────────────────────
    @app_commands.command(
        name="automod-remove-word",
        description="Quita palabra del filtro.",
    )
    @app_commands.default_permissions(manage_guild=True)
    async def remove_word(self, interaction: discord.Interaction, palabra: str):
        if not interaction.guild:
            return
        words = _get_word_filter(interaction.guild.id)
        target = palabra.lower().strip()
        if target not in words:
            await interaction.response.send_message(
                embed=utils.warning_embed(f"`{target}` no esta en la lista."),
                ephemeral=True,
            )
            return
        words.discard(target)
        _set_word_filter(interaction.guild.id, words)
        await interaction.response.send_message(
            embed=utils.success_embed(f"Palabra removida. Total: **{len(words)}**."),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Automod(bot))
