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
  Wrapper para i18n.t com fallback seguro.
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


class NPCTempModifierModal(discord.ui.Modal):
  def __init__(self, parent_view: 'NPCAttributeCheckView', locale: str = "pt"):
    title = _tr("npc.attr.mod.modal.title", locale, "🎲 Modificador Adicional para NPC")
    super().__init__(title=title, custom_id="npc:attrcheck:tempmod")
    self.parent_view = parent_view
    self._loc = locale

    self.modifier_input = discord.ui.TextInput(
      label=_tr("npc.attr.mod.field.label", locale, "Bônus ou Penalidade"),
      placeholder=_tr("npc.attr.mod.field.ph", locale, "Ex: +2, -1d4, +1d6"),
      custom_id="npc:attrcheck:tempmod:field"
    )
    self.add_item(self.modifier_input)

  async def on_submit(self, interaction: discord.Interaction):
    if interaction.user.id != self.parent_view.npc_context.mestre_id:
      msg = _tr("npc.only_gm", resolve_locale(interaction, fallback=self._loc), "Apenas o mestre deste NPC pode interagir aqui.")
      return await interaction.response.send_message(msg, ephemeral=True)

    self.parent_view.temp_modifier_str = self.modifier_input.value

    added = _tr("npc.attr.mod.added", self._loc, "Bônus de **{mod}** adicionado.", mod=self.modifier_input.value)
    await self.parent_view.update_view(interaction, added)


