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


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))
