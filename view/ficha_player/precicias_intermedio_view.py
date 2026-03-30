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
from utils import player_utils
from models.player_modals.skills.skill_edit_modal import SkillEditModal
from utils import rpg_rules
from utils.i18n import t as t_raw
from utils.locale_resolver import resolve_locale

def _tr(key: str, locale: str, fallback: str, **kwargs) -> str:
  """
  Wrapper para i18n.t com fallback seguro.
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


class SkillManagementView(discord.ui.View):
  def __init__(self, user: discord.User, guild_id: int | None = None):
    super().__init__(timeout=None)
    self.user = user
    self._loc = "pt"
    self.guild_id = guild_id

    self.add_item(self.SkillActionSelect(user=self.user, parent_view=self))
    self.add_item(self.BackButton(user=self.user))

  def create_embed(self) -> discord.Embed:
    character_name = f"{self.user.id}_{self.user.name.lower()}"
    ficha = player_utils.load_player_sheet(character_name, guild_id=self.guild_id)
    pericias = ficha.get("pericias", {})

    title = _tr("player.skills.embed.title", self._loc, "💡 Perícias de {name}", name=self.user.display_name)
    embed = discord.Embed(title=title, color=self.user.color)

    if not pericias:
      embed.description = _tr(
        "player.skills.embed.none",
        self._loc,
        "Você ainda não possui nenhuma perícia.\nUse o menu abaixo para adicionar sua primeira perícia!"
      )
    else:
      description = ""
      for nome, dados in pericias.items():
        if isinstance(dados, dict):
          bonus = dados.get('bonus', 0)
          sinal = "+" if bonus >= 0 else ""
          atributo = dados.get('atributo_base', 'N/A')
          prof = dados.get("proficiencia_dnd") or "nenhuma"
          description += f"• **{nome}** (`{atributo}` {sinal}{bonus}, prof D&D: {prof})\n"
        elif isinstance(dados, str):
          description += f"• **{nome}** (`{dados}` +0) - *Formato antigo*\n"
      embed.description = description

    return embed

  class SkillActionSelect(discord.ui.Select):
    def __init__(self, user: discord.User, parent_view: 'SkillManagementView'):
      self.user = user
      self.parent_view = parent_view

      character_name = f"{user.id}_{user.name.lower()}"
      ficha = player_utils.load_player_sheet(character_name, guild_id=self.parent_view.guild_id)
      pericias = ficha.get("pericias", {})

      options = [
        discord.SelectOption(
          label=_tr("player.skills.select.add", parent_view._loc, "➕ Adicionar Nova Perícia"),
          value="CREATE_NEW"
        )
      ]
      if pericias:
        options.append(discord.SelectOption(
          label=_tr("player.skills.select.remove", parent_view._loc, "➖ Remover Perícias"),
          value="REMOVE_SKILLS",
          emoji="🗑️"
        ))
        options.extend([
          discord.SelectOption(
            label=_tr("player.skills.select.edit_prefix", parent_view._loc, "✏️ Editar: {name}", name=nome),
            value=nome
          ) for nome in pericias.keys()
        ])

      placeholder = _tr("player.skills.select.placeholder", parent_view._loc, "Escolha uma ação...")
      super().__init__(placeholder=placeholder, options=options)

    async def callback(self, interaction: discord.Interaction):
      self.parent_view._loc = resolve_locale(interaction, fallback=self.parent_view._loc)

      selection = self.values[0]
      if selection == "CREATE_NEW":
        await interaction.response.send_modal(SkillEditModal(interaction))
      elif selection == "REMOVE_SKILLS":
        view = RemoveSkillView(user=self.user, loc=self.parent_view._loc, guild_id=self.parent_view.guild_id)
        content = _tr("player.skills.remove.prompt", self.parent_view._loc, "Selecione as perícias para remover:")
        await interaction.response.edit_message(content=content, embed=None, view=view)
      else:
        await interaction.response.send_modal(SkillEditModal(interaction, skill_name=selection))

  class BackButton(discord.ui.Button):
    def __init__(self, user: discord.User):
      super().__init__(label="🔙 Voltar", style=discord.ButtonStyle.danger, row=1, custom_id="player:skills:back")
      self.user = user

    async def callback(self, interaction: discord.Interaction):
      from view.ficha_player.ficha_player_menu import PlayerMainMenuView
      loc = resolve_locale(interaction, fallback="pt")
      view = PlayerMainMenuView(user=self.user)
      content = _tr("player.menu.main.title", loc, "🎮 Menu Principal do Player")
      await interaction.response.edit_message(content=content, view=view, embed=None)


class RemoveSkillView(discord.ui.View):
  def __init__(self, user: discord.User, loc: str = "pt", guild_id: int | None = None):
    super().__init__(timeout=None)
    self.user = user
    self._loc = loc
    self.character_name = f"{user.id}_{user.name.lower()}"
    self.guild_id = guild_id

    ficha = player_utils.load_player_sheet(self.character_name, guild_id=self.guild_id)
    pericias = ficha.get("pericias", {})

    if pericias:
      self.add_item(self.SkillRemoveSelect(list(pericias.keys()), parent_view=self))
      self.add_item(self.ConfirmRemoveButton())
    self.add_item(self.CancelButton(user, guild_id=self.guild_id))

  class SkillRemoveSelect(discord.ui.Select):
    def __init__(self, skills: list, parent_view: 'RemoveSkillView'):
      self.parent_view = parent_view
      placeholder = _tr(
        "player.skills.remove.placeholder",
        parent_view._loc,
        "Selecione as perícias para remover..."
      )
      options = [discord.SelectOption(label=skill) for skill in skills]
      super().__init__(placeholder=placeholder, min_values=1, max_values=len(skills), options=options)

    async def callback(self, interaction: discord.Interaction):
      await interaction.response.defer()

  class ConfirmRemoveButton(discord.ui.Button):
    def __init__(self):
      super().__init__(label="Confirmar Remoção", style=discord.ButtonStyle.danger, row=1, custom_id="player:skills:confirm_remove")

    async def callback(self, interaction: discord.Interaction):
      if hasattr(self.view, "_loc"):
        loc = resolve_locale(interaction, fallback=self.view._loc)
      else:
        loc = resolve_locale(interaction, fallback="pt")

      skills_to_remove = self.view.children[0].values
      ficha = player_utils.load_player_sheet(self.view.character_name, guild_id=self.view.guild_id)
      for skill in skills_to_remove:
        ficha["pericias"].pop(skill, None)
      player_utils.save_player_sheet(self.view.character_name, ficha, guild_id=self.view.guild_id)

      view = SkillManagementView(user=self.view.user, guild_id=self.view.guild_id)
      view._loc = loc
      new_embed = view.create_embed()
      msg = _tr(
        "player.skills.remove.done",
        loc,
        "✅ **{count}** perícia(s) removida(s)!",
        count=len(skills_to_remove)
      )
      await interaction.response.edit_message(content=msg, embed=new_embed, view=view)

  class CancelButton(discord.ui.Button):
    def __init__(self, user: discord.User, guild_id: int | None = None):
      super().__init__(label="Cancelar", style=discord.ButtonStyle.secondary, row=1, custom_id="player:skills:cancel")
      self.user = user
      self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
      loc = resolve_locale(interaction, fallback="pt")
      view = SkillManagementView(user=self.user, guild_id=self.guild_id)
      view._loc = loc
      embed = view.create_embed()
      await interaction.response.edit_message(content=None, embed=embed, view=view)


class AttributeLinkView(discord.ui.View):
  def __init__(
      self,
      user: discord.User,
      skill_name: str,
      skill_bonus: int,
      prof_dnd: str = "",
      guild_id: int | None = None,
  ):
    super().__init__(timeout=180)
    self.user = user
    self.skill_name = skill_name
    self.skill_bonus = skill_bonus
    self.prof_dnd = (prof_dnd or "").strip().lower() or "nenhuma"
    self._loc = "pt"
    self.guild_id = guild_id

    character_name = f"{user.id}_{user.name.lower()}"
    ficha = player_utils.load_player_sheet(character_name, guild_id=self.guild_id)
    sistema = ficha.get("informacoes_basicas", {}).get("sistema_rpg", "dnd")
    atributos = rpg_rules.get_system_checks(sistema)

    self.add_item(self.AttributeSelect(atributos, parent_view=self))

  class AttributeSelect(discord.ui.Select):
    def __init__(self, atributos: list, parent_view: 'AttributeLinkView'):
      self.parent_view = parent_view
      placeholder = _tr("player.skills.attr.placeholder", parent_view._loc, "Selecione o atributo base...")
      options = [discord.SelectOption(label=attr) for attr in atributos]
      super().__init__(placeholder=placeholder, options=options)

    async def callback(self, interaction: discord.Interaction):
      loc = resolve_locale(interaction, fallback=self.parent_view._loc)
      selected_attribute = self.values[0]

      character_name = f"{self.view.user.id}_{self.view.user.name.lower()}"
      ficha = player_utils.load_player_sheet(character_name, guild_id=self.view.guild_id)
      pericias = ficha.setdefault("pericias", {})

      entry = {
        "atributo_base": selected_attribute,
        "bonus": self.view.skill_bonus,
      }
      if self.view.prof_dnd and self.view.prof_dnd != "nenhuma":
        entry["proficiencia_dnd"] = self.view.prof_dnd
      pericias[self.view.skill_name] = entry

      player_utils.save_player_sheet(character_name, ficha, guild_id=self.view.guild_id)

      from view.ficha_player.precicias_intermedio_view import SkillManagementView
      view = SkillManagementView(user=self.view.user, guild_id=self.view.guild_id)
      view._loc = loc
      embed = view.create_embed()
      content = _tr(
        "player.skills.attr.saved",
        loc,
        "✅ Perícia **{skill}** salva com o atributo **{attr}**!",
        skill=self.view.skill_name,
        attr=selected_attribute
      )
      await interaction.response.edit_message(
        content=content,
        embed=embed,
        view=view
      )
