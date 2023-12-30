from discord.ext import commands
import secrets
import discord
import os
import asyncio

class Shop(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

    @commands.command()
    async def ident(self, ctx):

        u = ctx.message.author
        rand = secrets.token_hex(16)
        self.bot.buxman.anticipate_shop_activation(u.id, rand, u.display_name)

        await u.send(f"Visit this link to authenticate on the website: {self.bot.settings['website']}/authenticate/{rand}")


async def setup(bot):

    await bot.add_cog(Shop(bot))
