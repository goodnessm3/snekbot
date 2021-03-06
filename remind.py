from discord.ext import commands
import re
import asyncio
import datetime
import time


class Reminder(commands.Cog):

    time_finder = re.compile('''([0-9]{1,6})[\s]{,2}([hmsd])(?:[\S]*\s{0,1})''')
    date_finder = re.compile('''[0-9]{4}-[0-9]{2}-[0-9]{2}''')
    time_units = {"s": 1, "m": 60, "h": 3600, "d": 86400}

    def __init__(self, bot):

        self.bot = bot
        reminders = self.bot.buxman.get_reminders()  # get all reminders from DB yet to be run
        for rem in reminders:
            uid, timestamp, message, rid, channel_id = rem
            chan = self.bot.get_channel(channel_id)  # need to recreate the discord object from saved id
            # future_time = datetime.datetime.fromisoformat(timestamp) not for 3.7
            y, m, d = timestamp[:10].split("-")
            future_time = datetime.datetime(int(y), int(m), int(d))  # works on earlier python versions
            delay = future_time - datetime.datetime.now()
            self.bot.loop.call_later(int(delay.total_seconds()),
                                     lambda: asyncio.ensure_future(chan.send(message)))

            print("Added reminder to loop: {} at {}".format(message, timestamp))

    @commands.command()
    async def remindme(self, ctx, *astr):

        """set a reminder after a certain time e.g. !remindme 10 minutes asdf"""

        in_string = " ".join(astr)  # make the arguments a string and then fish out the time with regex
        dat = self.date_finder.search(in_string)
        if dat:
            # try for an exact ISO time first
            # future_time = datetime.datetime.fromisoformat(dat.group())  # this function is only available in 3.7+!
            y, m, d = dat.group().split("-")
            future_time = datetime.datetime(int(y), int(m), int(d))  # works on earlier python versions
            delt = future_time - datetime.datetime.now()
            delay = int(delt.total_seconds())
            extracted = self.strip_date(in_string)
        else:
            delay = self.find_time(in_string)  # the delay in seconds regardless of the unit the user used
            extracted = self.strip_time(in_string)
        to_send = "{}, reminder: {}!".format(ctx.message.author.mention, extracted)
        print_delay = datetime.timedelta(seconds=delay)
        await ctx.message.channel.send("OK! I'll remind you in {}.".format(print_delay))
        self.bot.loop.call_later(delay, lambda: asyncio.ensure_future(ctx.message.channel.send(to_send)))

        self.bot.buxman.add_reminder(ctx.message.author.id, to_send, ctx.message.channel.id, delay)
        # write the reminder to the SQL db in case the bot is restarted before the reminder is sent

    def find_time(self, astr):

        total = 0
        for match in self.time_finder.findall(astr):
            num, unit = match
            num = int(num) * self.time_units[unit]
            total += num

        return total

    def strip_time(self, astr):

        return self.time_finder.sub("", astr)

    def strip_date(self, astr):

        return self.date_finder.sub("", astr)


def setup(bot):
    bot.add_cog(Reminder(bot))
