"""Cog economy — XP, niveles, monedas y tienda.

Sistema:
  - Cada mensaje (no comando, no bot, fuera de cooldown 60s) otorga
    XP_PER_MESSAGE +/- 30% al autor.
  - Formula de nivel: xp_para_nivel(n) = 5*n^2 + 50*n + 100
    -> nivel 1: 155 xp, nivel 5: 475 xp, nivel 10: 1100, nivel 20: 3100,
       nivel 50: 15100.
  - Al subir de nivel: anuncio publico + COINS_PER_LEVEL monedas.
  - Comandos publicos:
      /rank [@user]      Muestra nivel, XP, posicion, monedas.
      /top               Leaderboard top 10 por XP.
      /coins [@user]     Monedas actuales.
      /pay @user N       Transfiere monedas (con cooldown 1h).
      /daily             Reclama 50 monedas diarias.
  - Comandos staff:
      /xp-add @user N    Otorga XP manualmente.
      /coins-add @user N Otorga monedas manualmente.
      /shop-list         Ver items.
      /shop-add          Agregar item.
      /shop-remove       Quitar item.
  - /buy <item>          Comprar (otorga rol si tiene role_id).
  - /shop                Lista items.
"""
from __future__ import annotations

import datetime as dt
import logging
import math
import random
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from .. import config, db, utils

log = logging.getLogger("bot.cogs.economy")

DAILY_AMOUNT = 50
PAY_COOLDOWN_SECONDS = 3600


def xp_for_level(level: int) -> int:
    """Devuelve el XP total acumulado necesario para alcanzar un nivel."""
    return 5 * level * level + 50 * level + 100


