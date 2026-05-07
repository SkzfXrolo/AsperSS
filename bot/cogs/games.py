"""Cog games — trivia, counting, blackjack, ahorcado.

Comandos:
    /trivia [categoria]   Pregunta con 4 botones, 30s para responder.
                          Premio: 10 monedas + 25 XP por acierto.
    /counting-set         (Staff) Designa el canal de counting.
                          A partir de ahi, los mensajes deben ser numeros
                          incrementales y nadie puede contestar dos veces
                          seguidas. Si fallan, se reinicia.
    /blackjack [apuesta]  Juega contra el dealer. Si ganas duplicas, si
                          pierdes pierdes la apuesta.
    /ahorcado             Adivina una palabra letra por letra. Soporta
                          un juego por canal.
"""
from __future__ import annotations

import asyncio
import json
import logging
import random
import string
from pathlib import Path
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from .. import config, db, utils

log = logging.getLogger("bot.cogs.games")

_TRIVIA_PATH = Path(__file__).resolve().parent.parent / "data" / "trivia.json"


def _load_trivia() -> dict:
    try:
        return json.loads(_TRIVIA_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"general": []}


# ═════════════════════════════════════════════════════════════════════════
# TRIVIA
# ═════════════════════════════════════════════════════════════════════════

class TriviaView(discord.ui.View):
    def __init__(self, options: list[str], correct: str, timeout: float = 30):
        super().__init__(timeout=timeout)
        self.correct = correct
        self.answered: dict[int, str] = {}
        # Crear botones
        for i, opt in enumerate(options):
            button = discord.ui.Button(
                label=opt[:80],
                style=discord.ButtonStyle.secondary,
                custom_id=f"trivia:{i}",
            )

            async def cb(interaction: discord.Interaction, choice=opt):
                if interaction.user.id in self.answered:
                    await interaction.response.send_message(
                        "Ya respondiste.", ephemeral=True
                    )
                    return
                self.answered[interaction.user.id] = choice
                if choice == self.correct:
                    await interaction.response.send_message(
                        f"✅ ¡Correcto! +25 XP +10 🪙",
                        ephemeral=True,
                    )
                    # Premiar
                    if interaction.guild:
                        with db.cursor() as cur:
                            cur.execute(
                                """
                                INSERT INTO bot_xp (guild_id, user_id, xp, level, coins)
                                VALUES (%s, %s, 25, 0, 10)
                                ON CONFLICT (guild_id, user_id) DO UPDATE
                                  SET xp = bot_xp.xp + 25, coins = bot_xp.coins + 10
                                """,
                                (interaction.guild.id, interaction.user.id),
                            )
                else:
                    await interaction.response.send_message(
                        f"❌ Incorrecto. La respuesta era: **{self.correct}**",
                        ephemeral=True,
                    )

            button.callback = cb  # type: ignore[assignment]
            self.add_item(button)


# ═════════════════════════════════════════════════════════════════════════
# BLACKJACK
# ═════════════════════════════════════════════════════════════════════════

CARD_VALUES = {
    "A": 11, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8,
    "9": 9, "10": 10, "J": 10, "Q": 10, "K": 10,
}
CARD_SUITS = ["♠", "♥", "♦", "♣"]


def _new_card() -> tuple[str, str]:
    return (random.choice(list(CARD_VALUES.keys())), random.choice(CARD_SUITS))


def _hand_value(hand: list[tuple[str, str]]) -> int:
    total = sum(CARD_VALUES[c[0]] for c in hand)
    aces = sum(1 for c, _ in hand if c == "A")
    while total > 21 and aces > 0:
        total -= 10
        aces -= 1
    return total


def _format_hand(hand: list[tuple[str, str]], hide_first: bool = False) -> str:
    if hide_first and hand:
        cards = ["🂠"] + [f"{c}{s}" for c, s in hand[1:]]
    else:
        cards = [f"{c}{s}" for c, s in hand]
    return " ".join(cards)


