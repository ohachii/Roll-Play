# Painel do Mestre, gerar NPC e utilitários de sessão (D&D 5e).
from __future__ import annotations

import logging
import re
import os

import discord
from discord import app_commands
from discord.ext import commands
from discord import ui
from dotenv import load_dotenv

from data import dnd5e_srd
from utils import dice_roller, mestre_utils, player_utils, rpg_rules
from utils.dnd_sheet_builder import build_npc_sheet
from utils.embed_utils import create_player_summary_embed
from utils.npc_utils import NPCContext

log = logging.getLogger("rpg-bot")


def _norm_bonus(expr: str) -> str:
    if not expr:
        return "0"
    return re.sub(r"(^|[^0-9a-zA-Z_])d(\d+)", r"\g<1>1d\2", expr.strip())


def _build_init_roll(bonus_raw: str) -> str:
    b = _norm_bonus((bonus_raw or "0").strip())
    if not b or b == "0":
        return "1d20"
    if b.startswith("+"):
        return f"1d20{b}"
    if b.startswith("-"):
        return f"1d20{b}"
    return f"1d20+{b}"


def _safe_npc_filename(name: str) -> str:
    s = re.sub(r'[\\/*?:"<>|]', "_", name.strip())[:60]
    return s or "npc"


class GenerateNPCModal(ui.Modal, title="Gerar NPC rápido"):
    def __init__(self, guild_id: int, mestre_id: int):
        super().__init__()
        self.guild_id = guild_id
        self.mestre_id = mestre_id
        self.nome = ui.TextInput(label="Nome (vazio = aleatório)", required=False, max_length=60)
        self.raca = ui.TextInput(label="Raça", default="Humano", max_length=40)
        self.classe = ui.TextInput(label="Classe", default="Guerreiro", max_length=40)
        self.dificuldade = ui.TextInput(label="Dificuldade", default="Fácil", max_length=20)
        self.tipo = ui.TextInput(label="Tipo SRD (opcional: Goblin, Orc...)", required=False, max_length=40)
        self.add_item(self.nome)
        self.add_item(self.raca)
        self.add_item(self.classe)
        self.add_item(self.dificuldade)
        self.add_item(self.tipo)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        nome = (self.nome.value or "").strip() or dnd5e_srd.random_npc_name()
        race = _match_key(self.raca.value, dnd5e_srd.RACES, "Humano")
        cls = _match_key(self.classe.value, dnd5e_srd.CLASSES, "Guerreiro")
        diff = self.dificuldade.value.strip() or "Fácil"
        tipo = (self.tipo.value or "").strip() or None
        if tipo and tipo not in dnd5e_srd.MONSTERS:
            tipo = None

        base_fn = _safe_npc_filename(nome)
        fn = base_fn
        ctx = NPCContext(self.guild_id, self.mestre_id, fn)
        n = 1
        while ctx.load():
            n += 1
            fn = f"{base_fn}_{n}"
            ctx = NPCContext(self.guild_id, self.mestre_id, fn)

        payload = build_npc_sheet(
            nome=nome,
            race=race,
            class_key=cls,
            difficulty=diff,
            monster_type=tipo,
        )
        ctx.save(payload)

        emb = _npc_embed(payload, fn)
        await interaction.followup.send(embed=emb, ephemeral=False)


def _match_key(raw: str, d: dict, default: str) -> str:
    t = raw.strip().lower()
    for k in d:
        if k.lower() == t:
            return k
    return default


def _npc_embed(npc: dict, file_slug: str) -> discord.Embed:
    ib = npc.get("informacoes_basicas", {})
    ix = npc.get("informacoes_extras", {})
    attrs = npc.get("atributos", {})
    line = " · ".join(f"{k[:3]} {attrs.get(k, '?')}" for k in dnd5e_srd.DND_ATTRIBUTES)
    emb = discord.Embed(
        title=f"🎭 {npc.get('nome', 'NPC')}",
        description=f"**{ib.get('raca_especie')}** {ib.get('classe_profissao')} · `{file_slug}.json`",
        color=discord.Color.dark_magenta(),
    )
    emb.add_field(name="Atributos", value=line, inline=False)
    comb = npc.get("informacoes_combate", {})
    emb.add_field(name="PV / CA", value=f"`{comb.get('vida_atual')}/{comb.get('vida_maxima')}` · CA `{comb.get('defesa')}`", inline=True)
    emb.add_field(name="Iniciativa (bônus)", value=f"`{comb.get('iniciativa', '0')}`", inline=True)
    pers = ix.get("personalidade_ia", "")
    if pers:
        emb.add_field(name="Sugestão de papel", value=pers, inline=False)
    if ix.get("vantagem_em_ts"):
        emb.set_footer(text="Difícil: considere vantagem em testes de resistência (efeito narrativo).")
    return emb


