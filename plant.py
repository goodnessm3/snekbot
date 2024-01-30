import discord
from discord.ext import commands
import asyncio
import aiohttp
from async_timeout import timeout
from io import BytesIO


def check(msg):

    return msg.content == "```taking picture... please wait warmly```"


class Plant(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.expecting = set()  # channels who have requested to see a picture of the plant
        self.waiting = False
        self.plant_url = self.bot.settings["plant_url"]

    # @commands.command()  # to be deprecated
    async def plant(self, ctx):

        self.expecting.add(ctx.message.channel.id)
        await ctx.message.channel.send("```taking picture... please wait warmly```")

        if not self.waiting:
            self.waiting = True
            #try:
            await asyncio.wait_for(self.send_plant_pic(), timeout=30)
            #except:
                #await ctx.message.channel.send("camera timed out!")
                #self.waiting = False

    async def send_plant_pic(self):

        print("image from", self.plant_url)
        async with aiohttp.ClientSession(loop=self.bot.loop) as s:
            async with s.get(self.plant_url) as r:
                async with timeout(10):
                    image_data = await r.read()
                    image_io = BytesIO(image_data)

        for chan_id in self.expecting:
            chan = self.bot.get_channel(chan_id)
            await chan.send("", file=discord.File(image_io, filename="image.jpg"))
            try:
                await chan.purge(check=check)
            except discord.ext.commands.errors.CommandInvokeError:
                print("couldn't delete message!")

        self.expecting.clear()
        self.waiting = False
        return


async def setup(bot):

    await bot.add_cog(Plant(bot))