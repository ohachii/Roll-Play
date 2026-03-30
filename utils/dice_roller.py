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

import d20
import asyncio
import re
from discord.ext import commands
from utils import rpg_rules

bot_ref: commands.Bot = None

def set_bot_instance(bot_instance: commands.Bot):
  global bot_ref
  bot_ref = bot_instance


def natural_d20_kept_face_from_roll_text(text: str) -> int:
  """Face do d20 que vale para o ataque (dado mantido com vantagem/desvantagem)."""
  m = re.search(r"\(([^)]+)\)", text)
  if not m:
    for x in re.findall(r"\b(\d+)\b", text):
      v = int(x)
      if 1 <= v <= 20:
        return v
    return 10
  inner = m.group(1)
  kept: list[int] = []
  for part in inner.split(","):
    part = part.strip()
    if "~~" in part:
      continue
    nm = re.search(r"(\d+)", part)
    if nm:
      v = int(nm.group(1))
      if 1 <= v <= 20:
        kept.append(v)
  if len(kept) == 1:
    return kept[0]
  if len(kept) >= 2:
    low = text.lower()
    if "kl" in low:
      return min(kept)
    if "kh" in low:
      return max(kept)
    return kept[0]
  return 10


def natural_d20_kept_face_from_roll(roll) -> int:
  return natural_d20_kept_face_from_roll_text(str(roll))


async def _roll_attack_with_d20(expr: str) -> tuple[int, str, object]:
  translated = _translate_to_d20_syntax(expr.strip())
  def do_roll():
    return d20.roll(translated, allow_comments=True)
  if bot_ref and getattr(bot_ref, "loop", None):
    r = await bot_ref.loop.run_in_executor(None, do_roll)
  else:
    r = do_roll()
  b = _clean_d20_formatting(str(r))
  return r.total, b, r


async def _dnd_crit_roll_damage_twice(dano_base_str: str, modifier: int) -> tuple[int, str]:
  """D&D 5e: em crítico, rola os dados de dano duas vezes e soma o modificador uma vez."""
  dice_1, br1 = await roll_dice(dano_base_str)
  dice_2, br2 = await roll_dice(dano_base_str)
  total = dice_1 + dice_2 + modifier
  breakdown = (
    f"Dados (crítico — 5e: 2× rolagem dos dados): {br1}\n"
    f"+ segunda rolagem: {br2}\n"
    f"Modificador (1×): {modifier:+}\n**Total: {total}**"
  )
  return total, breakdown

def _translate_to_d20_syntax(dice_string: str) -> str:
  normalized = re.sub(r'\s+', '', dice_string)

  if len(normalized) > 100 or normalized.count('*') > 3 or normalized.count('+') > 10:
    normalized = re.sub(r'(\d)(\()', r'\1*\2', normalized)
    normalized = re.sub(r'(\))(\d)', r'\1*\2', normalized)
    return normalized
  special_commands = [
    r'^s#', r'^ore#', r'^fortune#', r'^group#',
    r'^[BGW]\d+',
    r'<<', r'>>', r'>=', r'<=', r'>', r'<', r'=',
    r'c\d+', r'!', r'ns',
    r'\+\+', r'--'
  ]
  if '++' in normalized:
    match = re.match(r'(\d+)d(\d+)\+\+(\d+)', normalized)
    if match:
      dice_count = int(match.group(1))
      bonus_per_die = int(match.group(3))
      total_bonus = dice_count * bonus_per_die
      normalized = f"{match.group(1)}d{match.group(2)}+{total_bonus}"
  elif '--' in normalized:
    match = re.match(r'(\d+)d(\d+)\-\-(\d+)', normalized)
    if match:
      dice_count = int(match.group(1))
      bonus_per_die = int(match.group(3))
      total_bonus = dice_count * bonus_per_die
      normalized = f"{match.group(1)}d{match.group(2)}-{total_bonus}"
  for pattern in special_commands:
    if re.search(pattern, normalized, re.IGNORECASE):
      return normalized
  if re.match(r'^(\d+)?dF', normalized, re.IGNORECASE):
    match = re.match(r'^(\d+)?dF', normalized, re.IGNORECASE)
    count = int(match.group(1)) if match.group(1) else 1
    return f"{count}d3-{count * 2}"
  if '(' in normalized and ')' in normalized:
    return normalized
  if 'adv' in normalized.lower():
    if 'd20' in normalized.lower():
      normalized = re.sub(r'.*d20.*', '2d20kh1', normalized, flags=re.IGNORECASE)
    else:
      normalized = re.sub(r'adv', '', normalized, flags=re.IGNORECASE)
      if not re.search(r'\d*d20', normalized, re.IGNORECASE):
        normalized = '2d20kh1' + normalized
      else:
        normalized = re.sub(r'(\d*)d20', r'2d20kh1', normalized, flags=re.IGNORECASE)
  elif 'dis' in normalized.lower() or 'disadvantage' in normalized.lower():
    if 'd20' in normalized.lower():
      normalized = re.sub(r'.*d20.*', '2d20kl1', normalized, flags=re.IGNORECASE)
    else:
      normalized = re.sub(r'dis(advantage)?', '', normalized, flags=re.IGNORECASE)
      if not re.search(r'\d*d20', normalized, re.IGNORECASE):
        normalized = '2d20kl1' + normalized
      else:
        normalized = re.sub(r'(\d*)d20', r'2d20kl1', normalized, flags=re.IGNORECASE)
  if re.search(r'(\d+d\d+)dl(\d+)', normalized, re.IGNORECASE):
    match = re.search(r'(\d+d\d+)dl(\d+)', normalized, re.IGNORECASE)
    dice_expr = match.group(1)
    drop_count = int(match.group(2))
    dice_count = int(re.search(r'(\d+)d', dice_expr).group(1))
    keep_count = dice_count - drop_count
    normalized = re.sub(r'(\d+d\d+)dl(\d+)', f'{dice_expr}kh{keep_count}', normalized, flags=re.IGNORECASE)
  if re.search(r'(\d+d\d+)d(\d+)', normalized, re.IGNORECASE):
    match = re.search(r'(\d+d\d+)d(\d+)', normalized, re.IGNORECASE)
    dice_expr = match.group(1)
    drop_count = int(match.group(2))
    dice_count = int(re.search(r'(\d+)d', dice_expr).group(1))
    keep_count = dice_count - drop_count
    normalized = re.sub(r'(\d+d\d+)d(\d+)', f'{dice_expr}kh{keep_count}', normalized, flags=re.IGNORECASE)
  if re.search(r'(\d+d\d+)dh(\d+)', normalized, re.IGNORECASE):
    match = re.search(r'(\d+d\d+)dh(\d+)', normalized, re.IGNORECASE)
    dice_expr = match.group(1)
    drop_count = int(match.group(2))
    dice_count = int(re.search(r'(\d+)d', dice_expr).group(1))
    keep_count = dice_count - drop_count
    normalized = re.sub(r'(\d+d\d+)dh(\d+)', f'{dice_expr}kl{keep_count}', normalized, flags=re.IGNORECASE)
  if normalized.startswith('d') and normalized[1:].isdigit():
    normalized = '1' + normalized
  return normalized