class MasterPanelView(ui.View):
    def __init__(self, guild: discord.Guild, gm: discord.abc.User):
        super().__init__(timeout=600)
        self.guild = guild
        self.gm = gm
        self.target_user: discord.Member | None = None

        # Seleciona o alvo para os botões de ajuste rápido.
        self.add_item(TargetPlayerSelect(self))

    @ui.button(label="🎲 Gerar NPC", style=discord.ButtonStyle.primary, row=2)
    async def gen_npc(self, interaction: discord.Interaction, button: ui.Button):
        if not mestre_utils.pode_painel_mestre(interaction.guild, interaction.user):
            return await interaction.response.send_message("Sem permissão.", ephemeral=True)
        await interaction.response.send_modal(GenerateNPCModal(interaction.guild_id, interaction.user.id))

    @ui.button(label="⚡ Iniciativa", style=discord.ButtonStyle.success, row=2)
    async def initiative(self, interaction: discord.Interaction, button: ui.Button):
        if not mestre_utils.pode_painel_mestre(interaction.guild, interaction.user):
            return await interaction.response.send_message("Sem permissão.", ephemeral=True)
        v = InitiativePanelView(self.guild.id, interaction.user.id)
        await interaction.response.send_message(
            "Selecione jogadores (e opcionalmente NPCs) e clique em **Rolar**.",
            view=v,
            ephemeral=True,
        )

    @ui.button(label="🌙 Descanso longo", style=discord.ButtonStyle.secondary, row=2)
    async def long_rest(self, interaction: discord.Interaction, button: ui.Button):
        if not mestre_utils.pode_painel_mestre(interaction.guild, interaction.user):
            return await interaction.response.send_message("Sem permissão.", ephemeral=True)
        v = LongRestView()
        await interaction.response.send_message(
            "Selecione os jogadores que completam descanso longo (PV e magia ao máximo, se preenchidos).",
            view=v,
            ephemeral=True,
        )

    @ui.button(label="➕ Adicionar Atributo", style=discord.ButtonStyle.success, row=3)
    async def add_attribute(self, interaction: discord.Interaction, button: ui.Button):
        if not mestre_utils.pode_painel_mestre(interaction.guild, interaction.user):
            return await interaction.response.send_message("Sem permissão.", ephemeral=True)
        if not self.target_user:
            return await interaction.response.send_message("Selecione um jogador alvo no dropdown acima.", ephemeral=True)
        await interaction.response.send_message("Escolha o atributo e confirme.", ephemeral=True, view=AttributeAdjustView(self.target_user, +1))

    @ui.button(label="➖ Remover Atributo", style=discord.ButtonStyle.secondary, row=3)
    async def remove_attribute(self, interaction: discord.Interaction, button: ui.Button):
        if not mestre_utils.pode_painel_mestre(interaction.guild, interaction.user):
            return await interaction.response.send_message("Sem permissão.", ephemeral=True)
        if not self.target_user:
            return await interaction.response.send_message("Selecione um jogador alvo no dropdown acima.", ephemeral=True)
        await interaction.response.send_message("Escolha o atributo e confirme.", ephemeral=True, view=AttributeAdjustView(self.target_user, -1))

    @ui.button(label="🗑️ Deletar Personagem", style=discord.ButtonStyle.danger, row=4)
    async def delete_character(self, interaction: discord.Interaction, button: ui.Button):
        if not mestre_utils.pode_painel_mestre(interaction.guild, interaction.user):
            return await interaction.response.send_message("Sem permissão.", ephemeral=True)
        if not self.target_user:
            return await interaction.response.send_message("Selecione um jogador alvo no dropdown acima.", ephemeral=True)
        await interaction.response.send_modal(DeleteCharacterModal(self.target_user, interaction.guild.id))


class TargetPlayerSelect(ui.UserSelect):
    def __init__(self, parent: MasterPanelView):
        super().__init__(placeholder="Jogador alvo (para ajustes)", min_values=1, max_values=1, row=0)
        self._parent = parent

    async def callback(self, interaction: discord.Interaction):
        self._parent.target_user = self.values[0]
        await interaction.response.defer(ephemeral=True)


