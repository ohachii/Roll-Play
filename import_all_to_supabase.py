from __future__ import annotations

import json
import os
from pathlib import Path

from utils.supabase_storage import is_supabase_enabled, save_character_sheet


ROOT = Path(__file__).resolve().parent
PLAYERS_DIR = ROOT / "data" / "players"
NPCS_DIR = ROOT / "data" / "npcs"


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        return {}
    return data


def import_players() -> tuple[int, int]:
    ok = 0
    fail = 0
    if not PLAYERS_DIR.exists():
        return ok, fail

    for file in PLAYERS_DIR.glob("*.json"):
        slug = file.stem
        ficha = _load_json(file)
        if not ficha:
            fail += 1
            continue

        try:
            user_id = int(slug.split("_", 1)[0])
        except Exception:
            fail += 1
            continue

        guild_id = ficha.get("guild_id")
        try:
            guild_id = int(guild_id) if guild_id is not None else None
        except Exception:
            guild_id = None

        try:
            save_character_sheet(
                discord_user_id=user_id,
                character_name=slug,
                guild_id=guild_id,
                ficha=ficha,
            )
            ok += 1
        except Exception:
            fail += 1
    return ok, fail


def import_npcs() -> tuple[int, int]:
    ok = 0
    fail = 0
    if not NPCS_DIR.exists():
        return ok, fail

    for guild_dir in NPCS_DIR.iterdir():
        if not guild_dir.is_dir() or not guild_dir.name.isdigit():
            continue
        guild_id = int(guild_dir.name)
        for mestre_dir in guild_dir.iterdir():
            if not mestre_dir.is_dir() or not mestre_dir.name.isdigit():
                continue
            mestre_id = int(mestre_dir.name)
            for file in mestre_dir.glob("*.json"):
                slug = file.stem
                ficha = _load_json(file)
                if not ficha:
                    fail += 1
                    continue
                try:
                    save_character_sheet(
                        discord_user_id=mestre_id,
                        character_name=slug,
                        guild_id=guild_id,
                        ficha=ficha,
                    )
                    ok += 1
                except Exception:
                    fail += 1

    return ok, fail


def main():
    if not is_supabase_enabled():
        raise RuntimeError("Supabase não está configurado (SUPABASE_URL/SUPABASE_KEY) ou biblioteca ausente.")

    p_ok, p_fail = import_players()
    n_ok, n_fail = import_npcs()

    total_ok = p_ok + n_ok
    total_fail = p_fail + n_fail

    print(f"[import] players: ok={p_ok} fail={p_fail}")
    print(f"[import] npcs:    ok={n_ok} fail={n_fail}")
    print(f"[import] total:   ok={total_ok} fail={total_fail}")


if __name__ == "__main__":
    main()

