import discord
from discord.ext import commands
import os
import asyncio
import sys

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
        print("plantplant")  # print message to stdout that's monitored for by the camera script
        sys.stdout.flush()
        if not self.waiting:
            self.waiting = True
            try:
                await asyncio.wait_for(self.send_plant_pic(), timeout=30)
            except:
                await ctx.message.channel.send("camera timed out!")
                self.waiting = False

    async def send_plant_pic(self):

        pic_mod_time = os.stat("plant.jpg").st_mtime
        while 1:
            mod_time = os.stat("plant.jpg").st_mtime
            if not mod_time == pic_mod_time:
                await asyncio.sleep(2)  # wait for the file to be written
                for chan_id in self.expecting:
                    chan = self.bot.get_channel(chan_id)
                    await chan.send("", file=discord.File("plant.jpg"))
                    try:
                        await chan.purge(check=check)
                    except discord.ext.commands.errors.CommandInvokeError:
                        print("couldn't delete message!")
                await asyncio.sleep(5)  # make absolutely sure the file has finished being written
                self.expecting.clear()
                self.waiting = False
                return
            await asyncio.sleep(1)

def setup(bot):
    bot.add_cog(Plant(bot))
