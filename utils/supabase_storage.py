from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

_supabase_client = None


def _try_create_client():
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client
    if not SUPABASE_URL or not SUPABASE_KEY:
        _supabase_client = None
        return None
    try:
        from supabase import create_client  # type: ignore

        _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
        return _supabase_client
    except Exception:
        _supabase_client = None
        return None


def is_supabase_enabled() -> bool:
    return _try_create_client() is not None


def _to_int_or_none(v: Any) -> int | None:
    try:
        if v is None or v == "":
            return None
        return int(v)
    except Exception:
        return None


def _sheet_to_columns(ficha: dict[str, Any]) -> dict[str, Any]:
    info_basicas = ficha.get("informacoes_basicas") or {}
    info_gerais = ficha.get("informacoes_gerais") or {}
    info_combate = ficha.get("informacoes_combate") or {}
    attrs = ficha.get("atributos") or {}

    def _attr_score(key: str) -> int | None:
        for k in (key, key.lower(), key.capitalize(), key.upper()):
            if k in attrs:
                return _to_int_or_none(attrs.get(k))
        return None

    # compat: alguns campos no código podem estar em outras chaves
    spell_slots = ficha.get("spell_slots") or {}
    if not isinstance(spell_slots, dict):
        spell_slots = {}

    salv_ts = ficha.get("salvaguardas_proficientes")
    if salv_ts is None:
        salv_ts = []
    if not isinstance(salv_ts, list):
        salv_ts = []

    cond = ficha.get("condicoes_automaticas") or ficha.get("condicoes") or []
    if not isinstance(cond, list):
        cond = []

    return {
        "system_rpg": info_basicas.get("sistema_rpg") or ficha.get("system_rpg") or "dnd",
        "nivel_rank": info_gerais.get("nivel_rank") or info_basicas.get("nivel_rank"),
        "forca": _attr_score("Força"),
        "destreza": _attr_score("Destreza"),
        "constituicao": _attr_score("Constituição"),
        "inteligencia": _attr_score("Inteligência"),
        "sabedoria": _attr_score("Sabedoria"),
        "carisma": _attr_score("Carisma"),
        "ca": _to_int_or_none(info_combate.get("defesa")),
        "iniciativa": str(info_combate.get("iniciativa") or ""),
        "hp_atual": _to_int_or_none(info_combate.get("vida_atual")),
        "hp_max": _to_int_or_none(info_combate.get("vida_maxima")),
        "magia_atual": _to_int_or_none(info_combate.get("magia_atual")),
        "magia_max": _to_int_or_none(info_combate.get("magia_maxima")),
        "spell_slots": spell_slots,
        "salvaguardas_proficientes": salv_ts,
        "concentracao_magia": ficha.get("concentracao_magia") or info_combate.get("concentracao_magia"),
        "condicoes": cond,
        "sheet_json": ficha,
    }


def _find_character_row(
    *,
    discord_user_id: int,
    character_name: str,
    guild_id: int | None,
) -> dict[str, Any] | None:
    supa = _try_create_client()
    if supa is None:
        return None
    # Fallback de migração:
    # 1) Tenta preferir `guild_id` (quando informado)
    # 2) Se não houver, retorna a primeira linha compatível (inclusive `guild_id` NULL),
    #    para não quebrar fichas antigas durante a transição.
    resp = (
        supa.table("characters")
        .select("*")
        .eq("discord_user_id", discord_user_id)
        .eq("character_name", character_name)
        .limit(25)
        .execute()
    )
    rows = getattr(resp, "data", None) or []
    if not rows:
        return None
    if guild_id is None:
        return rows[0]
    # escolhe primeiro o que tem guild_id igual
    for r in rows:
        if r.get("guild_id") == guild_id:
            return r
    # fallback para qualquer guild (por exemplo NULL)
    return rows[0]


def load_character_sheet(
    *,
    discord_user_id: int,
    character_name: str,
    guild_id: int | None = None,
) -> dict[str, Any]:
    """
    Retorna `sheet_json` completo.
    Lança FileNotFoundError se não existir.
    """
    row = _find_character_row(discord_user_id=discord_user_id, character_name=character_name, guild_id=guild_id)
    if row is None:
        raise FileNotFoundError(f"Sheet não encontrada: {character_name}")
    sheet = row.get("sheet_json") or {}
    if not isinstance(sheet, dict):
        sheet = {}
    return sheet


def save_character_sheet(
    *,
    discord_user_id: int,
    character_name: str,
    guild_id: int | None,
    ficha: dict[str, Any],
) -> None:
    supa = _try_create_client()
    if supa is None:
        raise RuntimeError("Supabase não configurado/instalado.")

    payload = _sheet_to_columns(ficha)
    # garante chaves mínimas
    payload["discord_user_id"] = discord_user_id
    payload["character_name"] = character_name
    payload["guild_id"] = guild_id

    existing = _find_character_row(
        discord_user_id=discord_user_id, character_name=character_name, guild_id=guild_id
    )
    if existing and existing.get("id"):
        cid = existing["id"]
        supa.table("characters").update(payload).eq("id", cid).execute()
    else:
        supa.table("characters").insert(payload).execute()


def delete_character_sheet(
    *,
    discord_user_id: int,
    character_name: str,
    guild_id: int | None = None,
) -> bool:
    supa = _try_create_client()
    if supa is None:
        return False
    row = _find_character_row(
        discord_user_id=discord_user_id, character_name=character_name, guild_id=guild_id
    )
    if not row or not row.get("id"):
        return False
    cid = row["id"]
    supa.table("characters").delete().eq("id", cid).execute()
    return True


def list_character_names(*, discord_user_id: int, guild_id: int | None = None) -> list[str]:
    supa = _try_create_client()
    if supa is None:
        return []
    q = supa.table("characters").select("character_name").eq("discord_user_id", discord_user_id)
    if guild_id is not None:
        q = q.eq("guild_id", guild_id)
    resp = q.execute()
    rows = getattr(resp, "data", None) or []
    out: list[str] = []
    for r in rows:
        name = r.get("character_name")
        if isinstance(name, str):
            out.append(name)
    out.sort(key=lambda s: s.lower())
    return out

