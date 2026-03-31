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
import math
import random
import re

SUPPORTED_SYSTEMS = {
    "dnd": "Dungeons & Dragons / T20",
    "ordem_paranormal": "Ordem Paranormal",
    "cyberpunk": "Cyberpunk",
    "skyfall": "SkiFall RPG",
    "vampiro": "Vampiro: A Máscara",
    "cthulhu": "Call of Cthulhu"
}

def calculate_modifier(score: int) -> int:
    return math.floor((int(score) - 10) / 2)


def roll_stats_5e() -> list[int]:
    """
    Seis atributos: para cada um rola 4d6 e soma os 3 maiores (descarta o menor).
    Regra de sanidade: se qualquer atributo final ficar abaixo de 7, rerola o conjunto inteiro.
    """
    while True:
        stats: list[int] = []
        for _ in range(6):
            # 4d6 drop lowest (mais rápido que ordenar):
            # - soma dos 4 dados
            # - subtrai o menor (o menor é descartado)
            rolls = [random.randint(1, 6) for _ in range(4)]
            val = sum(rolls) - min(rolls)
            # teto pré-bônus racial para 4d6 drop lowest.
            val = min(18, val)
            stats.append(val)
        if all(v >= 7 for v in stats):
            return stats


def sum_ability_modifiers(scores: list[int]) -> int:
    return sum(calculate_modifier(s) for s in scores)


def roll_stats_5e_min_modifier_total(min_total: int = 4, max_attempts: int = 50) -> list[int]:
    """Para NPCs médio/difícil: rerola até a soma dos modificadores ser pelo menos min_total."""
    for _ in range(max_attempts):
        s = roll_stats_5e()
        if sum_ability_modifiers(s) >= min_total:
            return s
    return roll_stats_5e()


def _normalize_system_key(system_name: str | None) -> str:
    return (system_name or "dnd").lower().strip().replace(" ", "_")


def is_dnd_system(system_name: str | None) -> bool:
    return _normalize_system_key(system_name) == "dnd"


def proficiency_bonus(character_level: int) -> int:
    """
    Bônus de Proficiência SRD D&D 5e (2014 e 2024 usam a mesma progressão por nível de personagem).
    Níveis 1–4: +2; 5–8: +3; 9–12: +4; 13–16: +5; 17–20: +6
    """
    lvl = max(1, min(20, int(character_level)))
    return (lvl - 1) // 4 + 2


def parse_character_level(ficha: dict) -> int:
    """Lê nível a partir de informacoes_basicas.nivel_rank (aceita texto como '5' ou '5º nível')."""
    info = ficha.get("informacoes_basicas") or ficha.get("informacoes_gerais") or {}
    raw = info.get("nivel_rank") or "1"
    m = re.search(r"\d+", str(raw))
    if not m:
        return 1
    return max(1, min(20, int(m.group(0))))


def skill_proficiency_token(skill_data: dict | str | None) -> str | None:
    if not isinstance(skill_data, dict):
        return None
    return skill_data.get("proficiencia_dnd") or skill_data.get("dnd_proficiency")


def dnd_bonus_from_proficiency_token(token: str | None, character_level: int) -> int:
    """
    Interpreta proficiencia_dnd na ficha: 'expertise' = 2×BP; 'proficiente' (e sinônimos) = BP.
    'nenhuma' ou vazio = 0 (some ao campo bonus manual da perícia).
    """
    if not token:
        return 0
    t = str(token).strip().lower()
    if t in ("", "nenhuma", "none", "manual", "n", "0", "na"):
        return 0
    pb = proficiency_bonus(character_level)
    if t in ("expertise", "experiencia", "expert", "e", "2x", "2"):
        return 2 * pb
    if t in ("proficiente", "proficiency", "prof", "p", "sim", "yes", "true", "1"):
        return pb
    return 0


def dnd_flat_bonus_for_check(
    ficha: dict,
    sistema: str,
    *,
    is_skill_roll: bool,
    selected_skill_or_attr_name: str,
    skill_data: dict | str | None,
    atributo_base: str,
) -> int:
    """
    Parcela fixa do teste além do modificador de atributo: bônus de perícia manual + BP (D&D),
    ou BP em salvaguarda se o atributo estiver em salvaguardas_proficientes.
    """
    if not is_dnd_system(sistema):
        if is_skill_roll and isinstance(skill_data, dict):
            return int(skill_data.get("bonus", 0))
        return 0

    level = parse_character_level(ficha)
    if is_skill_roll:
        base = int(skill_data.get("bonus", 0)) if isinstance(skill_data, dict) else 0
        token = skill_proficiency_token(skill_data if isinstance(skill_data, dict) else None)
        return base + dnd_bonus_from_proficiency_token(token, level)

    prof_attrs = ficha.get("salvaguardas_proficientes") or []
    norm = {str(x).strip().lower() for x in prof_attrs}
    attr = selected_skill_or_attr_name.strip().lower()
    attr2 = (atributo_base or "").strip().lower()
    if attr in norm or attr2 in norm:
        return proficiency_bonus(level)
    return 0

MODIFIER_RULES = {
    "dnd": calculate_modifier,
    "skyfall": calculate_modifier,
    "ordem_paranormal": lambda score: score,
    "cyberpunk": lambda score: score,
    "vampiro": lambda score: score,
    "cthulhu": lambda score: 0,
}