class AttributeAdjustView(ui.View):
    def __init__(self, target_user: discord.Member, delta: int):
        super().__init__(timeout=180)
        self.target_user = target_user
        self.delta = delta

        attr_opts = [discord.SelectOption(label=a, value=a) for a in dnd5e_srd.DND_ATTRIBUTES]
        self.add_item(AttributeSelect(attr_opts, self))
        self.add_item(ConfirmAttributeAdjustButton(self))


class AttributeSelect(ui.Select):
    def __init__(self, options: list[discord.SelectOption], parent: AttributeAdjustView):
        super().__init__(placeholder="Selecione o atributo", options=options, row=0)
        self._parent = parent

    async def callback(self, interaction: discord.Interaction):
        self._parent.selected_attr = self.values[0]
        # Mantém a view sem recarregar; o mestre confirma no próximo botão.
        await interaction.response.defer(ephemeral=True)


class ConfirmAttributeAdjustButton(ui.Button):
    def __init__(self, parent: AttributeAdjustView):
        super().__init__(label="✅ Confirmar", style=discord.ButtonStyle.success, row=1)
        self._parent = parent

    async def callback(self, interaction: discord.Interaction):
        if not mestre_utils.pode_painel_mestre(interaction.guild, interaction.user):
            return await interaction.response.send_message("Sem permissão.", ephemeral=True)
        view: AttributeAdjustView = self._parent
        attr = getattr(view, "selected_attr", None)
        if not attr:
            return await interaction.response.send_message("Selecione um atributo primeiro.", ephemeral=True)

        user = view.target_user
        cn = f"{user.id}_{user.name.lower()}"
        ficha = player_utils.load_player_sheet(cn, guild_id=interaction.guild.id)
        if not ficha:
            return await interaction.response.send_message("Esse jogador não tem ficha para ajustar.", ephemeral=True)

        sistema = ficha.get("informacoes_basicas", {}).get("sistema_rpg", "dnd")
        if not dnd5e_srd.DND_ATTRIBUTES or not isinstance(ficha.get("atributos"), dict):
            return await interaction.response.send_message("Ficha inválida (atributos).", ephemeral=True)

        attrs = ficha["atributos"]
        old_raw = attrs.get(attr) or 10
        try:
            old = int(old_raw)
        except Exception:
            old = 10

        new = max(1, min(20, old + view.delta))
        attrs[attr] = str(new)

        # Recalcula campos derivados para D&D 5e (mínimo: AC e iniciativa).
        if rpg_rules.is_dnd_system(sistema):
            dex_score = int(attrs.get("Destreza", 10) or 10)
            dex_mod = rpg_rules.get_modifier("dnd", dex_score)
            combate = ficha.setdefault("informacoes_combate", {})
            combate["defesa"] = str(10 + dex_mod)
            combate["iniciativa"] = str(dex_mod)

            # Recalcula DC e bônus de ataque se estiverem marcados na ficha.
            casting_key = ficha.get("spellcasting_ability_key")
            casting_score = None
            if casting_key:
                casting_score = int(attrs.get(casting_key, attrs.get(casting_key.lower(), 10)) or 10)
            else:
                casting_key = ficha.get("spellcasting_ability_key")
                casting_score = int(ficha.get("spellcasting_ability_score") or 10)

            if casting_key and casting_score is not None:
                lvl = rpg_rules.parse_character_level(ficha)
                pb = rpg_rules.proficiency_bonus(lvl)
                mod = rpg_rules.get_modifier("dnd", casting_score)
                ficha["spellcasting_ability_score"] = casting_score
                ficha["spell_attack_bonus"] = pb + mod
                ficha["spell_save_dc"] = 8 + pb + mod

        player_utils.save_player_sheet(cn, ficha, guild_id=interaction.guild.id)

        emb = discord.Embed(
            title="🛠️ Atributo atualizado",
            description=f"{user.display_name}: **{attr}** {old} → {new}",
            color=discord.Color.green() if view.delta > 0 else discord.Color.orange(),
        )
        await interaction.response.send_message(embed=emb, ephemeral=True, view=MasterPanelView(interaction.guild, interaction.user))