def level_for_xp(xp: int) -> int:
    """Devuelve el nivel correspondiente a un XP total."""
    if xp < xp_for_level(1):
        return 0
    # Resuelve: 5n^2 + 50n + 100 <= xp
    # n <= (-50 + sqrt(2500 - 20*(100-xp))) / 10
    disc = 2500 + 20 * (xp - 100)
    if disc < 0:
        return 0
    return max(0, int((-50 + math.sqrt(disc)) // 10))


def progress_bar(current: int, total: int, length: int = 20) -> str:
    if total <= 0:
        return "─" * length
    filled = max(0, min(length, int(length * current / total)))
    return "█" * filled + "─" * (length - filled)


# ═════════════════════════════════════════════════════════════════════════
# Cog
# ═════════════════════════════════════════════════════════════════════════

class Economy(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ── Listener: XP por mensaje ──────────────────────────────────────
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        if message.content.startswith(("/", "!", "?")):
            return  # ignora comandos
        if len(message.content) < 3:
            return

        guild_id = message.guild.id
        user_id = message.author.id

        with db.cursor() as cur:
            cur.execute(
                "SELECT xp, level, last_message FROM bot_xp WHERE guild_id = %s AND user_id = %s",
                (guild_id, user_id),
            )
            row = cur.fetchone()

            now = dt.datetime.utcnow()
            if row:
                last = row["last_message"]
                if last and (now - last).total_seconds() < config.XP_COOLDOWN_SECONDS:
                    return

            gain = int(config.XP_PER_MESSAGE * random.uniform(0.7, 1.3))
            if row is None:
                cur.execute(
                    """
                    INSERT INTO bot_xp (guild_id, user_id, xp, level, coins, last_message, messages)
                    VALUES (%s, %s, %s, %s, 0, %s, 1)
                    """,
                    (guild_id, user_id, gain, level_for_xp(gain), now),
                )
                new_xp = gain
                new_level = level_for_xp(gain)
                old_level = 0
            else:
                new_xp = int(row["xp"]) + gain
                old_level = int(row["level"])
                new_level = level_for_xp(new_xp)
                cur.execute(
                    """
                    UPDATE bot_xp SET xp = %s, level = %s, last_message = %s, messages = messages + 1
                    WHERE guild_id = %s AND user_id = %s
                    """,
                    (new_xp, new_level, now, guild_id, user_id),
                )

        # Level up?
        if new_level > old_level:
            coins_reward = (new_level - old_level) * config.COINS_PER_LEVEL
            with db.cursor() as cur:
                cur.execute(
                    "UPDATE bot_xp SET coins = coins + %s WHERE guild_id = %s AND user_id = %s",
                    (coins_reward, guild_id, user_id),
                )
            try:
                await message.channel.send(
                    f"🎉 ¡{message.author.mention} subio a **nivel {new_level}**! "
                    f"+{coins_reward} 🪙",
                    delete_after=15,
                )
            except discord.Forbidden:
                pass

    # ── /rank ──────────────────────────────────────────────────────────
    @app_commands.command(name="rank", description="Muestra tu nivel y XP (o el de otro usuario).")
    async def rank(self, interaction: discord.Interaction, usuario: Optional[discord.Member] = None):
        target = usuario or interaction.user
        if not interaction.guild:
            return
        with db.cursor() as cur:
            cur.execute(
                "SELECT xp, level, coins, messages FROM bot_xp WHERE guild_id = %s AND user_id = %s",
                (interaction.guild.id, target.id),
            )
            row = cur.fetchone()
            cur.execute(
                "SELECT COUNT(*) AS c FROM bot_xp WHERE guild_id = %s AND xp > %s",
                (interaction.guild.id, row["xp"] if row else 0),
            )
            position_row = cur.fetchone()

        xp = int(row["xp"]) if row else 0
        level = int(row["level"]) if row else 0
        coins = int(row["coins"]) if row else 0
        messages = int(row["messages"]) if row else 0
        position = int(position_row["c"]) + 1 if position_row else 1

        cur_level_floor = xp_for_level(level)
        next_level_floor = xp_for_level(level + 1)
        progress = xp - cur_level_floor
        needed = next_level_floor - cur_level_floor
        bar = progress_bar(progress, needed)

        embed = utils.brand_embed(
            title=f"📊 Rank de {target.display_name}",
            description=(
                f"**Nivel:** `{level}`\n"
                f"**XP:** `{xp}` / `{next_level_floor}`\n"
                f"`{bar}` ({progress}/{needed})\n\n"
                f"**Monedas:** 🪙 `{coins}`\n"
                f"**Mensajes:** `{messages}`\n"
                f"**Posicion:** #{position}"
            ),
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    # ── /top ───────────────────────────────────────────────────────────
    @app_commands.command(name="top", description="Leaderboard top 10 por XP.")
    async def top(self, interaction: discord.Interaction):
        if not interaction.guild:
            return
        with db.cursor() as cur:
            cur.execute(
                "SELECT user_id, xp, level FROM bot_xp WHERE guild_id = %s ORDER BY xp DESC LIMIT 10",
                (interaction.guild.id,),
            )
            rows = cur.fetchall()
        if not rows:
            await interaction.response.send_message(
                embed=utils.info_embed("Aun no hay nadie con XP."),
                ephemeral=True,
            )
            return
        lines = []
        medals = ["🥇", "🥈", "🥉"]
        for i, r in enumerate(rows):
            mem = interaction.guild.get_member(int(r["user_id"]))
            name = mem.display_name if mem else f"`id:{r['user_id']}`"
            prefix = medals[i] if i < 3 else f"`#{i+1}`"
            lines.append(f"{prefix} **{name}** — Nv. {r['level']} · {r['xp']} XP")
        await interaction.response.send_message(
            embed=utils.brand_embed(
                title=f"🏆 Top 10 — {interaction.guild.name}",
                description="\n".join(lines),
            )
        )

    # ── /coins ─────────────────────────────────────────────────────────
    @app_commands.command(name="coins", description="Muestra tus monedas (o las de otro).")
    async def coins(self, interaction: discord.Interaction, usuario: Optional[discord.Member] = None):
        target = usuario or interaction.user
        if not interaction.guild:
            return
        with db.cursor() as cur:
            cur.execute(
                "SELECT coins FROM bot_xp WHERE guild_id = %s AND user_id = %s",
                (interaction.guild.id, target.id),
            )
            row = cur.fetchone()
        coins = int(row["coins"]) if row else 0
        await interaction.response.send_message(
            embed=utils.brand_embed(
                title=f"🪙 Monedas de {target.display_name}",
                description=f"**`{coins}`** monedas",
            )
        )

    # ── /pay ───────────────────────────────────────────────────────────
    @app_commands.command(name="pay", description="Transfiere monedas a otro usuario.")
    @app_commands.checks.cooldown(1, PAY_COOLDOWN_SECONDS, key=lambda i: (i.guild_id, i.user.id))
    async def pay(self, interaction: discord.Interaction, usuario: discord.Member, cantidad: int):
        if cantidad <= 0:
            await interaction.response.send_message(
                embed=utils.error_embed("Cantidad debe ser positiva."),
                ephemeral=True,
            )
            return
        if usuario.bot or usuario.id == interaction.user.id:
            await interaction.response.send_message(
                embed=utils.error_embed("No vale."),
                ephemeral=True,
            )
            return
        if not interaction.guild:
            return
        with db.cursor() as cur:
            cur.execute(
                "SELECT coins FROM bot_xp WHERE guild_id = %s AND user_id = %s",
                (interaction.guild.id, interaction.user.id),
            )
            sender_row = cur.fetchone()
            if not sender_row or int(sender_row["coins"]) < cantidad:
                await interaction.response.send_message(
                    embed=utils.error_embed("No tienes suficientes monedas."),
                    ephemeral=True,
                )
                return
            cur.execute(
                "UPDATE bot_xp SET coins = coins - %s WHERE guild_id = %s AND user_id = %s",
                (cantidad, interaction.guild.id, interaction.user.id),
            )
            cur.execute(
                """
                INSERT INTO bot_xp (guild_id, user_id, xp, level, coins)
                VALUES (%s, %s, 0, 0, %s)
                ON CONFLICT (guild_id, user_id) DO UPDATE SET coins = bot_xp.coins + %s
                """,
                (interaction.guild.id, usuario.id, cantidad, cantidad),
            )
        await interaction.response.send_message(
            embed=utils.success_embed(
                f"{interaction.user.mention} → {usuario.mention} : 🪙 **{cantidad}** monedas."
            )
        )

    # ── /daily ─────────────────────────────────────────────────────────
    @app_commands.command(name="daily", description=f"Reclama {DAILY_AMOUNT} monedas diarias.")
    async def daily(self, interaction: discord.Interaction):
        if not interaction.guild:
            return
        last = db.get_setting(interaction.guild.id, f"daily_{interaction.user.id}") or "0"
        try:
            last_ts = float(last)
        except ValueError:
            last_ts = 0.0
        now = dt.datetime.utcnow().timestamp()
        if now - last_ts < 86400:
            remaining = int(86400 - (now - last_ts))
            await interaction.response.send_message(
                embed=utils.warning_embed(
                    f"Ya reclamaste hoy. Vuelve en **{utils.humanize_delta(dt.timedelta(seconds=remaining))}**."
                ),
                ephemeral=True,
            )
            return
        with db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO bot_xp (guild_id, user_id, xp, level, coins)
                VALUES (%s, %s, 0, 0, %s)
                ON CONFLICT (guild_id, user_id) DO UPDATE SET coins = bot_xp.coins + %s
                """,
                (interaction.guild.id, interaction.user.id, DAILY_AMOUNT, DAILY_AMOUNT),
            )
        db.set_setting(interaction.guild.id, f"daily_{interaction.user.id}", str(now))
        await interaction.response.send_message(
            embed=utils.success_embed(f"Reclamaste 🪙 **{DAILY_AMOUNT}** monedas. Vuelve manana."),
        )

    # ── /xp-add (staff) ────────────────────────────────────────────────
    @app_commands.command(name="xp-add", description="(Staff) Otorga XP manualmente.")
    @app_commands.default_permissions(manage_guild=True)
    async def xp_add(self, interaction: discord.Interaction, usuario: discord.Member, cantidad: int):
        if not interaction.guild:
            return
        with db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO bot_xp (guild_id, user_id, xp, level, coins)
                VALUES (%s, %s, %s, 0, 0)
                ON CONFLICT (guild_id, user_id) DO UPDATE SET xp = bot_xp.xp + %s
                """,
                (interaction.guild.id, usuario.id, cantidad, cantidad),
            )
            cur.execute(
                "SELECT xp FROM bot_xp WHERE guild_id = %s AND user_id = %s",
                (interaction.guild.id, usuario.id),
            )
            row = cur.fetchone()
            new_xp = int(row["xp"])
            new_level = level_for_xp(new_xp)
            cur.execute(
                "UPDATE bot_xp SET level = %s WHERE guild_id = %s AND user_id = %s",
                (new_level, interaction.guild.id, usuario.id),
            )
        await interaction.response.send_message(
            embed=utils.success_embed(
                f"{usuario.mention} → +{cantidad} XP (total: {new_xp}, nivel {new_level})."
            ),
            ephemeral=True,
        )

    # ── /coins-add (staff) ─────────────────────────────────────────────
    @app_commands.command(name="coins-add", description="(Staff) Otorga monedas manualmente.")
    @app_commands.default_permissions(manage_guild=True)
    async def coins_add(self, interaction: discord.Interaction, usuario: discord.Member, cantidad: int):
        if not interaction.guild:
            return
        with db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO bot_xp (guild_id, user_id, xp, level, coins)
                VALUES (%s, %s, 0, 0, %s)
                ON CONFLICT (guild_id, user_id) DO UPDATE SET coins = bot_xp.coins + %s
                """,
                (interaction.guild.id, usuario.id, cantidad, cantidad),
            )
        await interaction.response.send_message(
            embed=utils.success_embed(f"{usuario.mention} → 🪙 +{cantidad} monedas."),
            ephemeral=True,
        )

    # ── /shop ──────────────────────────────────────────────────────────
    @app_commands.command(name="shop", description="Tienda de items con monedas.")
    async def shop(self, interaction: discord.Interaction):
        if not interaction.guild:
            return
        with db.cursor() as cur:
            cur.execute(
                "SELECT id, name, description, price, role_id, stock FROM bot_shop_items WHERE guild_id = %s ORDER BY price",
                (interaction.guild.id,),
            )
            rows = cur.fetchall()
        if not rows:
            await interaction.response.send_message(
                embed=utils.info_embed("La tienda esta vacia. Usa `/shop-add` para agregar items."),
                ephemeral=True,
            )
            return
        lines = []
        for r in rows:
            stock = "∞" if r["stock"] == -1 else str(r["stock"])
            extra = f" → <@&{r['role_id']}>" if r["role_id"] else ""
            lines.append(
                f"`#{r['id']}` **{r['name']}**{extra}\n"
                f"  🪙 {r['price']} · stock: {stock}\n"
                f"  *{r['description'] or 'sin descripcion'}*"
            )
        await interaction.response.send_message(
            embed=utils.brand_embed(
                title=f"🏪 Tienda de {interaction.guild.name}",
                description="\n\n".join(lines) + "\n\nUsa `/buy <id>` para comprar.",
            )
        )

    # ── /buy ───────────────────────────────────────────────────────────
    @app_commands.command(name="buy", description="Compra un item de la tienda.")
    async def buy(self, interaction: discord.Interaction, item_id: int):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return
        with db.cursor() as cur:
            cur.execute(
                "SELECT name, price, role_id, stock FROM bot_shop_items WHERE id = %s AND guild_id = %s",
                (item_id, interaction.guild.id),
            )
            item = cur.fetchone()
            if not item:
                await interaction.response.send_message(
                    embed=utils.error_embed("Item no encontrado."), ephemeral=True
                )
                return
            if item["stock"] == 0:
                await interaction.response.send_message(
                    embed=utils.error_embed("Sin stock."), ephemeral=True
                )
                return
            cur.execute(
                "SELECT coins FROM bot_xp WHERE guild_id = %s AND user_id = %s",
                (interaction.guild.id, interaction.user.id),
            )
            user_row = cur.fetchone()
            if not user_row or int(user_row["coins"]) < int(item["price"]):
                await interaction.response.send_message(
                    embed=utils.error_embed("No tienes suficientes monedas."),
                    ephemeral=True,
                )
                return
            cur.execute(
                "UPDATE bot_xp SET coins = coins - %s WHERE guild_id = %s AND user_id = %s",
                (item["price"], interaction.guild.id, interaction.user.id),
            )
            if item["stock"] > 0:
                cur.execute(
                    "UPDATE bot_shop_items SET stock = stock - 1 WHERE id = %s",
                    (item_id,),
                )
            cur.execute(
                """
                INSERT INTO bot_shop_purchases (guild_id, user_id, item_id, price_paid)
                VALUES (%s, %s, %s, %s)
                """,
                (interaction.guild.id, interaction.user.id, item_id, item["price"]),
            )

        # Otorgar rol si aplica
        role_msg = ""
        if item["role_id"]:
            role = interaction.guild.get_role(int(item["role_id"]))
            if role:
                try:
                    await interaction.user.add_roles(role, reason=f"Compra: {item['name']}")
                    role_msg = f"\n🎁 Rol {role.mention} otorgado."
                except discord.Forbidden:
                    role_msg = "\n⚠ No tengo permisos para darte el rol."

        await interaction.response.send_message(
            embed=utils.success_embed(
                f"Compraste **{item['name']}** por 🪙 **{item['price']}**.{role_msg}"
            )
        )

    # ── /shop-add (staff) ──────────────────────────────────────────────
    @app_commands.command(name="shop-add", description="(Staff) Agrega item a la tienda.")
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.describe(
        nombre="Nombre del item",
        precio="Costo en monedas",
        descripcion="Descripcion",
        rol="(Opcional) Rol que otorga al comprar",
        stock="Stock (-1 = infinito, default -1)",
    )
    async def shop_add(
        self,
        interaction: discord.Interaction,
        nombre: str,
        precio: int,
        descripcion: str = "",
        rol: Optional[discord.Role] = None,
        stock: int = -1,
    ):
        if not interaction.guild:
            return
        with db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO bot_shop_items (guild_id, name, description, price, role_id, stock)
                VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
                """,
                (interaction.guild.id, nombre, descripcion or None, precio,
                 rol.id if rol else None, stock),
            )
            row = cur.fetchone()
        await interaction.response.send_message(
            embed=utils.success_embed(f"Item agregado con ID `#{row['id']}`."),
            ephemeral=True,
        )

    # ── /shop-remove (staff) ───────────────────────────────────────────
    @app_commands.command(name="shop-remove", description="(Staff) Quita item de la tienda.")
    @app_commands.default_permissions(manage_guild=True)
    async def shop_remove(self, interaction: discord.Interaction, item_id: int):
        if not interaction.guild:
            return
        with db.cursor() as cur:
            cur.execute(
                "DELETE FROM bot_shop_items WHERE id = %s AND guild_id = %s",
                (item_id, interaction.guild.id),
            )
            removed = cur.rowcount
        if removed:
            await interaction.response.send_message(
                embed=utils.success_embed(f"Item `#{item_id}` eliminado."),
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                embed=utils.error_embed("Item no encontrado."), ephemeral=True
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Economy(bot))
