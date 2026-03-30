# Wizard de criação de ficha D&D 5e (4d6, 3 conjuntos, distribuição manual).
from __future__ import annotations

import discord
from discord import ui

from data import dnd5e_srd
from data import spells_srd
from utils import player_utils, rpg_rules
from utils.dnd_sheet_builder import build_player_sheet


def _embed_stats(rolls: list[int], rerolls_left: int) -> discord.Embed:
    line = ", ".join(str(x) for x in sorted(rolls, reverse=True))
    usados = 3 - rerolls_left
    emb = discord.Embed(
        title="🎲 Rolagem de atributos (4d6, descarta o menor)",
        description=f"**Valores:** {line}\n\n"
        f"Conjunto **{usados}/3** · Rerrolagens restantes: **{rerolls_left}**",
        color=discord.Color.teal(),
    )
    emb.set_footer(text="Aceite para distribuir cada valor a um atributo, ou role de novo se ainda tiver tentativas.")
    return emb


class CreatorRaceClassView(ui.View):
    def __init__(self, user: discord.User, sobrescrever: bool = False):
        super().__init__(timeout=600)
        self.user = user
        self.sobrescrever = sobrescrever
        self.race_pick: str | None = None
        self.class_pick: str | None = None
        self.bg_pick: str | None = None
        self.add_item(self._race_select())
        self.add_item(self._class_select())
        self.add_item(self._bg_select())
        self.add_item(ContinueRaceClassButton())

    def _race_select(self) -> ui.Select:
        sel = ui.Select(
            placeholder="1. Raça",
            options=[discord.SelectOption(label=n, value=n) for n in dnd5e_srd.race_names()[:25]],
            row=0,
        )

        async def cb(interaction: discord.Interaction):
            if interaction.user.id != self.user.id:
                return await interaction.response.send_message("Não é sua ficha.", ephemeral=True)
            self.race_pick = sel.values[0]
            await interaction.response.defer()

        sel.callback = cb
        return sel

    def _class_select(self) -> ui.Select:
        sel = ui.Select(
            placeholder="2. Classe",
            options=[discord.SelectOption(label=n, value=n) for n in dnd5e_srd.class_names()[:25]],
            row=1,
        )

        async def cb(interaction: discord.Interaction):
            if interaction.user.id != self.user.id:
                return await interaction.response.send_message("Não é sua ficha.", ephemeral=True)
            self.class_pick = sel.values[0]
            await interaction.response.defer()

        sel.callback = cb
        return sel

    def _bg_select(self) -> ui.Select:
        sel = ui.Select(
            placeholder="3. Antecedente",
            options=[discord.SelectOption(label=n, value=n) for n in dnd5e_srd.background_names()[:25]],
            row=2,
        )

        async def cb(interaction: discord.Interaction):
            if interaction.user.id != self.user.id:
                return await interaction.response.send_message("Não é sua ficha.", ephemeral=True)
            self.bg_pick = sel.values[0]
            await interaction.response.defer()

        sel.callback = cb
        return sel


class ContinueRaceClassButton(ui.Button):
    def __init__(self):
        super().__init__(label="Continuar para rolagem de atributos", style=discord.ButtonStyle.primary, row=3)

    async def callback(self, interaction: discord.Interaction):
        view: CreatorRaceClassView = self.view  # type: ignore
        if interaction.user.id != view.user.id:
            return await interaction.response.send_message("Não é sua ficha.", ephemeral=True)
        if not (view.race_pick and view.class_pick and view.bg_pick):
            return await interaction.response.send_message(
                "Selecione raça, classe e antecedente nos menus acima.", ephemeral=True
            )
        v = StatsRollView(
            user=view.user,
            race=view.race_pick,
            class_key=view.class_pick,
            background=view.bg_pick,
        )
        await interaction.response.edit_message(embed=_embed_stats(v.current_rolls, v.rerolls_left), view=v)


class StatsRollView(ui.View):
    def __init__(self, user: discord.User, race: str, class_key: str, background: str):
        super().__init__(timeout=600)
        self.user = user
        self.race = race
        self.class_key = class_key
        self.background = background
        self.rerolls_left = 2
        self.current_rolls = rpg_rules.roll_stats_5e()
        self.add_item(RerollStatsButton())
        self.add_item(AcceptStatsButton())