def _format_advantage_result(result_str: str, is_advantage: bool = True) -> str:
    try:
      if 'kh1' in result_str or 'kl1' in result_str:
        rolls_match = re.search(r'\(([^)]+)\)', result_str)
        if rolls_match:
          dice_rolls = rolls_match.group(1)
          rolls = re.findall(r'(\d+)|~~(\d+)~~', dice_rolls)
          valid_dice = []
          discarded_dice = []
          for roll in rolls:
            if roll[1]:
              discarded_dice.append(roll[1])
            elif roll[0]:
              valid_dice.append(roll[0])
          total_match = re.search(r'=\s*(\d+)', result_str)
          final_result = total_match.group(1) if total_match else "?"
          if is_advantage:
            return f"🎯 Vantagem\n- Dado mantido: {', '.join(valid_dice)}\n- Dado descartado: {', '.join(discarded_dice)}"
          else:
            return f"⚠️ Desvantagem\n- Dado mantido: {', '.join(valid_dice)}\n- Dado descartado: {', '.join(discarded_dice)}"
      return result_str
    except:
      return result_str

def _format_drop_keep_result(result_str: str) -> str:
  try:
    total_match = re.search(r'=\s*`?(\d+)`?', result_str)
    final_result = total_match.group(1) if total_match else "?"
    expr_match = re.search(r'(\d+d\d+[k][hl]\d+)\s*\(([^)]+)\)', result_str)
    if expr_match:
      dice_expr = expr_match.group(1)
      dice_rolls = expr_match.group(2)
      all_numbers = re.findall(r'(\d+)', dice_rolls)
      all_numbers = [int(num) for num in all_numbers]
      is_keep_highest = 'kh' in dice_expr
      keep_count = int(re.search(r'[k][hl](\d+)', dice_expr).group(1))
      sorted_numbers = sorted(all_numbers, reverse=is_keep_highest)
      kept_numbers = sorted_numbers[:keep_count]
      dropped_numbers = sorted_numbers[keep_count:]
      kept_dice = [str(num) for num in kept_numbers]
      dropped_dice = [str(num) for num in dropped_numbers]
      return f"🎲 Resultado\n- Dados mantidos: {', '.join(kept_dice)}\n- Dados descartados: {', '.join(dropped_dice)}"
    return result_str
  except Exception as e:
    print(f"Erro no format_drop_keep: {e}")
    return result_str

def _format_comparison_result(result_str: str, original_expr: str, result_total: int) -> str:
  try:
    dice_rolls_match = re.search(r'\(([^)]+)\)', result_str)
    if dice_rolls_match:
      dice_rolls = dice_rolls_match.group(1)
      numbers = re.findall(r'\d+', dice_rolls)
      real_total = sum(int(num) for num in numbers)
    else:
      real_total = result_total
    operators = ['>=', '<=', '>>', '<<', '>', '<', '=']
    found_operator = None
    for op in operators:
      if op in original_expr:
        found_operator = op
        break
    if not found_operator:
      return result_str
    parts = original_expr.split(found_operator)
    if len(parts) < 2:
      return result_str
    left_expr = parts[0].strip()
    right_value = parts[1].strip()
    try:
      right_num = int(right_value)
    except:
      return result_str
    is_true = False
    if found_operator == '>=':
      is_true = real_total >= right_num
    elif found_operator == '<=':
      is_true = real_total <= right_num
    elif found_operator == '>':
      is_true = real_total > right_num
    elif found_operator == '<':
      is_true = real_total < right_num
    elif found_operator == '=':
      is_true = real_total == right_num
    elif found_operator == '<<':
      is_true = real_total
    elif found_operator == '>>':
      is_true = real_total
    result_text = "✅ Verdadeiro" if is_true else "❌ Falso"
    if found_operator in ['<<', '>>']:
      return f"🔍 **Comparação**: {original_expr}\n**Resultado**: {real_total} dados\n**Avaliação**: {result_text}"
    else:
      return f"🔍 **Comparação**: {original_expr}\n**Total dos dados**: {real_total}\n**Avaliação**: {real_total} {found_operator} {right_num} → {result_text}"
  except Exception as e:
    return result_str

