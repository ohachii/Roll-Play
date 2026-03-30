# Montagem de ficha D&D 5e a partir de escolhas guiadas.
from __future__ import annotations

from typing import Any

from data import dnd5e_srd
from utils import rpg_rules


def _str_attr(n: int) -> str:
    return str(int(n))


def starting_hp(hit_die: int, constitution_final: int) -> int:
    con_mod = rpg_rules.get_modifier("dnd", constitution_final)
    return max(1, int(hit_die) + con_mod)


def default_ac(dexterity_final: int) -> str:
    dex_mod = rpg_rules.get_modifier("dnd", dexterity_final)
    return str(10 + dex_mod)


def merge_skills(class_key: str, background_key: str, extra_pick: list[str] | None = None) -> dict[str, Any]:
    cls = dnd5e_srd.CLASSES.get(class_key, dnd5e_srd.CLASSES["Guerreiro"])
    bg = dnd5e_srd.BACKGROUNDS.get(background_key, dnd5e_srd.BACKGROUNDS["Nenhum"])
    pool = list(cls.get("skill_choices") or [])
    n = int(cls.get("skill_pick") or 2)
    import random

    picked: list[str] = []
    if pool and n > 0:
        k = min(n, len(pool))
        picked.extend(random.sample(pool, k))
    for s in bg.get("extra_skills") or []:
        if s not in picked:
            picked.append(s)
    if extra_pick:
        for s in extra_pick:
            if s not in picked:
                picked.append(s)
    out: dict[str, Any] = {}
    for sk in picked:
        ab = dnd5e_srd.SKILL_TO_ATTR.get(sk, "Destreza")
        out[sk] = {
            "atributo_base": ab,
            "bonus": 0,
            "proficiencia_dnd": "proficiente",
        }
    return out


def build_player_sheet(
    *,
    titulo_apelido: str,
    race: str,
    class_key: str,
    background_key: str,
    base_scores_before_race: dict[str, int],
) -> dict[str, Any]:
    """base_scores: valores após 4d6 (antes dos bônus raciais)."""
    final_scores = dnd5e_srd.apply_racial_bonuses(dict(base_scores_before_race), race)
    cls = dnd5e_srd.CLASSES.get(class_key, dnd5e_srd.CLASSES["Guerreiro"])
    bg = dnd5e_srd.BACKGROUNDS.get(background_key, dnd5e_srd.BACKGROUNDS["Nenhum"])
    hd = int(cls["hit_die"])
    hp = starting_hp(hd, final_scores["Constituição"])
    ac = default_ac(final_scores["Destreza"])
    skills = merge_skills(class_key, background_key)

    atributos = {k: _str_attr(v) for k, v in final_scores.items()}

    extra_languages = bg.get("extra_languages") or []
    extra_items = bg.get("extra_items") or []

    # Itens/“kits” do background aparecem no inventário como categoria aleatória,
    # para o usuário ver no painel sem precisar preencher manualmente.
    inventario: dict[str, Any] = {}
    if extra_items:
        inventario["aleatorio"] = [
            {
                "nome": str(item),
                "quantidade": 1,
                "peso": "0",
                "descricao": "",
                "efeito": str(item),
            }
            for item in extra_items
        ]

    return {
        "informacoes_basicas": {
            "sistema_rpg": "dnd",
            "titulo_apelido": titulo_apelido or "Aventureiro",
            "raca_especie": race,
            "classe_profissao": class_key,
        },
        "informacoes_gerais": {
            "nivel_rank": "1",
            "genero": "",
            "idade": "",
            "altura_peso": "",
        },
        "atributos": atributos,
        "salvaguardas_proficientes": list(cls.get("save_proficiency") or []),
        "pericias": skills,
        "informacoes_combate": {
            "vida_atual": hp,
            "vida_maxima": hp,
            "magia_atual": 0,
            "magia_maxima": 0,
            "defesa": ac,
            "resistencia_magica": "",
            "iniciativa": str(rpg_rules.get_modifier("dnd", final_scores["Destreza"])),
        },
        "criacao_dnd": {
            "dado_vida_classe": f"d{hd}",
            "antecedente": background_key,
            "scores_pre_racial": {k: int(v) for k, v in base_scores_before_race.items()},
        },
        "inventario": inventario,
        "informacoes_extras": {
            "idiomas": ", ".join(map(str, extra_languages)) if extra_languages else "",
            "background": ", ".join(map(str, extra_items)) if extra_items else "",
            "origem": background_key,
            "personalidade": "",
            "aparencia": "",
        },
        "locale": "pt",
    }