class RerollStatsButton(ui.Button):
    def __init__(self, *, disabled: bool = False):
        super().__init__(
            label="🔄 Rolar novamente",
            style=discord.ButtonStyle.secondary,
            row=0,
            disabled=disabled,
        )

    async def callback(self, interaction: discord.Interaction):
        view: StatsRollView = self.view  # type: ignore
        if interaction.user.id != view.user.id:
            return await interaction.response.send_message("Não é sua ficha.", ephemeral=True)
        if view.rerolls_left <= 0:
            return await interaction.response.send_message(
                "Você já usou as 3 rolagens. Aceite este conjunto.", ephemeral=True
            )
        view.rerolls_left -= 1
        view.current_rolls = rpg_rules.roll_stats_5e()
        view.clear_items()
        view.add_item(RerollStatsButton(disabled=view.rerolls_left <= 0))
        view.add_item(AcceptStatsButton())
        await interaction.response.edit_message(embed=_embed_stats(view.current_rolls, view.rerolls_left), view=view)


class AcceptStatsButton(ui.Button):
    def __init__(self):
        super().__init__(label="✅ Aceitar e distribuir", style=discord.ButtonStyle.success, row=0)

    async def callback(self, interaction: discord.Interaction):
        view: StatsRollView = self.view  # type: ignore
        if interaction.user.id != view.user.id:
            return await interaction.response.send_message("Não é sua ficha.", ephemeral=True)
        av = AssignStatsView(
            user=view.user,
            race=view.race,
            class_key=view.class_key,
            background=view.background,
            pool=list(view.current_rolls),
        )
        av.refresh()
        await interaction.response.edit_message(embed=av.embed(), view=av)


class AssignStatsView(ui.View):
    def __init__(
        self,
        user: discord.User,
        race: str,
        class_key: str,
        background: str,
        pool: list[int],
    ):
        super().__init__(timeout=600)
        self.user = user
        self.race = race
        self.class_key = class_key
        self.background = background
        self.pool = list(pool)
        self.assignments: dict[str, int] = {}
        self.attr_order = list(dnd5e_srd.DND_ATTRIBUTES)
        self.step = 0

    def embed(self) -> discord.Embed:
        done = ", ".join(f"{k}: {v}" for k, v in self.assignments.items()) or "—"
        pend = ", ".join(str(x) for x in sorted(self.pool, reverse=True)) if self.pool else "—"
        emb = discord.Embed(
            title="📌 Distribuir atributos",
            description=f"**Já definidos:** {done}\n**Disponíveis:** {pend}",
            color=discord.Color.blue(),
        )
        if self.step < len(self.attr_order):
            emb.set_footer(text=f"Escolha o valor para **{self.attr_order[self.step]}** (bônus racial será aplicado depois).")
        return emb

    def refresh(self):
        self.clear_items()
        if self.step >= len(self.attr_order):
            self.add_item(FinishAssignButton())
            return
        attr = self.attr_order[self.step]
        if not self.pool:
            return
        self.add_item(StatValueSelect(self, attr))


class StatValueSelect(ui.Select):
    def __init__(self, parent: AssignStatsView, attr: str):
        opts = [
            discord.SelectOption(label=f"{parent.pool[i]}  (#{i + 1})", value=str(i))
            for i in range(min(len(parent.pool), 25))
        ]
        super().__init__(placeholder=f"Valor para {attr}", options=opts, row=0)
        self._parent = parent
        self._attr = attr

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self._parent.user.id:
            return await interaction.response.send_message("Não é sua ficha.", ephemeral=True)
        idx = int(self.values[0])
        if idx < 0 or idx >= len(self._parent.pool):
            return await interaction.response.send_message("Índice inválido.", ephemeral=True)
        v = self._parent.pool.pop(idx)
        self._parent.assignments[self._attr] = v
        self._parent.step += 1
        self._parent.refresh()
        await interaction.response.edit_message(embed=self._parent.embed(), view=self._parent)


