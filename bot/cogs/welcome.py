"""Cog welcome — bienvenida + verificacion captcha + autorole.

Flujo cuando un miembro entra:
  1. Recibe mensaje de bienvenida en el canal #bienvenidas (publico).
  2. Recibe DM con un captcha matematico simple + boton para resolver.
  3. Si lo resuelve correctamente -> rol "Verificado" + acceso a la comunidad.
  4. Si falla 3 veces -> debe pedir ayuda a staff o salir y reentrar.
  5. Se loguea cada join/leave/verify en #logs-joins.

Comandos:
    /verify-panel    Crea/recrea el panel publico de verificacion en el
                     canal donde se ejecuta (boton "Verificarme") por si
                     alguien tenia DMs cerrados.
    /unverify @user  Quita el rol Verificado a un usuario (staff).
"""
from __future__ import annotations

import asyncio
import datetime as dt
import logging
import random
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from .. import config, db, utils

log = logging.getLogger("bot.cogs.welcome")

CAPTCHA_TTL_MINUTES = 10
MAX_ATTEMPTS = 3


# ═════════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════════

def _gen_math_captcha() -> tuple[str, str]:
    """Devuelve (pregunta, respuesta_correcta_str)."""
    a = random.randint(2, 19)
    b = random.randint(2, 19)
    op = random.choice(["+", "-", "*"])
    if op == "+":
        ans = a + b
    elif op == "-":
        # garantizar resultado positivo
        if b > a:
            a, b = b, a
        ans = a - b
    else:
        a = random.randint(2, 12)
        b = random.randint(2, 12)
        ans = a * b
    return f"{a} {op} {b}", str(ans)


def _get_role(guild: discord.Guild, key: str) -> Optional[discord.Role]:
    """Obtiene un rol por su key (persistido por /setup)."""
    rid = db.get_setting(guild.id, key)
    if not rid:
        return None
    try:
        return guild.get_role(int(rid))
    except (TypeError, ValueError):
        return None


def _get_channel(guild: discord.Guild, key: str) -> Optional[discord.TextChannel]:
    cid = db.get_setting(guild.id, key)
    if not cid:
        return None
    try:
        ch = guild.get_channel(int(cid))
        return ch if isinstance(ch, discord.TextChannel) else None
    except (TypeError, ValueError):
        return None


# ═════════════════════════════════════════════════════════════════════════
# Modal con input para resolver el captcha
# ═════════════════════════════════════════════════════════════════════════

