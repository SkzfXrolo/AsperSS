"""Cogs del bot.

Cada modulo expone una funcion `setup(bot)` que registra el cog.
El main carga todos los modulos listados en COGS automaticamente.
"""

COGS: list[str] = [
    "bot.cogs.setup",
    "bot.cogs.welcome",
    "bot.cogs.moderation",
    "bot.cogs.automod",
    "bot.cogs.autoroles",
    "bot.cogs.economy",
    "bot.cogs.games",
    "bot.cogs.events",
    "bot.cogs.tickets",
    "bot.cogs.argus",
]