class FinishAssignButton(ui.Button):
    def __init__(self):
        super().__init__(label="Finalizar — nome do personagem", style=discord.ButtonStyle.success, row=0)

    async def callback(self, interaction: discord.Interaction):
        view: AssignStatsView = self.view  # type: ignore
        if interaction.user.id != view.user.id:
            return await interaction.response.send_message("Não é sua ficha.", ephemeral=True)
        if len(view.assignments) != 6:
            return await interaction.response.send_message("Atribuição incompleta.", ephemeral=True)
        final_scores = dnd5e_srd.apply_racial_bonuses(view.assignments.copy(), view.race)
        if spells_srd.get_open5e_spell_lists_for_class(view.class_key):
            return await interaction.response.edit_message(
                embed=discord.Embed(
                    title="🔮 Seleção de magias",
                    description="Escolha seus truques antes de continuar.",
                    color=discord.Color.blue(),
                ),
                view=SpellCantripsPickView(
                    user=view.user,
                    race=view.race,
                    class_key=view.class_key,
                    background=view.background,
                    base_scores_before_race=view.assignments.copy(),
                    final_scores=final_scores,
                ),
            )

        await interaction.response.send_modal(
            FinalizeCharacterModal(
                user=view.user,
                race=view.race,
                class_key=view.class_key,
                background=view.background,
                base_scores=view.assignments.copy(),
                selected_spells=[],
                spell_slots={},
                spell_save_dc=None,
                spell_attack_bonus=None,
                spellcasting_ability_key=None,
                spellcasting_ability_score=None,
            )
        )


class FinalizeCharacterModal(ui.Modal, title="Nome do personagem"):
    def __init__(
        self,
        user: discord.User,
        race: str,
        class_key: str,
        background: str,
        base_scores: dict[str, int],
        selected_spells: list[dict],
        spell_slots: dict,
        spell_save_dc: int | None,
        spell_attack_bonus: int | None,
        spellcasting_ability_key: str | None,
        spellcasting_ability_score: int | None,
    ):
        super().__init__()
        self.user = user
        self.race = race
        self.class_key = class_key
        self.background = background
        self.base_scores = base_scores
        self.selected_spells = selected_spells
        self.spell_slots = spell_slots
        self.spell_save_dc = spell_save_dc
        self.spell_attack_bonus = spell_attack_bonus
        self.spellcasting_ability_key = spellcasting_ability_key
        self.spellcasting_ability_score = spellcasting_ability_score
        self.nome = ui.TextInput(label="Nome / apelido na mesa", placeholder="Ex: Borin Oakfist", max_length=80, required=True)
        self.add_item(self.nome)

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("Inválido.", ephemeral=True)
        character_name = f"{self.user.id}_{self.user.name.lower()}"
        sheet = build_player_sheet(
            titulo_apelido=str(self.nome.value).strip(),
            race=self.race,
            class_key=self.class_key,
            background_key=self.background,
            base_scores_before_race=self.base_scores,
        )

        if self.selected_spells:
            sheet["magias"] = self.selected_spells
            sheet["spell_slots"] = self.spell_slots
            total_slots = sum(int(v.get("max", 0)) for v in self.spell_slots.values())
            sheet.setdefault("informacoes_combate", {})["magia_maxima"] = total_slots
            sheet.setdefault("informacoes_combate", {})["magia_atual"] = total_slots
            # armazena marcadores para cálculos de rolagens futuras
            sheet["spell_save_dc"] = self.spell_save_dc
            sheet["spell_attack_bonus"] = self.spell_attack_bonus
            sheet["spellcasting_ability_key"] = self.spellcasting_ability_key
            sheet["spellcasting_ability_score"] = self.spellcasting_ability_score

        player_utils.save_player_sheet(
            character_name,
            sheet,
            guild_id=interaction.guild.id if interaction.guild else None,
        )
        await interaction.response.send_message(
            f"✅ Ficha **{self.nome.value}** criada! Use `/minha_ficha` ou `/player_menu`.",
            ephemeral=True,
        )


_CASTING_ABILITY_KEY_BY_CLASS: dict[str, str] = {
    "Mago": "Inteligência",
    "Clérigo": "Sabedoria",
    "Bardo": "Carisma",
    "Bruxo": "Carisma",
    "Feiticeiro": "Carisma",
    "Druida": "Sabedoria",
    "Patrulheiro": "Sabedoria",
    "Paladino": "Carisma",
}

_DEFAULT_CANTRIPS_KNOWN_LVL1_BY_CLASS: dict[str, int] = {
    "Mago": 3,
    "Clérigo": 3,
    "Bardo": 3,
    "Bruxo": 2,
    "Feiticeiro": 4,
    "Druida": 3,
}

_DEFAULT_LVL1_SPELLS_BY_CLASS: dict[str, int] = {
    "Mago": 6,
    "Bardo": 4,
    "Bruxo": 2,
    "Feiticeiro": 2,
}


def _casting_mod_from_final_scores(class_key: str, final_scores: dict[str, int]) -> tuple[str, int]:
    ability_key = _CASTING_ABILITY_KEY_BY_CLASS.get(class_key)
    if not ability_key:
        return "Inteligência", rpg_rules.get_modifier("dnd", 10)
    score = int(final_scores.get(ability_key) or 10)
    mod = rpg_rules.get_modifier("dnd", score)
    return ability_key, mod