def _clean_d20_formatting(result_str: str) -> str:
  result_str = re.sub(r'`(\d+)`', r'\1', result_str)
  result_str = re.sub(r'\((\d+d\d+ \([^)]+\))\)', r'\1', result_str)
  return result_str

def is_complex_expression(expr: str) -> bool:
  if not expr or not isinstance(expr, str):
    return False
  return len(expr) > 50 or expr.count('d') > 10 or expr.count('*') > 3 or expr.count('+') > 8

async def roll_dice(dice_string: str) -> tuple[int, str]:
  if not bot_ref:
    return 0, "Erro: Instância do bot não foi definida."
  loop = bot_ref.loop
  def do_roll():
    original_string = dice_string.strip()
    try:
      def is_complex_expression(expr):
        return len(expr) > 100 or expr.count('d') > 20 or expr.count('*') > 5 or expr.count('+') > 15
      if is_complex_expression(original_string):
        return handle_complex_expression(original_string)
      translated_string = _translate_to_d20_syntax(original_string)
      subexpressions = re.split(r'(?=[\+\-])', translated_string)
      total = 0
      breakdown_parts = []
      for expr in subexpressions:
        expr = expr.strip()
        if not expr:
          continue
        sign = 1
        if expr.startswith('+'):
          expr = expr[1:].strip()
        elif expr.startswith('-'):
          sign = -1
          expr = expr[1:].strip()
        if not re.search(r'\d*d\d+', expr):
          try:
            val = int(expr)
            total += val * sign
            breakdown_parts.append(f"Modificador: {val:+}")
          except:
            pass
          continue
        roll_result = d20.roll(expr, allow_comments=True)
        subtotal = roll_result.total * sign
        total += subtotal
        rolls_text = str(roll_result)
      breakdown_parts.append(f"{expr}: {rolls_text} = {subtotal}")
      breakdown = "🎲 **Detalhes das Rolagens:**\n"
      breakdown += "\n".join(breakdown_parts)
      breakdown += f"\n\n💥 **Total Final: {total}**"

      return total, breakdown
      comparison_operators = ['>=', '<=', '>', '<', '=', '<<', '>>']
      has_comparison = any(op in original_string for op in comparison_operators)
      repeat_match = re.match(r'^\s*(\d+)\s*#\s*(.+)$', original_string)
      if repeat_match:
        count = int(repeat_match.group(1))
        expr = repeat_match.group(2).strip()
        translated_expr = _translate_to_d20_syntax(expr)
        results = []
        individual_totals = []
        for i in range(count):
          r = d20.roll(translated_expr, allow_comments=True)
          result_str = str(r)
          if any(op in expr for op in comparison_operators):
            formatted = _format_comparison_result(result_str, expr, r.total)
          else:
            is_advantage = 'adv' in expr.lower() or 'kh1' in translated_expr
            is_disadvantage = 'dis' in expr.lower() or 'kl1' in translated_expr
            if is_advantage or is_disadvantage:
              formatted = _format_advantage_result(result_str, is_advantage)
            elif 'kh' in translated_expr or 'kl' in translated_expr:
              formatted = _format_drop_keep_result(result_str)
            else:
              formatted = _clean_d20_formatting(result_str)
          results.append(f"{i + 1}# {formatted}")
          individual_totals.append(r.total)
        breakdown = "\n".join(results)
        return 0, breakdown
      if re.match(r'^\s*s#', original_string, re.IGNORECASE):
        expr = re.sub(r'^\s*s#', '', original_string, flags=re.IGNORECASE).strip()
        translated_expr = _translate_to_d20_syntax(expr)
        result = d20.roll(translated_expr, allow_comments=True)
        result_str = str(result)
        try:
          detailed_values = []
          def extract_all_dice(node):
            if hasattr(node, 'values'):
              for child in node.values:
                extract_all_dice(child)
            elif hasattr(node, 'expr'):
              extract_all_dice(node.expr)
            elif hasattr(node, 'data'):
              if hasattr(node.data, 'size') and hasattr(node.data, 'values'):
                vals = node.data.values
                size = node.data.size
                detailed_values.append(f"d{size}: {', '.join(str(v) for v in vals)}")
              elif hasattr(node, 'kept') or hasattr(node, 'dropped'):
                kept = [d.values[0] for d in getattr(node, 'kept', []) if hasattr(d, 'values')]
                dropped = [d.values[0] for d in getattr(node, 'dropped', []) if hasattr(d, 'values')]
                if kept or dropped:
                  txt = ""
                  if kept:
                    txt += f"Válidos: {kept}"
                  if dropped:
                    txt += f" | Descartados: {dropped}"
                  detailed_values.append(txt)
          extract_all_dice(result.expr)
          if detailed_values:
            detailed_text = "\n".join(f"🎲 {t}" for t in detailed_values)
            result_str = f"{result_str}\n\n📊 Detalhes completos:\n{detailed_text}"
        except Exception as e:
          print(f"[Debug: erro ao detalhar rolagem] {type(e).__name__}: {e}")

        if any(op in expr for op in comparison_operators):
          result_str = _format_comparison_result(result_str, expr, result.total)
        else:
          if 'adv' in expr.lower() or 'kh1' in translated_expr:
            result_str = _format_advantage_result(result_str, True)
          elif 'dis' in expr.lower() or 'kl1' in translated_expr:
            result_str = _format_advantage_result(result_str, False)
          elif 'kh' in translated_expr or 'kl' in translated_expr:
            result_str = _format_drop_keep_result(result_str)
          else:
            result_str = _clean_d20_formatting(result_str)
        return result.total, f"||{result_str}||"
      translated_string = _translate_to_d20_syntax(original_string)
      result = d20.roll(translated_string, allow_comments=True)
      result_str = str(result)
      try:
        detailed_values = []

        def extract_all_dice(node):
          if hasattr(node, 'values'):
            for child in node.values:
              extract_all_dice(child)
          elif hasattr(node, 'expr'):
            extract_all_dice(node.expr)
          elif hasattr(node, 'data'):
            # Dado simples
            if hasattr(node.data, 'size') and hasattr(node.data, 'values'):
              vals = node.data.values
              size = node.data.size
              detailed_values.append(f"d{size}: {', '.join(str(v) for v in vals)}")
            elif hasattr(node, 'kept') or hasattr(node, 'dropped'):
              kept = [d.values[0] for d in getattr(node, 'kept', []) if hasattr(d, 'values')]
              dropped = [d.values[0] for d in getattr(node, 'dropped', []) if hasattr(d, 'values')]
              if kept or dropped:
                txt = ""
                if kept:
                  txt += f"Válidos: {kept}"
                if dropped:
                  txt += f" | Descartados: {dropped}"
                detailed_values.append(txt)

        extract_all_dice(result.expr)

        if detailed_values:
          detailed_text = "\n".join(f"🎲 {t}" for t in detailed_values)
          result_str = f"{result_str}\n\n📊 Detalhes completos:\n{detailed_text}"

      except Exception as e:
        print(f"[Debug: erro ao detalhar rolagem] {type(e).__name__}: {e}")

      if has_comparison:
        result_str = _format_comparison_result(result_str, original_string, result.total)
      else:
        if 'adv' in original_string.lower() or 'kh1' in translated_string:
          result_str = _format_advantage_result(result_str, True)
        elif 'dis' in original_string.lower() or 'kl1' in translated_string:
          result_str = _format_advantage_result(result_str, False)
        elif 'kh' in translated_string or 'kl' in translated_string:
          result_str = _format_drop_keep_result(result_str)
        else:
          result_str = _clean_d20_formatting(result_str)
      return result.total, result_str
    except Exception as e:
      return handle_complex_expression(original_string)
  def handle_complex_expression(expr: str) -> tuple[int, str]:
    try:
      clean_expr = re.sub(r'\s+', '', expr)
      clean_expr = re.sub(r'(\d)(\()', r'\1*\2', clean_expr)
      clean_expr = re.sub(r'(\))(\d)', r'\1*\2', clean_expr)
      clean_expr = re.sub(r'(d\d+)(\()', r'\1*\2', clean_expr)
      result = d20.roll(clean_expr, allow_comments=True, verbose=True)
      total = result.total
      breakdown = create_complex_breakdown(result, expr)
      return total, breakdown
    except Exception as e:
      return handle_fallback_calculation(expr)
  def create_complex_breakdown(result, original_expr: str) -> str:
    try:
      dice_types = {}
      dice_matches = re.findall(r'(\d*)d(\d+)', original_expr.lower())
      for count, size in dice_matches:
        count = int(count) if count else 1
        size_key = f"d{size}"
        dice_types[size_key] = dice_types.get(size_key, 0) + count
      dice_summary = [f"{count}{size}" for size, count in dice_types.items()]
      breakdown = f"🎲 **Expressão Complexa**\n"
      breakdown += f"📊 Dados: {', '.join(dice_summary)}\n"
      breakdown += f"💥 **Total: {result.total}**"
      if len(original_expr) < 150:
        breakdown += f"\n`{original_expr}`"
      return breakdown
    except Exception as e:
      return f"💥 **Total: {result.total}**"
  def handle_fallback_calculation(expr: str) -> tuple[int, str]:
    try:
      total = 0
      parts = []
      dice_matches = re.findall(r'(\d*)d(\d+)', expr.lower())
      for count, size in dice_matches:
        count = int(count) if count else 1
        size = int(size)
        dice_roll = d20.roll(f"{count}d{size}")
        part_total = dice_roll.total
        total += part_total
        parts.append(f"{count}d{size}: {part_total}")
      numbers = re.findall(r'[+\-*/]?\s*(\d+)(?![dd])', expr)
      for num in numbers:
        total += int(num)
        parts.append(f"mod: {num}")
      breakdown = f"🔧 **Cálculo Simplificado**\n"
      breakdown += " + ".join(parts)
      breakdown += f"\n💥 **Total: {total}**"
      return total, breakdown
    except Exception as fallback_error:
      dice_count = expr.count('d')
      estimated_total = dice_count * 10
      return estimated_total, f"⚠️ **Valor Estimado: {estimated_total}**\nExpressão muito complexa para cálculo preciso"
  try:
    return await loop.run_in_executor(None, do_roll)
  except Exception as e:
    return 0, f"❌ **Erro ao processar**: {str(e)}"

