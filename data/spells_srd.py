from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any


@lru_cache(maxsize=1)
def _load_spells() -> list[dict[str, Any]]:
    base_dir = os.path.dirname(__file__)
    path = os.path.join(base_dir, "database", "spells_srd.json")
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


SPELLS = _load_spells()

# Mapeia classes PT (usadas no projeto) para identificadores em inglês do Open5E (spell_lists).
CLASS_TO_OPEN5E_SPELL_LISTS: dict[str, list[str]] = {
    "Mago": ["wizard"],
    "Bruxo": ["warlock"],
    "Feiticeiro": ["sorcerer"],
    "Bardo": ["bard"],
    "Clérigo": ["cleric"],
    "Druida": ["druid"],
    # Half casters (ranger/paladin) não foram integrados totalmente no wizard ainda,
    # mas deixamos aqui para expansão futura.
    "Patrulheiro": ["ranger"],
    "Paladino": ["paladin"],
}


def get_open5e_spell_lists_for_class(class_key: str) -> list[str]:
    return CLASS_TO_OPEN5E_SPELL_LISTS.get(class_key, [])


def is_spell_available_for_class(spell: dict[str, Any], class_key: str) -> bool:
    lists = get_open5e_spell_lists_for_class(class_key)
    if not lists:
        return False
    spell_lists = spell.get("classes") or []
    return any(x in lists for x in spell_lists)


def get_spells_by_level_for_class(class_key: str, spell_level_int: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for sp in SPELLS:
        if int(sp.get("nivel_int") or 0) != int(spell_level_int):
            continue
        if is_spell_available_for_class(sp, class_key):
            out.append(sp)
    # Ordenação estável por nome
    out.sort(key=lambda s: (str(s.get("nome") or ""), int(s.get("nivel_int") or 0)))
    return out


def get_spell_by_slug(slug: str) -> dict[str, Any] | None:
    for sp in SPELLS:
        if sp.get("slug") == slug:
            return sp
    return None


def truncate(text: str, n: int = 220) -> str:
    s = text or ""
    s = s.replace("\n", " ").strip()
    if len(s) <= n:
        return s
    return s[: n - 1] + "…"

