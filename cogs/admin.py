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
from utils.checks import is_app_owner
from utils.i18n import t as t_raw
from utils.locale_resolver import resolve_locale
from utils import mestre_utils
from utils import content_templates

def _tr(key: str, locale: str, fallback: str, **kwargs) -> str:
    try:
        text = t_raw(key, locale, **kwargs)
    except Exception:
        return fallback.format(**kwargs) if kwargs else fallback
    if text == key:
        try:
            return fallback.format(**kwargs) if kwargs else fallback
        except Exception:
            return fallback
    return text

def localized_command(name_pt, desc_pt, name_en, desc_en):
    def decorator(func):
        cmd = app_commands.command(name=name_pt, description=desc_pt)(func)
        cmd.name_localizations = {"en-US": name_en, "en-GB": name_en}
        cmd.description_localizations = {"en-US": desc_en, "en-GB": desc_en}
        return cmd
    return decorator


class AdminCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @localized_command(
        name_pt="virar_mestre", desc_pt="Cria/atribui o cargo de Mestre e registra você como Mestre no servidor.",
        name_en="become_gm", desc_en="Create/assign the GM role and register you as a GM on this server."
    )
    async def virar_mestre(self, interaction: discord.Interaction):
        loc = resolve_locale(interaction, fallback="pt")
        guild: discord.Guild | None = interaction.guild

        if guild is None:
            msg = _tr("admin.guild_only", loc, "❌ Este comando só pode ser usado em um servidor.")
            return await interaction.response.send_message(msg, ephemeral=True)

        if mestre_utils.verificar_mestre(guild.name, interaction.user.id):
            msg = _tr("admin.already_gm", loc, "✅ Você já é Mestre neste servidor.")
            return await interaction.response.send_message(msg, ephemeral=True)

        role_name = _tr("admin.role.name", loc, "Mestre")
        mestre_role: discord.Role | None = discord.utils.get(guild.roles, name=role_name)

        created_role = False
        if mestre_role is None:
            try:
                mestre_role = await guild.create_role(
                    name=role_name,
                    mentionable=True,
                    color=discord.Color.orange()
                )
                created_role = True
            except discord.Forbidden:
                msg = _tr("admin.role.create.forbidden", loc,
                          "❌ Não tenho permissão para criar o cargo **{role}**. Verifique minhas permissões.",
                          role=role_name)
                return await interaction.response.send_message(msg, ephemeral=True)
            except discord.HTTPException:
                msg = _tr("admin.role.create.http", loc,
                          "❌ Ocorreu um erro ao criar o cargo **{role}**.", role=role_name)
                return await interaction.response.send_message(msg, ephemeral=True)

        try:
            await interaction.user.add_roles(mestre_role, reason="Become GM command")
        except discord.Forbidden:
            msg = _tr("admin.role.assign.forbidden", loc,
                      "❌ Não consegui atribuir o cargo **{role}**. "
                      "Coloque meu cargo acima do cargo de Mestre.", role=role_name)
            return await interaction.response.send_message(msg, ephemeral=True)
        except discord.HTTPException:
            msg = _tr("admin.role.assign.http", loc,
                      "❌ Ocorreu um erro ao atribuir o cargo **{role}**.", role=role_name)
            return await interaction.response.send_message(msg, ephemeral=True)

        try:
            mestre_utils.registrar_mestre(guild.name, interaction.user.id, interaction.user.display_name)
        except Exception:
            warn = _tr("admin.register.warn", loc,
                       "⚠️ Cargo atribuído, mas houve um problema ao registrar você como Mestre internamente.")
            await interaction.response.send_message(warn, ephemeral=True)
            return

        # Sucesso
        created_txt = _tr("admin.role.created.suffix", loc, " (cargo criado)") if created_role else ""
        msg = _tr("admin.success", loc,
                  "✅ Você agora é Mestre neste servidor{created}. Use `/npc_menu` para gerenciar seus NPCs.",
                  created=created_txt)
        await interaction.response.send_message(msg, ephemeral=True)

    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.command(
        name="admin_conteudo",
        description="Gerenciar templates de Raças, Classes e Origens (homebrew/SRD).",
    )
    async def admin_conteudo(self, interaction: discord.Interaction):
        """Abre painel de gerenciamento de conteúdo SRD/Homebrew."""
        loc = resolve_locale(interaction, fallback="pt")
        if interaction.guild is None:
            msg = _tr(
                "admin.content.guild_only",
                loc,
                "❌ Este painel só pode ser usado dentro de um servidor.",
            )
            return await interaction.response.send_message(msg, ephemeral=True)

        class ContentAdminView(discord.ui.View):
            def __init__(self, user: discord.User):
                super().__init__(timeout=300)
                self.user = user

            async def interaction_check(self, i: discord.Interaction) -> bool:
                return i.user.id == self.user.id

        view = ContentAdminView(interaction.user)

        @discord.ui.button(label="+ Nova Raça", style=discord.ButtonStyle.primary, row=0)
        async def new_race_button(btn_inter: discord.Interaction, button: discord.ui.Button):  # type: ignore[override]
            if btn_inter.user.id != interaction.user.id:
                return await btn_inter.response.send_message("Não é seu painel.", ephemeral=True)

            class NewRaceModal(discord.ui.Modal, title="Nova Raça / Editar Raça"):
                def __init__(self, nome_inicial: str = ""):
                    super().__init__()
                    self.nome = discord.ui.TextInput(
                        label="Nome da raça",
                        placeholder="Ex: Meio-Ciborgue",
                        default=nome_inicial,
                        max_length=80,
                    )
                    self.deslocamento = discord.ui.TextInput(
                        label="Deslocamento",
                        placeholder="Ex: 9m",
                        default="9m",
                        max_length=32,
                    )
                    self.bonus = discord.ui.TextInput(
                        label="Bônus de Atributo",
                        placeholder="Ex: Força +2, Inteligência +1",
                        style=discord.TextStyle.paragraph,
                        max_length=200,
                    )
                    self.descricao = discord.ui.TextInput(
                        label="Descrição",
                        placeholder="Resumo da raça (fluff/regras).",
                        style=discord.TextStyle.paragraph,
                        required=False,
                        max_length=500,
                    )
                    self.add_item(self.nome)
                    self.add_item(self.deslocamento)
                    self.add_item(self.bonus)
                    self.add_item(self.descricao)

                async def on_submit(self, modal_inter: discord.Interaction):
                    if modal_inter.user.id != interaction.user.id:
                        return await modal_inter.response.send_message("Não é seu painel.", ephemeral=True)
                    await modal_inter.response.defer(ephemeral=True)

                    raw_name = str(self.nome.value).strip()
                    if not raw_name:
                        return await modal_inter.followup.send("❌ Nome da raça é obrigatório.", ephemeral=True)

                    # parse bônus: "Força +2, Inteligência +1"
                    bonus_map: dict[str, int] = {}
                    allowed = {"força", "forca", "destreza", "constituição", "constituicao", "inteligência", "inteligencia", "sabedoria", "carisma"}
                    parts = str(self.bonus.value or "").split(",")
                    for part in parts:
                        part = part.strip()
                        if not part:
                            continue
                        tokens = part.replace("+", " +").replace("-", " -").split()
                        if len(tokens) < 2:
                            continue
                        attr = tokens[0].strip().lower()
                        if attr not in allowed:
                            return await modal_inter.followup.send(
                                "❌ Use nomes completos de atributos: Força, Destreza, Constituição, Inteligência, Sabedoria, Carisma.",
                                ephemeral=True,
                            )
                        try:
                            value = int(tokens[-1])
                        except Exception:
                            return await modal_inter.followup.send(
                                "❌ Não consegui ler o valor numérico em um dos bônus.",
                                ephemeral=True,
                            )
                        key_norm = attr.capitalize().replace("ç", "ç").replace("cao", "ção")
                        if key_norm.startswith("Forc"):
                            key_norm = "Força"
                        elif key_norm.startswith("Dest"):
                            key_norm = "Destreza"
                        elif key_norm.startswith("Const"):
                            key_norm = "Constituição"
                        elif key_norm.startswith("Intel"):
                            key_norm = "Inteligência"
                        elif key_norm.startswith("Sab"):
                            key_norm = "Sabedoria"
                        elif key_norm.startswith("Car"):
                            key_norm = "Carisma"
                        bonus_map[key_norm] = int(value)

                    payload = {
                        "nome": raw_name,
                        "deslocamento": str(self.deslocamento.value or "9m"),
                        "bonus_atributo": bonus_map,
                        "descricao": str(self.descricao.value or ""),
                    }
                    content_templates.upsert_race_template(payload)
                    print(f"[CONTENT UPDATE] Raça {raw_name} atualizada por {interaction.user.id}")
                    await modal_inter.followup.send(
                        f"✅ Raça **{raw_name}** salva/atualizada com sucesso.",
                        ephemeral=True,
                    )

            await btn_inter.response.send_modal(NewRaceModal())

        view.add_item(new_race_button)  # type: ignore[arg-type]

        races = content_templates.get_race_templates()
        race_labels = ", ".join(r["nome"] for r in races[:25]) or "Nenhuma raça disponível ainda."
        emb = discord.Embed(
            title="⚙️ Painel de Conteúdo (SRD / Homebrew)",
            description=(
                "Gerencie raças, classes e origens que serão usadas na criação de fichas.\n\n"
                f"**Raças atuais (amostra):** {race_labels}"
            ),
            color=discord.Color.orange(),
        )
        await interaction.response.send_message(embed=emb, view=view, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))
