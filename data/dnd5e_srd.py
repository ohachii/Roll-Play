# Dados simplificados SRD D&D 5e para criação guiada e NPCs (referência de jogo; não substitui o livro).
# Copyright (C) 2025 — AGPL-3.0 where applicable.

from __future__ import annotations

import random
from typing import Any

DND_ATTRIBUTES: list[str] = [
    "Força",
    "Destreza",
    "Constituição",
    "Inteligência",
    "Sabedoria",
    "Carisma",
]

# bônus numéricos por atributo (aplicados após distribuição de pontos base)
RACES: dict[str, dict[str, Any]] = {
    "Humano": {
        "ability_bonuses": {a: 1 for a in DND_ATTRIBUTES},
        "desc": "+1 em todos os atributos (SRD).",
    },
    "Anão": {
        "ability_bonuses": {"Constituição": 2},
        "desc": "+2 Constituição.",
    },
    "Elfo": {
        "ability_bonuses": {"Destreza": 2},
        "desc": "+2 Destreza.",
    },
    "Halfling": {
        "ability_bonuses": {"Destreza": 2},
        "desc": "+2 Destreza.",
    },
    "Meio-Elfo": {
        "ability_bonuses": {"Carisma": 2, "Inteligência": 1, "Sabedoria": 1},
        "desc": "+2 Carisma; +1 Int e +1 Sab (simplificado).",
    },
    "Meio-Orc": {
        "ability_bonuses": {"Força": 2, "Constituição": 1},
        "desc": "+2 Força, +1 Constituição.",
    },
    "Draconato": {
        "ability_bonuses": {"Força": 2, "Carisma": 1},
        "desc": "+2 Força, +1 Carisma.",
    },
    "Gnomo": {
        "ability_bonuses": {"Inteligência": 2},
        "desc": "+2 Inteligência.",
    },
    "Tiefling": {
        "ability_bonuses": {"Carisma": 2, "Inteligência": 1},
        "desc": "+2 Carisma, +1 Inteligência.",
    },
}

CLASSES: dict[str, dict[str, Any]] = {
    "Guerreiro": {
        "hit_die": 10,
        "save_proficiency": ["Força", "Constituição"],
        "primary": ["Força", "Constituição", "Destreza"],
        "skill_choices": [
            "Atletismo", "Acrobacia", "Intimidação", "Adestramento", "História", "Intuição",
            "Percepção", "Sobrevivência",
        ],
        "skill_pick": 2,
    },
    "Mago": {
        "hit_die": 6,
        "save_proficiency": ["Inteligência", "Sabedoria"],
        "primary": ["Inteligência", "Constituição", "Destreza"],
        "skill_choices": [
            "Arcanismo", "História", "Investigação", "Medicina", "Religião", "Intuição",
        ],
        "skill_pick": 2,
    },
    "Ladino": {
        "hit_die": 8,
        "save_proficiency": ["Destreza", "Inteligência"],
        "primary": ["Destreza", "Inteligência", "Carisma"],
        "skill_choices": [
            "Acrobacia", "Atletismo", "Enganação", "Intuição", "Intimidação", "Investigação",
            "Percepção", "Prestidigitação", "Furtividade",
        ],
        "skill_pick": 4,
    },
    "Clérigo": {
        "hit_die": 8,
        "save_proficiency": ["Sabedoria", "Carisma"],
        "primary": ["Sabedoria", "Constituição", "Força"],
        "skill_choices": [
            "História", "Intuição", "Medicina", "Persuasão", "Religião",
        ],
        "skill_pick": 2,
    },
    "Paladino": {
        "hit_die": 10,
        "save_proficiency": ["Sabedoria", "Carisma"],
        "primary": ["Força", "Carisma", "Constituição"],
        "skill_choices": [
            "Atletismo", "Intuição", "Intimidação", "Medicina", "Persuasão", "Religião",
        ],
        "skill_pick": 2,
    },
    "Patrulheiro": {
        "hit_die": 10,
        "save_proficiency": ["Força", "Destreza"],
        "primary": ["Destreza", "Sabedoria", "Constituição"],
        "skill_choices": [
            "Adestramento", "Atletismo", "Intuição", "Investigação", "Natureza", "Percepção",
            "Furtividade", "Sobrevivência",
        ],
        "skill_pick": 3,
    },
    "Bárbaro": {
        "hit_die": 12,
        "save_proficiency": ["Força", "Constituição"],
        "primary": ["Força", "Constituição", "Destreza"],
        "skill_choices": [
            "Atletismo", "Intimidação", "Natureza", "Percepção", "Sobrevivência", "Acrobacia",
        ],
        "skill_pick": 2,
    },
    "Bardo": {
        "hit_die": 8,
        "save_proficiency": ["Destreza", "Carisma"],
        "primary": ["Carisma", "Destreza", "Constituição"],
        "skill_choices": [
            "Atuação", "Enganação", "Intimidação", "Persuasão", "Acrobacia", "História",
            "Intuição", "Investigação", "Prestidigitação", "Furtividade",
        ],
        "skill_pick": 3,
    },
    "Monge": {
        "hit_die": 8,
        "save_proficiency": ["Destreza", "Sabedoria"],
        "primary": ["Destreza", "Sabedoria", "Constituição"],
        "skill_choices": [
            "Acrobacia",
            "Atletismo",
            "Adestramento",
            "Furtividade",
            "História",
            "Intuição",
            "Religião",
            "Percepção",
        ],
        "skill_pick": 2,
    },
    "Bruxo": {
        "hit_die": 8,
        "save_proficiency": ["Sabedoria", "Carisma"],
        "primary": ["Carisma", "Sabedoria", "Constituição"],
        "skill_choices": [
            "Arcanismo",
            "Enganação",
            "Intimidação",
            "Investigação",
            "Natureza",
            "Religião",
        ],
        "skill_pick": 2,
    },
}

