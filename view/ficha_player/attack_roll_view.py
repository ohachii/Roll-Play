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
from utils import player_utils, rpg_rules, dice_roller
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


class AttackRollView(discord.ui.View):
  def __init__(self, user: discord.User):
    super().__init__(timeout=300)
    self.user = user
    self.character_name = f"{user.id}_{user.name.lower()}"
    self.selected_attack = None
    self.ficha = player_utils.load_player_sheet(self.character_name)
    self.advantage_state = "normal"
    self._loc = self.ficha.get("locale") or "pt"

    ataques = self.ficha.get("ataques", [])
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
    await interaction.response.defer(thinking=True)

    loc = resolve_locale(interaction, fallback=self._loc)

    if not self.selected_attack:
      msg = _tr("player.attack.need_selection", loc, "❌ Você precisa selecionar um ataque primeiro!")
      await interaction.followup.send(msg, ephemeral=True)
      return

    self.ficha = player_utils.load_player_sheet(self.character_name)

    try:
      roll_results = await dice_roller.execute_attack_roll(
        ficha=self.ficha,
        selected_attack=self.selected_attack,
        advantage_state=self.advantage_state
      )
    except Exception as e:
      err = _tr("player.attack.error", loc, "❌ Ocorreu um erro crítico ao calcular a rolagem. Verifique o console.")
      await interaction.followup.send(err, ephemeral=True)
      return

    adv_paren = ""
    if self.advantage_state == "vantagem":
      adv_paren = _tr("player.attack.adv.short",       loc, "(Vantagem)")
    elif self.advantage_state == "desvantagem":
      adv_paren = _tr("player.attack.disadv.short",    loc, "(Desvantagem)")

    adv_ital = ""
    if self.advantage_state == "vantagem":
      adv_ital = _tr("player.attack.adv.italic",       loc, "_Rolado com Vantagem_")
    elif self.advantage_state == "desvantagem":
      adv_ital = _tr("player.attack.disadv.italic",    loc, "_Rolado com Desvantagem_")

    lbl_hits        = _tr("player.attack.field.hits",      loc, "🎯 Acertos")
    lbl_hit         = _tr("player.attack.field.hit",       loc, "🎯 Acerto")
    lbl_damages     = _tr("player.attack.field.damages",   loc, "💥 Danos")
    lbl_damage      = _tr("player.attack.field.damage",    loc, "💥 Dano")
    lbl_effects     = _tr("player.attack.field.effects",   loc, "✨ Efeitos")
    lbl_info        = _tr("player.attack.field.info",      loc, "📊 Informações")
    lbl_details     = _tr("player.attack.field.details",   loc, "📋 Detalhes")
    lbl_summary     = _tr("player.attack.field.summary",   loc, "📈 Resumo")
    lbl_total_dmg_t = _tr("player.attack.total_damage",    loc, "**💥 Dano Total:** {total}")
    lbl_dmg_type_t  = _tr("player.attack.damage_type",     loc, "**🎯 Tipo de Dano:** {dtype}")
    lbl_type_t      = _tr("player.attack.type.short",      loc, "**🎯 Tipo:** {dtype}")

    # Embeds
    if roll_results.get('is_multiple', False):
      if roll_results.get('is_complex', False):
        title = _tr(
          "player.attack.multi.complex.title",
          loc,
          "⚔️ {n} Ataques Complexos: {atk}",
          n=roll_results['num_attacks'],
          atk=self.selected_attack['nome']
        )
        if roll_results['is_crit']:
          title = _tr(
            "player.attack.multi.complex.crit",
            loc,
            "💥 {n} ATAQUES COMPLEXOS COM CRÍTICO! {atk}",
            n=roll_results['num_attacks'],
            atk=self.selected_attack['nome']
          )
          color = discord.Color.gold()
        else:
          color = discord.Color.orange()

        embed = discord.Embed(title=title, color=color)
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(
          name=f"{lbl_hits} {adv_paren}",
          value=roll_results['acerto_breakdown'] or _tr("player.common.none_calculated", loc, "Nenhum acerto calculado"),
          inline=True
        )
        embed.add_field(
          name=lbl_damages,
          value=roll_results['dano_breakdown'] or _tr("player.common.none_calculated_dmg", loc, "Nenhum dano calculado"),
          inline=True
        )
        if roll_results.get("efeitos"):
          embed.add_field(name=lbl_effects, value=roll_results["efeitos"], inline=False)

        if roll_results.get('acertos_individuals'):
          acertos = roll_results['acertos_individuals']
          avg_acerto = sum(acertos) / len(acertos)

        if roll_results.get('info_breakdown'):
          embed.add_field(name=lbl_details, value=roll_results['info_breakdown'], inline=False)

        total_dano_text = lbl_total_dmg_t.format(total=roll_results['dano_total'])
        if roll_results.get('tipo_de_dano'):
          total_dano_text += " | " + _tr("player.attack.type.short", loc, "**🎯 Tipo:** {dtype}", dtype=roll_results['tipo_de_dano'])

        embed.add_field(name=lbl_summary, value=total_dano_text, inline=False)

      else:
        title = _tr(
          "player.attack.multi.title",
          loc,
          "⚔️ {n} Ataques: {atk}{weapon}",
          n=roll_results['num_attacks'],
          atk=self.selected_attack['nome'],
          weapon=roll_results.get('arma_usada_text', "")
        )
        if roll_results['is_crit']:
          title = _tr(
            "player.attack.multi.crit",
            loc,
            "💥 {n} ATAQUES COM CRÍTICO! {atk}{weapon}",
            n=roll_results['num_attacks'],
            atk=self.selected_attack['nome'],
            weapon=roll_results.get('arma_usada_text', "")
          )
          color = discord.Color.gold()
        else:
          color = getattr(interaction.user, "color", discord.Color.blurple())

        embed = discord.Embed(title=title, color=color)
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name=f"{lbl_hits} {adv_paren}", value=roll_results['acerto_breakdown'], inline=True)
        embed.add_field(name=lbl_damages, value=roll_results['dano_breakdown'], inline=True)

        if roll_results.get("efeitos"):
          embed.add_field(name=lbl_effects, value=roll_results["efeitos"], inline=False)

        if roll_results.get('info_breakdown'):
          embed.add_field(name=lbl_info, value=roll_results['info_breakdown'], inline=False)

        total_dano_text = lbl_total_dmg_t.format(total=roll_results['dano_total'])
        if roll_results.get('tipo_de_dano'):
          total_dano_text += "   |   " + _tr("player.attack.damage_type", loc, "**🎯 Tipo de Dano:** {dtype}", dtype=roll_results['tipo_de_dano'])

        embed.add_field(name=lbl_summary, value=total_dano_text, inline=False)

    else:
      title = _tr(
        "player.attack.single.title",
        loc,
        "⚔️ Ataque: {atk}{weapon}",
        atk=self.selected_attack['nome'],
        weapon=roll_results.get('arma_usada_text', "")
      )
      color = getattr(interaction.user, "color", discord.Color.blurple())
      if roll_results['is_crit']:
        title = _tr(
          "player.attack.single.crit",
          loc,
          "💥 ACERTO CRÍTICO! {atk}{weapon}",
          atk=self.selected_attack['nome'],
          weapon=roll_results.get('arma_usada_text', "")
        )
        color = discord.Color.gold()
      elif roll_results.get("is_fumble"):
        title = _tr(
          "player.attack.single.fumble",
          loc,
          "💀 FALHA (natural 1) — {atk}{weapon}",
          atk=self.selected_attack['nome'],
          weapon=roll_results.get('arma_usada_text', "")
        )
        color = discord.Color.dark_red()

      embed = discord.Embed(title=title, color=color)
      embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
      embed.add_field(
        name=f"{lbl_hit} {adv_ital}",
        value=f"**{roll_results['acerto_total']}**\n{roll_results['acerto_breakdown']}",
        inline=True
      )
      embed.add_field(
        name=lbl_damage,
        value=f"**{roll_results['dano_total']} {roll_results['tipo_de_dano']}**\n{roll_results['dano_breakdown']}",
        inline=True
      )
      if roll_results.get("efeitos"):
        embed.add_field(name=lbl_effects, value=roll_results["efeitos"], inline=False)

    await interaction.followup.send(embed=embed)

  class AttackSelect(discord.ui.Select):
    def __init__(self, ataques: list, parent_view: 'AttackRollView', locale: str = "pt"):
      self.parent_view = parent_view
      self._loc = locale
      options = [discord.SelectOption(label=a['nome'], value=a['nome']) for a in ataques]
      placeholder = _tr("player.attack.select.ph", locale, "Selecione um ataque para rolar...")
      super().__init__(placeholder=placeholder, options=options, disabled=not ataques, row=0, custom_id="player:attackroll:select")

    async def callback(self, interaction: discord.Interaction):
      selected_name = self.values[0]
      self.parent_view.selected_attack = next(
        (a for a in self.parent_view.ficha['ataques'] if a['nome'] == selected_name), None)
      await self.parent_view.update_state_buttons(interaction)

  class AdvantageButton(discord.ui.Button):
    def __init__(self, parent_view: 'AttackRollView', locale: str = "pt"):
      label = _tr("player.attack.btn.adv", locale, "Vantagem")
      super().__init__(label=label, style=discord.ButtonStyle.secondary, row=1, custom_id="player:attackroll:adv")
      self.parent_view = parent_view
      self.state_name = "vantagem"

    async def callback(self, interaction: discord.Interaction):
      self.parent_view.advantage_state = self.state_name
      await self.parent_view.update_state_buttons(interaction)

  class NormalButton(discord.ui.Button):
    def __init__(self, parent_view: 'AttackRollView', locale: str = "pt"):
      label = _tr("player.attack.btn.normal", locale, "Normal")
      super().__init__(label=label, style=discord.ButtonStyle.success, row=1, custom_id="player:attackroll:normal")
      self.parent_view = parent_view
      self.state_name = "normal"

    async def callback(self, interaction: discord.Interaction):
      self.parent_view.advantage_state = self.state_name
      await self.parent_view.update_state_buttons(interaction)

  class DisadvantageButton(discord.ui.Button):
    def __init__(self, parent_view: 'AttackRollView', locale: str = "pt"):
      label = _tr("player.attack.btn.disadv", locale, "Desvantagem")
      super().__init__(label=label, style=discord.ButtonStyle.secondary, row=1, custom_id="player:attackroll:disadv")
      self.parent_view = parent_view
      self.state_name = "desvantagem"

    async def callback(self, interaction: discord.Interaction):
      self.parent_view.advantage_state = self.state_name
      await self.parent_view.update_state_buttons(interaction)

  class RollAttackButton(discord.ui.Button):
    def __init__(self, parent_view: 'AttackRollView', locale: str = "pt"):
      label = _tr("player.attack.btn.roll", locale, "⚔️ Rolar Ataque")
      super().__init__(label=label, style=discord.ButtonStyle.danger, disabled=True, row=2, custom_id="player:attackroll:roll")
      self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
      await self.view.process_full_attack_roll(interaction)
