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

import os
import json
import re

BASE_PLAYER_PATH = "data/players"

try:
    from utils.supabase_storage import (
        is_supabase_enabled,
        load_character_sheet,
        save_character_sheet,
        delete_character_sheet,
        list_character_names,
    )
except Exception:
    is_supabase_enabled = None  # type: ignore

def sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "_", name)

def get_player_sheet_path(character_name: str) -> str:
    safe_name = sanitize_filename(character_name.lower().replace(" ", "_"))
    return os.path.join(BASE_PLAYER_PATH, f"{safe_name}.json")

def load_player_sheet(character_name: str, guild_id: int | None = None) -> dict:
    if callable(globals().get("is_supabase_enabled")) and is_supabase_enabled():
        try:
            discord_user_id = int(character_name.split("_", 1)[0])
        except Exception:
            discord_user_id = 0
        try:
            return load_character_sheet(
                discord_user_id=discord_user_id,
                character_name=character_name,
                guild_id=guild_id,
            )
        except FileNotFoundError:
            pass

    path = get_player_sheet_path(character_name)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            ficha = json.load(f)
        # Migração preguiçosa: se há Supabase e não achou, persiste no banco.
        if callable(globals().get("is_supabase_enabled")) and is_supabase_enabled():
            try:
                discord_user_id = int(character_name.split("_", 1)[0])
            except Exception:
                discord_user_id = ficha.get("discord_user_id") or 0
            try:
                save_character_sheet(
                    discord_user_id=int(discord_user_id),
                    character_name=character_name,
                    guild_id=ficha.get("guild_id") or guild_id,
                    ficha=ficha,
                )
            except Exception:
                pass
        return ficha
    return {}

def save_player_sheet(character_name: str, data: dict, guild_id: int | None = None):
    try:
        from utils.carry_utils import apply_encumbrance_flag
        apply_encumbrance_flag(data)
    except Exception:
        pass

    if callable(globals().get("is_supabase_enabled")) and is_supabase_enabled():
        try:
            discord_user_id = int(character_name.split("_", 1)[0])
        except Exception:
            discord_user_id = int(data.get("discord_user_id") or 0)

        if guild_id is None:
            guild_id = data.get("guild_id") or (data.get("informacoes_basicas") or {}).get("guild_id")
        if guild_id is None:
            guild_id = 0

        # guarda também dentro do sheet_json (ajuda em migração preguiçosa)
        data["guild_id"] = int(guild_id)

        save_character_sheet(
            discord_user_id=discord_user_id,
            character_name=character_name,
            guild_id=guild_id,
            ficha=data,
        )
        return

    path = get_player_sheet_path(character_name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def player_sheet_exists(character_name: str, guild_id: int | None = None) -> bool:
    if callable(globals().get("is_supabase_enabled")) and is_supabase_enabled():
        try:
            discord_user_id = int(character_name.split("_", 1)[0])
        except Exception:
            discord_user_id = 0
        try:
            _ = load_character_sheet(
                discord_user_id=discord_user_id,
                character_name=character_name,
                guild_id=guild_id,
            )
            return True
        except FileNotFoundError:
            return False
    return os.path.exists(get_player_sheet_path(character_name))

def list_player_sheet_slugs_for_user(user_id: int, guild_id: int | None = None) -> list[str]:
    """
    Lista os "slugs" (nome do arquivo sem .json) das fichas do usuário.
    Nosso padrão atual é: `<user_id>_<nickname>.json` (após sanitização).
    """
    if callable(globals().get("is_supabase_enabled")) and is_supabase_enabled():
        try:
            names = list_character_names(discord_user_id=int(user_id), guild_id=guild_id)
            if names:
                return names
        except Exception:
            pass

    if not os.path.exists(BASE_PLAYER_PATH):
        return []
    prefix = f"{int(user_id)}_"
    out: list[str] = []
    for fn in os.listdir(BASE_PLAYER_PATH):
        if not fn.lower().endswith(".json"):
            continue
        slug = fn[:-5]  # remove .json
        if slug.lower().startswith(prefix):
            out.append(slug)
    out.sort(key=lambda s: s.lower())
    return out

def delete_player_sheet(character_name: str) -> bool:
    if callable(globals().get("is_supabase_enabled")) and is_supabase_enabled():
        try:
            discord_user_id = int(character_name.split("_", 1)[0])
        except Exception:
            discord_user_id = 0
        return delete_character_sheet(
            discord_user_id=discord_user_id,
            character_name=character_name,
            guild_id=None,
        )

    path = get_player_sheet_path(character_name)
    if os.path.exists(path):
        os.remove(path)
        return True
    return False