def build_npc_sheet(
    *,
    nome: str,
    race: str,
    class_key: str,
    difficulty: str,
    monster_type: str | None = None,
) -> dict[str, Any]:
    """Gera NPC nível 1 para pasta do mestre."""
    import random

    diff = (difficulty or "fácil").strip().lower()
    cls = dnd5e_srd.CLASSES.get(class_key, dnd5e_srd.CLASSES["Guerreiro"])
    hd = int(cls["hit_die"])

    if monster_type and monster_type in dnd5e_srd.MONSTERS:
        base_scores = dnd5e_srd.variation_on_monster(monster_type, spread=2)
    else:
        if diff in ("fácil", "facil", "easy", "minion"):
            raw = rpg_rules.roll_stats_5e()
        else:
            raw = rpg_rules.roll_stats_5e_min_modifier_total(4, max_attempts=80)
        primary = list(cls.get("primary") or ["Força", "Constituição", "Destreza"])
        base_scores = dnd5e_srd.auto_assign_stats(raw, primary)

    base_scores = dnd5e_srd.apply_racial_bonuses(base_scores, race)

    if diff in ("médio", "medio", "medium", "elite"):
        base_scores = {k: min(20, v + 2) for k, v in base_scores.items()}
    elif diff in ("difícil", "dificil", "hard", "boss"):
        base_scores = {k: min(20, v + 4) for k, v in base_scores.items()}

    con = base_scores["Constituição"]
    if diff in ("difícil", "dificil", "hard", "boss"):
        hp = max(1, hd * 2 + rpg_rules.get_modifier("dnd", con))
    elif diff in ("médio", "medio", "medium", "elite"):
        hp = max(1, hd + hd // 2 + 1 + rpg_rules.get_modifier("dnd", con))
    else:
        hp = starting_hp(hd, con)

    ac = default_ac(base_scores["Destreza"])
    n_skills = 4 if diff in ("difícil", "dificil", "hard", "boss") else 2
    pool = list(cls.get("skill_choices") or [])
    picked = random.sample(pool, min(n_skills, len(pool))) if pool else []
    skills: dict[str, Any] = {}
    for sk in picked:
        ab = dnd5e_srd.SKILL_TO_ATTR.get(sk, "Destreza")
        skills[sk] = {"atributo_base": ab, "bonus": 0, "proficiencia_dnd": "proficiente"}

    npc = {
        "nome": nome,
        "informacoes_basicas": {
            "sistema_rpg": "dnd",
            "titulo_apelido": nome,
            "raca_especie": race,
            "classe_profissao": class_key,
        },
        "informacoes_gerais": {"nivel_rank": "1"},
        "atributos": {k: _str_attr(v) for k, v in base_scores.items()},
        "salvaguardas_proficientes": list(cls.get("save_proficiency") or []),
        "pericias": skills,
        "informacoes_combate": {
            "vida_atual": hp,
            "vida_maxima": hp,
            "magia_atual": 0,
            "magia_maxima": 0,
            "defesa": ac,
            "resistencia_magica": "",
            "iniciativa": str(rpg_rules.get_modifier("dnd", base_scores["Destreza"])),
        },
        "informacoes_extras": {
            "personalidade_ia": dnd5e_srd.random_personality(),
            "dificuldade_npc": difficulty,
            "vantagem_em_ts": diff in ("difícil", "dificil", "hard", "boss"),
        },
        "inventario": {},
    }
    return npc