class CaptchaModal(discord.ui.Modal):
    """Modal con input numerico para resolver el captcha."""

    answer_input: discord.ui.TextInput = discord.ui.TextInput(
        label="Tu respuesta (solo el numero)",
        placeholder="Ej: 42",
        required=True,
        max_length=10,
    )

    def __init__(self, guild_id: int, expected: str):
        super().__init__(title="Verificacion de seguridad")
        self.guild_id = guild_id
        self.expected = expected.strip()

    async def on_submit(self, interaction: discord.Interaction):
        given = (self.answer_input.value or "").strip()
        guild = interaction.client.get_guild(self.guild_id)
        if guild is None:
            await interaction.response.send_message(
                embed=utils.error_embed("No encuentro el servidor. Intenta mas tarde."),
                ephemeral=True,
            )
            return
        member = guild.get_member(interaction.user.id) or await guild.fetch_member(interaction.user.id)

        if given == self.expected:
            verified_role = _get_role(guild, "role_verified")
            if verified_role:
                try:
                    await member.add_roles(verified_role, reason="Captcha resuelto")
                except discord.Forbidden:
                    await interaction.response.send_message(
                        embed=utils.error_embed("Verificado, pero no pude darte el rol (permisos). Avisa a staff."),
                        ephemeral=True,
                    )
                    return
            with db.cursor() as cur:
                cur.execute(
                    "DELETE FROM bot_verifications WHERE user_id = %s AND guild_id = %s",
                    (member.id, guild.id),
                )
            await interaction.response.send_message(
                embed=utils.success_embed(
                    f"Bienvenido a **{guild.name}**, {member.mention}.\n\n"
                    "Ya tenes acceso a todos los canales publicos. "
                    "Si necesitas soporte, abre un ticket en `❓・soporte`."
                ),
                ephemeral=True,
            )
            log_ch = _get_channel(guild, "ch_log_joins")
            if log_ch:
                await log_ch.send(embed=utils.success_embed(
                    f"✅ {member.mention} (`{member.id}`) se verifico correctamente.",
                    title="Verificacion exitosa",
                ))
            return

        # Fallo
        with db.cursor() as cur:
            cur.execute(
                "UPDATE bot_verifications SET attempts = attempts + 1 WHERE user_id = %s AND guild_id = %s RETURNING attempts",
                (member.id, guild.id),
            )
            row = cur.fetchone()
            attempts = row["attempts"] if row else 1
        if attempts >= MAX_ATTEMPTS:
            await interaction.response.send_message(
                embed=utils.error_embed(
                    f"Has fallado **{MAX_ATTEMPTS} veces**. "
                    "Espera 10 minutos y vuelve a intentar, o pide ayuda a staff."
                ),
                ephemeral=True,
            )
            with db.cursor() as cur:
                cur.execute(
                    "DELETE FROM bot_verifications WHERE user_id = %s AND guild_id = %s",
                    (member.id, guild.id),
                )
            log_ch = _get_channel(guild, "ch_log_joins")
            if log_ch:
                await log_ch.send(embed=utils.warning_embed(
                    f"⚠ {member.mention} (`{member.id}`) fallo el captcha {MAX_ATTEMPTS} veces.",
                    title="Verificacion fallida",
                ))
            return
        await interaction.response.send_message(
            embed=utils.error_embed(
                f"Respuesta incorrecta. Intentos restantes: **{MAX_ATTEMPTS - attempts}**.\n"
                f"Usa el boton de nuevo para reintentar."
            ),
            ephemeral=True,
        )


# ═════════════════════════════════════════════════════════════════════════
# Boton persistente "Verificarme"
# ═════════════════════════════════════════════════════════════════════════

class VerifyButton(discord.ui.View):
    """Vista persistente: el bot la registra al arrancar y sobrevive a reinicios."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Verificarme",
        style=discord.ButtonStyle.success,
        emoji="✅",
        custom_id="argus:verify",
    )
    async def verify(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        if not guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("Solo en servidores.", ephemeral=True)
            return

        verified_role = _get_role(guild, "role_verified")
        if verified_role and verified_role in interaction.user.roles:
            await interaction.response.send_message(
                embed=utils.info_embed("Ya estas verificado.", title="Listo"),
                ephemeral=True,
            )
            return

        # Genera captcha y persiste
        question, answer = _gen_math_captcha()
        expires = dt.datetime.utcnow() + dt.timedelta(minutes=CAPTCHA_TTL_MINUTES)
        with db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO bot_verifications (user_id, guild_id, code, attempts, expires_at)
                VALUES (%s, %s, %s, 0, %s)
                ON CONFLICT (user_id, guild_id) DO UPDATE
                  SET code = EXCLUDED.code, attempts = 0, expires_at = EXCLUDED.expires_at, created_at = NOW()
                """,
                (interaction.user.id, guild.id, answer, expires),
            )

        # Pop modal
        modal = CaptchaModal(guild_id=guild.id, expected=answer)
        modal.title = f"Verificacion · {question} = ?"
        await interaction.response.send_modal(modal)


# ═════════════════════════════════════════════════════════════════════════
# Cog
# ═════════════════════════════════════════════════════════════════════════