async def execute_attack_roll(ficha: dict, selected_attack: dict, advantage_state: str) -> dict:
  atributos = ficha.get("atributos", {})
  sistema = ficha.get("informacoes_basicas", {}).get("sistema_rpg", "dnd")
  attr_name = selected_attack.get("atributo", "força").lower()
  attr_score_str = atributos.get(attr_name.capitalize(), atributos.get(attr_name, "10"))
  attr_score = int(attr_score_str)
  modifier = rpg_rules.get_modifier(sistema, attr_score)
  hit_formula = selected_attack.get('teste_de_acerto', 'd20+MOD')
  is_multiple_attack = hit_formula.strip().startswith(('1#', '2#', '3#', '4#', '5#', '6#', '7#', '8#', '9#'))
  if is_multiple_attack:
    return await execute_multiple_attack_roll(ficha, selected_attack, advantage_state, hit_formula)
  else:
    return await execute_single_attack_roll(ficha, selected_attack, advantage_state, hit_formula)

async def execute_single_attack_roll(ficha: dict, selected_attack: dict, advantage_state: str,
                                     hit_formula: str) -> dict:
  if is_complex_expression(hit_formula):
    return await execute_complex_attack_roll(ficha, selected_attack, advantage_state, hit_formula)
  atributos = ficha.get("atributos", {})
  sistema = ficha.get("informacoes_basicas", {}).get("sistema_rpg", "dnd")
  attr_name = selected_attack.get("atributo", "força").lower()
  attr_score_str = atributos.get(attr_name.capitalize(), atributos.get(attr_name, "10"))
  attr_score = int(attr_score_str)
  modifier = rpg_rules.get_modifier(sistema, attr_score)
  hit_resolved = re.sub(r"\bMOD\b", str(modifier), hit_formula)
  if advantage_state == "vantagem":
    if 'd20' in hit_resolved:
      hit_dice_expression = re.sub(r'(\d*)d20', r'2d20kh1', hit_resolved)
    else:
      hit_dice_expression = f"2d20kh1{hit_resolved}"
  elif advantage_state == "desvantagem":
    if 'd20' in hit_resolved:
      hit_dice_expression = re.sub(r'(\d*)d20', r'2d20kl1', hit_resolved)
    else:
      hit_dice_expression = f"2d20kl1{hit_resolved}"
  else:
    hit_dice_expression = hit_resolved
  try:
    acerto_total, acerto_breakdown, main_roll = await _roll_attack_with_d20(hit_dice_expression)
    natural_d20 = natural_d20_kept_face_from_roll(main_roll)
  except Exception:
    acerto_total, acerto_breakdown = await roll_dice(hit_dice_expression)
    natural_d20 = natural_d20_kept_face_from_roll_text(acerto_breakdown)
  crit_range = int(selected_attack.get("margem_critico", 20))
  is_crit = natural_d20 >= crit_range
  is_fumble = rpg_rules.is_dnd_system(sistema) and natural_d20 == 1
  acerto_breakdown_formatado = acerto_breakdown
  partes_dano = []
  itens_usados_nomes = []
  ataque_dano_str = selected_attack.get('dano', '0').strip()
  if ataque_dano_str and ataque_dano_str != '0':
    partes_dano.append(ataque_dano_str)
  itens_vinculados_nomes = selected_attack.get("itens_vinculados", [])
  if itens_vinculados_nomes:
    inventario_combate = ficha.get("inventario", {}).get("combate", [])
    for item_nome in itens_vinculados_nomes:
      item_encontrado = next((item for item in inventario_combate if item['nome'] == item_nome), None)
      if item_encontrado and item_encontrado.get('dano', '0').strip() not in ['', '0']:
        partes_dano.append(item_encontrado.get('dano').strip())
        itens_usados_nomes.append(item_nome)
  dano_base_str = " + ".join(partes_dano) if partes_dano else "0"
  if is_crit:
    if rpg_rules.is_dnd_system(sistema):
      dano_total, dano_breakdown = await _dnd_crit_roll_damage_twice(dano_base_str, modifier)
    else:
      multiplicador = int(selected_attack.get("multiplicador_critico", 2))
      dano_dados_total, dano_dados_breakdown = await roll_dice(dano_base_str)
      dano_normal_total = dano_dados_total + modifier
      dano_total = dano_normal_total * multiplicador
      dano_breakdown = f"Multiplicador (×{multiplicador})\n"
      dano_breakdown += f"Dados: {dano_dados_breakdown}\n"
      if modifier != 0:
        dano_breakdown += f"Modificador: {modifier:+}\n"
      dano_breakdown += f"Dano normal: {dano_normal_total}"
  else:
    dano_dados_total, dano_dados_breakdown = await roll_dice(dano_base_str)
    dano_total = dano_dados_total + modifier
    dano_breakdown = f"Dados: {dano_dados_breakdown}"
    if modifier != 0:
      dano_breakdown += f"\nModificador: {modifier:+}"
  return {
    "acerto_total": acerto_total,
    "acerto_breakdown": acerto_breakdown_formatado,
    "dano_total": dano_total,
    "dano_breakdown": dano_breakdown,
    "is_crit": is_crit,
    "is_fumble": is_fumble,
    "natural_d20": natural_d20,
    "tipo_de_dano": selected_attack.get("tipo_dano", ""),
    "arma_usada_text": f" (com {', '.join(itens_usados_nomes)})" if itens_usados_nomes else "",
    "efeitos": selected_attack.get("efeitos", "").strip(),
    "is_multiple": False
  }