class InitiativePanelView(ui.View):
    def __init__(self, guild_id: int, mestre_id: int):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.mestre_id = mestre_id
        self.picked_users: list[discord.Member] = []
        self.picked_npcs: list[str] = []
        self.add_item(InitiativeUserSelect(self))
        npc_names = NPCContext.list_npcs(guild_id, mestre_id)[:24]
        if npc_names:
            self.add_item(NPCInitiativeSelect(npc_names, self))
        self.add_item(RollInitiativeButton())


class InitiativeUserSelect(ui.UserSelect):
    def __init__(self, parent: InitiativePanelView):
        super().__init__(placeholder="Jogadores no combate", min_values=1, max_values=25, row=0)
        self._parent = parent

    async def callback(self, interaction: discord.Interaction):
        self._parent.picked_users = list(self.values)
        await interaction.response.defer(ephemeral=True)


class NPCInitiativeSelect(ui.Select):
    def __init__(self, names: list[str], parent: InitiativePanelView):
        super().__init__(
            placeholder="NPCs (opcional)",
            options=[discord.SelectOption(label=n[:100], value=n) for n in names],
            min_values=0,
            max_values=min(len(names), 25),
            row=1,
        )
        self._parent = parent

    async def callback(self, interaction: discord.Interaction):
        self._parent.picked_npcs = list(self.values)
        await interaction.response.defer(ephemeral=True)


class RollInitiativeButton(ui.Button):
    def __init__(self):
        super().__init__(label="Rolar iniciativa", style=discord.ButtonStyle.danger, row=2)

    async def callback(self, interaction: discord.Interaction):
        view: InitiativePanelView = self.view  # type: ignore
        users = view.picked_users
        npc_choices = view.picked_npcs
        if not users:
            return await interaction.response.send_message(
                "Selecione ao menos um jogador no menu acima e confirme (o menu grava ao escolher).",
                ephemeral=True,
            )
        await interaction.response.defer(ephemeral=True)
        linhas: list[tuple[int, str]] = []
        for u in users:
            cn = f"{u.id}_{u.name.lower()}"
            ficha = player_utils.load_player_sheet(cn, guild_id=view.guild_id)
            bonus = (ficha.get("informacoes_combate", {}) or {}).get("iniciativa") or "0"
            expr = _build_init_roll(str(bonus))
            total, _ = await dice_roller.roll_dice(expr)
            linhas.append((total, f"**{u.display_name}** (PJ): {total}"))
        for npc_name in npc_choices:
            ctx = NPCContext(view.guild_id, view.mestre_id, npc_name)
            data = ctx.load()
            bonus = (data.get("informacoes_combate", {}) or {}).get("iniciativa") or "0"
            expr = _build_init_roll(str(bonus))
            total, _ = await dice_roller.roll_dice(expr)
            linhas.append((total, f"**{npc_name}** (NPC): {total}"))
        linhas.sort(key=lambda x: -x[0])
        body = "\n".join(x[1] for x in linhas)
        emb = discord.Embed(title="⚡ Ordem de iniciativa", description=body, color=discord.Color.gold())
        await interaction.followup.send(embed=emb, ephemeral=False)


class LongRestView(ui.View):
    def __init__(self):
        super().__init__(timeout=300)
        self.targets: list[discord.Member] = []
        self.add_item(LongRestUserSelect(self))
        self.add_item(ApplyLongRestButton())


class LongRestUserSelect(ui.UserSelect):
    def __init__(self, parent: LongRestView):
        super().__init__(placeholder="Quem descansa?", min_values=1, max_values=25, row=0)
        self._parent = parent

    async def callback(self, interaction: discord.Interaction):
        self._parent.targets = list(self.values)
        await interaction.response.defer(ephemeral=True)