class NPCAttributeCheckView(discord.ui.View):
  def __init__(self, npc_context: npc_utils.NPCContext):
    super().__init__(timeout=180)
    self.npc_context = npc_context
    self.npc_data = self.npc_context.load()
    self.sistema = self.npc_data.get("informacoes_basicas", {}).get("sistema_rpg", "dnd")
    self._loc = (
      getattr(npc_context, "user_pref", None)
      or getattr(npc_context, "guild_pref", None)
      or getattr(npc_context, "locale", None)
      or "pt"
    )
    self.selected_category = None
    self.selected_skill_or_attr = None
    self.temp_modifier_str = ""
    self.advantage_state = "normal"

    self._add_components()

  def _add_components(self):
    self.clear_items()
    self.add_item(self.create_category_select())
    self.add_item(self.create_skill_or_attr_select())
    self.add_item(self.create_temp_modifier_button())
    self.add_item(self.create_advantage_button())
    self.add_item(self.create_normal_button())
    self.add_item(self.create_disadvantage_button())
    self.add_item(self.create_roll_button())

  async def update_view(self, interaction: discord.Interaction, content: str = None):
    await interaction.response.defer()
    self._add_components()
    content = content or interaction.message.content
    await interaction.edit_original_response(content=content, view=self)

  def create_category_select(self):
    categorias_de_pericia = rpg_rules.get_system_skills(self.sistema).keys()
    opt_attrcheck = _tr("npc.attr.category.attrcheck", self._loc, "Teste de Resistência")
    opt_skill_fmt = _tr("npc.attr.category.skills_of", self._loc, "Perícias de {cat}", cat="{cat}")

    options = [discord.SelectOption(label=opt_skill_fmt.format(cat=cat), value=f"skillcat_{cat}") for cat in categorias_de_pericia]
    options.insert(0, discord.SelectOption(label=opt_attrcheck, value="attr_check", emoji="🛡️"))

    if self.selected_category:
      for option in options:
        if option.value == self.selected_category:
          option.default = True

    placeholder = _tr("npc.attr.select.category.ph", self._loc, "1. Escolha a categoria do teste...")
    select = discord.ui.Select(placeholder=placeholder, options=options, row=0, custom_id="npc:attrcheck:category")

    async def callback(interaction: discord.Interaction):
      if interaction.user.id != self.npc_context.mestre_id:
        return
      self.selected_category = select.values[0]
      self.selected_skill_or_attr = None
      msg = _tr("npc.attr.prompt.pick_skill_or_attr", resolve_locale(interaction, fallback=self._loc), "2. Agora escolha a perícia ou atributo específico.")
      await self.update_view(interaction, msg)

    select.callback = callback
    return select

  def create_skill_or_attr_select(self):
    options = []
    placeholder = _tr("npc.attr.select.skill.placeholder", self._loc, "2. Primeiro escolha uma categoria...")
    is_disabled = True

    if self.selected_category:
      is_disabled = False
      pericias_aprendidas = self.npc_data.get("pericias", {})

      if self.selected_category == "attr_check":
        atributos = rpg_rules.get_system_checks(self.sistema)
        placeholder = _tr("npc.attr.select.attr.ph", self._loc, "2. Escolha o Atributo de Resistência...")
        options = [discord.SelectOption(label=attr, value=f"attr_{attr}") for attr in atributos]

      elif self.selected_category.startswith("skillcat_"):
        category_name = self.selected_category.replace("skillcat_", "")
        todas_pericias_sistema = rpg_rules.get_system_skills(self.sistema)
        pericias_na_categoria = set(todas_pericias_sistema.get(category_name, []))

        for nome_pericia, dados_pericia in pericias_aprendidas.items():
          if isinstance(dados_pericia, dict) and dados_pericia.get("atributo_base") == category_name:
            pericias_na_categoria.add(nome_pericia)

        placeholder = _tr("npc.attr.select.skill.of_cat", self._loc, "2. Escolha a Perícia de {cat}...", cat=category_name)

        for pericia in sorted(list(pericias_na_categoria)):
          option = discord.SelectOption(label=pericia, value=f"skill_{pericia}")
          if pericia in pericias_aprendidas:
            bonus_data = pericias_aprendidas.get(pericia, {})
            bonus = bonus_data.get('bonus', 0) if isinstance(bonus_data, dict) else 0
            plus_fmt = _tr("npc.attr.select.skill.plus", self._loc, " (+{bonus})", bonus=bonus)
            option.label += plus_fmt
            option.emoji = "💡"
          options.append(option)

    if not options:
      options.append(discord.SelectOption(label=_tr("npc.attr.select.none", self._loc, "Nenhuma opção disponível"), value="placeholder"))
      is_disabled = True

    if self.selected_skill_or_attr:
      for option in options:
        if option.value == self.selected_skill_or_attr:
          option.default = True

    select = discord.ui.Select(placeholder=placeholder, options=options, disabled=is_disabled, row=1, custom_id="npc:attrcheck:skillorattr")

    async def callback(interaction: discord.Interaction):
      if interaction.user.id != self.npc_context.mestre_id:
        return
      self.selected_skill_or_attr = select.values[0]
      sel_name = select.values[0].split('_', 1)[-1]
      msg = _tr("npc.attr.selection.ready", resolve_locale(interaction, fallback=self._loc), "Seleção: **{name}**. Pronto para rolar.", name=sel_name)
      await self.update_view(interaction, msg)

    select.callback = callback
    return select

  def create_roll_button(self):
    label = _tr("npc.attr.roll.btn", self._loc, "Rolar Teste do NPC!")
    button = discord.ui.Button(
      label=label,
      style=discord.ButtonStyle.red,
      disabled=(self.selected_skill_or_attr is None),
      row=3,
      custom_id="npc:attrcheck:roll"
    )

    async def callback(interaction: discord.Interaction):
      if interaction.user.id != self.npc_context.mestre_id:
        return
      await interaction.response.defer()

      is_skill_roll = self.selected_skill_or_attr.startswith("skill_")
      selected_name = self.selected_skill_or_attr.split('_', 1)[-1]

      hit_dice_expression = "1d20"
      advantage_text = ""
      if self.advantage_state == "vantagem":
        hit_dice_expression = "2d20kh1"
        advantage_text = _tr("npc.attr.adv.text", resolve_locale(interaction, fallback=self._loc), "_(Vantagem)_")
      elif self.advantage_state == "desvantagem":
        hit_dice_expression = "2d20kl1"
        advantage_text = _tr("npc.attr.disadv.text", resolve_locale(interaction, fallback=self._loc), "_(Desvantagem)_")

      natural_roll, raw_d20_breakdown = await dice_roller.roll_dice(hit_dice_expression)
      is_crit = (natural_roll == 20)
      is_fumble = (natural_roll == 1)

      atributo_base_final = selected_name
      skill_data = None
      if is_skill_roll:
        todas_pericias_sistema = rpg_rules.get_system_skills(self.sistema)
        pericias_aprendidas = self.npc_data.get("pericias", {})
        skill_data = pericias_aprendidas.get(selected_name)
        if skill_data and isinstance(skill_data, dict):
          atributo_base_final = skill_data.get("atributo_base") or atributo_base_final
        else:
          for attr, skills in todas_pericias_sistema.items():
            if selected_name in skills:
              atributo_base_final = attr
              break

      bonus_pericia = rpg_rules.dnd_flat_bonus_for_check(
        self.npc_data,
        self.sistema,
        is_skill_roll=is_skill_roll,
        selected_skill_or_attr_name=selected_name,
        skill_data=skill_data,
        atributo_base=atributo_base_final,
      )

      atributos_ficha = self.npc_data.get("atributos", {})
      attr_score_str = (atributos_ficha.get(atributo_base_final)
                        or atributos_ficha.get(atributo_base_final.lower())
                        or atributos_ficha.get(atributo_base_final.capitalize())
                        or atributos_ficha.get(atributo_base_final.upper())
                        or "10")

      modificador_atributo = rpg_rules.get_modifier(self.sistema, int(attr_score_str))

      bonus_string = f"{modificador_atributo} + {bonus_pericia}"
      if self.temp_modifier_str:
        bonus_string += f" {self.temp_modifier_str}"

      bonus_total, _ = await dice_roller.roll_dice(bonus_string)
      resultado_final = natural_roll + bonus_total

      title = _tr("npc.attr.embed.title", resolve_locale(interaction, fallback=self._loc), "🛡️ Teste de {sel} para {npc}", sel=selected_name, npc=self.npc_context.npc_name)
      embed = discord.Embed(title=title, description=f"## {resultado_final}", color=discord.Color.dark_orange())

      if is_crit:
        embed.description += "\n" + _tr("npc.attr.embed.crit", self._loc, "**✨ SUCESSO CRÍTICO! ✨**")
        embed.color = discord.Color.gold()
      elif is_fumble:
        embed.description += "\n" + _tr("npc.attr.embed.fumble", self._loc, "**💀 FALHA CRÍTICA! 💀**")
        embed.color = discord.Color.dark_red()

      embed.set_author(
        name=_tr("npc.attack.rolled_by", self._loc, "Rolado por {user}", user=interaction.user.display_name),
        icon_url=interaction.user.display_avatar.url
      )

      details_label = _tr("npc.attr.embed.details", self._loc, "Detalhes {adv}", adv=advantage_text)
      details_value = _tr("npc.attr.embed.details.value", self._loc, "{breakdown} + Bônus({bonus}) = **{total}**",
                          breakdown=raw_d20_breakdown, bonus=bonus_total, total=resultado_final)
      embed.add_field(name=details_label, value=details_value)

      await interaction.followup.send(embed=embed)

    button.callback = callback
    return button

  def create_temp_modifier_button(self):
    label = _tr("npc.attr.mod.btn", self._loc, "🎲 Bônus/Pena")
    button = discord.ui.Button(label=label, style=discord.ButtonStyle.secondary, row=3, custom_id="npc:attrcheck:tempmod:open")

    async def callback(interaction: discord.Interaction):
      if interaction.user.id != self.npc_context.mestre_id:
        return
      loc = resolve_locale(interaction, fallback=self._loc)
      await interaction.response.send_modal(NPCTempModifierModal(self, locale=loc))

    button.callback = callback
    return button

  def create_advantage_button(self):
    label = _tr("npc.attack.btn.adv", self._loc, "Vantagem")
    style = discord.ButtonStyle.success if self.advantage_state == "vantagem" else discord.ButtonStyle.secondary
    button = discord.ui.Button(label=label, style=style, row=2, custom_id="npc:attrcheck:adv")

    async def callback(interaction: discord.Interaction):
      if interaction.user.id != self.npc_context.mestre_id:
        return
      self.advantage_state = "vantagem"
      await self.update_view(interaction)

    button.callback = callback
    return button

  def create_normal_button(self):
    label = _tr("npc.attack.btn.normal", self._loc, "Normal")
    style = discord.ButtonStyle.success if self.advantage_state == "normal" else discord.ButtonStyle.secondary
    button = discord.ui.Button(label=label, style=style, row=2, custom_id="npc:attrcheck:normal")

    async def callback(interaction: discord.Interaction):
      if interaction.user.id != self.npc_context.mestre_id:
        return
      self.advantage_state = "normal"
      await self.update_view(interaction)

    button.callback = callback
    return button

  def create_disadvantage_button(self):
    label = _tr("npc.attack.btn.disadv", self._loc, "Desvantagem")
    style = discord.ButtonStyle.success if self.advantage_state == "desvantagem" else discord.ButtonStyle.secondary
    button = discord.ui.Button(label=label, style=style, row=2, custom_id="npc:attrcheck:disadv")

    async def callback(interaction: discord.Interaction):
      if interaction.user.id != self.npc_context.mestre_id:
        return
      self.advantage_state = "desvantagem"
      await self.update_view(interaction)

    button.callback = callback
    return button
