from discord.ext import commands
import datetime
import time

class Daily(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

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

    def time_check(self, uid):

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


def setup(bot):
    bot.add_cog(Daily(bot))