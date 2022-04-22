from discord.ext import commands
import datetime
import time

class Stonks(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

    async def explain(self, chan):

        await chan.send("Format of command is: snek buy/sell [tag] [price] e.g. to invest 1000 snekbux in the "
                        "'sideboob' "
                        "tag type 'snek buy sideboob 1000'. Each time an image with that tag is posted, 50 snekbux"
                        " will be divided among users who own a share of that tag.")

    @commands.command()
    async def buy(self, ctx, *args):

        if len(args) == 1:  # just asking about a stonk
            pass
        try:
            tag, cost = args
            cost = int(cost)
        except:
            await self.explain(ctx.message.channel)
            return

        if cost < 0:
            await ctx.message.channel.send("Can't buy a negative amount, nice try!")
            return
        funds = self.bot.buxman.get_bux(ctx.message.author.id)

        if cost > funds:
            await ctx.message.channel.send(f"You are too poor! That order is for {cost} snekbux and you only have"
                                           f" {funds} snekbux!")
            return

        uid = str(ctx.message.author.id)
        self.bot.buxman.adjust_stonk(uid, tag, cost)
        eq = self.bot.buxman.calculate_equity(uid, tag)
        msg = f"You invested {cost} snekbux in {tag}! You will recieve a dividend each time an image with that tag is " \
              f"posted. You now own {eq}% of this tag."
        await ctx.message.channel.send(msg)


    @commands.command()
    async def sell(self, ctx, *args):

        out = ""

        try:
            tag, cost = args
            cost = int(cost)
        except:
            await self.explain(ctx.message.channel)
            return

        if cost < 0:
            await ctx.message.channel.send("Can't sell a negative amount!")
            return

        uid = str(ctx.message.author.id)
        owned = self.bot.buxman.get_stonk(uid, tag)
        if not owned:
            await ctx.message.channel.send("You don't own any of that stock!")
            return
        if owned < cost:
            cost = owned
            out += f"You can't sell more shares than you have, selling {cost} snekbux worth instead. "

        self.bot.buxman.adjust_stonk(uid, tag, cost * -1)  # -1 because we are SELLING
        eq = self.bot.buxman.calculate_equity(uid, tag)
        out +=f"Sold {cost} snekbux worth of {tag}! You now own {eq}% of this tag."

        await ctx.message.channel.send(out)

    @commands.command()
    async def portfolio(self, ctx):

        res = self.bot.buxman.get_portfolio(ctx.message.author.id)
        if not res:
            await ctx.message.channel.send("Your portfolio is empty!")
            await self.explain(ctx.message.channel)
            return

        out = "Your current portfolio:\n"

        for x in res:
            a, b = x
            eq = self.bot.buxman.calculate_equity(ctx.message.author.id, a)
            out += f"{a}: {b} snekbux ({eq}% equity)\n"

        old = self.bot.buxman.get_bux(ctx.message.author.id)
        self.bot.buxman.pay_dividend(ctx.message.author.id)
        new  = self.bot.buxman.get_bux(ctx.message.author.id)
        delta = new - old
        out += f"\nYou have gained {delta} snekbux from your investments since you last checked!"

        await ctx.message.channel.send(out)


def setup(bot):
    bot.add_cog(Stonks(bot))