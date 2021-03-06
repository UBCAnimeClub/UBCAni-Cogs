import aiohttp
import discord
import io
import os
from .utils.dataIO import dataIO
from discord.ext import commands
from .utils import checks

def check_folders():
    if not os.path.exists("data/UBCAniCogs/redirect"):
        print("Creating data/UBCAniCogs/redirect folder...")
        os.makedirs("data/UBCAniCogs/redirect")


def check_files():
    f = "data/UBCAniCogs/redirect/redirect.json"
    if not dataIO.is_valid_json(f):
        print("Creating default redirect.json...")
        dataIO.save_json(f, {})

async def download(attachment):
    async with aiohttp.get(attachment["url"]) as response:
        return await response.read()

class Redirect:
    """Redirect messages from one channel to another"""

    def __init__(self, bot):
        self.bot = bot
        self.file_path = "data/UBCAniCogs/redirect/redirect.json"
        self.routes = dataIO.load_json(self.file_path)

    @commands.command(name="redirect", pass_context=True, no_pm=True)
    @checks.admin_or_permissions(manage_server=True)
    async def redirect(self, ctx, src: discord.Channel, dst: discord.Channel):
        """Redirects messages from one channel to another"""
        server = ctx.message.server

        if server.id not in self.routes:
            self.routes[server.id] = {}

        self.routes[server.id][src.id] = dst.id

        dataIO.save_json(self.file_path, self.routes)

        return await self.bot.say("Redirecting messages from {} to {}".format(src.mention, dst.mention))

    async def on_message(self, message):
        author = message.author
        server = message.server

        if server is None or self.bot.user == author:
            return

        if server.id not in self.routes or message.channel.id not in self.routes[server.id]:
            return

        if not isinstance(author, discord.Member) or author.bot:
            return

        attachments = []

        for attachment in message.attachments:
            attachments.append((await download(attachment), attachment["filename"]))

        await self.bot.delete_message(message)
        destination = discord.utils.get(server.channels, id=self.routes[server.id][message.channel.id])

        await self.bot.send_message(destination, "Report submitted by {}\n{}".format(message.author.mention, message.content))

        for attachment in attachments:
            data, filename = attachment
            buffer = io.BytesIO(data)

            await self.bot.send_file(destination, buffer, filename=filename)
            buffer.close()

def setup(bot):
    check_folders()
    check_files()

    bot.add_cog(Redirect(bot))
