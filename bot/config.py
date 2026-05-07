"""Configuracion centralizada del bot.

Lee de .env (al lado de este archivo) y expone constantes.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass

# ── Discord ───────────────────────────────────────────────────────────────
DISCORD_TOKEN: str = os.environ.get("DISCORD_TOKEN", "").strip()
DISCORD_GUILD: int = int(os.environ.get("DISCORD_GUILD", "0") or 0)
DISCORD_OWNER_ID: int = int(os.environ.get("DISCORD_OWNER_ID", "0") or 0)

# ── Base de datos ─────────────────────────────────────────────────────────
DATABASE_URL: str = (
    os.environ.get("DATABASE_URL", "")
    .replace("postgres://", "postgresql://", 1)
    .strip()
)

# ── Misc ──────────────────────────────────────────────────────────────────
COMMAND_PREFIX: str = os.environ.get("COMMAND_PREFIX", "!").strip() or "!"
PANEL_URL: str = os.environ.get("PANEL_URL", "https://asperss.onrender.com").rstrip("/")
DEBUG: bool = os.environ.get("BOT_DEBUG", "0") == "1"

# ── Branding ──────────────────────────────────────────────────────────────
BRAND_NAME = "Argus Projects"
BRAND_COLOR = 0xB87333          # cobre principal del web app
BRAND_COLOR_BRIGHT = 0xD4915A   # cobre claro
BRAND_COLOR_DARK = 0x5C2E1A     # cobre oscuro
BRAND_FOOTER = "Argus Projects · All-Seeing. Always Watching."

# ── Defaults ──────────────────────────────────────────────────────────────
WARN_THRESHOLD_MUTE = 3
WARN_THRESHOLD_KICK = 5
WARN_THRESHOLD_BAN = 7
DEFAULT_MUTE_MINUTES = 60
XP_PER_MESSAGE = 15
XP_COOLDOWN_SECONDS = 60
COINS_PER_LEVEL = 100


def validate() -> list[str]:
    """Devuelve lista de errores; vacia si todo ok."""
    errors: list[str] = []
    if not DISCORD_TOKEN or len(DISCORD_TOKEN) < 50:
        errors.append("DISCORD_TOKEN ausente o invalido (debe ser el token del bot, ~70 chars).")
    if not DISCORD_GUILD:
        errors.append("DISCORD_GUILD ausente (ID del servidor donde corre el bot).")
    if not DATABASE_URL.startswith(("postgresql://", "postgres://")):
        errors.append("DATABASE_URL ausente o no es Postgres (postgresql://...).")
    return errors


def assert_valid() -> None:
    errs = validate()
    if errs:
        print("=" * 60)
        print("[CONFIG] El .env tiene errores:")
        for e in errs:
            print(f"  - {e}")
        print()
        print("Copia bot/.env.example como bot/.env y completa los valores.")
        print("=" * 60)
        sys.exit(1)
