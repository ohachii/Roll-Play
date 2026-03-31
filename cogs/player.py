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

import discord
from discord.ext import commands
from discord import app_commands
from utils import player_utils, mestre_utils
from utils.i18n import t as t_raw
from utils.locale_resolver import resolve_locale
from view.ficha_player.ficha_player_menu import PlayerMainMenuView
from view.ficha_player.personal_sheet_view import PersonalSheetView
from utils.embed_utils import create_player_summary_embed
from models.shared_models.add_pet_modal import AddPetModal
from view.pet_view.npc_pet_selector_view import NPCPetSelectorView
from view.character_creation.character_creator_view import CreatorRaceClassView
from utils import rpg_rules

def _tr(key: str, locale: str, fallback: str, **kwargs) -> str:
    try:
        text = t_raw(key, locale, **kwargs)
    except Exception:
        return fallback.format(**kwargs) if kwargs else fallback
    if text == key:
        return fallback.format(**kwargs) if kwargs else fallback
    return text

def localized_command(name_pt, desc_pt, name_en, desc_en):
    def decorator(func):
        cmd = app_commands.command(name=name_pt, description=desc_pt)(func)
        cmd.name_localizations = {"en-US": name_en, "en-GB": name_en}
        cmd.description_localizations = {"en-US": desc_en, "en-GB": desc_en}
        return cmd
    return decorator

class PlayerCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @localized_command(
        name_pt="upar_nivel",
        desc_pt="Aplicar level up automático na sua ficha D&D 5e.",
        name_en="level_up",
        desc_en="Apply automatic D&D 5e level up to your sheet.",
    )
    @app_commands.describe(novo_nivel="Novo nível de personagem (1–20).")
    async def upar_nivel(self, interaction: discord.Interaction, novo_nivel: int):
        loc = resolve_locale(interaction, fallback="pt")
        await interaction.response.defer(ephemeral=True)

        if interaction.guild is None:
            return await interaction.followup.send(
                "❌ Este comando só pode ser usado em um servidor.",
                ephemeral=True,
            )

        character_name = f"{interaction.user.id}_{interaction.user.name.lower()}"
        gid = interaction.guild.id
        if not player_utils.player_sheet_exists(character_name, guild_id=gid):
            msg = _tr(
                "player.sheet.missing",
                loc,
                "❌ Você ainda não tem uma ficha! Use `/criar_ficha` primeiro.",
            )
            return await interaction.followup.send(msg, ephemeral=True)

        ficha = player_utils.load_player_sheet(character_name, guild_id=gid)
        old_level = rpg_rules.parse_character_level(ficha)
        novo_nivel = max(1, min(20, int(novo_nivel)))
        if novo_nivel <= old_level:
            return await interaction.followup.send(
                f"⚠️ O nível informado ({novo_nivel}) não é maior que o atual ({old_level}).",
                ephemeral=True,
            )

        # Teto de atributo por campanha (default 20).
        campaign = (ficha.get("campaign_settings") or {})
        attr_cap = int(campaign.get("dnd_attr_cap") or 20)

        # ASI em níveis 4, 8, 12, 16, 19 (se atravessar um desses, abre modal).
        asi_levels = {4, 8, 12, 16, 19}
        needs_asi = any(lvl in asi_levels for lvl in range(old_level + 1, novo_nivel + 1))

        # Primeiro aplica avanço “seco” (HP e nível).
        from utils.dnd_sheet_builder import starting_hp  # type: ignore

        criacao = ficha.get("criacao_dnd") or {}
        dd = str(criacao.get("dado_vida_classe") or "").strip().lower()
        hit_die = 8
        if dd.startswith("d") and dd[1:].isdigit():
            hit_die = int(dd[1:])

        ficha_before_hp = dict(ficha)
        ficha = rpg_rules.advance_level(ficha, novo_nivel, hit_die=hit_die)
        ficha = rpg_rules.update_class_resources(ficha)

        # ASI: se necessário, abrimos modal para distribuir +2 em atributos e, em seguida,
        # um seletor de perícias extras quando aplicável.
        if needs_asi:
            attrs = ficha.setdefault("atributos", {})
            pericias = ficha.setdefault("pericias", {})

            class ASIModal(discord.ui.Modal, title="Melhoria de Atributo (ASI)"):
                def __init__(self):
                    super().__init__()
                    self.forca = discord.ui.TextInput(
                        label="Força (delta)",
                        placeholder="Ex: 0, 1 ou 2",
                        required=False,
                        max_length=2,
                        default="0",
                    )
                    self.destreza = discord.ui.TextInput(
                        label="Destreza (delta)",
                        placeholder="Ex: 0, 1 ou 2",
                        required=False,
                        max_length=2,
                        default="0",
                    )
                    self.constituicao = discord.ui.TextInput(
                        label="Constituição (delta)",
                        placeholder="Ex: 0, 1 ou 2",
                        required=False,
                        max_length=2,
                        default="0",
                    )
                    self.inteligencia = discord.ui.TextInput(
                        label="Inteligência (delta)",
                        placeholder="Ex: 0, 1 ou 2",
                        required=False,
                        max_length=2,
                        default="0",
                    )
                    self.sabedoria = discord.ui.TextInput(
                        label="Sabedoria (delta)",
                        placeholder="Ex: 0, 1 ou 2",
                        required=False,
                        max_length=2,
                        default="0",
                    )
                    self.carisma = discord.ui.TextInput(
                        label="Carisma (delta)",
                        placeholder="Ex: 0, 1 ou 2",
                        required=False,
                        max_length=2,
                        default="0",
                    )
                    for field in (
                        self.forca,
                        self.destreza,
                        self.constituicao,
                        self.inteligencia,
                        self.sabedoria,
                        self.carisma,
                    ):
                        self.add_item(field)

                async def on_submit(self, modal_inter: discord.Interaction):
                    if modal_inter.user.id != interaction.user.id:
                        return await modal_inter.response.send_message("Não é sua ficha.", ephemeral=True)
                    await modal_inter.response.defer(ephemeral=True)

                    deltas = {}
                    total = 0
                    mapping = {
                        "Força": self.forca,
                        "Destreza": self.destreza,
                        "Constituição": self.constituicao,
                        "Inteligência": self.inteligencia,
                        "Sabedoria": self.sabedoria,
                        "Carisma": self.carisma,
                    }
                    for name, field in mapping.items():
                        raw = (field.value or "0").strip()
                        if not raw:
                            raw = "0"
                        try:
                            dv = int(raw)
                        except ValueError:
                            return await modal_inter.followup.send(
                                f"❌ Valor inválido para {name}: use inteiros (ex: 0, 1 ou 2).",
                                ephemeral=True,
                            )
                        deltas[name] = dv
                        total += dv

                    if total != 2:
                        return await modal_inter.followup.send(
                            "❌ A soma das melhorias deve ser exatamente **2 pontos** (ex: +2 em um atributo ou +1/+1).",
                            ephemeral=True,
                        )

                    # Aplica deltas com teto de atributo.
                    for name, dv in deltas.items():
                        if dv == 0:
                            continue
                        cur_raw = attrs.get(name) or 10
                        try:
                            cur = int(cur_raw)
                        except (TypeError, ValueError):
                            cur = 10
                        new_val = cur + dv
                        if new_val > attr_cap:
                            return await modal_inter.followup.send(
                                f"❌ {name} não pode ultrapassar o teto de **{attr_cap}**.",
                                ephemeral=True,
                            )
                        attrs[name] = new_val

                    # Reatividade em cascata: CA, iniciativa, perícias e HP retroativo se CON subir.
                    dex = int(attrs.get("Destreza") or attrs.get("destreza") or 10)
                    con_before = int((ficha_before_hp.get("atributos") or {}).get("Constituição") or 10)
                    con_after = int(attrs.get("Constituição") or attrs.get("constituicao") or 10)
                    wis = int(attrs.get("Sabedoria") or attrs.get("sabedoria") or 10)

                    info_combate = ficha.setdefault("informacoes_combate", {})
                    # CA: considera armadura sem armadura para Bárbaro/Monge (simplificado).
                    cls_name = str((ficha.get("informacoes_basicas") or {}).get("classe_profissao") or "").strip().lower()
                    ac_base = 10 + rpg_rules.calculate_modifier(dex)
                    if cls_name == "bárbaro" or cls_name == "barbaro":
                        ac_base = 10 + max(0, rpg_rules.calculate_modifier(dex)) + max(
                            0, rpg_rules.calculate_modifier(con_after)
                        )
                    elif cls_name == "monge":
                        ac_base = 10 + max(0, rpg_rules.calculate_modifier(dex)) + max(
                            0, rpg_rules.calculate_modifier(wis)
                        )
                    info_combate["defesa"] = str(ac_base)
                    info_combate["iniciativa"] = str(rpg_rules.calculate_modifier(dex))

                    # HP retroativo se Constituição aumentou.
                    if con_after > con_before:
                        extra_mod = rpg_rules.calculate_modifier(con_after) - rpg_rules.calculate_modifier(con_before)
                        gained_levels = max(1, novo_nivel)  # total de níveis conta para retroativo
                        try:
                            hp_max = int(info_combate.get("vida_maxima") or 0)
                        except (TypeError, ValueError):
                            hp_max = 0
                        hp_max += extra_mod * gained_levels
                        info_combate["vida_maxima"] = max(hp_max, info_combate.get("vida_atual") or 0)

                    # Atualiza recursos de classe após ASI (por exemplo, Monge/Bruxo).
                    ficha = rpg_rules.update_class_resources(ficha)
                    # Salva ficha atualizada em Supabase/arquivo.
                    player_utils.save_player_sheet(character_name, ficha, guild_id=gid)

                    # Seletor de perícias extras (ex.: Bardo em certos níveis, subclasses).
                    # Para simplificar, assumimos que todas as classes permitem 1 perícia extra
                    # quando `campaign_settings.dnd_extra_skill_on_level_up` estiver habilitado.
                    extra_skill_flag = (ficha.get("campaign_settings") or {}).get(
                        "dnd_extra_skill_on_level_up", False
                    )
                    if extra_skill_flag:
                        from data import dnd5e_srd as dnd_data  # type: ignore

                        cls_name = str(
                            (ficha.get("informacoes_basicas") or {}).get("classe_profissao") or ""
                        ).strip()
                        cls_cfg = dnd_data.CLASSES.get(cls_name, {})
                        pool = list(cls_cfg.get("skill_choices") or [])
                        owned = set(pericias.keys())
                        candidates = [s for s in pool if s not in owned]

                        if candidates:
                            class ExtraSkillSelect(discord.ui.View):
                                def __init__(self, user: discord.User):
                                    super().__init__(timeout=180)
                                    self.user = user
                                    options = [
                                        discord.SelectOption(label=s, value=s) for s in candidates[:25]
                                    ]
                                    self.select = discord.ui.Select(
                                        placeholder="Escolha uma nova perícia para ganhar proficiência",
                                        min_values=1,
                                        max_values=1,
                                        options=options,
                                    )
                                    self.select.callback = self._on_select  # type: ignore
                                    self.add_item(self.select)

                                async def interaction_check(
                                    self, i: discord.Interaction
                                ) -> bool:
                                    return i.user.id == self.user.id

                                async def _on_select(self, i: discord.Interaction):
                                    choice = self.select.values[0]
                                    if choice in pericias:
                                        return await i.response.send_message(
                                            "Você já possui essa perícia.", ephemeral=True
                                        )
                                    from data import dnd5e_srd as dnd_data2  # type: ignore

                                    ab = dnd_data2.SKILL_TO_ATTR.get(choice, "Destreza")
                                    pericias[choice] = {
                                        "atributo_base": ab,
                                        "bonus": 0,
                                        "proficiencia_dnd": "proficiente",
                                    }
                                    player_utils.save_player_sheet(
                                        character_name, ficha, guild_id=gid
                                    )
                                    await i.response.edit_message(
                                        content=f"✅ Perícia extra adquirida: **{choice}**.",
                                        view=None,
                                    )

                            view = ExtraSkillSelect(interaction.user)
                            await modal_inter.followup.send(
                                "📚 Você pode escolher **1 nova perícia** de classe:",
                                view=view,
                                ephemeral=True,
                            )

                    # Embed comemorativo.
                    pb = rpg_rules.proficiency_bonus(novo_nivel)
                    emb = discord.Embed(
                        title=f"🆙 Nível {novo_nivel} atingido!",
                        description=(
                            f"PV Máximo atual: **{info_combate.get('vida_maxima')}**\n"
                            f"Bônus de Proficiência: **+{pb}**"
                        ),
                        color=discord.Color.green(),
                    )
                    emb.add_field(
                        name="Melhorias de atributo",
                        value=", ".join(
                            f"{k} {('+' + str(v)) if v >= 0 else v}"
                            for k, v in deltas.items()
                            if v
                        ),
                        inline=False,
                    )
                    await modal_inter.followup.send(embed=emb, ephemeral=True)

            modal = ASIModal()
            await interaction.followup.send(
                "✨ Você ganhou uma **Melhoria de Atributo**. Preencha os deltas abaixo:",
                ephemeral=True,
            )
            await interaction.followup.send_modal(modal)
            return

        # Caso não haja ASI no intervalo, apenas salva e mostra resumo simples.
        ficha = rpg_rules.update_class_resources(ficha)
        player_utils.save_player_sheet(character_name, ficha, guild_id=gid)
        pb = rpg_rules.proficiency_bonus(novo_nivel)
        info_combate = ficha.get("informacoes_combate") or {}
        emb = discord.Embed(
            title=f"🆙 Nível {novo_nivel} atingido!",
            description=(
                f"PV Máximo atual: **{info_combate.get('vida_maxima')}**\n"
                f"Bônus de Proficiência: **+{pb}**"
            ),
            color=discord.Color.green(),
        )
        await interaction.followup.send(embed=emb, ephemeral=True)

    @localized_command(
        name_pt="criar_ficha",
        desc_pt="Assistente D&D 5e: raça, classe, 4d6 (3 chances) e distribuição de atributos.",
        name_en="create_sheet",
        desc_en="D&D 5e wizard: race, class, 4d6×3 rolls and assign stats.",
    )
    @app_commands.describe(sobrescrever="Se já existir ficha, substitui pela nova.")
    async def criar_ficha(self, interaction: discord.Interaction, sobrescrever: bool = False):
        loc = resolve_locale(interaction, fallback="pt")
        character_name = f"{interaction.user.id}_{interaction.user.name.lower()}"
        gid = interaction.guild.id if interaction.guild else None
        if player_utils.player_sheet_exists(character_name, guild_id=gid) and not sobrescrever:
            msg = _tr(
                "player.create.exists",
                loc,
                "❌ Você já tem uma ficha. Use `sobrescrever: Sim` para refazer do zero.",
            )
            return await interaction.response.send_message(msg, ephemeral=True)
        emb = discord.Embed(
            title="📜 Criação de personagem (D&D 5e)",
            description=(
                "1) Escolha **raça**, **classe** e **antecedente**.\n"
                "2) **Rolagem:** 4d6 descartando o menor, **3 conjuntos** (2 rerrolagens).\n"
                "3) **Distribua** cada valor a um atributo; depois informe o **nome**.\n"
                "Os bônus raciais são aplicados automaticamente."
            ),
            color=discord.Color.green(),
        )
        view = CreatorRaceClassView(interaction.user, sobrescrever=sobrescrever)
        await interaction.response.send_message(embed=emb, view=view, ephemeral=True)

    @localized_command(
        name_pt="player_menu", desc_pt="Abrir o menu do player",
        name_en="player_menu", desc_en="Open the player menu"
    )
    async def player_menu(self, interaction: discord.Interaction):
        loc = resolve_locale(interaction, fallback="pt")
        title = _tr("player.menu.main.title", loc, "🎮 Menu Principal do Player")
        await interaction.response.send_message(
            content=title,
            view=PlayerMainMenuView(user=interaction.user),
            ephemeral=True
        )

    @localized_command(
        name_pt="minha_ficha", desc_pt="Exibe sua ficha de personagem interativa.",
        name_en="my_sheet", desc_en="Show your interactive character sheet."
    )
    async def minha_ficha(self, interaction: discord.Interaction):
        loc = resolve_locale(interaction, fallback="pt")
        character_name = f"{interaction.user.id}_{interaction.user.name.lower()}"
        gid = interaction.guild.id if interaction.guild else None
        if not player_utils.player_sheet_exists(character_name, guild_id=gid):
            msg = _tr("player.sheet.missing", loc, "❌ Você ainda não tem uma ficha! Use `/player_menu` para começar.")
            return await interaction.response.send_message(msg, ephemeral=True)
        view = PersonalSheetView(user=interaction.user, guild_id=gid)
        initial = await view.create_embed()
        await interaction.response.send_message(embed=initial, view=view, ephemeral=True)

    @localized_command(
        name_pt="ficha",
        desc_pt="Escolhe qual ficha do seu arquivo carregar (se houver mais de uma).",
        name_en="sheet",
        desc_en="Pick which character sheet file to open.",
    )
    async def ficha(self, interaction: discord.Interaction):
        loc = resolve_locale(interaction, fallback="pt")
        gid = interaction.guild.id if interaction.guild else None
        slugs = player_utils.list_player_sheet_slugs_for_user(interaction.user.id, guild_id=gid)
        if not slugs:
            msg = _tr("player.sheet.none", loc, "❌ Você ainda não tem fichas. Use `/criar_ficha` primeiro.")
            return await interaction.response.send_message(msg, ephemeral=True)

        entries: list[tuple[str, str]] = []
        for slug in slugs[:10]:
            try:
                data = player_utils.load_player_sheet(slug, guild_id=interaction.guild.id if interaction.guild else None)
                title = data.get("informacoes_basicas", {}).get("titulo_apelido") or slug
                entries.append((slug, str(title)))
            except Exception:
                entries.append((slug, slug))

        class SheetPickView(discord.ui.View):
            def __init__(self, user: discord.User, items: list[tuple[str, str]]):
                super().__init__(timeout=180)
                self._user = user
                self._items = items

                for i, (_slug, label) in enumerate(items):
                    btn = discord.ui.Button(
                        label=f"📄 Ficha: {label[:20]}",
                        style=discord.ButtonStyle.primary,
                        custom_id=f"player:sheet:pick:{i}",
                        row=0 if i < 2 else 1,
                    )

                    async def _cb(btn_interaction: discord.Interaction, idx: int = i):
                        if btn_interaction.user.id != self._user.id:
                            return await btn_interaction.response.send_message("Não é sua ficha.", ephemeral=True)
                        char_name, _ = self._items[idx]
                        view = PersonalSheetView(
                            user=self._user,
                            character_name=char_name,
                            guild_id=btn_interaction.guild.id if btn_interaction.guild else None,
                        )
                        embed = await view.create_embed()
                        await btn_interaction.response.edit_message(embed=embed, view=view, content=None)

                    btn.callback = _cb
                    self.add_item(btn)

        view = SheetPickView(interaction.user, entries)
        await interaction.response.send_message(
            content=_tr("player.sheet.pick.prompt", loc, "Selecione qual ficha abrir:"),
            view=view,
            ephemeral=True,
        )

    @localized_command(
        name_pt="ver_player", desc_pt="Exibe a ficha de um jogador.",
        name_en="view_player", desc_en="Show a player's sheet."
    )
    @app_commands.describe(jogador="Jogador alvo / Target player")
    async def ver_player(self, interaction: discord.Interaction, jogador: discord.Member):
        loc = resolve_locale(interaction, fallback="pt")
        character_name = f"{jogador.id}_{jogador.name.lower()}"
        gid = interaction.guild.id if interaction.guild else None
        if not player_utils.player_sheet_exists(character_name, guild_id=gid):
            msg = _tr("player.sheet.other_missing", loc, "❌ O jogador **{name}** ainda não possui uma ficha.",
                      name=jogador.display_name)
            return await interaction.response.send_message(msg, ephemeral=True)

        if mestre_utils.verificar_mestre(interaction.guild.name, interaction.user.id):
            view = PersonalSheetView(
                user=jogador,
                character_name=character_name,
                guild_id=interaction.guild.id if interaction.guild else None,
            )
            embed = await view.create_embed()
            header = _tr("player.sheet.master_view", loc, "👁️ Visão de Mestre: Ficha completa de **{name}**",
                         name=jogador.display_name)
            await interaction.response.send_message(header, embed=embed, view=view, ephemeral=True)
        else:
            ps = player_utils.load_player_sheet(character_name, guild_id=interaction.guild.id if interaction.guild else None)
            embed = create_player_summary_embed(ps, jogador)
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @localized_command(
        name_pt="registrar_pet", desc_pt="Registra um novo pet para seu personagem ou para um NPC.",
        name_en="register_pet", desc_en="Register a new pet for your character or an NPC."
    )
    async def registrar_pet(self, interaction: discord.Interaction):
        loc = resolve_locale(interaction, fallback="pt")
        guild_name = interaction.guild.name
        user_id = interaction.user.id

        if mestre_utils.verificar_mestre(guild_name, user_id):
            view = NPCPetSelectorView(interaction.guild_id, user_id)
            msg = _tr("pet.master.prompt", loc, "Você é um mestre. Selecione um NPC para registrar um pet para ele:")
            await interaction.response.send_message(msg, view=view, ephemeral=True)
            return

        modal = AddPetModal()
        await interaction.response.send_modal(modal)
        await modal.wait()
        if modal.pet_data:
            character_name = f"{user_id}_{interaction.user.name.lower()}"
            player_sheet = player_utils.load_player_sheet(character_name, guild_id=interaction.guild.id if interaction.guild else None)
            pets_list = player_sheet.setdefault("pets", [])
            pets_list.append(modal.pet_data)
            player_utils.save_player_sheet(character_name, player_sheet, guild_id=interaction.guild.id if interaction.guild else None)
            msg = _tr("pet.player.saved", loc, "🐾 Pet **{pet}** foi registrado para seu personagem!",
                      pet=modal.pet_data['nome'])
            await interaction.followup.send(msg, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(PlayerCog(bot))
