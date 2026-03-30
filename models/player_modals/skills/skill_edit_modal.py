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
from models.player_modals.player_basic_modal import PlayerModalBase
from utils.i18n import t
from utils.locale_resolver import resolve_locale

class SkillEditModal(PlayerModalBase):
    def __init__(self, interaction: discord.Interaction, skill_name: str | None = None):
        self.locale = resolve_locale(interaction)
        title_name = skill_name or t("common.new", self.locale)
        super().__init__(interaction, title=t("skill_edit.title", self.locale, name=title_name))

        self.skill_name_to_edit = skill_name
        pericia_data = (self.ficha.get("pericias", {}).get(skill_name, {}) if skill_name else {})

        self.nome = discord.ui.TextInput(
            label=t("skill_edit.name.label", self.locale),
            placeholder=t("skill_edit.name.ph", self.locale),
            default=skill_name or "",
            max_length=100,
            required=True
        )
        self.bonus = discord.ui.TextInput(
            label=t("skill_edit.bonus.label", self.locale),
            placeholder=t("skill_edit.bonus.ph", self.locale),
            default=str(pericia_data.get("bonus", 0)),
            max_length=6,
            required=True
        )
        _prof_default = pericia_data.get("proficiencia_dnd") or "nenhuma"
        self.prof_dnd = discord.ui.TextInput(
            label="D&D 5e — proficiência (opcional)",
            placeholder="nenhuma | proficiente | expertise",
            default=str(_prof_default),
            max_length=20,
            required=False
        )

        self.add_item(self.nome)
        self.add_item(self.bonus)
        self.add_item(self.prof_dnd)

    async def on_submit(self, interaction: discord.Interaction):
        from view.ficha_player.precicias_intermedio_view import AttributeLinkView

        try:
            bonus_val = int(self.bonus.value or 0)
            nome_val = (self.nome.value or "").strip()

            if not nome_val:
                raise ValueError(t("skill_edit.errors.empty_name", self.locale))

            if self.skill_name_to_edit and self.skill_name_to_edit != nome_val:
                pericias = self.ficha.setdefault("pericias", {})
                pericias.pop(self.skill_name_to_edit, None)
                self.save()

            prof_raw = (self.prof_dnd.value or "nenhuma").strip().lower() or "nenhuma"
            view = AttributeLinkView(
                user=interaction.user,
                skill_name=nome_val,
                skill_bonus=bonus_val,
                prof_dnd=prof_raw,
                guild_id=interaction.guild.id if interaction.guild else None,
            )

            await interaction.response.edit_message(
                content=t("skill_edit.next.prompt", self.locale, name=nome_val, bonus=bonus_val),
                view=view,
                embed=None
            )

        except ValueError as e:
            msg = str(e)
            if "invalid literal" in msg or msg == "":
                msg = t("skill_edit.errors.invalid_bonus", self.locale)
            await interaction.response.send_message(
                t("skill_edit.errors.prefix", self.locale, msg=msg),
                ephemeral=True
            )
