from discord.ext import commands
from async_timeout import timeout
import aiohttp


class Temp(commands.Cog):

    def __init__(self, bot):

        self.bot = bot
        self.url = self.bot.settings["temperature_url"]

    @commands.command()
    async def temp(self, ctx):

        async with aiohttp.ClientSession(loop=self.bot.loop) as s:
            async with s.get(self.url) as r:
                async with timeout(10):
                    a = await r.text()

        t = a.rstrip("\n")
        await ctx.send(f"The temperature in Goodness Me's room is {t}°F!")


async def setup(bot):

    await bot.add_cog(Temp(bot))