class BlackjackView(discord.ui.View):
    def __init__(self, player: discord.Member, bet: int):
        super().__init__(timeout=120)
        self.player = player
        self.bet = bet
        self.player_hand = [_new_card(), _new_card()]
        self.dealer_hand = [_new_card(), _new_card()]
        self.finished = False
        self.message: Optional[discord.Message] = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.player.id:
            await interaction.response.send_message(
                "Esta no es tu mano.", ephemeral=True
            )
            return False
        return True

    def _build_embed(self, *, reveal_dealer: bool = False, status: str = "") -> discord.Embed:
        return utils.brand_embed(
            title=f"🎲 Blackjack — apuesta 🪙{self.bet}",
            description=(
                f"**Tu mano:** {_format_hand(self.player_hand)} (= {_hand_value(self.player_hand)})\n"
                f"**Dealer:** {_format_hand(self.dealer_hand, hide_first=not reveal_dealer)}"
                + (f" (= {_hand_value(self.dealer_hand)})" if reveal_dealer else "")
                + (f"\n\n{status}" if status else "")
            ),
        )

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.success, emoji="🃏")
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.player_hand.append(_new_card())
        if _hand_value(self.player_hand) > 21:
            self.finished = True
            await self._end(interaction, status="💥 Te pasaste. Pierdes la apuesta.", payout=-self.bet)
        else:
            await interaction.response.edit_message(embed=self._build_embed(), view=self)

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.primary, emoji="✋")
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.finished = True
        # Dealer juega
        while _hand_value(self.dealer_hand) < 17:
            self.dealer_hand.append(_new_card())
        pv = _hand_value(self.player_hand)
        dv = _hand_value(self.dealer_hand)
        if dv > 21 or pv > dv:
            await self._end(interaction, status="🏆 ¡Ganaste! +"+str(self.bet)+" 🪙", payout=self.bet)
        elif pv == dv:
            await self._end(interaction, status="🤝 Empate. Recuperas tu apuesta.", payout=0)
        else:
            await self._end(interaction, status="😔 Perdiste contra el dealer.", payout=-self.bet)

    async def _end(self, interaction: discord.Interaction, status: str, payout: int):
        for item in self.children:
            item.disabled = True  # type: ignore[attr-defined]
        # Aplicar pago
        if interaction.guild and payout != 0:
            with db.cursor() as cur:
                cur.execute(
                    "UPDATE bot_xp SET coins = coins + %s WHERE guild_id = %s AND user_id = %s",
                    (payout, interaction.guild.id, self.player.id),
                )
        await interaction.response.edit_message(
            embed=self._build_embed(reveal_dealer=True, status=status),
            view=self,
        )
        self.stop()


# ═════════════════════════════════════════════════════════════════════════
# AHORCADO
# ═════════════════════════════════════════════════════════════════════════

HANGMAN_WORDS = [
    "minecraft", "anticheat", "ghostclient", "killaura", "speedhack",
    "scaffolding", "blockglitch", "screenshare", "veredicto", "argus",
    "prefetch", "registry", "automod", "trivia", "discord",
    "moderacion", "comunidad", "owner", "staff", "verificado",
]


class HangmanGame:
    def __init__(self, word: str):
        self.word = word.lower()
        self.guessed: set[str] = set()
        self.wrong: list[str] = []
        self.max_wrong = 6

    @property
    def display(self) -> str:
        return " ".join(c if c in self.guessed or not c.isalpha() else "_" for c in self.word)

    @property
    def is_won(self) -> bool:
        return all((not c.isalpha()) or c in self.guessed for c in self.word)

    @property
    def is_lost(self) -> bool:
        return len(self.wrong) >= self.max_wrong

    def guess(self, letter: str) -> str:
        letter = letter.lower()
        if letter in self.guessed or letter in self.wrong:
            return "repetida"
        if letter in self.word:
            self.guessed.add(letter)
            return "acierto"
        self.wrong.append(letter)
        return "fallo"


# ═════════════════════════════════════════════════════════════════════════
# Cog
# ═════════════════════════════════════════════════════════════════════════

