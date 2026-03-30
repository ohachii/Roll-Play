# Carga D&D 5e: Força × 15 lb (simplificado; assumir peso em lb nos itens numéricos).
from __future__ import annotations

import re
from typing import Any

from utils import rpg_rules


def _parse_weight_lb(raw: Any) -> float:
    if raw is None:
        return 0.0
    s = str(raw).strip().lower().replace(",", ".")
    if not s:
        return 0.0
    m = re.search(r"([\d.]+)", s)
    if not m:
        return 0.0
    try:
        val = float(m.group(1))
    except ValueError:
        return 0.0
    if "kg" in s:
        return val * 2.20462
    return val


def total_inventory_weight_lb(ficha: dict) -> float:
    inv = ficha.get("inventario") or {}
    total = 0.0
    for key in ("defesa", "combate", "consumivel", "itens", "aleatorio"):
        for item in inv.get(key) or []:
            if not isinstance(item, dict):
                continue
            try:
                q = int(item.get("quantidade") or 1)
            except (TypeError, ValueError):
                q = 1
            total += q * _parse_weight_lb(item.get("peso"))
    return total


def carrying_capacity_lb(ficha: dict) -> int:
    attrs = ficha.get("atributos") or {}
    raw = attrs.get("Força") or attrs.get("força") or "10"
    try:
        s = int(raw)
    except (TypeError, ValueError):
        s = 10
    return max(0, s) * 15


def apply_encumbrance_flag(ficha: dict) -> None:
    if not rpg_rules.is_dnd_system((ficha.get("informacoes_basicas") or {}).get("sistema_rpg", "dnd")):
        return
    cap = carrying_capacity_lb(ficha)
    w = total_inventory_weight_lb(ficha)
    flags = ficha.setdefault("flags_5e", {})
    flags["peso_total_lb"] = round(w, 2)
    flags["carga_max_lb"] = cap
    flags["sobrecarregado"] = bool(cap > 0 and w > cap)
    cond = ficha.setdefault("condicoes_automaticas", [])
    tag = "Sobrecarregado"
    if flags["sobrecarregado"]:
        if tag not in cond:
            cond.append(tag)
    else:
        if tag in cond:
            cond.remove(tag)