async def execute_complex_attack_roll(ficha: dict, selected_attack: dict, advantage_state: str,
                                      hit_formula: str) -> dict:
  atributos = ficha.get("atributos", {})
  sistema = ficha.get("informacoes_basicas", {}).get("sistema_rpg", "dnd")
  attr_name = selected_attack.get("atributo", "força").lower()
  attr_score_str = atributos.get(attr_name.capitalize(), atributos.get(attr_name, "10"))
  attr_score = int(attr_score_str)
  modifier = rpg_rules.get_modifier(sistema, attr_score)
  hit_dice_expression = re.sub(r"\bMOD\b", str(modifier), hit_formula)
  acerto_total, acerto_breakdown = await roll_dice(hit_dice_expression)
  crit_range = int(selected_attack.get("margem_critico", 20))
  natural_d20 = natural_d20_kept_face_from_roll_text(acerto_breakdown)
  is_crit = natural_d20 >= crit_range
  is_fumble = rpg_rules.is_dnd_system(sistema) and natural_d20 == 1
  partes_dano = []
  itens_usados_nomes = []

  ataque_dano_str = selected_attack.get('dano', '0').strip()
  if ataque_dano_str and ataque_dano_str != '0':
    partes_dano.append(ataque_dano_str)

  itens_vinculados_nomes = selected_attack.get("itens_vinculados", [])
  if itens_vinculados_nomes:
    inventario_combate = ficha.get("inventario", {}).get("combate", [])
    for item_nome in itens_vinculados_nomes:
      item_encontrado = next((item for item in inventario_combate if item['nome'] == item_nome), None)
      if item_encontrado and item_encontrado.get('dano', '0').strip() not in ['', '0']:
        partes_dano.append(item_encontrado.get('dano').strip())
        itens_usados_nomes.append(item_nome)

  dano_base_str = " + ".join(partes_dano) if partes_dano else "0"
  if is_complex_expression(dano_base_str):
    dano_total, dano_breakdown = await roll_dice(dano_base_str)
    if is_crit:
      if rpg_rules.is_dnd_system(sistema):
        dano_total, dano_breakdown = await _dnd_crit_roll_damage_twice(dano_base_str, modifier)
      else:
        multiplicador = int(selected_attack.get("multiplicador_critico", 2))
        dano_total = dano_total * multiplicador
        dano_breakdown = f"💥 **DANO CRÍTICO** (×{multiplicador})\nTotal: {dano_total}"
    else:
      dano_breakdown = f"Total: {dano_total}"
  else:
    if is_crit:
      if rpg_rules.is_dnd_system(sistema):
        dano_total, dano_breakdown = await _dnd_crit_roll_damage_twice(dano_base_str, modifier)
      else:
        multiplicador = int(selected_attack.get("multiplicador_critico", 2))
        dano_dados_total, dano_dados_breakdown = await roll_dice(dano_base_str)
        dano_normal_total = dano_dados_total + modifier
        dano_total = dano_normal_total * multiplicador
        dano_breakdown = f"Multiplicador (×{multiplicador})\n"
        dano_breakdown += f"Dados: {dano_dados_breakdown}\n"
        if modifier != 0:
          dano_breakdown += f"Modificador: {modifier:+}\n"
        dano_breakdown += f"Dano normal: {dano_normal_total}"
    else:
      dano_dados_total, dano_dados_breakdown = await roll_dice(dano_base_str)
      dano_total = dano_dados_total + modifier
      dano_breakdown = f"Dados: {dano_dados_breakdown}"
      if modifier != 0:
        dano_breakdown += f"\nModificador: {modifier:+}"
  dice_count = hit_formula.count('d')
  d20_count = len(re.findall(r'(\d*)d20', hit_formula.lower()))
  acerto_breakdown_formatado = f"🎯 **Ataque Complexo**\n"
  acerto_breakdown_formatado += f"• {dice_count} tipos de dados ({d20_count} d20)\n"
  acerto_breakdown_formatado += f"💥 **Total: {acerto_total}**"
  if is_crit:
    acerto_breakdown_formatado += " 💥**CRÍTICO**💥"
  if d20_count > 0:
    crit_chance = 1 - ((crit_range - 1) / 20) ** d20_count
    acerto_breakdown_formatado += f"\n🎲 Probabilidade de crítico: {crit_chance:.1%}"
  if len(acerto_breakdown) < 200:
    acerto_breakdown_formatado += f"\n```{acerto_breakdown}```"

  return {
    "acerto_total": acerto_total,
    "acerto_breakdown": acerto_breakdown_formatado,
    "dano_total": dano_total,
    "dano_breakdown": dano_breakdown,
    "is_crit": is_crit,
    "is_fumble": is_fumble,
    "natural_d20": natural_d20,
    "tipo_de_dano": selected_attack.get("tipo_dano", ""),
    "arma_usada_text": f" (com {', '.join(itens_usados_nomes)})" if itens_usados_nomes else "",
    "efeitos": selected_attack.get("efeitos", "").strip(),
    "is_multiple": False,
    "is_complex": True
  }

