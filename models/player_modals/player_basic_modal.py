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
from utils.player_utils import load_player_sheet, save_player_sheet
from utils.i18n import t
from utils.locale_resolver import resolve_locale

class PlayerModalBase(discord.ui.Modal):
    def __init__(self, interaction: discord.Interaction, title: str | None = None):
        self.locale = resolve_locale(interaction)
        final_title = title if title is not None else t("common.sheet_title", self.locale)

        super().__init__(title=final_title)
        self.interaction = interaction
        self.character_name = f"{interaction.user.id}_{interaction.user.name.lower()}"
        guild_id = interaction.guild.id if interaction.guild else None
        self.ficha = load_player_sheet(self.character_name, guild_id=guild_id)

    def tr(self, key: str, **kwargs) -> str:
        return t(key, self.locale, **kwargs)

    def save(self):
        guild_id = self.interaction.guild.id if self.interaction.guild else None
        if guild_id is not None:
            self.ficha["guild_id"] = int(guild_id)
        save_player_sheet(self.character_name, self.ficha, guild_id=guild_id)
