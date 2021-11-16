from discord.ext import commands
import secrets
import socket
import os
import xml.etree.ElementTree as ElementTree
import random
from async_timeout import timeout
import json
import asyncio
from collections import defaultdict
import clean_text as ct
from Tree_Server import Tree_Server
import aiohttp


class Shop(commands.Cog):

    def __init__(self, bot):

        self.bot = bot
        self.bot.loop.create_task(self.shop_monitor())
        with open("shop_file.txt", "w") as f:
            pass  # just overwrite the file anew each startup
        self.shop_file = open("shop_file.txt", "r")  # now keep handle open

    @commands.command()
    async def shop(self, ctx):

        u = ctx.message.author
        rand = secrets.token_hex(2).upper()
        self.bot.buxman.anticipate_shop_activation(u.id, rand, u.display_name)
        await u.send(f"Enter this code at {self.bot.settings['shop_address']}: {rand}")
        await ctx.message.channel.send(f"Spend your snekbux at {self.bot.settings['shop_address']}!")

    async def shop_monitor(self):

            line = self.shop_file.readline()  # will just be nothing if at EOF
            if line.rstrip(os.linesep):
                await self.process_shop_cmd(line)
            self.bot.loop.call_later(1, lambda: asyncio.ensure_future(self.shop_monitor()))

    async def process_shop_cmd(self, command):

        # parts are (channel id, message)
        parts = command.rstrip(os.linesep).split("||")
        cmd = parts[0]  # a string the identifies what to actually do
        uid = parts[1]
        if cmd == "sendmessage":
              # get the discord ID so we can charge snekbux accordingly
            self.bot.buxman.adjust_bux(uid, -1000)
            chan = self.bot.get_channel(int(parts[2]))
            print(parts[3])
            if len(parts[3]) > 0:
                await chan.send(parts[3])
        elif cmd == "namechange":
            newname = parts[2]
            guild_id = self.bot.settings["shop_server"]
            srv = self.bot.get_guild(guild_id)
            self.bot.buxman.adjust_bux(uid, -10000)
            await srv.me.edit(nick=newname)

def setup(bot):

    bot.add_cog(Shop(bot))