async def execute_multiple_attack_roll(ficha: dict, selected_attack: dict, advantage_state: str,
                                       hit_formula: str) -> dict:
  match = re.match(r'^\s*(\d+)\s*#\s*(.+)$', hit_formula)
  if not match:
    return await execute_single_attack_roll(ficha, selected_attack, advantage_state, hit_formula)
  num_attacks = int(match.group(1))
  base_expression = match.group(2).strip()

  if is_complex_expression(base_expression):
    return await execute_complex_multiple_attack_roll(ficha, selected_attack, advantage_state, hit_formula, num_attacks,
                                                      base_expression)
  resultados = []
  for i in range(num_attacks):
    temp_attack = selected_attack.copy()
    temp_attack['teste_de_acerto'] = base_expression
    resultado = await execute_single_attack_roll(ficha, temp_attack, advantage_state, base_expression)
    resultados.append(resultado)
  acerto_breakdown_combined = ""
  dano_breakdown_combined = ""
  total_dano = 0
  any_crit = False
  for i, resultado in enumerate(resultados, 1):
    crit_indicator = " 💥" if resultado['is_crit'] else ""
    any_crit = any_crit or resultado['is_crit']
    acerto_breakdown_combined += f"**Ataque {i}:** {resultado['acerto_total']}{crit_indicator}\n"
    dano_breakdown_combined += f"**Ataque {i}:** {resultado['dano_total']}\n"
    total_dano += resultado['dano_total']
  info_breakdown = ""
  hit_dice_info = base_expression
  if advantage_state == "vantagem":
    if 'd20' in hit_dice_info:
      hit_dice_info = re.sub(r'(\d*)d20', r'2d20kh1', hit_dice_info)
    else:
      hit_dice_info = f"2d20kh1{hit_dice_info}"
  elif advantage_state == "desvantagem":
    if 'd20' in hit_dice_info:
      hit_dice_info = re.sub(r'(\d*)d20', r'2d20kl1', hit_dice_info)
    else:
      hit_dice_info = f"2d20kl1{hit_dice_info}"
  info_breakdown += f"**Dados de acerto:** {hit_dice_info}\n"
  dano_info = selected_attack.get('dano', '0').strip()
  if not dano_info or dano_info == '0':
    dano_info = "Nenhum"
  info_breakdown += f"**Dados de dano:** {dano_info}"
  atributos = ficha.get("atributos", {})
  sistema = ficha.get("informacoes_basicas", {}).get("sistema_rpg", "dnd")
  attr_name = selected_attack.get("atributo", "força").lower()
  attr_score_str = atributos.get(attr_name.capitalize(), atributos.get(attr_name, "10"))
  attr_score = int(attr_score_str)
  modifier = rpg_rules.get_modifier(sistema, attr_score)
  if modifier != 0:
    info_breakdown += f"\n**Modificador:** {modifier:+}"
  return {
    "acerto_total": f"{num_attacks} ataques",
    "acerto_breakdown": acerto_breakdown_combined,
    "dano_total": total_dano,
    "dano_breakdown": dano_breakdown_combined,
    "info_breakdown": info_breakdown,
    "is_crit": any_crit,
    "tipo_de_dano": selected_attack.get("tipo_dano", ""),
    "arma_usada_text": selected_attack.get("arma_usada_text", ""),
    "efeitos": selected_attack.get("efeitos", "").strip(),
    "is_multiple": True,
    "num_attacks": num_attacks
  }