BACKGROUNDS: dict[str, dict[str, Any]] = {
    "Nenhum": {"extra_skills": [], "extra_languages": [], "extra_items": []},
    "Acólito": {
        "extra_skills": ["Intuição", "Religião"],
        "extra_languages": [],
        "extra_items": ["Símbolo sagrado (kit do Acólito)", "Roupas comuns"],
        "descricao": "Cultiva fé e práticas devocionais.",
        "beneficios": "Bônus de proficiência via perícias fixas do background.",
    },
    "Charlatão": {
        "extra_skills": ["Enganação", "Prestidigitação"],
        "extra_languages": [],
        "extra_items": ["Conjunto de roupas caras", "Itens de disfarce"],
        "descricao": "Sobrevive de lábia, truques e enganações.",
        "beneficios": "Bônus de proficiência via perícias fixas do background.",
    },
    "Criminoso": {
        "extra_skills": ["Enganação", "Furtividade"],
        "extra_languages": [],
        "extra_items": ["Conjunto de roupas de crime", "Punhal"],
        "descricao": "Aprendeu a agir no submundo.",
        "beneficios": "Bônus de proficiência via perícias fixas do background.",
    },
    "Entretenimento": {
        "extra_skills": ["Atuação", "Persuasão"],
        "extra_languages": [],
        "extra_items": ["Instrumento musical", "Trajes de palco"],
        "descricao": "Vive da performance e do carisma.",
        "beneficios": "Bônus de proficiência via perícias fixas do background.",
    },
    "Herói do Povo": {
        "extra_skills": ["Adestramento", "Sobrevivência"],
        "extra_languages": [],
        "extra_items": ["Objeto significativo", "Ferramentas de trabalho"],
        "descricao": "Protege sua comunidade com coragem e instinto.",
        "beneficios": "Bônus de proficiência via perícias fixas do background.",
    },
    "Artesão de Guilda": {
        "extra_skills": ["Investigação", "Intuição"],
        "extra_languages": [],
        "extra_items": ["Ferramenta de artesão", "Crachá/insígnia"],
        "descricao": "Pertence a uma guilda e segue tradições de ofício.",
        "beneficios": "Bônus de proficiência via perícias fixas do background.",
    },
    "Eremita": {
        "extra_skills": ["Medicina", "Religião"],
        "extra_languages": [],
        "extra_items": ["Conjunto de roupas", "Kit do eremita (livros/objetos)"],
        "descricao": "Busca respostas longe do barulho das cidades.",
        "beneficios": "Bônus de proficiência via perícias fixas do background.",
    },
    # Compatibilidade com sheets antigos que usavam “Ermitão”
    "Ermitão": {
        "extra_skills": ["Medicina", "Religião"],
        "extra_languages": [],
        "extra_items": ["Conjunto de roupas", "Kit do eremita (livros/objetos)"],
        "descricao": "Compat: mesma origem de “Eremita”.",
        "beneficios": "Bônus de proficiência via perícias fixas do background.",
    },
    "Nobre": {
        "extra_skills": ["História", "Persuasão"],
        "extra_languages": [],
        "extra_items": ["Brasão", "Roupas elegantes"],
        "descricao": "Portador(a) de linhagem, etiqueta e influência.",
        "beneficios": "Bônus de proficiência via perícias fixas do background.",
    },
    "Forasteiro": {
        "extra_skills": ["Percepção", "Sobrevivência"],
        "extra_languages": [],
        "extra_items": ["Conjunto de roupas de viajante", "Mapa"],
        "descricao": "Conhece rotas e perigos fora do comum.",
        "beneficios": "Bônus de proficiência via perícias fixas do background.",
    },
    "Sábio": {
        "extra_skills": ["Arcanismo", "História"],
        "extra_languages": [],
        "extra_items": ["Livros", "Papelaria"],
        "descricao": "Estuda, arquiva e compartilha conhecimento.",
        "beneficios": "Bônus de proficiência via perícias fixas do background.",
    },
    "Marinheiro": {
        "extra_skills": ["Percepção", "Sobrevivência"],
        "extra_languages": [],
        "extra_items": ["Mapa náutico", "Ferramentas náuticas"],
        "descricao": "Carrega o cheiro de mares e tempestades.",
        "beneficios": "Bônus de proficiência via perícias fixas do background.",
    },
    "Soldado": {
        "extra_skills": ["Atletismo", "Intimidação"],
        "extra_languages": [],
        "extra_items": ["Insígnias", "Arma"],
        "descricao": "Aprendeu disciplina e coragem em linha de frente.",
        "beneficios": "Bônus de proficiência via perícias fixas do background.",
    },
    "Órfão": {
        "extra_skills": ["Prestidigitação", "Furtividade"],
        "extra_languages": [],
        "extra_items": ["Baralho de cartas", "Tira de tecido"],
        "descricao": "Sobreviveu em meio à rua e ao acaso.",
        "beneficios": "Bônus de proficiência via perícias fixas do background.",
    },
}

