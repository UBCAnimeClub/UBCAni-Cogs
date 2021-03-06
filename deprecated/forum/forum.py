import aiohttp
import discord

from discord.ext import commands
from .utils.dataIO import dataIO
from .utils import checks
from __main__ import send_cmd_help
from datetime import datetime

import os

def check_folders():
    if not os.path.exists("data/UBCAniCogs/forum"):
        print("Creating data/UBCAniCogs/forum folder...")
        os.makedirs("data/UBCAniCogs/forum")

def check_files():
    f = "data/UBCAniCogs/forum/forum.json"
    if not dataIO.is_valid_json(f):
        print("Creating default forum.json...")
        dataIO.save_json(f, {})

class Forum:
    """Forum games"""

    def __init__(self, bot):
        self.bot = bot
        self.file_path = "data/UBCAniCogs/forum/forum.json"
        self.data = dataIO.load_json(self.file_path)

    @commands.command(pass_context=True, no_pm=True)
    async def count(self, ctx, value: int):
        """Continues the count"""
        server_id = ctx.message.server.id
        author_id = ctx.message.author.id

        if server_id not in self.data:
           self.data[server_id] = { "last_count": 0, "contributors": {}, "last_contributor": None }

        d = self.data[server_id]

        if d["last_count"] + 1 != value:
            return await self.bot.say("Learn to count; the current number is {}.".format(d["last_count"]))

        if author_id != d["last_contributor"]:
            d["last_count"] += 1

            if author_id not in d["contributors"]:
                d["contributors"][author_id] = []
            
            d["contributors"][author_id].append(d["last_count"])
            d["last_contributor"] = author_id

            dataIO.save_json(self.file_path, self.data)

            return await self.bot.say("We're now at {}.".format(d["last_count"]))

        return await self.bot.say("Let someone else continue the count.")

    @commands.command(pass_context=True, no_pm=True)
    async def countinfo(self, ctx):
        """Gives the current value"""
        server_id = ctx.message.server.id
        author_id = ctx.message.author.id

        if server_id not in self.data:
           self.data[server_id] = { "last_count": 0, "contributors": {}, "last_contributor": None }

        d = self.data[server_id]

        message = "You have made no contributions; get counting!"

        if author_id in d["contributors"]:
            contributions = d["contributors"][author_id]
            message = "You've counted {} number{}: {}".format(len(contributions), "" if len(contributions) == 1 else "s", ", ".join(map(str, contributions)))

        return await self.bot.say("We are now at {}.\n{}".format(d["last_count"], message))

def setup(bot):
    check_folders()
    check_files()
    bot.add_cog(Forum(bot))
