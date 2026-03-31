# Copyright (C) 2025 Matheus Pereira
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
# TRADEMARK NOTICE: The name "Roll & Play Bot" and its logo are distinct
# from the software and are NOT covered by the AGPL. They remain the
# exclusive property of the author.

import re
import logging
import discord
from discord.ext import commands
from discord import app_commands
from utils import dice_roller
from utils.i18n import t as t_raw
from utils.locale_resolver import resolve_locale
from view.rolling.dice_hub_view import DiceHubView

log = logging.getLogger("rpg-bot")


def _tr(key: str, locale: str, fallback: str, **kwargs) -> str:
    try:
        text = t_raw(key, locale, **kwargs)
    except Exception:
        return fallback.format(**kwargs) if kwargs else fallback
    if text == key:
        try:
            return fallback.format(**kwargs) if kwargs else fallback
        except Exception:
            return fallback
    return text


def localized_command(name_pt, desc_pt, name_en, desc_en):
    def decorator(func):
        cmd = app_commands.command(name=name_pt, description=desc_pt)(func)
        cmd.name_localizations = {"en-US": name_en, "en-GB": name_en}
        cmd.description_localizations = {"en-US": desc_en, "en-GB": desc_en}
        return cmd
    return decorator


def _normalize_locale(loc: str | None) -> str:
    if not loc:
        return "pt"
    loc = str(loc).lower()
    if loc.startswith("pt"):
        return "pt"
    if loc.startswith("en"):
        return "en"
    return "pt"


def _guess_message_locale(message: discord.Message) -> str:
    try:
        if message.guild and getattr(message.guild, "preferred_locale", None):
            return _normalize_locale(message.guild.preferred_locale)
    except Exception:
        pass
    return "pt"


def _apply_adv_token(expr: str, advantage_state: str) -> str:
    def _apply_adv(expr_in: str, mode: str) -> str:
        if mode not in ("vantagem", "desvantagem"):
            return expr_in
        def repl(match):
            prefix = match.group(1) or ""
            if mode == "vantagem":
                return f"{prefix}2d20kh1"
            return f"{prefix}2d20kl1"
        return re.sub(r'(?i)\b(\d*)d20\b(?!k[hl]\d)', repl, expr_in, count=1)
    return _apply_adv(expr, advantage_state)


async def _free_roll_embed_from_parsed(content: str, loc: str, author: discord.abc.User) -> discord.Embed:
    expr = content
    advantage_state = "normal"
    if re.match(r'^\s*(adv|vantagem|advantage)\b', expr, flags=re.IGNORECASE):
        advantage_state = "vantagem"
        expr = re.sub(r'^\s*(adv|vantagem|advantage)\b[:\-]*\s*', '', expr, flags=re.IGNORECASE)
    elif re.match(r'^\s*(dis|desvantagem|disadvantage)\b', expr, flags=re.IGNORECASE):
        advantage_state = "desvantagem"
        expr = re.sub(r'^\s*(dis|desvantagem|disadvantage)\b[:\-]*\s*', '', expr, flags=re.IGNORECASE)

    repeat = 1
    m_repeat = re.match(r'^\s*(\d+)\s*#\s*(.+)$', expr, flags=re.IGNORECASE)
    if m_repeat:
        repeat = max(1, int(m_repeat.group(1)))
        expr = m_repeat.group(2).strip()

    expr = _apply_adv_token(expr, advantage_state)
    expr = re.sub(r'(?i)(^|[^0-9a-zA-Z_])d(\d+)', r'\g<1>1d\2', expr)
    results = []
    for _ in range(repeat):
        total, breakdown = await dice_roller.roll_dice(expr)
        results.append((total, breakdown))

    title_single = _tr("roll.free.title.single", loc, "🎲 Rolagem")
    title_multi = _tr("roll.free.title.multi", loc, "🎲 Rolagens ({count})", count=repeat)
    details_label = _tr("roll.free.details", loc, "Detalhes")

    if repeat == 1:
        total, breakdown = results[0]
        embed = discord.Embed(
            title=title_single,
            description=f"## {total}",
            color=discord.Color.blurple()
        )
        embed.add_field(name=details_label, value=f"`{breakdown}`", inline=False)
    else:
        embed = discord.Embed(
            title=title_multi,
            color=discord.Color.blurple()
        )
        lines = []
        for i, (total, breakdown) in enumerate(results, start=1):
            lines.append(f"**#{i}** → **{total}**  ·  `{breakdown}`")
        embed.description = "\n".join(lines)

    embed.set_author(name=author.display_name, icon_url=author.display_avatar.url)
    return embed


class CoreCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        try:
            dice_roller.set_bot_instance(bot)
        except Exception:
            pass

    @localized_command(
        name_pt="bot_status",
        desc_pt="Mostrar capacidades automatizadas atuais do bot.",
        name_en="bot_status",
        desc_en="Show what automation features the bot currently provides.",
    )
    async def bot_status(self, interaction: discord.Interaction):
        loc = resolve_locale(interaction, fallback="pt")
        desc = _tr(
            "core.bot_status.body",
            loc,
            (
                "Este bot está com as seguintes automações ativas:\n"
                "• **HP Retroativo** (aumentos de Constituição ajustam PV de níveis anteriores).\n"
                "• **Travas de ASI** (+2 pontos obrigatórios em atributos com teto por campanha).\n"
                "• **Bônus de Proficiência Progressivo** (conforme nível D&D 5e).\n"
                "• **Reatividade de Atributos** (CA, Iniciativa e perícias reagem a mudanças em atributos)."
            ),
        )
        emb = discord.Embed(
            title=_tr("core.bot_status.title", loc, "⚙️ Status de Automação do Bot"),
            description=desc,
            color=discord.Color.blurple(),
        )
        await interaction.response.send_message(embed=emb, ephemeral=True)

    @localized_command(
        name_pt="dado", desc_pt="Abrir o hub de rolagens (ataque, testes, iniciativa).",
        name_en="dice", desc_en="Open the rolling hub (attack, checks, initiative)."
    )
    async def dado(self, interaction: discord.Interaction):
        loc = resolve_locale(interaction, fallback="pt")
        title = _tr("player.dice.hub.title", loc, "🎲 Centro de Rolagens")
        view = DiceHubView(user=interaction.user, loc=loc)
        await interaction.response.send_message(content=title, view=view, ephemeral=True)

    @app_commands.command(name="roll", description="Roll dice (e.g. 1d20+5, adv 1d20+3). Leave empty to open the hub.")
    @app_commands.describe(expressao="Expression like 1d20+5 or 4#1d6")
    async def roll_slash(self, interaction: discord.Interaction, expressao: str | None = None):
        loc = resolve_locale(interaction, fallback="pt")
        if not expressao or not str(expressao).strip():
            title = _tr("player.dice.hub.title", loc, "🎲 Centro de Rolagens")
            view = DiceHubView(user=interaction.user, loc=loc)
            return await interaction.response.send_message(content=title, view=view, ephemeral=True)
        try:
            embed = await _free_roll_embed_from_parsed(str(expressao).strip(), loc, interaction.user)
            await interaction.response.send_message(embed=embed)
        except Exception:
            log.exception("roll_slash failed")
            err = _tr("roll.free.error", loc, "❌ Não consegui interpretar essa rolagem. Tente algo como `1d20+5`.")
            await interaction.response.send_message(err, ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.content or message.author.bot:
            return

        content = message.content.strip()
        looks_like_roll = bool(re.search(r'(^\s*\d+\s*#)|(\bd\d+)|(\d+d\d+)', content, flags=re.IGNORECASE))
        adv_token = re.match(r'^\s*(adv|vantagem|advantage)\b', content, flags=re.IGNORECASE)
        dis_token = re.match(r'^\s*(dis|desvantagem|disadvantage)\b', content, flags=re.IGNORECASE)

        if not (looks_like_roll or adv_token or dis_token):
            return

        loc = _guess_message_locale(message)

        try:
            embed = await _free_roll_embed_from_parsed(content, loc, message.author)
            await message.channel.send(embed=embed)
        except Exception:
            log.exception("on_message free roll failed")
            err = _tr("roll.free.error", loc, "❌ Não consegui interpretar essa rolagem. Tente algo como `1d20+5`.")
            await message.channel.send(err)


async def setup(bot: commands.Bot):
    await bot.add_cog(CoreCog(bot))
