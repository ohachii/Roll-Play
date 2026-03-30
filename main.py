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
import asyncio
import logging
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
from utils.checks import is_app_owner

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
log = logging.getLogger("rpg-bot")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

EXTENSIONS = [
    "cogs.npc",
    "cogs.admin",
    "cogs.notes",
    "cogs.core",
    "cogs.player",
    "cogs.gm_panel",
]

GUILD_ID_FOR_FAST_SYNC = None
AUTO_SYNC_GUILD_ID = 1321153391832993864

class RPGbot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=commands.when_mentioned_or("!"),
            intents=intents,
            application_id=int(os.getenv("DISCORD_APP_ID", "0")) or None
        )

    async def setup_hook(self):
        for ext in EXTENSIONS:
            try:
                await self.load_extension(ext)
                log.info(f"[cogs] loaded: {ext}")
            except Exception as e:
                log.exception(f"[cogs] failed to load {ext}: {e}")

    async def on_ready(self):
        log.info(f"Logged in as {self.user} (id={self.user.id})")
        try:
            guild_obj = discord.Object(id=AUTO_SYNC_GUILD_ID)
            # Copia os comandos definidos no código para a guild alvo e sincroniza.
            self.tree.copy_global_to(guild=guild_obj)
            synced = await self.tree.sync(guild=guild_obj)
            log.info(f"[sync] auto guild ok: {len(synced)} commands (guild={AUTO_SYNC_GUILD_ID})")
        except Exception:
            log.exception("[sync] auto sync error")
        await self.change_presence(
            activity=discord.Game(name="/npc_menu • /notas")
        )

bot = RPGbot()

def main():
    token = os.getenv("DISCORD_TOKEN") or os.getenv("TOKEN")
    if not token:
        raise RuntimeError("Defina DISCORD_TOKEN (ou TOKEN) no .env com o token do seu bot.")
    bot.run(token)

if __name__ == "__main__":
    main()
