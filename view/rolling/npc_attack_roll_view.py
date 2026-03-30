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
import re
from utils import npc_utils, rpg_rules, dice_roller
from utils.npc_utils import NPCContext
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


class NPCAttackRollView(discord.ui.View):
  def __init__(self, npc_context: NPCContext):
    super().__init__(timeout=None)
    self.npc_context = npc_context
    self.selected_attack = None
    self.npc_data = self.npc_context.load()
    self.advantage_state = "normal"
    self._loc = (
      getattr(npc_context, "user_pref", None)
      or getattr(npc_context, "guild_pref", None)
      or getattr(npc_context, "locale", None)
      or "pt"
    )

    ataques = self.npc_data.get("ataques", [])
    self.attack_select = self.AttackSelect(ataques, self, locale=self._loc)
    self.roll_button = self.RollAttackButton(self, locale=self._loc)
    self.add_item(self.attack_select)
    self.add_item(self.AdvantageButton(self, locale=self._loc))
    self.add_item(self.NormalButton(self, locale=self._loc))
    self.add_item(self.DisadvantageButton(self, locale=self._loc))
    self.add_item(self.roll_button)

  async def update_state_buttons(self, interaction: discord.Interaction):
    for item in self.children:
      if hasattr(item, 'state_name'):
        item.style = discord.ButtonStyle.success if item.state_name == self.advantage_state else discord.ButtonStyle.secondary
    if self.selected_attack:
      for option in self.attack_select.options:
        option.default = (option.label == self.selected_attack['nome'])
    self.roll_button.disabled = self.selected_attack is None
    await interaction.response.edit_message(view=self)

  async def process_full_attack_roll(self, interaction: discord.Interaction):
    await interaction.response.defer()
    loc = resolve_locale(
      interaction,
      user_pref=getattr(self.npc_context, "user_pref", None),
      guild_pref=getattr(self.npc_context, "guild_pref", None),
      fallback=self._loc,
    )

    if not self.selected_attack:
      msg = _tr("npc.attack.need_selection", loc, "❌ Você precisa selecionar um ataque do NPC primeiro!")
      return await interaction.followup.send(msg, ephemeral=True)

    self.npc_data = self.npc_context.load()
    roll_results = await dice_roller.execute_attack_roll(
      ficha=self.npc_data,
      selected_attack=self.selected_attack,
      advantage_state=self.advantage_state
    )
    title_tpl = _tr(
      "npc.attack.title",
      loc,
      "⚔️ Ataque: {name} usa {attack}{weapon}",
      name=self.npc_context.npc_name,
      attack=self.selected_attack['nome'],
      weapon=roll_results.get('arma_usada_text', "")
    )
    color = discord.Color.dark_red()

    if roll_results.get('is_crit'):
      title_tpl = _tr(
        "npc.attack.title.crit",
        loc,
        "💥 ACERTO CRÍTICO! 💥 {name} usa {attack}{weapon}",
        name=self.npc_context.npc_name,
        attack=self.selected_attack['nome'],
        weapon=roll_results.get('arma_usada_text', "")
      )
      color = discord.Color.gold()
    elif roll_results.get("is_fumble"):
      title_tpl = _tr(
        "npc.attack.title.fumble",
        loc,
        "💀 FALHA (natural 1) — {name} usa {attack}{weapon}",
        name=self.npc_context.npc_name,
        attack=self.selected_attack['nome'],
        weapon=roll_results.get('arma_usada_text', "")
      )
      color = discord.Color.dark_red()

    adv_text = ""
    if self.advantage_state == "vantagem":
      adv_text = _tr("npc.attack.advantage", loc, "_Rolado com Vantagem_")
    elif self.advantage_state == "desvantagem":
      adv_text = _tr("npc.attack.disadvantage", loc, "_Rolado com Desvantagem_")

    lbl_hits      = _tr("npc.attack.field.hits",      loc, "🎯 Acertos")
    lbl_hit       = _tr("npc.attack.field.hit",       loc, "🎯 Acerto")
    lbl_damage    = _tr("npc.attack.field.damage",    loc, "💥 Dano")
    lbl_damages   = _tr("npc.attack.field.damages",   loc, "💥 Danos")
    lbl_info      = _tr("npc.attack.field.info",      loc, "📊 Informações")
    lbl_summary   = _tr("npc.attack.field.summary",   loc, "📈 Resumo")
    lbl_total     = _tr("npc.attack.total_damage",    loc, "**💥 Dano Total:** {total}", total=roll_results.get('dano_total'))
    lbl_type      = _tr("npc.attack.damage_type",     loc, "**🎯 Tipo de Dano:** {dtype}", dtype=roll_results.get('tipo_de_dano', ""))

    embed = discord.Embed(title=title_tpl, color=color)
    embed.set_author(
      name=_tr("npc.attack.rolled_by", loc, "Rolado por {user}", user=interaction.user.display_name),
      icon_url=interaction.user.display_avatar.url
    )

    if roll_results.get('is_multiple', False):
      embed.add_field(
        name=f"{lbl_hits} {adv_text}",
        value=roll_results['acerto_breakdown'],
        inline=True
      )
      embed.add_field(
        name=lbl_damages,
        value=roll_results['dano_breakdown'],
        inline=True
      )

      if roll_results.get('info_breakdown'):
        embed.add_field(
          name=lbl_info,
          value=roll_results['info_breakdown'],
          inline=False
        )

      total_line = lbl_total
      if roll_results.get('tipo_de_dano'):
        total_line += f"   |   {lbl_type}"

      embed.add_field(
        name=lbl_summary,
        value=total_line,
        inline=False
      )
    else:
      embed.add_field(
        name=f"{lbl_hit} {adv_text}",
        value=f"**{roll_results['acerto_total']}**\n{roll_results['acerto_breakdown']}",
        inline=True
      )
      embed.add_field(
        name=lbl_damage,
        value=f"**{roll_results['dano_total']} {roll_results['tipo_de_dano']}**\n{roll_results['dano_breakdown']}",
        inline=True
      )

    await interaction.followup.send(embed=embed)

  class AttackSelect(discord.ui.Select):
    def __init__(self, ataques: list, parent_view: 'NPCAttackRollView', locale: str = "pt"):
      self.parent_view = parent_view
      self._loc = locale
      options = [discord.SelectOption(label=a['nome'], value=a['nome']) for a in ataques]
      placeholder = _tr("npc.attack.select.ph", locale, "Selecione um ataque do NPC...")
      super().__init__(placeholder=placeholder, options=options, disabled=not ataques, row=0, custom_id="npc:attackroll:select")

    async def callback(self, interaction: discord.Interaction):
      if interaction.user.id != self.parent_view.npc_context.mestre_id:
        msg = _tr("npc.only_gm", resolve_locale(interaction, fallback=self._loc), "Apenas o mestre deste NPC pode interagir aqui.")
        return await interaction.response.send_message(msg, ephemeral=True)

      selected_name = self.values[0]
      self.parent_view.selected_attack = next(
        (a for a in self.parent_view.npc_data['ataques'] if a['nome'] == selected_name), None)
      await self.parent_view.update_state_buttons(interaction)

  class AdvantageButton(discord.ui.Button):
    def __init__(self, parent_view: 'NPCAttackRollView', locale: str = "pt"):
      label = _tr("npc.attack.btn.adv", locale, "Vantagem")
      super().__init__(label=label, style=discord.ButtonStyle.secondary, row=1, custom_id="npc:attackroll:adv")
      self.parent_view = parent_view
      self._loc = locale
      self.state_name = "vantagem"

    async def callback(self, interaction: discord.Interaction):
      if interaction.user.id != self.parent_view.npc_context.mestre_id:
        msg = _tr("npc.only_gm", resolve_locale(interaction, fallback=self._loc), "Apenas o mestre deste NPC pode interagir aqui.")
        return await interaction.response.send_message(msg, ephemeral=True)

      self.parent_view.advantage_state = self.state_name
      await self.parent_view.update_state_buttons(interaction)

  class NormalButton(discord.ui.Button):
    def __init__(self, parent_view: 'NPCAttackRollView', locale: str = "pt"):
      label = _tr("npc.attack.btn.normal", locale, "Normal")
      super().__init__(label=label, style=discord.ButtonStyle.success, row=1, custom_id="npc:attackroll:normal")
      self.parent_view = parent_view
      self._loc = locale
      self.state_name = "normal"

    async def callback(self, interaction: discord.Interaction):
      if interaction.user.id != self.parent_view.npc_context.mestre_id:
        msg = _tr("npc.only_gm", resolve_locale(interaction, fallback=self._loc), "Apenas o mestre deste NPC pode interagir aqui.")
        return await interaction.response.send_message(msg, ephemeral=True)

      self.parent_view.advantage_state = self.state_name
      await self.parent_view.update_state_buttons(interaction)

  class DisadvantageButton(discord.ui.Button):
    def __init__(self, parent_view: 'NPCAttackRollView', locale: str = "pt"):
      label = _tr("npc.attack.btn.disadv", locale, "Desvantagem")
      super().__init__(label=label, style=discord.ButtonStyle.secondary, row=1, custom_id="npc:attackroll:disadv")
      self.parent_view = parent_view
      self._loc = locale
      self.state_name = "desvantagem"

    async def callback(self, interaction: discord.Interaction):
      if interaction.user.id != self.parent_view.npc_context.mestre_id:
        msg = _tr("npc.only_gm", resolve_locale(interaction, fallback=self._loc), "Apenas o mestre deste NPC pode interagir aqui.")
        return await interaction.response.send_message(msg, ephemeral=True)

      self.parent_view.advantage_state = self.state_name
      await self.parent_view.update_state_buttons(interaction)

  class RollAttackButton(discord.ui.Button):
    def __init__(self, parent_view: 'NPCAttackRollView', locale: str = "pt"):
      label = _tr("npc.attack.btn.roll", locale, "⚔️ Rolar Ataque do NPC")
      super().__init__(label=label, style=discord.ButtonStyle.danger, disabled=True, row=2, custom_id="npc:attackroll:roll")
      self.parent_view = parent_view
      self._loc = locale

    async def callback(self, interaction: discord.Interaction):
      if interaction.user.id != self.parent_view.npc_context.mestre_id:
        msg = _tr("npc.only_gm", resolve_locale(interaction, fallback=self._loc), "Apenas o mestre deste NPC pode interagir aqui.")
        return await interaction.response.send_message(msg, ephemeral=True)

      await self.view.process_full_attack_roll(interaction)
