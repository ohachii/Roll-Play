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

import discord
from view.ficha_player.player_info_menu import PlayerInfoMenuView
from view.ficha_player.atributos.ded import PlayerDeAtributosView
from view.ficha_player.player_skills import PlayerAtaquesMenuView
from view.ficha_player.player_itens import PlayerInventarioMenuView
from view.ficha_player.player_satus import PlayerStatusMenuView
from view.ficha_player.player_config_avancada import PlayerRoleplayMenuView
from view.ficha_player.precicias_intermedio_view import SkillManagementView
from models.player_modals.dashboard_modifier import TestsDashboardView
from utils.i18n import t as t_raw
from utils.locale_resolver import resolve_locale

def _tr(key: str, locale: str, fallback: str, **kwargs) -> str:
    """
    Wrapper para usar i18n.t com fallback seguro.
    Se a chave não existir (t retorna a própria key), usamos o fallback informado.
    """
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


class PlayerMainMenuView(discord.ui.View):
    def __init__(self, user: discord.User):
        super().__init__(timeout=None)
        self.user = user
        self._loc = "pt"

        for item in self.children:
            if isinstance(item, discord.ui.Button):
                if item.custom_id == "player:main:info":
                    item.label = _tr("player.menu.btn.info", self._loc, "📜 Informações")
                elif item.custom_id == "player:main:attrs":
                    item.label = _tr("player.menu.btn.attrs", self._loc, "💪 Atributos")
                elif item.custom_id == "player:main:inventory":
                    item.label = _tr("player.menu.btn.inventory", self._loc, "🎒 Inventário")
                elif item.custom_id == "player:main:combat":
                    item.label = _tr("player.menu.btn.combat", self._loc, "⚔️ Combate")
                elif item.custom_id == "player:main:about":
                    item.label = _tr("player.menu.btn.about", self._loc, "🧔 Sobre o personagem")
                elif item.custom_id == "player:main:roleplay":
                    item.label = _tr("player.menu.btn.roleplay", self._loc, "🎭 Roleplay")
                elif item.custom_id == "player:main:skills":
                    item.label = _tr("player.menu.btn.skills", self._loc, "⚙️ Proficiência & Expertises")
                elif item.custom_id == "player:main:tests":
                    item.label = _tr("player.menu.btn.tests", self._loc, "🛡️ Testes e Resistências")

    @discord.ui.button(label="📜 Informações", style=discord.ButtonStyle.primary, custom_id="player:main:info")
    async def infos(self, interaction: discord.Interaction, button: discord.ui.Button):
        loc = resolve_locale(interaction, fallback=self._loc)
        content = _tr("player.menu.info.title", loc, "📝 Menu de **Informações**")
        await interaction.response.edit_message(
            content=content,
            view=PlayerInfoMenuView(user=self.user)
        )

    @discord.ui.button(label="💪 Atributos", style=discord.ButtonStyle.success, custom_id="player:main:attrs")
    async def atributos(self, interaction: discord.Interaction, button: discord.ui.Button):
        loc = resolve_locale(interaction, fallback=self._loc)
        content = _tr("player.menu.attrs.title", loc, "📊 Menu de **Atributos**")
        await interaction.response.edit_message(
            content=content,
            view=PlayerDeAtributosView(user=self.user)
        )

    @discord.ui.button(label="🎒 Inventário", style=discord.ButtonStyle.primary, custom_id="player:main:inventory")
    async def inventario(self, interaction: discord.Interaction, button: discord.ui.Button):
        loc = resolve_locale(interaction, fallback=self._loc)
        view = PlayerInventarioMenuView(user=interaction.user)
        content = _tr("player.menu.inventory.title", loc, "🎒 Menu de **Inventário**")
        await interaction.response.edit_message(
            content=content,
            view=view
        )

    @discord.ui.button(label="⚔️ Combate", style=discord.ButtonStyle.secondary, custom_id="player:main:combat")
    async def ataques(self, interaction: discord.Interaction, button: discord.ui.Button):
        loc = resolve_locale(interaction, fallback=self._loc)
        content = _tr("player.menu.combat.title", loc, "🗡️ Menu de **Ataques & Habilidades**")
        await interaction.response.edit_message(
            content=content,
            view=PlayerAtaquesMenuView(user=self.user)
        )

    @discord.ui.button(label="🧔 Sobre o personagem", style=discord.ButtonStyle.danger, custom_id="player:main:about")
    async def status_e_condicoes(self, interaction: discord.Interaction, button: discord.ui.Button):
        loc = resolve_locale(interaction, fallback=self._loc)
        view = PlayerStatusMenuView(user=interaction.user)
        content = _tr("player.menu.about.title", loc, "🧔 Menu de **Sobre o personagem**")
        await interaction.response.edit_message(
            content=content,
            view=view
        )

    @discord.ui.button(label="🎭 Roleplay", style=discord.ButtonStyle.success, custom_id="player:main:roleplay")
    async def roleplay(self, interaction: discord.Interaction, button: discord.ui.Button):
        loc = resolve_locale(interaction, fallback=self._loc)
        view = PlayerRoleplayMenuView(user=interaction.user)
        content = _tr("player.menu.roleplay.title", loc, "🎭 Menu de **Roleplay**")
        await interaction.response.edit_message(
            content=content,
            view=view
        )

    @discord.ui.button(label="⚙️ Proficiência & Expertises", style=discord.ButtonStyle.success, custom_id="player:main:skills")
    async def manage_skills(self, interaction: discord.Interaction, button: discord.ui.Button):
        loc = resolve_locale(interaction, fallback=self._loc)
        if interaction.user.id != self.user.id:
            msg = _tr("player.menu.only_self", loc, "Você só pode interagir com o seu próprio menu.")
            await interaction.response.send_message(msg, ephemeral=True)
            return
        view = SkillManagementView(user=interaction.user, guild_id=interaction.guild.id if interaction.guild else None)
        content = _tr("player.menu.skills.title", loc, "⚙️ Menu de **Gerenciamento de Proficências e Expertises**")
        await interaction.response.edit_message(
            content=content,
            view=view
        )

    @discord.ui.button(label="🛡️ Testes e Resistências", style=discord.ButtonStyle.primary, custom_id="player:main:tests")
    async def manage_tests(self, interaction: discord.Interaction, button: discord.ui.Button):
        loc = resolve_locale(interaction, fallback=self._loc)
        if interaction.user.id != self.user.id:
            msg = _tr("player.menu.only_self", loc, "Você só pode interagir com o seu próprio menu.")
            await interaction.response.send_message(msg, ephemeral=True)
            return
        view = TestsDashboardView(user=interaction.user)
        embed = view.create_embed()

        await interaction.response.edit_message(
            content=None,
            embed=embed,
            view=view
        )