async def execute_complex_multiple_attack_roll(ficha: dict, selected_attack: dict, advantage_state: str,
                                               hit_formula: str, num_attacks: int, base_expression: str) -> dict:
  resultados = []
  total_dano = 0
  any_crit = False
  for i in range(num_attacks):
    temp_attack = selected_attack.copy()
    temp_attack['teste_de_acerto'] = base_expression
    resultado = await execute_complex_attack_roll(ficha, temp_attack, advantage_state, base_expression)
    resultados.append(resultado)
    total_dano += resultado['dano_total']
    any_crit = any_crit or resultado['is_crit']
  acerto_breakdown_combined = ""
  dano_breakdown_combined = ""
  for i, resultado in enumerate(resultados, 1):
    crit_indicator = " 💥" if resultado['is_crit'] else ""
    acerto_valor = resultado['acerto_total']
    dano_valor = resultado['dano_total']
    acerto_breakdown_combined += f"Ataque {i}: {acerto_valor}{crit_indicator}\n"
    dano_breakdown_combined += f"Ataque {i}: {dano_valor}\n"
  info_breakdown = f"**Ataques Complexos:** {num_attacks}×\n"
  if len(base_expression) > 80:
    expr_preview = base_expression[:80] + "..."
  else:
    expr_preview = base_expression
  info_breakdown += f"**Expressão:** {expr_preview}"
  acertos = [r['acerto_total'] for r in resultados]
  avg_acerto = sum(acertos) / len(acertos)
  max_acerto = max(acertos)
  min_acerto = min(acertos)
  info_breakdown += f"\n**Estatísticas:** Média {avg_acerto:.0f} (Min {min_acerto} - Max {max_acerto})"
  dano_info = selected_attack.get('dano', '0').strip()
  if dano_info and dano_info != '0':
    if len(dano_info) > 50:
      dano_preview = dano_info[:50] + "..."
    else:
      dano_preview = dano_info
    info_breakdown += f"\n**Dano:** {dano_preview}"
  atributos = ficha.get("atributos", {})
  sistema = ficha.get("informacoes_basicas", {}).get("sistema_rpg", "dnd")
  attr_name = selected_attack.get("atributo", "força").lower()
  attr_score_str = atributos.get(attr_name.capitalize(), atributos.get(attr_name, "10"))
  attr_score = int(attr_score_str)
  modifier = rpg_rules.get_modifier(sistema, attr_score)
  if modifier != 0:
    info_breakdown += f"\n**Modificador:** {modifier:+}"
  return {
    "acerto_total": f"{num_attacks} ataques",
    "acerto_breakdown": acerto_breakdown_combined,
    "dano_total": total_dano,
    "dano_breakdown": dano_breakdown_combined,
    "info_breakdown": info_breakdown,
    "is_crit": any_crit,
    "tipo_de_dano": selected_attack.get("tipo_dano", ""),
    "arma_usada_text": "",
    "efeitos": selected_attack.get("efeitos", "").strip(),
    "is_multiple": True,
    "num_attacks": num_attacks,
    "is_complex": True,
    "acertos_individuals": acertos,
    "danos_individuals": [r['dano_total'] for r in resultados]
  }

