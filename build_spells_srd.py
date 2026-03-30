from __future__ import annotations

import json
import os
import time
from typing import Any

import urllib.parse
import urllib.request


BASE_URL = "https://api.open5e.com"
DOC_SLUG = "wotc-srd"
OUT_DIR = os.path.join("data", "database")
OUT_PATH = os.path.join(OUT_DIR, "spells_srd.json")


def _get_json(url: str, params: dict[str, Any]) -> dict[str, Any]:
    r = requests.get(url, params=params, timeout=60)
    r.raise_for_status()
    return r.json()


def _strip_components(components: str) -> str:
    # Open5e usa "V, S" etc. Mantemos e só limpamos espaços duplicados.
    return ", ".join([c.strip() for c in components.split(",") if c.strip()])


def _spell_out(spell: dict[str, Any]) -> dict[str, Any]:
    return {
        "slug": spell.get("slug"),
        "nome": spell.get("name"),
        "nivel": spell.get("level"),
        "nivel_int": spell.get("level_int"),
        "escola": spell.get("school"),
        "tempo_conjuracao": spell.get("casting_time"),
        "alcance": spell.get("range"),
        "componentes": _strip_components(spell.get("components") or ""),
        "duracao": spell.get("duration"),
        "concentracao": bool(spell.get("requires_concentration") or spell.get("concentration") == "yes"),
        "descricao": spell.get("desc"),
        "classes": spell.get("spell_lists") or [],
        # useful for UI
        "higher_level": spell.get("higher_level") or "",
    }


def fetch_spells_srd(max_level_int: int = 9) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    opener = urllib.request.build_opener()

    def get_json(url: str, params: dict[str, Any]) -> dict[str, Any]:
        qs = urllib.parse.urlencode(params, doseq=True)
        full = f"{url}?{qs}"
        req = urllib.request.Request(full, headers={"User-Agent": "roll-play-bot"})
        with opener.open(req, timeout=60) as resp:
            raw = resp.read()
        return json.loads(raw.decode("utf-8"))

    for lvl in range(0, max_level_int + 1):
        page = 1
        while True:
            params = {
                "limit": 100,
                "page": page,
                "document__slug": DOC_SLUG,
                "level_int": lvl,
                "format": "json",
            }
            url = f"{BASE_URL}/spells/"
            data = get_json(url, params)
            results = data.get("results") or []
            out.extend(_spell_out(s) for s in results)
            next_url = data.get("next")
            if not next_url:
                break
            page += 1
            time.sleep(0.15)
    # Remove duplicates by slug
    seen = set()
    dedup: list[dict[str, Any]] = []
    for sp in out:
        slug = sp.get("slug")
        if not slug or slug in seen:
            continue
        seen.add(slug)
        dedup.append(sp)
    return dedup


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    spells = fetch_spells_srd(9)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(spells, f, ensure_ascii=False, indent=2)
    print(f"OK: saved {len(spells)} spells to {OUT_PATH}")


if __name__ == "__main__":
    main()

