from __future__ import annotations

from typing import Any, Dict, List

from data import dnd5e_srd
from utils.supabase_storage import get_supabase_client, is_supabase_enabled


def _safe_client():
    if not is_supabase_enabled():
        return None
    return get_supabase_client()


def get_race_templates() -> List[Dict[str, Any]]:
    """
    Retorna a lista de raças disponíveis para criação de ficha.
    Se houver Supabase, mescla templates da tabela com os valores SRD,
    permitindo que entradas do banco sobrescrevam as padrões.
    """
    base: Dict[str, Dict[str, Any]] = {}
    for name, data in dnd5e_srd.RACES.items():
        base[name] = {
            "nome": name,
            "bonus_atributo": data.get("ability_bonuses") or {},
            "deslocamento": data.get("speed", "9m"),
            "descricao": data.get("desc", ""),
            "source": "srd",
        }

    supa = _safe_client()
    if supa is None:
        return list(base.values())

    try:
        resp = supa.table("templates_races").select("*").execute()
        rows = getattr(resp, "data", None) or []
        for r in rows:
            name = str(r.get("nome") or "").strip()
            if not name:
                continue
            base[name] = {
                "nome": name,
                "bonus_atributo": r.get("bonus_atributo") or {},
                "deslocamento": r.get("deslocamento") or "9m",
                "descricao": r.get("descricao") or "",
                "source": "custom",
            }
    except Exception as e:
        print(f"[DB ERROR] get_race_templates: {e}")

    return sorted(base.values(), key=lambda x: str(x.get("nome", "")).lower())


def get_class_templates() -> List[Dict[str, Any]]:
    """
    Retorna classes disponíveis (SRD + templates customizados).
    """
    base: Dict[str, Dict[str, Any]] = {}
    for name, data in dnd5e_srd.CLASSES.items():
        base[name] = {
            "nome": name,
            "dado_vida": data.get("hit_die"),
            "salvaguardas": list(data.get("save_proficiency") or []),
            "pericias_qtd": int(data.get("skill_pick") or 2),
            "habilidades_nivel_1": data.get("level1_features") or [],
            "source": "srd",
        }

    supa = _safe_client()
    if supa is None:
        return list(base.values())

    try:
        resp = supa.table("templates_classes").select("*").execute()
        rows = getattr(resp, "data", None) or []
        for r in rows:
            name = str(r.get("nome") or "").strip()
            if not name:
                continue
            base[name] = {
                "nome": name,
                "dado_vida": r.get("dado_vida"),
                "salvaguardas": r.get("salvaguardas") or [],
                "pericias_qtd": int(r.get("pericias_qtd") or 2),
                "habilidades_nivel_1": r.get("habilidades_nivel_1") or [],
                "source": "custom",
            }
    except Exception as e:
        print(f"[DB ERROR] get_class_templates: {e}")

    return sorted(base.values(), key=lambda x: str(x.get("nome", "")).lower())


def get_background_templates() -> List[Dict[str, Any]]:
    """
    Retorna backgrounds (origens) disponíveis (SRD + templates customizados).
    """
    base: Dict[str, Dict[str, Any]] = {}
    for name, data in dnd5e_srd.BACKGROUNDS.items():
        base[name] = {
            "nome": name,
            "pericias_fixas": list(data.get("extra_skills") or []),
            "equipamento_inicial": list(data.get("extra_items") or []),
            "source": "srd",
        }

    supa = _safe_client()
    if supa is None:
        return list(base.values())

    try:
        resp = supa.table("templates_backgrounds").select("*").execute()
        rows = getattr(resp, "data", None) or []
        for r in rows:
            name = str(r.get("nome") or "").strip()
            if not name:
                continue
            base[name] = {
                "nome": name,
                "pericias_fixas": r.get("pericias_fixas") or [],
                "equipamento_inicial": r.get("equipamento_inicial") or [],
                "source": "custom",
            }
    except Exception as e:
        print(f"[DB ERROR] get_background_templates: {e}")

    return sorted(base.values(), key=lambda x: str(x.get("nome", "")).lower())


def upsert_race_template(payload: Dict[str, Any]) -> None:
    supa = _safe_client()
    if supa is None:
        raise RuntimeError("Supabase não configurado/instalado para templates.")
    try:
        supa.table("templates_races").upsert(payload).execute()
    except Exception as e:
        print(f"[DB ERROR] upsert_race_template: {e}")
        raise


def upsert_class_template(payload: Dict[str, Any]) -> None:
    supa = _safe_client()
    if supa is None:
        raise RuntimeError("Supabase não configurado/instalado para templates.")
    try:
        supa.table("templates_classes").upsert(payload).execute()
    except Exception as e:
        print(f"[DB ERROR] upsert_class_template: {e}")
        raise


def upsert_background_template(payload: Dict[str, Any]) -> None:
    supa = _safe_client()
    if supa is None:
        raise RuntimeError("Supabase não configurado/instalado para templates.")
    try:
        supa.table("templates_backgrounds").upsert(payload).execute()
    except Exception as e:
        print(f"[DB ERROR] upsert_background_template: {e}")
        raise

