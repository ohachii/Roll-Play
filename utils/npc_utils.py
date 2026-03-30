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

try:
    from utils.supabase_storage import (
        is_supabase_enabled,
        load_character_sheet,
        save_character_sheet,
        list_character_names,
    )
except Exception:
    is_supabase_enabled = None  # type: ignore

class NPCContext:
    BASE_DIR = "data/npcs"
    def __init__(self, guild_id: int, mestre_id: int, npc_name: str):
        self.guild_id = guild_id
        self.mestre_id = mestre_id
        self.npc_name = npc_name

    @classmethod
    def get_npc_folder(cls, guild_id: int, mestre_id: int):
        return os.path.join(cls.BASE_DIR, str(guild_id), str(mestre_id))

    @classmethod
    def get_npc_path(cls, guild_id: int, mestre_id: int, npc_name: str):
        folder = cls.get_npc_folder(guild_id, mestre_id)
        return os.path.join(folder, f"{npc_name}.json")

    def save(self, npc_data: dict):
        if callable(globals().get("is_supabase_enabled")) and is_supabase_enabled():
            save_character_sheet(
                discord_user_id=self.mestre_id,
                character_name=self.npc_name,
                guild_id=self.guild_id,
                ficha=npc_data,
            )
            return

        folder = self.get_npc_folder(self.guild_id, self.mestre_id)
        os.makedirs(folder, exist_ok=True)
        path = self.get_npc_path(self.guild_id, self.mestre_id, self.npc_name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(npc_data, f, indent=4, ensure_ascii=False)

    def load(self) -> dict:
        if callable(globals().get("is_supabase_enabled")) and is_supabase_enabled():
            try:
                return load_character_sheet(
                    discord_user_id=self.mestre_id,
                    character_name=self.npc_name,
                    guild_id=self.guild_id,
                )
            except FileNotFoundError:
                return {}

        path = self.get_npc_path(self.guild_id, self.mestre_id, self.npc_name)
        if not os.path.exists(path):
            return {}
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    @classmethod
    def list_npcs(cls, guild_id: int, mestre_id: int) -> list[str]:
        if callable(globals().get("is_supabase_enabled")) and is_supabase_enabled():
            try:
                names = list_character_names(discord_user_id=mestre_id, guild_id=guild_id)
                if names:
                    return names
            except Exception:
                return []

        folder = cls.get_npc_folder(guild_id, mestre_id)
        if not os.path.exists(folder):
            return []
        return [
            filename[:-5] for filename in os.listdir(folder)
            if filename.endswith(".json")
        ]

    @classmethod
    def list_visible_npcs(cls, guild_id: int) -> list[str]:
        if callable(globals().get("is_supabase_enabled")) and is_supabase_enabled():
            # Consulta por `guild_id` e filtra em `sheet_json.visivel_para_players`.
            try:
                from dotenv import load_dotenv

                load_dotenv()
                supa_url = os.getenv("SUPABASE_URL")
                supa_key = os.getenv("SUPABASE_KEY")
                if not supa_url or not supa_key:
                    return []

                from supabase import create_client  # type: ignore

                supa = create_client(supa_url, supa_key)
                resp = (
                    supa.table("characters")
                    .select("character_name, sheet_json")
                    .eq("guild_id", guild_id)
                    .execute()
                )
                rows = getattr(resp, "data", None) or []
                out: list[str] = []
                for r in rows:
                    sheet = r.get("sheet_json") or {}
                    if not isinstance(sheet, dict):
                        continue
                    if sheet.get("visivel_para_players", False):
                        name = sheet.get("nome") or r.get("character_name")
                        if isinstance(name, str) and name.strip():
                            out.append(name)
                out = list(dict.fromkeys(out))  # remove duplicados preservando ordem
                out.sort(key=lambda s: s.lower())
                if out:
                    return out
            except Exception:
                # fallback em caso de erro com Supabase
                pass

        # Fallback: varre arquivos JSON locais.
        visible_npcs: list[str] = []
        guild_folder = os.path.join(cls.BASE_DIR, str(guild_id))
        if not os.path.exists(guild_folder):
            return []

        for mestre_id in os.listdir(guild_folder):
            mestre_folder = os.path.join(guild_folder, mestre_id)
            if not os.path.isdir(mestre_folder):
                continue
            for npc_filename in os.listdir(mestre_folder):
                if not npc_filename.endswith(".json"):
                    continue
                npc_path = os.path.join(mestre_folder, npc_filename)
                with open(npc_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("visivel_para_players", False):
                    visible_npcs.append(data.get("nome", npc_filename[:-5]))

        visible_npcs.sort(key=lambda s: s.lower())
        return visible_npcs