SKILL_TO_ATTR: dict[str, str] = {
    "Atletismo": "Força",
    "Acrobacia": "Destreza",
    "Furtividade": "Destreza",
    "Prestidigitação": "Destreza",
    "Arcanismo": "Inteligência",
    "História": "Inteligência",
    "Investigação": "Inteligência",
    "Natureza": "Inteligência",
    "Religião": "Inteligência",
    "Adestramento": "Sabedoria",
    "Intuição": "Sabedoria",
    "Medicina": "Sabedoria",
    "Percepção": "Sabedoria",
    "Sobrevivência": "Sabedoria",
    "Atuação": "Carisma",
    "Enganação": "Carisma",
    "Intimidação": "Carisma",
    "Persuasão": "Carisma",
}

MONSTERS: dict[str, dict[str, Any]] = {
    "Goblin": {
        "base_scores": {
            "Força": 8, "Destreza": 14, "Constituição": 10,
            "Inteligência": 10, "Sabedoria": 8, "Carisma": 8,
        },
        "hit_die": 6,
        "hit_dice_count": 1,
    },
    "Orc": {
        "base_scores": {
            "Força": 16, "Destreza": 12, "Constituição": 16,
            "Inteligência": 7, "Sabedoria": 11, "Carisma": 10,
        },
        "hit_die": 12,
        "hit_dice_count": 2,
    },
    "Guarda": {
        "base_scores": {
            "Força": 13, "Destreza": 12, "Constituição": 12,
            "Inteligência": 10, "Sabedoria": 10, "Carisma": 10,
        },
        "hit_die": 8,
        "hit_dice_count": 2,
    },
}

PERSONALITY_SNIPPETS = [
    "Extremamente desconfiado e fala em sussurros.",
    "Covarde que cheira a queijo velho.",
    "Fanático por ordem e listas numeradas.",
    "Risonho demais para a situação.",
    "Coleciona botões e acha que são amuletos.",
    "Jurou vingança contra todo mundo que usa chapéu.",
    "Educado até demais com estranhos.",
    "Sempre conta a mesma história de pescaria.",
]

NAME_PREFIXES = ["Grish", "Drok", "Mara", "Vel", "Karn", "Zep", "Lumo", "Fex", "Rix", "Nym"]
NAME_SUFFIXES = ["ak", "ik", "os", "ara", "eth", "un", "ix", "a", "o", "is"]


def random_npc_name() -> str:
    return random.choice(NAME_PREFIXES) + random.choice(NAME_SUFFIXES) + f" {random.randint(1, 99)}"


def random_personality() -> str:
    return random.choice(PERSONALITY_SNIPPETS)


def race_names() -> list[str]:
    return sorted(RACES.keys())


def class_names() -> list[str]:
    return sorted(CLASSES.keys())


def background_names() -> list[str]:
    return sorted(BACKGROUNDS.keys())


def auto_assign_stats(stats: list[int], primary_order: list[str]) -> dict[str, int]:
    """Ordena stats desc; preenche primary_order em ordem, depois os atributos restantes."""
    s = sorted(stats, reverse=True)
    primary_order = [p for p in primary_order if p in DND_ATTRIBUTES]
    rest = [a for a in DND_ATTRIBUTES if a not in primary_order]
    order = primary_order + rest
    return {order[i]: s[i] for i in range(6)}


def apply_racial_bonuses(base: dict[str, int], race_key: str) -> dict[str, int]:
    race = RACES.get(race_key, RACES["Humano"])
    bonuses: dict[str, int] = race.get("ability_bonuses") or {}
    out = dict(base)
    for attr, b in bonuses.items():
        out[attr] = min(20, out.get(attr, 10) + int(b))
    return out


def variation_on_monster(tipo: str, spread: int = 2) -> dict[str, int]:
    m = MONSTERS.get(tipo, MONSTERS["Guarda"])
    base = m["base_scores"]
    out: dict[str, int] = {}
    for k, v in base.items():
        delta = random.randint(-spread, spread)
        out[k] = max(3, min(20, int(v) + delta))
    return out
