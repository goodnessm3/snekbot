from discord.ext import commands
import secrets
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

    @commands.command()
    async def shop(self, ctx):

        u = ctx.message.author
        rand = secrets.token_hex(4)
        self.bot.buxman.anticipate_shop_activation(u.id, rand, u.display_name)
        await u.send(f"Enter this code on the snekbux store web page: {rand}")


def setup(bot):

    bot.add_cog(Shop(bot))