class Welcome(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        # Registrar la view persistente cuando carga el cog
        bot.add_view(VerifyButton())

    # ── Eventos ────────────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild = member.guild

        # Mensaje publico en #bienvenidas
        ch_welcome = _get_channel(guild, "ch_welcome")
        if ch_welcome:
            embed = utils.brand_embed(
                title=f"🎉 Bienvenido a {guild.name}",
                description=(
                    f"Hola {member.mention}, somos **miembro #{guild.member_count}**.\n\n"
                    f"Para acceder a la comunidad necesitas **verificarte**:\n"
                    f"1. Revisa tus DMs (te mande un boton).\n"
                    f"2. O usa el boton de verificacion en el canal de bienvenida.\n\n"
                    f"📜 Lee las reglas en <#{_get_channel(guild, 'ch_rules').id if _get_channel(guild, 'ch_rules') else 0}>."
                ),
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            await ch_welcome.send(embed=embed, content=member.mention)

        # DM con boton
        dm_embed = utils.brand_embed(
            title="🛡 Verificate para acceder",
            description=(
                f"Hola **{member.display_name}**, bienvenido a **{guild.name}**.\n\n"
                "Para confirmar que no eres un bot y desbloquear todos los canales, "
                "haz click en el boton de abajo y resuelve el captcha que aparece.\n\n"
                f"Tienes **{CAPTCHA_TTL_MINUTES} minutos** y **{MAX_ATTEMPTS} intentos**."
            ),
        )
        try:
            await member.send(embed=dm_embed, view=VerifyButton())
        except discord.Forbidden:
            pass  # DMs cerrados; usara el panel publico

        # Log
        log_ch = _get_channel(guild, "ch_log_joins")
        if log_ch:
            joined_age = (dt.datetime.utcnow() - member.created_at.replace(tzinfo=None)).days
            embed = utils.brand_embed(
                title="🟢 Miembro entro",
                description=(
                    f"{member.mention} (`{member.id}`)\n"
                    f"Cuenta creada hace **{joined_age}** dias\n"
                    f"Total miembros: **{guild.member_count}**"
                ),
                color=0x57F287,
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            await log_ch.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        log_ch = _get_channel(member.guild, "ch_log_joins")
        if log_ch:
            embed = utils.brand_embed(
                title="🔴 Miembro salio",
                description=(
                    f"{member.mention} (`{member.id}`)\n"
                    f"Estaba en el server hace "
                    f"{utils.humanize_delta(dt.datetime.utcnow() - member.joined_at.replace(tzinfo=None)) if member.joined_at else '?'}\n"
                    f"Total miembros: **{member.guild.member_count}**"
                ),
                color=0xED4245,
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            await log_ch.send(embed=embed)

    # ── Comandos ───────────────────────────────────────────────────────
    @app_commands.command(
        name="verify-panel",
        description="Publica el panel de verificacion (boton 'Verificarme') en este canal.",
    )
    @app_commands.default_permissions(manage_guild=True)
    async def verify_panel(self, interaction: discord.Interaction):
        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("Usa esto en un canal de texto.", ephemeral=True)
            return
        embed = utils.brand_embed(
            title="🛡 Verificacion de seguridad",
            description=(
                "Para acceder a todos los canales del servidor, **verificate** con el boton de abajo.\n\n"
                f"Resuelve un captcha simple. Tienes **{MAX_ATTEMPTS}** intentos y **{CAPTCHA_TTL_MINUTES}** minutos."
            ),
        )
        await interaction.channel.send(embed=embed, view=VerifyButton())
        await interaction.response.send_message(
            embed=utils.success_embed("Panel publicado."),
            ephemeral=True,
        )

    @app_commands.command(
        name="unverify",
        description="Quita el rol Verificado a un usuario (staff).",
    )
    @app_commands.default_permissions(manage_roles=True)
    @app_commands.describe(usuario="Usuario al que quitar la verificacion")
    async def unverify(self, interaction: discord.Interaction, usuario: discord.Member):
        guild = interaction.guild
        if not guild or not isinstance(interaction.user, discord.Member):
            return
        if not utils.is_staff(interaction.user):
            await interaction.response.send_message(
                embed=utils.error_embed("Solo staff."), ephemeral=True
            )
            return
        verified_role = _get_role(guild, "role_verified")
        if not verified_role:
            await interaction.response.send_message(
                embed=utils.error_embed("No hay rol Verificado configurado. Ejecuta /setup."),
                ephemeral=True,
            )
            return
        if verified_role not in usuario.roles:
            await interaction.response.send_message(
                embed=utils.warning_embed(f"{usuario.mention} no esta verificado."),
                ephemeral=True,
            )
            return
        await usuario.remove_roles(verified_role, reason=f"Unverify por {interaction.user}")
        await interaction.response.send_message(
            embed=utils.success_embed(f"Rol Verificado quitado a {usuario.mention}."),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Welcome(bot))
