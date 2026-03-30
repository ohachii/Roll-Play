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
from data import dnd5e_srd
from utils import rpg_rules

def create_player_summary_embed(player_data: dict, user: discord.User) -> discord.Embed:
  info_basicas = player_data.get("informacoes_basicas", {})
  info_gerais = player_data.get("informacoes_gerais", {})
  extras = player_data.get("extras", {})

  embed = discord.Embed(
    title=f"📜 Resumo de {user.display_name}",
    description=f"**{info_basicas.get('titulo_apelido', 'Aventureiro')}**",
    color=user.color
  )

  aparencia_link = extras.get("aparencia")
  if aparencia_link and (aparencia_link.startswith("http://") or aparencia_link.startswith("https://")):
    embed.set_thumbnail(url=aparencia_link)
  else:
    embed.set_thumbnail(url=user.display_avatar.url)

  embed.add_field(name="Raça/Espécie", value=info_basicas.get('raca_especie', 'N/A'), inline=True)
  embed.add_field(name="Classe/Profissão", value=info_basicas.get('classe_profissao', 'N/A'), inline=True)
  embed.add_field(name="Nível/Rank", value=info_gerais.get('nivel_rank', 'N/A'), inline=True)

  if aparencia_link and not (aparencia_link.startswith("http://") or aparencia_link.startswith("https://")):
    embed.add_field(name="Aparência", value=aparencia_link, inline=False)

  # Modificadores D&D 5e ao lado do valor base
  sistema = (info_basicas.get("sistema_rpg") or "dnd")
  if rpg_rules.is_dnd_system(sistema):
    attrs = player_data.get("atributos", {}) or {}
    abbr = {
      "Força": "FOR",
      "Destreza": "DES",
      "Constituição": "CON",
      "Inteligência": "INT",
      "Sabedoria": "SAB",
      "Carisma": "CAR",
    }
    parts: list[str] = []
    for attr in dnd5e_srd.DND_ATTRIBUTES:
      try:
        score = int(attrs.get(attr) or 10)
      except Exception:
        score = 10
      mod = rpg_rules.calculate_modifier(score)
      parts.append(f"{abbr.get(attr, attr[:3].upper())}: {score} ({mod:+d})")
    embed.add_field(name="Modificadores", value=" | ".join(parts), inline=False)

  return embed


def create_npc_summary_embed(npc_data: dict) -> discord.Embed:
  info_basicas = npc_data.get("informacoes_basicas", {})
  info_gerais = npc_data.get("informacoes_gerais", {})
  extras = npc_data.get("extras", {})

  embed = discord.Embed(
    title=f"👹 {npc_data.get('nome', 'NPC')}",
    description=f"**{info_basicas.get('titulo_apelido', 'Criatura Misteriosa')}**",
    color=discord.Color.dark_red()
  )
  aparencia_valor = extras.get("aparencia") or npc_data.get("informacoes_extras", {}).get("aparencia")
  if aparencia_valor:
    if aparencia_valor.startswith("http://") or aparencia_valor.startswith("https://"):
      embed.set_image(url=aparencia_valor)
    else:
      embed.add_field(name="Aparência", value=aparencia_valor, inline=False)

  embed.add_field(name="Raça/Espécie", value=info_basicas.get('raca_especie', 'N/A'), inline=True)
  embed.add_field(name="Classe/Profissão", value=info_basicas.get('classe_profissao', 'N/A'), inline=True)
  embed.add_field(name="Nível/Rank", value=info_gerais.get('nivel_rank', 'N/A'), inline=True)

  return embed