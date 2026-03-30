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
from discord.ext import commands
from discord import app_commands
from utils import player_utils, mestre_utils
from utils.i18n import t as t_raw
from utils.locale_resolver import resolve_locale
from view.ficha_player.ficha_player_menu import PlayerMainMenuView
from view.ficha_player.personal_sheet_view import PersonalSheetView
from utils.embed_utils import create_player_summary_embed
from models.shared_models.add_pet_modal import AddPetModal
from view.pet_view.npc_pet_selector_view import NPCPetSelectorView
from view.character_creation.character_creator_view import CreatorRaceClassView

def _tr(key: str, locale: str, fallback: str, **kwargs) -> str:
    try:
        text = t_raw(key, locale, **kwargs)
    except Exception:
        return fallback.format(**kwargs) if kwargs else fallback
    if text == key:
        return fallback.format(**kwargs) if kwargs else fallback
    return text

def localized_command(name_pt, desc_pt, name_en, desc_en):
    def decorator(func):
        cmd = app_commands.command(name=name_pt, description=desc_pt)(func)
        cmd.name_localizations = {"en-US": name_en, "en-GB": name_en}
        cmd.description_localizations = {"en-US": desc_en, "en-GB": desc_en}
        return cmd
    return decorator

class PlayerCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @localized_command(
        name_pt="criar_ficha",
        desc_pt="Assistente D&D 5e: raça, classe, 4d6 (3 chances) e distribuição de atributos.",
        name_en="create_sheet",
        desc_en="D&D 5e wizard: race, class, 4d6×3 rolls and assign stats.",
    )
    @app_commands.describe(sobrescrever="Se já existir ficha, substitui pela nova.")
    async def criar_ficha(self, interaction: discord.Interaction, sobrescrever: bool = False):
        loc = resolve_locale(interaction, fallback="pt")
        character_name = f"{interaction.user.id}_{interaction.user.name.lower()}"
        gid = interaction.guild.id if interaction.guild else None
        if player_utils.player_sheet_exists(character_name, guild_id=gid) and not sobrescrever:
            msg = _tr(
                "player.create.exists",
                loc,
                "❌ Você já tem uma ficha. Use `sobrescrever: Sim` para refazer do zero.",
            )
            return await interaction.response.send_message(msg, ephemeral=True)
        emb = discord.Embed(
            title="📜 Criação de personagem (D&D 5e)",
            description=(
                "1) Escolha **raça**, **classe** e **antecedente**.\n"
                "2) **Rolagem:** 4d6 descartando o menor, **3 conjuntos** (2 rerrolagens).\n"
                "3) **Distribua** cada valor a um atributo; depois informe o **nome**.\n"
                "Os bônus raciais são aplicados automaticamente."
            ),
            color=discord.Color.green(),
        )
        view = CreatorRaceClassView(interaction.user, sobrescrever=sobrescrever)
        await interaction.response.send_message(embed=emb, view=view, ephemeral=True)

    @localized_command(
        name_pt="player_menu", desc_pt="Abrir o menu do player",
        name_en="player_menu", desc_en="Open the player menu"
    )
    async def player_menu(self, interaction: discord.Interaction):
        loc = resolve_locale(interaction, fallback="pt")
        title = _tr("player.menu.main.title", loc, "🎮 Menu Principal do Player")
        await interaction.response.send_message(
            content=title,
            view=PlayerMainMenuView(user=interaction.user),
            ephemeral=True
        )

    @localized_command(
        name_pt="minha_ficha", desc_pt="Exibe sua ficha de personagem interativa.",
        name_en="my_sheet", desc_en="Show your interactive character sheet."
    )
    async def minha_ficha(self, interaction: discord.Interaction):
        loc = resolve_locale(interaction, fallback="pt")
        character_name = f"{interaction.user.id}_{interaction.user.name.lower()}"
        gid = interaction.guild.id if interaction.guild else None
        if not player_utils.player_sheet_exists(character_name, guild_id=gid):
            msg = _tr("player.sheet.missing", loc, "❌ Você ainda não tem uma ficha! Use `/player_menu` para começar.")
            return await interaction.response.send_message(msg, ephemeral=True)
        view = PersonalSheetView(user=interaction.user, guild_id=gid)
        initial = await view.create_embed()
        await interaction.response.send_message(embed=initial, view=view, ephemeral=True)

    @localized_command(
        name_pt="ficha",
        desc_pt="Escolhe qual ficha do seu arquivo carregar (se houver mais de uma).",
        name_en="sheet",
        desc_en="Pick which character sheet file to open.",
    )
    async def ficha(self, interaction: discord.Interaction):
        loc = resolve_locale(interaction, fallback="pt")
        gid = interaction.guild.id if interaction.guild else None
        slugs = player_utils.list_player_sheet_slugs_for_user(interaction.user.id, guild_id=gid)
        if not slugs:
            msg = _tr("player.sheet.none", loc, "❌ Você ainda não tem fichas. Use `/criar_ficha` primeiro.")
            return await interaction.response.send_message(msg, ephemeral=True)

        entries: list[tuple[str, str]] = []
        for slug in slugs[:10]:
            try:
                data = player_utils.load_player_sheet(slug, guild_id=interaction.guild.id if interaction.guild else None)
                title = data.get("informacoes_basicas", {}).get("titulo_apelido") or slug
                entries.append((slug, str(title)))
            except Exception:
                entries.append((slug, slug))

        class SheetPickView(discord.ui.View):
            def __init__(self, user: discord.User, items: list[tuple[str, str]]):
                super().__init__(timeout=180)
                self._user = user
                self._items = items

                for i, (_slug, label) in enumerate(items):
                    btn = discord.ui.Button(
                        label=f"📄 Ficha: {label[:20]}",
                        style=discord.ButtonStyle.primary,
                        custom_id=f"player:sheet:pick:{i}",
                        row=0 if i < 2 else 1,
                    )

                    async def _cb(btn_interaction: discord.Interaction, idx: int = i):
                        if btn_interaction.user.id != self._user.id:
                            return await btn_interaction.response.send_message("Não é sua ficha.", ephemeral=True)
                        char_name, _ = self._items[idx]
                        view = PersonalSheetView(
                            user=self._user,
                            character_name=char_name,
                            guild_id=btn_interaction.guild.id if btn_interaction.guild else None,
                        )
                        embed = await view.create_embed()
                        await btn_interaction.response.edit_message(embed=embed, view=view, content=None)

                    btn.callback = _cb
                    self.add_item(btn)

        view = SheetPickView(interaction.user, entries)
        await interaction.response.send_message(
            content=_tr("player.sheet.pick.prompt", loc, "Selecione qual ficha abrir:"),
            view=view,
            ephemeral=True,
        )

    @localized_command(
        name_pt="ver_player", desc_pt="Exibe a ficha de um jogador.",
        name_en="view_player", desc_en="Show a player's sheet."
    )
    @app_commands.describe(jogador="Jogador alvo / Target player")
    async def ver_player(self, interaction: discord.Interaction, jogador: discord.Member):
        loc = resolve_locale(interaction, fallback="pt")
        character_name = f"{jogador.id}_{jogador.name.lower()}"
        gid = interaction.guild.id if interaction.guild else None
        if not player_utils.player_sheet_exists(character_name, guild_id=gid):
            msg = _tr("player.sheet.other_missing", loc, "❌ O jogador **{name}** ainda não possui uma ficha.",
                      name=jogador.display_name)
            return await interaction.response.send_message(msg, ephemeral=True)

        if mestre_utils.verificar_mestre(interaction.guild.name, interaction.user.id):
            view = PersonalSheetView(
                user=jogador,
                character_name=character_name,
                guild_id=interaction.guild.id if interaction.guild else None,
            )
            embed = await view.create_embed()
            header = _tr("player.sheet.master_view", loc, "👁️ Visão de Mestre: Ficha completa de **{name}**",
                         name=jogador.display_name)
            await interaction.response.send_message(header, embed=embed, view=view, ephemeral=True)
        else:
            ps = player_utils.load_player_sheet(character_name, guild_id=interaction.guild.id if interaction.guild else None)
            embed = create_player_summary_embed(ps, jogador)
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @localized_command(
        name_pt="registrar_pet", desc_pt="Registra um novo pet para seu personagem ou para um NPC.",
        name_en="register_pet", desc_en="Register a new pet for your character or an NPC."
    )
    async def registrar_pet(self, interaction: discord.Interaction):
        loc = resolve_locale(interaction, fallback="pt")
        guild_name = interaction.guild.name
        user_id = interaction.user.id

        if mestre_utils.verificar_mestre(guild_name, user_id):
            view = NPCPetSelectorView(interaction.guild_id, user_id)
            msg = _tr("pet.master.prompt", loc, "Você é um mestre. Selecione um NPC para registrar um pet para ele:")
            await interaction.response.send_message(msg, view=view, ephemeral=True)
            return

        modal = AddPetModal()
        await interaction.response.send_modal(modal)
        await modal.wait()
        if modal.pet_data:
            character_name = f"{user_id}_{interaction.user.name.lower()}"
            player_sheet = player_utils.load_player_sheet(character_name, guild_id=interaction.guild.id if interaction.guild else None)
            pets_list = player_sheet.setdefault("pets", [])
            pets_list.append(modal.pet_data)
            player_utils.save_player_sheet(character_name, player_sheet, guild_id=interaction.guild.id if interaction.guild else None)
            msg = _tr("pet.player.saved", loc, "🐾 Pet **{pet}** foi registrado para seu personagem!",
                      pet=modal.pet_data['nome'])
            await interaction.followup.send(msg, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(PlayerCog(bot))
