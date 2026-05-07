"""Utilidades compartidas: embeds con branding, helpers de tiempo, parsers."""
from __future__ import annotations

import datetime as dt
import logging
import re
from typing import Optional

import discord

from . import config

log = logging.getLogger("bot.utils")


# ── Embeds con branding ──────────────────────────────────────────────────

def brand_embed(
    title: str | None = None,
    description: str | None = None,
    color: int | discord.Color = config.BRAND_COLOR,
    *,
    url: str | None = None,
) -> discord.Embed:
    """Embed estandar con footer y color cobre."""
    if isinstance(color, int):
        color = discord.Color(color)
    e = discord.Embed(
        title=title,
        description=description,
        color=color,
        url=url,
        timestamp=dt.datetime.utcnow(),
    )
    e.set_footer(text=config.BRAND_FOOTER)
    return e


def success_embed(description: str, title: str = "Listo") -> discord.Embed:
    return brand_embed(title=f":white_check_mark: {title}", description=description, color=0x57F287)


def error_embed(description: str, title: str = "Error") -> discord.Embed:
    return brand_embed(title=f":x: {title}", description=description, color=0xED4245)


def warning_embed(description: str, title: str = "Atencion") -> discord.Embed:
    return brand_embed(title=f":warning: {title}", description=description, color=0xFEE75C)


def info_embed(description: str, title: str | None = None) -> discord.Embed:
    return brand_embed(title=title, description=description, color=config.BRAND_COLOR_BRIGHT)


# ── Parsers ──────────────────────────────────────────────────────────────

_DURATION_RE = re.compile(r"(\d+)\s*([smhdw])", re.IGNORECASE)
_DURATION_UNITS = {
    "s": 1,
    "m": 60,
    "h": 3600,
    "d": 86400,
    "w": 604800,
}


def parse_duration(text: str) -> Optional[dt.timedelta]:
    """Parsea '10m', '2h30m', '1d12h', etc. Devuelve None si invalido."""
    if not text:
        return None
    total = 0
    matched = False
    for value, unit in _DURATION_RE.findall(text):
        matched = True
        total += int(value) * _DURATION_UNITS[unit.lower()]
    if not matched:
        try:
            total = int(text) * 60  # numero solo = minutos
        except ValueError:
            return None
    if total <= 0:
        return None
    return dt.timedelta(seconds=total)


def humanize_delta(delta: dt.timedelta) -> str:
    """Humaniza una timedelta: '2d 3h 15m'."""
    secs = int(delta.total_seconds())
    if secs < 60:
        return f"{secs}s"
    parts: list[str] = []
    days, secs = divmod(secs, 86400)
    hours, secs = divmod(secs, 3600)
    minutes, secs = divmod(secs, 60)
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if secs and not parts:
        parts.append(f"{secs}s")
    return " ".join(parts)


# ── Helpers de permisos / roles ─────────────────────────────────────────

def get_role_by_name(guild: discord.Guild, name: str) -> Optional[discord.Role]:
    """Busca un rol case-insensitive por nombre."""
    name_low = name.lower()
    for r in guild.roles:
        if r.name.lower() == name_low:
            return r
    return None


def is_staff(member: discord.Member) -> bool:
    """True si el miembro tiene Manage Guild o algun rol de staff por nombre."""
    if member.guild_permissions.manage_guild:
        return True
    staff_role_names = {"admin", "owner", "senior staff", "staff", "moderator", "mod", "developer", "dev", "trainee staff"}
    return any(r.name.lower() in staff_role_names for r in member.roles)


def is_admin(member: discord.Member) -> bool:
    """True si tiene Administrator."""
    return member.guild_permissions.administrator


# ── Logging visual ───────────────────────────────────────────────────────

def setup_logging() -> None:
    """Configura logging con colores ANSI si esta disponible."""
    level = logging.DEBUG if config.DEBUG else logging.INFO
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logging.basicConfig(level=level, format=fmt, datefmt="%H:%M:%S")
    # discord.py es muy verbose en DEBUG, lo subimos a WARNING salvo en debug explicito
    if not config.DEBUG:
        logging.getLogger("discord").setLevel(logging.WARNING)
        logging.getLogger("discord.gateway").setLevel(logging.WARNING)
        logging.getLogger("discord.http").setLevel(logging.WARNING)
