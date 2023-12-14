from discord.ext import commands
import datetime
import time

class Activity(commands.Cog):

    def __init__(self, bot):

        self.bot = bot
        self.tracked = []

    @commands.command()
    async def count(self, ctx):

        mems = ctx.message.channel.guild.members
        print(len(mems))

        print(mems)
        for x in mems:
            print(x)


def setup(bot):
    bot.add_cog(Activity(bot))