from discord.ext import commands
import datetime
import time
import matplotlib.pyplot as plt
from io import BytesIO
import discord

class Daily(commands.Cog):

    def __init__(self, bot):

        self.bot = bot
        self.temp = []  # to deal with server going down, a more long term solution is needed

    @commands.command()
    async def daily(self, ctx):

        uid = ctx.message.author.id
        _ = self.bot.buxman.get_bux(uid)
        #  first just query the bux and do nothing, this will create a new entry if one is required (new user)
        check, msg = self.time_check(uid)
        self.bot.buxman.increment_daily_time(uid, time.time())
        # just using the seconds since epoch for easy conversion back to a datetime object later
        if check == 0 or check == 1:
            # reset streak regardless of if too early or too late
            await ctx.message.channel.send(msg)
            self.bot.buxman.reset_streak(uid)
        if check == 1:
            return  # too early, nothing else to do

        # otherwise, the user is within the right time window or want to give snekbux at the start of a new streak
        self.bot.buxman.increment_streak(uid)
        strk = self.bot.buxman.get_streak(uid)
        amount = 180 + 20 * strk
        await ctx.message.channel.send(f"You got {amount} snekbux. You are on a {strk}-day streak!")
        self.bot.buxman.adjust_bux(uid, amount)
        if strk == 69:
            await ctx.message.channel.send("Nice!")

    def time_check(self, uid):

        if uid not in self.temp:
            self.temp.append(uid)
            return 2, ""  # free pass first time regardless of time interval, a temporary fix

        now = datetime.datetime.now()
        tim = self.bot.buxman.daily_time(uid)
        strk = self.bot.buxman.get_streak(uid)
        if not tim:
            return 2, ""  # Null value in db because first time ever the user has done this

        then = datetime.datetime.fromtimestamp(float(tim))
        delta = now - then
        if delta > datetime.timedelta(days=2):
            # waited too long
            d = delta.days
            return 0, f"It is {d} days since you last checked your daily, your {strk}-day streak has been reset!"
        else:
            if now.day == then.day:
                # too soon, on the same day
                t = self.until_midnight()
                return 1, f"You are too early by {t}! Your {strk}-day streak has been reset!"
            else:
                return 2, ""  # the day has advanced since last time but the delta is 1 to 2 days

    def until_midnight(self):

        """Returns hh:mm:ss until midnight when the function is called, to show the user
        how long they should have waited"""

        now = datetime.datetime.now()
        mn = datetime.datetime.combine(now.date(), datetime.time(23, 59, 59))
        return str(mn - now)[:8]

    @commands.command()
    async def bux_history(self, ctx):

        fig, ax = plt.subplots()  # Create a figure containing a single axes.
        ax.plot(*self.bot.buxman.bux_graph_data(ctx.message.author.id))
        # ax.plot(*get_data("solo", 7))
        uname = ctx.message.author.display_name
        ax.set_title(f"{uname}'s wealth over time")
        ax.set_ylabel("count (cumulative)")

        for label in ax.get_xticklabels(which='major'):
            label.set(rotation=50, horizontalalignment='right')

        buffer = BytesIO()
        plt.tight_layout()  # otherwise the rotated date labels will get cut off
        plt.savefig(buffer, format="png")
        buffer.seek(0)

        await ctx.message.channel.send(file=discord.File(buffer, filename="graph.png"))
        # we need to provide a filename so it's correctly detected as a .png and shown as an image




async def setup(bot):

    await bot.add_cog(Daily(bot))