class ApplyLongRestButton(ui.Button):
    def __init__(self):
        super().__init__(label="Aplicar descanso longo", style=discord.ButtonStyle.success, row=1)

    async def callback(self, interaction: discord.Interaction):
        view: LongRestView = self.view  # type: ignore
        if not view.targets:
            return await interaction.response.send_message("Selecione jogadores no menu acima.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        ok = 0
        for u in view.targets:
            cn = f"{u.id}_{u.name.lower()}"
            data = player_utils.load_player_sheet(cn, guild_id=interaction.guild.id)
            if not data:
                continue
            c = data.setdefault("informacoes_combate", {})
            vm = c.get("vida_maxima")
            if vm is not None:
                c["vida_atual"] = vm
            # Slots de magia (por nível) — se existir na ficha
            spell_slots = data.get("spell_slots")
            if isinstance(spell_slots, dict) and spell_slots:
                total_slots = 0
                for slot_level, slot_data in spell_slots.items():
                    try:
                        sd = slot_data if isinstance(slot_data, dict) else {}
                        sd["used"] = 0
                        mx = int(sd.get("max", 0))
                        total_slots += mx
                        spell_slots[slot_level] = sd
                    except Exception:
                        continue
                c["magia_maxima"] = total_slots
                c["magia_atual"] = total_slots
            else:
                # Compat: fichas antigas com magia genérica
                mm = c.get("magia_maxima")
                if mm is not None:
                    c["magia_atual"] = mm
            player_utils.save_player_sheet(cn, data, guild_id=interaction.guild.id)
            ok += 1
        await interaction.followup.send(f"✅ Descanso longo aplicado em **{ok}** ficha(s).", ephemeral=True)


class ViewPlayerSummarySelect(ui.UserSelect):
    def __init__(self):
        super().__init__(placeholder="Ver resumo de ficha (Mestre)", min_values=1, max_values=1, row=1)

    async def callback(self, interaction: discord.Interaction):
        if not mestre_utils.pode_painel_mestre(interaction.guild, interaction.user):
            return await interaction.response.send_message("Sem permissão.", ephemeral=True)
        u = self.values[0]
        cn = f"{u.id}_{u.name.lower()}"
        if not player_utils.player_sheet_exists(cn, guild_id=interaction.guild.id):
            return await interaction.response.send_message("Este jogador não tem ficha.", ephemeral=True)
        data = player_utils.load_player_sheet(cn, guild_id=interaction.guild.id)
        emb = create_player_summary_embed(data, u)
        await interaction.response.send_message(embed=emb, ephemeral=True)


class DeleteCharacterModal(ui.Modal, title="Deletar personagem"):
    def __init__(self, target_user: discord.Member, guild_id: int):
        super().__init__()
        self.target_user = target_user
        self.guild_id = guild_id
        self.character_title = ui.TextInput(
            label="Título/Apelido da ficha",
            placeholder="Ex: Hachi, Borin Oakfist...",
            max_length=100,
            required=True,
        )
        self.add_item(self.character_title)

    async def on_submit(self, interaction: discord.Interaction):
        if not mestre_utils.pode_painel_mestre(interaction.guild, interaction.user):
            return await interaction.response.send_message("Sem permissão.", ephemeral=True)

        title = (self.character_title.value or "").strip()
        if not title:
            return await interaction.response.send_message("Nome inválido.", ephemeral=True)

        resolved_slug: str | None = None
        try:
            load_dotenv()
            supa_url = os.getenv("SUPABASE_URL")
            supa_key = os.getenv("SUPABASE_KEY")
            if not supa_url or not supa_key:
                return await interaction.response.send_message(
                    "SUPABASE_URL/SUPABASE_KEY não configuradas.",
                    ephemeral=True,
                )

            from supabase import create_client  # type: ignore

            supabase = create_client(supa_url, supa_key)
            rows_resp = (
                supabase.table("characters")
                .select("character_name, sheet_json")
                .eq("discord_user_id", self.target_user.id)
                .eq("guild_id", self.guild_id)
                .execute()
            )
            rows = getattr(rows_resp, "data", None) or []
            title_lower = title.lower()
            matches: list[str] = []
            for row in rows:
                slug = row.get("character_name")
                sheet = row.get("sheet_json") or {}
                nick = (sheet.get("informacoes_basicas") or {}).get("titulo_apelido", "")
                if not isinstance(slug, str):
                    continue
                if isinstance(nick, str) and nick.strip().lower() == title_lower:
                    matches.append(slug)

            if len(matches) == 1:
                resolved_slug = matches[0]
            elif len(matches) > 1:
                return await interaction.response.send_message(
                    "Há mais de uma ficha com esse título. Use um título único.",
                    ephemeral=True,
                )
        except Exception as e:
            log.exception("[gm_panel] erro no lookup de personagem")
            return await interaction.response.send_message(
                f"Erro ao buscar personagem no Supabase: {e}",
                ephemeral=True,
            )

        if not resolved_slug:
            return await interaction.response.send_message(
                "Não encontrei ficha com esse Título/Apelido para o jogador selecionado.",
                ephemeral=True,
            )

        try:
            supabase.table("characters").delete().eq("character_name", resolved_slug).eq(
                "discord_user_id", self.target_user.id
            ).eq("guild_id", self.guild_id).execute()
        except Exception as e:
            log.exception("[gm_panel] erro ao deletar personagem")
            return await interaction.response.send_message(
                f"Erro ao deletar no Supabase: {e}",
                ephemeral=True,
            )

        await interaction.response.send_message(
            f"🗑️ Personagem **{resolved_slug}** (título: **{title}**) deletado com sucesso.",
            ephemeral=True,
        )


def _tr(key: str, locale: str, fallback: str, **kwargs) -> str:
    try:
        from utils.i18n import t as t_raw
        text = t_raw(key, locale, **kwargs)
        if text != key:
            return text
    except Exception:
        pass
    return fallback.format(**kwargs) if kwargs else fallback


def localized_command(name_pt, desc_pt, name_en, desc_en):
    def decorator(func):
        cmd = app_commands.command(name=name_pt, description=desc_pt)(func)
        cmd.name_localizations = {"en-US": name_en, "en-GB": name_en}
        cmd.description_localizations = {"en-US": desc_en, "en-GB": desc_en}
        return cmd
    return decorator


class GMPanelCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @localized_command(
        name_pt="painel_mestre",
        desc_pt="Painel do Mestre: NPCs, iniciativa, descanso e fichas.",
        name_en="gm_panel",
        desc_en="GM panel: NPCs, initiative, long rest, and sheets.",
    )
    async def painel_mestre(self, interaction: discord.Interaction):
        from utils.locale_resolver import resolve_locale
        loc = resolve_locale(interaction, fallback="pt")
        if interaction.guild is None:
            msg = _tr("admin.guild_only", loc, "❌ Use em um servidor.")
            return await interaction.response.send_message(msg, ephemeral=True)
        if not mestre_utils.pode_painel_mestre(interaction.guild, interaction.user):
            return await interaction.response.send_message(
                "❌ Apenas Mestres registrados, cargo **Mestre** ou administradores.", ephemeral=True
            )
        v = MasterPanelView(interaction.guild, interaction.user)
        v.add_item(ViewPlayerSummarySelect())
        emb = discord.Embed(
            title="👑 Painel do Mestre",
            description="Use os botões abaixo. **Ver ficha:** menu de jogador.",
            color=discord.Color.gold(),
        )
        await interaction.response.send_message(embed=emb, view=v, ephemeral=True)

    @app_commands.command(name="gerar_npc", description="Gera NPC D&D 5e (Mestre) e salva na sua pasta de NPCs.")
    @app_commands.describe(
        raca="Raça (ex: Humano, Elfo)",
        classe="Classe (ex: Guerreiro)",
        dificuldade="Fácil, Médio ou Difícil",
        tipo="Opcional: Goblin, Orc, Guarda (usa base SRD)",
        nome="Nome do NPC (opcional)",
    )
    async def gerar_npc(
        self,
        interaction: discord.Interaction,
        raca: str,
        classe: str,
        dificuldade: str,
        tipo: str | None = None,
        nome: str | None = None,
    ):
        if interaction.guild is None:
            return await interaction.response.send_message("Use em um servidor.", ephemeral=True)
        if not mestre_utils.pode_painel_mestre(interaction.guild, interaction.user):
            return await interaction.response.send_message("Sem permissão.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        race = _match_key(raca, dnd5e_srd.RACES, "Humano")
        cls = _match_key(classe, dnd5e_srd.CLASSES, "Guerreiro")
        ttipo = (tipo or "").strip() or None
        if ttipo and ttipo not in dnd5e_srd.MONSTERS:
            ttipo = None
        nom = (nome or "").strip() or dnd5e_srd.random_npc_name()
        base_fn = _safe_npc_filename(nom)
        fn = base_fn
        ctx = NPCContext(interaction.guild_id, interaction.user.id, fn)
        n = 1
        while ctx.load():
            n += 1
            fn = f"{base_fn}_{n}"
            ctx = NPCContext(interaction.guild_id, interaction.user.id, fn)
        payload = build_npc_sheet(
            nome=nom,
            race=race,
            class_key=cls,
            difficulty=dificuldade,
            monster_type=ttipo,
        )
        ctx.save(payload)
        emb = _npc_embed(payload, fn)
        await interaction.followup.send(embed=emb, ephemeral=False)


async def setup(bot: commands.Bot):
    await bot.add_cog(GMPanelCog(bot))
