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
from utils.npc_utils import NPCContext
from view.ficha_npc.npc_submenu import NPCMainMenuView
from utils.i18n import t as t_raw
from utils.locale_resolver import resolve_locale

def _tr(key: str, locale: str, fallback: str, **kwargs) -> str:
    """
    Wrapper para usar i18n.t com fallback.
    Se a chave não existir (t retorna a própria key), usa o fallback informado.
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


class CreateNPCModal(discord.ui.Modal):
    def __init__(self, guild_id: int, mestre_id: int, locale: str = "pt"):
        title = _tr("npc.select.create.title", locale, "Criar Novo NPC")
        super().__init__(title=title, custom_id="npc:create:modal")
        self.guild_id = guild_id
        self.mestre_id = mestre_id
        self._loc = locale

        self.npc_name_input = discord.ui.TextInput(
            label=_tr("npc.select.create.name.label", locale, "Nome do NPC"),
            placeholder=_tr("npc.select.create.name.ph", locale, "Digite o nome do NPC"),
            required=True,
            max_length=100,
            custom_id="npc:create:field:name"
        )
        self.add_item(self.npc_name_input)

    async def on_submit(self, interaction: discord.Interaction):
        loc = resolve_locale(interaction, fallback=self._loc)

        npc_name = self.npc_name_input.value.strip()
        # Supabase migração: a detecção de duplicata deve usar o banco (ou fallback JSON).
        existing = NPCContext.list_npcs(self.guild_id, self.mestre_id)
        if npc_name in existing:
            msg = _tr(
                "npc.select.create.duplicate",
                loc,
                "❌ Já existe um NPC chamado **{name}**. Por favor, escolha outro nome.",
                name=npc_name
            )
            await interaction.response.send_message(msg, ephemeral=True)
            return

        context = NPCContext(self.guild_id, self.mestre_id, npc_name)
        context.save({"nome": npc_name, "visivel_para_players": False})

        view = NPCMainMenuView(npc_context=context)
        content = _tr(
            "npc.select.editing_new",
            loc,
            "📜 Editando o novo NPC: **{name}**",
            name=npc_name
        )
        await interaction.response.edit_message(content=content, view=view)


class NPCSelect(discord.ui.Select):
    def __init__(self, guild_id: int, mestre_id: int, locale: str = "pt"):
        self.guild_id = guild_id
        self.mestre_id = mestre_id
        self._loc = locale

        npc_names = NPCContext.list_npcs(guild_id, mestre_id)

        opt_desc_edit = _tr("npc.select.option.edit.desc", locale, "Editar NPC existente")
        options = [
            discord.SelectOption(label=npc, value=npc, description=opt_desc_edit)
            for npc in npc_names
        ]
        options.append(
            discord.SelectOption(
                label=_tr("npc.select.option.create.label", locale, "➕ Criar Novo NPC"),
                value="create_new",
                description=_tr("npc.select.option.create.desc", locale, "Começar a criação de um novo NPC")
            )
        )

        super().__init__(
            placeholder=_tr("npc.select.placeholder", locale, "Selecione um NPC ou crie um novo..."),
            min_values=1,
            max_values=1,
            options=options,
            custom_id="npc:select:list"
        )

    async def callback(self, interaction: discord.Interaction):
        loc = resolve_locale(interaction, fallback=self._loc)
        selected = self.values[0]

        if selected == "create_new":
            await interaction.response.send_modal(CreateNPCModal(self.guild_id, self.mestre_id, locale=loc))
        else:
            npc_context = NPCContext(self.guild_id, self.mestre_id, selected)
            content = _tr(
                "npc.select.editing",
                loc,
                "📜 Editando NPC: **{name}**",
                name=selected
            )
            await interaction.response.edit_message(
                content=content,
                view=NPCMainMenuView(npc_context=npc_context),
            )


class NPCSelectView(discord.ui.View):
    def __init__(self, guild_id: int, mestre_id: int, interaction: discord.Interaction | None = None):
        super().__init__(timeout=None)
        loc = resolve_locale(interaction, fallback="pt") if interaction else "pt"
        self.add_item(NPCSelect(guild_id, mestre_id, locale=loc))