def get_modifier(system_name: str, attribute_score: int) -> int:
    system_key = system_name.lower().strip().replace(" ", "_") if system_name else "dnd"
    calculation_function = MODIFIER_RULES.get(system_key, MODIFIER_RULES["dnd"])
    try:
        score = int(attribute_score)
        return calculation_function(score)
    except (ValueError, TypeError):
        return 0
SYSTEM_CHECKS = {
    "dnd": ["Força", "Destreza", "Constituição", "Inteligência", "Sabedoria", "Carisma"],
    "skyfall": ["Força", "Destreza", "Vigor", "Intelecto", "Percepção", "Vontade"],
    "ordem_paranormal": ["Força", "Agilidade", "Vigor", "Presença", "Intelecto"],
    "cyberpunk": ["Inteligência", "Reflexos", "Técnica", "Empatia", "Frio", "Corpo", "Atratividade", "Sorte"],
    "vampiro": ["Força", "Destreza", "Vigor", "Carisma", "Manipulação", "Autocontrole", "Inteligência", "Raciocínio", "Perseverança"],
    "cthulhu": ["Força", "Destreza", "Constituição", "Inteligência", "Poder", "Educação", "Tamanho", "Aparência"]
}

def get_system_checks(system_name: str) -> list[str]:
    system_key = system_name.lower().strip().replace(" ", "_") if system_name else "dnd"
    return SYSTEM_CHECKS.get(system_key, SYSTEM_CHECKS["dnd"])
SYSTEM_SKILLS = {
    "dnd": {
        "Força": ["Atletismo"],
        "Destreza": ["Acrobacia", "Furtividade", "Prestidigitação"],
        "Inteligência": ["Arcanismo", "História", "Investigação", "Natureza", "Religião"],
        "Sabedoria": ["Intuição", "Lidar com Animais", "Medicina", "Percepção", "Sobrevivência"],
        "Carisma": ["Atuação", "Enganação", "Intimidação", "Persuasão"]
    },
    "ordem_paranormal": {
        "Agilidade": [
            "Acrobacia", "Crime", "Furtividade", "Iniciativa", "Pilotagem", "Pontaria", "Reflexos"],
        "Força": ["Atletismo", "Luta"],
        "Intelecto": [
            "Atualidades", "Ciências", "Investigação", "Medicina", "Ocultismo",
            "Percepção", "Profissão", "Sobrevivência", "Tática", "Tecnologia"],
        "Presença": [
            "Adestramento", "Artes", "Diplomacia", "Enganação", "Intimidação",
            "Intuição", "Liderança", "Religião", "Vontade"],
        "Vigor": ["Fortitude"]
    },
    "cthulhu": {
        "Força": ["Intimidação", "Luta", "Natação", "Saltar"],
        "Destreza": [
            "Arcos", "Arremessar", "Artes/Ofícios", "Chaveiro", "Consertos Elétricos",
            "Consertos Mecânicos", "Furtividade", "Operar Maquinário", "Pilotar"],
        "Educação": ["Antropologia", "Arqueologia", "Ciências", "Contabilidade",
                     "Direito", "História", "Língua Nativa", "Língua Outra", "Medicina",
                     "Mitos de Cthulhu", "Mundo Natural", "Ocultismo", "Primeiros Socorros", "Psicanálise"],
        "Poder": ["Encontrar", "Escutar", "Psicologia"],
        "Aparência": ["Charme", "Disfarce", "Lábia", "Persuasão"],
        "Inteligência": ["Avaliação", "Rastrear"]
    },
     "vampiro": {
        "Força": ["Atletismo", "Briga", "Armas Brancas"],
        "Destreza": ["Ofícios", "Condução", "Larcínia", "Furtividade"],
        "Autocontrole": ["Armas de Fogo", "Etiqueta", "Intuição"],
        "Raciocínio": ["Sobrevivência", "Consciência"],
        "Carisma": ["Trato com Animais", "Liderança", "Performance", "Persuasão"],
        "Manipulação": ["Intimidação", "Manha", "Lábia", "Política"],
        "Inteligência": ["Erudição", "Finanças", "Investigação", "Medicina", "Ocultismo", "Ciência", "Tecnologia"]
    },
    "cyberpunk": {
        "Vontade": ["Concentração", "Resistência"],
        "Inteligência": ["Acadêmicos", "Burocracia", "Criptografia", "Línguas", "Percepção"],
        "Reflexos": ["Condução (Terrestre)", "Pistolas", "Fuzis", "Armas Pesadas"],
        "Destreza": ["Atletismo", "Briga", "Evasão", "Armas Brancas (Corpo a Corpo)", "Furtividade"],
        "Frio": ["Atuação", "Suborno", "Interrogatório", "Persuasão", "Comércio"],
        "Empatia": ["Conversação", "Percepção Humana"],
        "Técnica": ["Cybertecnia", "Primeiros Socorros", "Eletrônica/Segurança", "Fabricação de Armas"]
    },
    "skyfall": {
        "Força": ["Luta"],
        "Destreza": ["Pontaria", "Reflexos", "Furtividade", "Ladinagem"],
        "Vigor": ["Fortitude"],
        "Percepção": ["Iniciativa", "Intuição", "Investigar", "Percepção", "Sobrevivência"],
        "Vontade": ["Vontade", "Intimidação", "Misticismo"],
        "Intelecto": ["Conhecimento", "Cura", "Diplomacia", "Enganação", "Magia", "Nobreza", "Ofícios"]
    }
}

def get_system_skills(system_name: str) -> dict:
    system_key = system_name.lower().strip().replace(" ", "_") if system_name else "dnd"
    return SYSTEM_SKILLS.get(system_key, SYSTEM_SKILLS["dnd"])