class Games(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._hangman_games: dict[int, HangmanGame] = {}  # channel_id -> game

    # ── /trivia ────────────────────────────────────────────────────────
    @app_commands.command(name="trivia", description="Responde una pregunta para ganar XP y monedas.")
    @app_commands.choices(categoria=[
        app_commands.Choice(name="anticheat", value="anticheat"),
        app_commands.Choice(name="minecraft", value="minecraft"),
        app_commands.Choice(name="general",   value="general"),
        app_commands.Choice(name="aleatoria", value="random"),
    ])
    async def trivia(self, interaction: discord.Interaction, categoria: Optional[app_commands.Choice[str]] = None):
        data = _load_trivia()
        cat = (categoria.value if categoria else "random")
        if cat == "random":
            cat = random.choice(list(data.keys()))
        pool = data.get(cat) or []
        if not pool:
            await interaction.response.send_message(
                embed=utils.error_embed(f"Sin preguntas en categoria `{cat}`."),
                ephemeral=True,
            )
            return
        q = random.choice(pool)
        options = list(q["options"])
        random.shuffle(options)
        embed = utils.brand_embed(
            title=f"🎲 Trivia · {cat}",
            description=f"**{q['q']}**\n\n*Tienes 30 segundos.*",
        )
        view = TriviaView(options=options, correct=q["a"])
        await interaction.response.send_message(embed=embed, view=view)

    # ── /counting-set ──────────────────────────────────────────────────
    @app_commands.command(name="counting-set", description="(Staff) Designa el canal de counting.")
    @app_commands.default_permissions(manage_guild=True)
    async def counting_set(self, interaction: discord.Interaction, canal: discord.TextChannel):
        if not interaction.guild:
            return
        with db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO bot_counting (guild_id, channel_id, current, last_user_id)
                VALUES (%s, %s, 0, NULL)
                ON CONFLICT (guild_id) DO UPDATE
                  SET channel_id = EXCLUDED.channel_id, current = 0, last_user_id = NULL
                """,
                (interaction.guild.id, canal.id),
            )
        await canal.send(embed=utils.brand_embed(
            title="🔢 Counting iniciado",
            description=(
                "Cuenta de uno en uno. **Reglas:**\n"
                "• Solo numeros enteros, sin texto extra.\n"
                "• Nadie puede responder dos veces seguidas.\n"
                "• Si fallan, se reinicia y queda registro del record.\n\n"
                "**Empezamos en 1.**"
            ),
        ))
        await interaction.response.send_message(
            embed=utils.success_embed(f"Counting configurado en {canal.mention}."),
            ephemeral=True,
        )

    # ── on_message para counting ──────────────────────────────────────
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        with db.cursor() as cur:
            cur.execute(
                "SELECT channel_id, current, last_user_id, record FROM bot_counting WHERE guild_id = %s",
                (message.guild.id,),
            )
            cnt = cur.fetchone()
        if not cnt or int(cnt["channel_id"]) != message.channel.id:
            return
        # Validar
        try:
            n = int(message.content.strip())
        except ValueError:
            try:
                await message.delete()
            except (discord.NotFound, discord.Forbidden):
                pass
            return
        expected = int(cnt["current"]) + 1
        last_user = cnt["last_user_id"]
        if last_user is not None and int(last_user) == message.author.id:
            try:
                await message.add_reaction("❌")
            except discord.Forbidden:
                pass
            await self._counting_reset(message.guild.id, message.channel, "doble turno")
            return
        if n != expected:
            try:
                await message.add_reaction("❌")
            except discord.Forbidden:
                pass
            await self._counting_reset(message.guild.id, message.channel, f"esperaba {expected}, recibio {n}")
            return
        # Acierto
        try:
            await message.add_reaction("✅")
        except discord.Forbidden:
            pass
        with db.cursor() as cur:
            cur.execute(
                "UPDATE bot_counting SET current = %s, last_user_id = %s WHERE guild_id = %s",
                (n, message.author.id, message.guild.id),
            )
            if int(cnt["record"] or 0) < n:
                cur.execute(
                    "UPDATE bot_counting SET record = %s, record_at = NOW() WHERE guild_id = %s",
                    (n, message.guild.id),
                )
        # Bonus de XP cada 50
        if n % 50 == 0:
            with db.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO bot_xp (guild_id, user_id, xp, level, coins)
                    VALUES (%s, %s, 100, 0, 50)
                    ON CONFLICT (guild_id, user_id) DO UPDATE
                      SET xp = bot_xp.xp + 100, coins = bot_xp.coins + 50
                    """,
                    (message.guild.id, message.author.id),
                )
            try:
                await message.channel.send(
                    f"🎉 ¡{message.author.mention} alcanzo **{n}**! +100 XP +50 🪙",
                    delete_after=20,
                )
            except discord.Forbidden:
                pass

    async def _counting_reset(self, guild_id: int, channel: discord.abc.Messageable, reason: str):
        with db.cursor() as cur:
            cur.execute(
                "UPDATE bot_counting SET current = 0, last_user_id = NULL WHERE guild_id = %s",
                (guild_id,),
            )
        try:
            await channel.send(  # type: ignore[union-attr]
                embed=utils.warning_embed(
                    f"💥 Counting reiniciado: {reason}. Empezamos en **1**.",
                    title="Reset",
                )
            )
        except discord.Forbidden:
            pass

    # ── /blackjack ─────────────────────────────────────────────────────
    @app_commands.command(name="blackjack", description="Juega blackjack contra el dealer.")
    async def blackjack(self, interaction: discord.Interaction, apuesta: app_commands.Range[int, 10, 10000] = 50):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return
        with db.cursor() as cur:
            cur.execute(
                "SELECT coins FROM bot_xp WHERE guild_id = %s AND user_id = %s",
                (interaction.guild.id, interaction.user.id),
            )
            row = cur.fetchone()
        coins = int(row["coins"]) if row else 0
        if coins < apuesta:
            await interaction.response.send_message(
                embed=utils.error_embed(f"No tienes 🪙 {apuesta}. Solo tienes 🪙 {coins}."),
                ephemeral=True,
            )
            return

        view = BlackjackView(interaction.user, apuesta)
        # Si jugador tiene 21 -> blackjack auto
        if _hand_value(view.player_hand) == 21:
            view.finished = True
            with db.cursor() as cur:
                cur.execute(
                    "UPDATE bot_xp SET coins = coins + %s WHERE guild_id = %s AND user_id = %s",
                    (int(apuesta * 1.5), interaction.guild.id, interaction.user.id),
                )
            await interaction.response.send_message(
                embed=view._build_embed(reveal_dealer=True,
                                         status=f"🎰 ¡BLACKJACK! +{int(apuesta*1.5)} 🪙"),
            )
            return
        await interaction.response.send_message(embed=view._build_embed(), view=view)

    # ── /ahorcado ──────────────────────────────────────────────────────
    @app_commands.command(name="ahorcado", description="Adivina la palabra letra por letra.")
    async def ahorcado(self, interaction: discord.Interaction):
        if interaction.channel and interaction.channel.id in self._hangman_games:
            await interaction.response.send_message(
                embed=utils.warning_embed("Ya hay un juego de ahorcado en este canal."),
                ephemeral=True,
            )
            return
        word = random.choice(HANGMAN_WORDS)
        game = HangmanGame(word)
        self._hangman_games[interaction.channel.id] = game  # type: ignore[union-attr]
        embed = utils.brand_embed(
            title="🎯 Ahorcado",
            description=(
                f"`{game.display}`\n\n"
                f"Letras falladas: *(ninguna)*\n"
                f"Vidas: {'❤️' * game.max_wrong}\n\n"
                f"Escribe una letra en el chat. Tema: **anti-cheat / Minecraft / dev**."
            ),
        )
        await interaction.response.send_message(embed=embed)

    @commands.Cog.listener("on_message")
    async def hangman_listener(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        game = self._hangman_games.get(message.channel.id)
        if not game:
            return
        text = message.content.strip().lower()
        if len(text) != 1 or text not in string.ascii_lowercase:
            return
        result = game.guess(text)
        if result == "repetida":
            try:
                await message.add_reaction("🔁")
            except discord.Forbidden:
                pass
            return
        try:
            await message.add_reaction("✅" if result == "acierto" else "❌")
        except discord.Forbidden:
            pass

        if game.is_won:
            del self._hangman_games[message.channel.id]
            # Premio
            with db.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO bot_xp (guild_id, user_id, xp, level, coins)
                    VALUES (%s, %s, 50, 0, 25)
                    ON CONFLICT (guild_id, user_id) DO UPDATE
                      SET xp = bot_xp.xp + 50, coins = bot_xp.coins + 25
                    """,
                    (message.guild.id, message.author.id),
                )
            await message.channel.send(embed=utils.success_embed(
                f"🎉 ¡{message.author.mention} adivino la palabra **{game.word}**! +50 XP +25 🪙",
                title="Ahorcado",
            ))
            return
        if game.is_lost:
            del self._hangman_games[message.channel.id]
            await message.channel.send(embed=utils.error_embed(
                f"💀 La palabra era **{game.word}**.",
                title="Ahorcado · perdiste",
            ))
            return

        # Update display
        await message.channel.send(embed=utils.brand_embed(
            description=(
                f"`{game.display}`\n\n"
                f"Falladas: `{', '.join(game.wrong) or 'ninguna'}`\n"
                f"Vidas: {'❤️' * (game.max_wrong - len(game.wrong))}{'🖤' * len(game.wrong)}"
            ),
        ))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Games(bot))