async def execute_attribute_check(ficha: dict, sistema: str, selected_skill: str, selected_attribute: str,
                                  advantage_state: str, temp_modifier_str: str) -> dict:
  hit_dice_expression = "1d20"
  advantage_text = ""
  if advantage_state == "vantagem":
    hit_dice_expression = "2d20kh1"
    advantage_text = "_(Vantagem)_"
  elif advantage_state == "desvantagem":
    hit_dice_expression = "2d20kl1"
    advantage_text = "_(Desvantagem)_"
  natural_roll, raw_d20_breakdown = await roll_dice(hit_dice_expression)
  is_crit = (natural_roll == 20)
  is_fumble = (natural_roll == 1)
  atributo_base = selected_attribute
  skill_data = None
  if selected_skill:
    pericias_aprendidas = ficha.get("pericias", {})
    skill_data = pericias_aprendidas.get(selected_skill)
    if skill_data and isinstance(skill_data, dict):
      atributo_base = skill_data.get("atributo_base") or atributo_base
    else:
      todas_pericias_sistema = rpg_rules.get_system_skills(sistema)
      is_categorized = isinstance(next(iter(todas_pericias_sistema.values()), None), list)
      if is_categorized:
        for attr, skills in todas_pericias_sistema.items():
          if selected_skill in skills:
            atributo_base = attr
            break
      else:
        atributo_base = todas_pericias_sistema.get(selected_skill) or atributo_base
  bonus_pericia = rpg_rules.dnd_flat_bonus_for_check(
    ficha,
    sistema,
    is_skill_roll=bool(selected_skill),
    selected_skill_or_attr_name=selected_skill or selected_attribute,
    skill_data=skill_data,
    atributo_base=atributo_base,
  )
  atributos_ficha = ficha.get("atributos", {})
  ab = atributo_base or selected_attribute
  attr_score_str = (
      atributos_ficha.get(ab)
      or atributos_ficha.get(ab.lower())
      or atributos_ficha.get(ab.capitalize())
      or atributos_ficha.get(ab.upper())
      or "10"
  )
  modificador_atributo = rpg_rules.get_modifier(sistema, int(attr_score_str))
  bonus_string = f"{modificador_atributo} + {bonus_pericia}"
  if temp_modifier_str:
    bonus_string += f" {temp_modifier_str}"
  bonus_total, _ = await roll_dice(bonus_string)
  resultado_final = natural_roll + bonus_total
  title_name = selected_skill if selected_skill else selected_attribute
  breakdown_final = f"Dado ({natural_roll}) + Bônus ({bonus_total}) = **{resultado_final}**"
  if advantage_state in ["vantagem", "desvantagem"]:
    try:
      rolls = []
      rolls_text = re.search(r'\((\d+),\s*(\d+)\)', raw_d20_breakdown)
      if rolls_text:
        rolls = [int(rolls_text.group(1)), int(rolls_text.group(2))]
      else:
        numbers = re.findall(r'\d+', raw_d20_breakdown)
        if len(numbers) >= 2:
          rolls = [int(numbers[0]), int(numbers[1])]
      if len(rolls) == 2:
        d1, d2 = rolls
        if advantage_state == "vantagem":
          valid_die = max(d1, d2)
          discarded_die = min(d1, d2)
          vantagem_text_display = "Vantagem"
        else:
          valid_die = min(d1, d2)
          discarded_die = max(d1, d2)
          vantagem_text_display = "Desvantagem"
        breakdown_final = (
          f"Dado mantido: {valid_die} + Bônus {bonus_total} = **{resultado_final}**\n"
          f"Dado descartado: {discarded_die}"
        )
    except Exception as e:
      breakdown_final = f"{raw_d20_breakdown} + Bônus({bonus_total}) = **{resultado_final}**"
  return {
    "resultado_final": resultado_final,
    "breakdown": breakdown_final,
    "is_crit": is_crit,
    "is_fumble": is_fumble,
    "title": f"🛡️ Teste de {title_name}",
    "advantage_text": advantage_text
  }
