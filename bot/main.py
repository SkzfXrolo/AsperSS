"""Entrypoint del bot de Discord — Argus Projects.

Ejecutar con:
    python -m bot           (desde la raiz del repo)
"""
from __future__ import annotations

import asyncio
import logging
import sys
import traceback

# La consola de Windows usa cp1252 por defecto y se asfixia con los
# emojis del banner. Forzamos UTF-8 antes de cualquier print.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass

import discord
from discord.ext import commands

from . import config, db, utils
from .cogs import COGS

log = logging.getLogger("bot.main")


# ── Bot subclass ─────────────────────────────────────────────────────────

class ArgusBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.members = True           # bienvenidas, autoroles, banes
        intents.message_content = True   # automod (filtros, anti-spam)
        intents.guilds = True

        super().__init__(
            command_prefix=commands.when_mentioned_or(config.COMMAND_PREFIX),
            intents=intents,
            help_command=None,
            allowed_mentions=discord.AllowedMentions(
                everyone=False, roles=False, users=True, replied_user=True
            ),
        )

    async def setup_hook(self) -> None:
        log.info("[Bot] setup_hook: cargando cogs...")
        for cog_path in COGS:
            try:
                await self.load_extension(cog_path)
                log.info("[Bot]   + %s cargado", cog_path)
            except Exception as e:
                log.exception("[Bot]   ! fallo al cargar %s: %s", cog_path, e)

        # Sincroniza slash commands SOLO al guild configurado (instantaneo)
        if config.DISCORD_GUILD:
            guild_obj = discord.Object(id=config.DISCORD_GUILD)
            self.tree.copy_global_to(guild=guild_obj)
            synced = await self.tree.sync(guild=guild_obj)
            log.info("[Bot] %d comandos sincronizados al guild %d",
                     len(synced), config.DISCORD_GUILD)
        else:
            synced = await self.tree.sync()
            log.info("[Bot] %d comandos sincronizados globalmente (puede tardar 1h en aparecer)",
                     len(synced))

    async def on_ready(self) -> None:
        assert self.user is not None
        guild = self.get_guild(config.DISCORD_GUILD) if config.DISCORD_GUILD else None
        guild_name = guild.name if guild else "(no configurado)"
        members = guild.member_count if guild else 0
        db_host = config.DATABASE_URL.split("@")[-1] if "@" in config.DATABASE_URL else "local"

        # Usar logging en vez de print: el logger del root maneja unicode
        # incluso cuando stdout no esta reconfigurado a UTF-8 en Windows.
        log.info("=" * 60)
        log.info("  ARGUS DISCORD BOT - conectado como %s", self.user)
        log.info("  Guild: %s (%d miembros)", guild_name, members)
        log.info("  Panel: %s", config.PANEL_URL)
        log.info("  DB:    %s", db_host)
        log.info("=" * 60)

        await self.change_presence(
            status=discord.Status.online,
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=f"{members} miembros · /help",
            ),
        )

    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            return
        log.exception("[Bot] Error en comando: %s", error)


# ── Manejo global de errores en slash commands ───────────────────────────

async def _on_app_command_error(
    interaction: discord.Interaction,
    error: discord.app_commands.AppCommandError,
) -> None:
    if isinstance(error, discord.app_commands.MissingPermissions):
        msg = "No tienes permisos para usar este comando."
    elif isinstance(error, discord.app_commands.CommandOnCooldown):
        msg = f"En cooldown. Intentalo en {error.retry_after:.1f}s."
    elif isinstance(error, discord.app_commands.CheckFailure):
        msg = "No cumples los requisitos para usar este comando."
    else:
        msg = f"Error inesperado: `{error.__class__.__name__}: {error}`"
        log.error("[Bot] AppCommandError:\n%s", "".join(traceback.format_exception(error)))

    embed = utils.error_embed(msg)
    try:
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)
    except discord.HTTPException:
        pass


# ── Main ─────────────────────────────────────────────────────────────────

async def amain() -> None:
    utils.setup_logging()
    config.assert_valid()

    log.info("[Bot] Inicializando pool de DB...")
    db.init_pool()
    try:
        db.apply_schema()
    except Exception:
        log.exception("[Bot] Error aplicando schema; revisa permisos del usuario de la BD")
        sys.exit(1)

    bot = ArgusBot()
    bot.tree.on_error = _on_app_command_error  # type: ignore[assignment]

    try:
        await bot.start(config.DISCORD_TOKEN)
    finally:
        db.close_pool()


def main() -> None:
    try:
        asyncio.run(amain())
    except KeyboardInterrupt:
        log.info("[Bot] Interrumpido por el usuario, cerrando...")


if __name__ == "__main__":
    main()
