import discord
from discord.ext import commands
import asyncio
import subprocess


def check(msg):

    return msg.content == "```taking picture... please wait warmly```"


class Plant(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.expecting = set()  # channels who have requested to see a picture of the plant
        self.waiting = False
        # self.pic_mod_time = os.stat("plant.jpg").st_mtime  # to detect when a new plant.jpg has been uploaded

    @commands.command()
    async def plant(self, ctx):

        self.expecting.add(ctx.message.channel.id)
        await ctx.message.channel.send("```taking picture... please wait warmly```")

        if not self.waiting:
            self.waiting = True
            try:
                await asyncio.wait_for(self.send_plant_pic(), timeout=30)
            except:
                await ctx.message.channel.send("camera timed out!")
                self.waiting = False

    async def send_plant_pic(self):

        error = False
        retcode = subprocess.run(["ffmpeg", "-y", "-i", "rtmp://localhost:5000/live", "-vframes", "1", "plant.jpg"])
        if not retcode == 0:
            error = True
        for chan_id in self.expecting:
            chan = self.bot.get_channel(chan_id)
            if error:
                await chan.send("Something went wrong!")
            else:
                await chan.send("", file=discord.File("plant.jpg"))
            try:
                await chan.purge(check=check)
            except discord.ext.commands.errors.CommandInvokeError:
                print("couldn't delete message!")

        self.expecting.clear()
        self.waiting = False
        return


def setup(bot):
    bot.add_cog(Plant(bot))
