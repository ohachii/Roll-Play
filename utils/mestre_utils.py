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

from __future__ import annotations

import os
import json

BASE_DIR = "data/servidores"

def get_server_path(guild_name: str) -> str:
    server_path = os.path.join(BASE_DIR, guild_name)
    os.makedirs(server_path, exist_ok=True)
    return server_path

def get_mestres_path(guild_name: str) -> str:
    return os.path.join(get_server_path(guild_name), "mestres.json")

def carregar_mestres(guild_name: str) -> list:
    mestres_path = get_mestres_path(guild_name)
    if not os.path.exists(mestres_path):
        return []
    with open(mestres_path, "r", encoding="utf-8") as f:
        return json.load(f)

def salvar_mestres(guild_name: str, mestres: list):
    mestres_path = get_mestres_path(guild_name)
    with open(mestres_path, "w", encoding="utf-8") as f:
        json.dump(mestres, f, indent=4, ensure_ascii=False)

def adicionar_mestre(guild_name: str, mestre_id: int, mestre_nome: str):
    mestres = carregar_mestres(guild_name)
    if any(m["id"] == mestre_id for m in mestres):
        return False
    mestres.append({"id": mestre_id, "nome": mestre_nome})
    salvar_mestres(guild_name, mestres)
    return True

def verificar_mestre(guild_name: str, user_id: int) -> bool:
    mestres = carregar_mestres(guild_name)
    return any(m["id"] == user_id for m in mestres)


def registrar_mestre(guild_name: str, user_id: int, mestre_nome: str = "Mestre") -> bool:
    """Registra mestre (usado por /virar_mestre)."""
    return adicionar_mestre(guild_name, user_id, mestre_nome)


def pode_painel_mestre(guild, user) -> bool:
    """Mestre registrado, administrador do servidor ou cargo nomeado 'Mestre'."""
    if guild is None:
        return False
    try:
        if getattr(user, "guild_permissions", None) and user.guild_permissions.administrator:
            return True
    except Exception:
        pass
    gname = getattr(guild, "name", None) or str(guild.id)
    uid = int(getattr(user, "id", 0))
    if verificar_mestre(gname, uid):
        return True
    try:
        roles = getattr(user, "roles", ()) or ()
        for r in roles:
            if getattr(r, "name", None) == "Mestre":
                return True
    except Exception:
        pass
    return False