def _slots_lvl1_for_caster(class_key: str) -> dict[int, dict[str, int]]:
    # Versão inicial: como o /criar_ficha sempre cria no nível 1,
    # modelamos apenas os slots de 1º nível. Expansão futura: tabelas completas por nível.
    # Bruxo (pacto): 1 slot de 1º nível no nível 1 (pact magic).
    if class_key.strip().lower() == "bruxo":
        return {1: {"max": 1, "used": 0}}
    if spells_srd.get_open5e_spell_lists_for_class(class_key):
        return {1: {"max": 2, "used": 0}}
    return {}


class SpellCantripsPickView(ui.View):
    def __init__(
        self,
        user: discord.User,
        race: str,
        class_key: str,
        background: str,
        base_scores_before_race: dict[str, int],
        final_scores: dict[str, int],
    ):
        super().__init__(timeout=600)
        self.user = user
        self.race = race
        self.class_key = class_key
        self.background = background
        self.base_scores_before_race = base_scores_before_race
        self.final_scores = final_scores
        self.level = 1

        self.ability_key, self.casting_mod = _casting_mod_from_final_scores(class_key, final_scores)
        self.cantrips_known = _DEFAULT_CANTRIPS_KNOWN_LVL1_BY_CLASS.get(class_key, 3)

        all_cantrips = spells_srd.get_spells_by_level_for_class(class_key, 0)
        if not all_cantrips:
            self.cantrips_known = 0
        self.cantrips = all_cantrips
        opts = [discord.SelectOption(label=sp["nome"][:100], value=sp["slug"]) for sp in all_cantrips[:25]]

        self.selected_slugs: list[str] = []
        self.select = ui.Select(
            placeholder="Escolha seus truques",
            options=opts,
            min_values=self.cantrips_known,
            max_values=self.cantrips_known if self.cantrips_known > 0 else 1,
            row=0,
        )

        async def cb(interaction: discord.Interaction):
            if interaction.user.id != self.user.id:
                return await interaction.response.send_message("Não é sua ficha.", ephemeral=True)
            self.selected_slugs = list(self.select.values)
            await interaction.response.edit_message(embed=self._embed(), view=self)

        self.select.callback = cb
        self.add_item(self.select)

    def _embed(self) -> discord.Embed:
        emb = discord.Embed(title="🔮 Truques do grimório", color=discord.Color.teal())
        if not self.selected_slugs:
            emb.description = f"Selecione até **{self.cantrips_known}** truques."
            return emb
        picked = [sp for sp in self.cantrips if sp.get("slug") in self.selected_slugs]
        lines = []
        for sp in picked:
            lines.append(f"**{sp['nome']}** (Escolha: Truque)\n{sp['descricao'][:180]}{'…' if len(sp['descricao'])>180 else ''}")
        emb.description = "\n\n".join(lines)
        emb.set_footer(text=f"Quantidade escolhida: {len(self.selected_slugs)}/{self.cantrips_known}")
        return emb

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user.id

    async def on_timeout(self) -> None:
        for item in self.children:
            try:
                item.disabled = True
            except Exception:
                pass

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: ui.Item[Any]) -> None:
        await interaction.response.send_message("Erro ao selecionar truques.", ephemeral=True)

    @ui.button(label="✅ Confirmar truques", style=discord.ButtonStyle.success, row=1)
    async def confirm(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("Não é sua ficha.", ephemeral=True)
        if self.cantrips_known > 0 and len(self.selected_slugs) != self.cantrips_known:
            return await interaction.response.send_message(
                f"Você precisa escolher exatamente **{self.cantrips_known}** truques.",
                ephemeral=True,
            )
        await interaction.response.edit_message(
            embed=discord.Embed(title="⚡ Magias de 1º nível", description="Agora escolha suas magias de 1º nível.", color=discord.Color.blue()),
            view=SpellLevelPickView(
                user=self.user,
                race=self.race,
                class_key=self.class_key,
                background=self.background,
                base_scores_before_race=self.base_scores_before_race,
                final_scores=self.final_scores,
                selected_cantrips_slugs=self.selected_slugs,
            ),
        )


class SpellLevelPickView(ui.View):
    def __init__(
        self,
        user: discord.User,
        race: str,
        class_key: str,
        background: str,
        base_scores_before_race: dict[str, int],
        final_scores: dict[str, int],
        selected_cantrips_slugs: list[str],
    ):
        super().__init__(timeout=600)
        self.user = user
        self.race = race
        self.class_key = class_key
        self.background = background
        self.base_scores_before_race = base_scores_before_race
        self.final_scores = final_scores
        self.level = 1
        self.selected_cantrips_slugs = selected_cantrips_slugs

        self.ability_key, self.casting_mod = _casting_mod_from_final_scores(class_key, final_scores)
        self.lvl1_spells_known = _DEFAULT_LVL1_SPELLS_BY_CLASS.get(class_key)
        if self.lvl1_spells_known is None:
            # Para classes preparadoras simples: 1 + modificador (mínimo 1)
            self.lvl1_spells_known = max(1, 1 + self.casting_mod)

        self.lvl1_spells = spells_srd.get_spells_by_level_for_class(class_key, 1)
        opts = [discord.SelectOption(label=sp["nome"][:100], value=sp["slug"]) for sp in self.lvl1_spells[:25]]

        self.selected_lvl1_slugs: list[str] = []
        self.select = ui.Select(
            placeholder=f"Escolha {self.lvl1_spells_known} magias de 1º nível",
            options=opts,
            min_values=self.lvl1_spells_known,
            max_values=self.lvl1_spells_known,
            row=0,
        )

        async def cb(interaction: discord.Interaction):
            if interaction.user.id != self.user.id:
                return await interaction.response.send_message("Não é sua ficha.", ephemeral=True)
            self.selected_lvl1_slugs = list(self.select.values)
            await interaction.response.edit_message(embed=self._embed(), view=self)

        self.select.callback = cb
        self.add_item(self.select)

        save_button = ui.Button(label="✅ Confirmar magias", style=discord.ButtonStyle.success, row=1)
        self.add_item(save_button)

        async def _cb(interaction: discord.Interaction):
            if interaction.user.id != self.user.id:
                return await interaction.response.send_message("Não é sua ficha.", ephemeral=True)
            if len(self.selected_lvl1_slugs) != self.lvl1_spells_known:
                return await interaction.response.send_message(
                    f"Você precisa escolher exatamente **{self.lvl1_spells_known}** magias de 1º nível.",
                    ephemeral=True,
                )
            chosen_cantrips = [sp for sp in spells_srd.get_spells_by_level_for_class(self.class_key, 0) if sp.get("slug") in self.selected_cantrips_slugs]
            chosen_lvl1 = [sp for sp in self.lvl1_spells if sp.get("slug") in self.selected_lvl1_slugs]
            spell_book = chosen_cantrips + chosen_lvl1

            sheet_magias = []
            for sp in spell_book:
                sheet_magias.append(
                    {
                        "nome": sp["nome"],
                        "custo": sp["nivel"],
                        "alcance": sp["alcance"],
                        "duracao": sp["duracao"],
                        "efeito": sp["descricao"],
                        "nivel_int": sp.get("nivel_int", 0),
                    }
                )

            spell_slots = _slots_lvl1_for_caster(self.class_key)
            pb = rpg_rules.proficiency_bonus(self.level)
            dc = 8 + pb + self.casting_mod
            atk = pb + self.casting_mod

            await interaction.response.send_modal(
                FinalizeCharacterModal(
                    user=self.user,
                    race=self.race,
                    class_key=self.class_key,
                    background=self.background,
                    base_scores=self.base_scores_before_race,
                    selected_spells=sheet_magias,
                    spell_slots=spell_slots,
                    spell_save_dc=dc,
                    spell_attack_bonus=atk,
                    spellcasting_ability_key=self.ability_key,
                    spellcasting_ability_score=int(self.final_scores.get(self.ability_key) or 10),
                )
            )
        save_button.callback = _cb

    def _embed(self) -> discord.Embed:
        emb = discord.Embed(title="📖 Revisão das magias", color=discord.Color.purple())
        if not self.selected_lvl1_slugs:
            emb.description = f"Selecione **{self.lvl1_spells_known}** magias de 1º nível."
            return emb
        picked = [sp for sp in self.lvl1_spells if sp.get("slug") in self.selected_lvl1_slugs]
        lines = []
        for sp in picked:
            lines.append(f"**{sp['nome']}** (1º nível)\n{sp['descricao'][:220]}{'…' if len(sp['descricao'])>220 else ''}")
        emb.description = "\n\n".join(lines)
        emb.set_footer(text=f"Quantidade escolhida: {len(self.selected_lvl1_slugs)}/{self.lvl1_spells_known}")
        return emb

