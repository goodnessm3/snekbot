from discord.ext import commands
import random
import asyncio
import time
import discord


class SnekGame(commands.Cog):

    def __init__(self, bot):

        self.bot = bot
        self.bonuses = self.make_bonuses()
        self.running = False  # one at a time

    def chance(self, pct):

        if random.randint(0, 100) < pct:
            return True
        else:
            return False

    def make_bonuses(self):

        ls1 = [
            "Three-in-a-row bonus",
            "Two-in-a-row bonus",
            "Multiple colour bonus",
            "Streak bonus",
            "Compensatory bonus",
            "Royal sampler bonus",
            "Reverse order bonus",
        ]
        ls2 = [f"All {x} bonus" for x in ["red", "green", "blue", "purple", "yellow"]]
        ls3 = [f"{x}-tile bonus" for x in range(1,5)]

        return ls1 + ls2 + ls3

    def make_matrix(self):

        code = 128997
        out = ""
        for x in range(1, 10):
            if self.chance(2):
                out += chr(9883)
            else:
                out += chr(code + random.randint(0, 5))
            if x % 3 == 0:
                out += "\n"
        return out

    def bux_check(self, uid, amt):

        """Return True if user has more bux than amt"""

        b = self.bot.buxman.get_bux(uid)
        if b > amt:
            return True
        else:
            return False

    def reset_status(self):

        print("reset game running status")
        self.running = False

    @commands.command()
    async def game(self, ctx):

        """Posts the game message and schedules evaluation after a random time"""

        if self.running:
            await ctx.message.channel.send("A game is already running! "
                                           "You have been fined 150 snekbux for your insolence!")
            theid = ctx.message.author.id
            self.bot.buxman.adjust_bux(theid, -150)
            return

        self.running = True
        delay = random.randint(10,20)
        cost = random.randint(100,600)
        rules = random.choice(["standard", "modified", "second-edition", "altered", "special", "normal", "regular"])
        ms = f"The game will last for {delay} seconds and cost {cost} snekbux. Choose the tiles you want to play" \
             f" in order, radially from the centre counterclockwise ({rules} rules apply).\n\n"
        ms += self.make_matrix()
        msg = await ctx.message.channel.send(ms)
        chan = ctx.message.channel
        code = 128997
        for _ in range(6):
            await msg.add_reaction(chr(code))
            code += 1

        self.bot.loop.call_later(delay, lambda: asyncio.ensure_future(self.evaluate_game(msg.id, chan, cost)))
        self.bot.loop.call_later(delay, self.reset_status)

    async def evaluate_game(self, msgid, chan, cost):

        msg = await chan.fetch_message(msgid)
        # need to re-get the message now that reactions have been added
        users = set()
        for x in msg.reactions:
            async for u in x.users():
                if not u == self.bot.user:
                    users.add(u)  # accumulate everyone who reacted

        out = []
        buyin = len(users) * cost  # the total snekbux that has been bet. Very occasionally
        #  this will be an overestimate if someone was too poor to play but never mind
        if len(users) == 0:
            await chan.send("Nobody played the game!")
            return
        if len(users) > 1:
            # determine an overall winner if multiple people "played"
            out.append("Results")
            winner = random.choice(list(users))
            out.append(f"{winner.mention} is the overall winner and gets {buyin} snekbux!")
            self.bot.buxman.adjust_bux(winner.id, buyin - cost)
            # the whole pool goes to this player minus what they paid to play
        else:
            out.append("Results (single-player mode)")
            winner = None  # single player mode
        for u in users:
            if u == winner:
                continue
            if not self.bux_check(u.id, cost):
                out.append(f"{u.mention} was too poor to play and has been fined 100 snekbux!")
                self.bot.buxman.adjust_bux(u.id, -100)
                continue
            if winner:
                won = self.chance(20)
            else:
                won = self.chance(50)
            amount = random.randint(int(buyin/2), buyin)
            if won:
                st = f"{u.mention} won {buyin + amount} snekbux!"
                if self.chance(30):
                    st += " "
                    st += f"({random.choice(self.bonuses)})"
                out.append(st)
                self.bot.buxman.adjust_bux(u.id, amount)  # always win more than you bet
            else:
                amount2 = amount//2
                out.append(f"{u.mention} lost {amount2 + cost} snekbux on this game! Too bad!")
                self.bot.buxman.adjust_bux(u.id, -(amount2+cost))

        await chan.send("\n".join(out))


async def setup(bot):

    await bot.add_cog(SnekGame(bot))