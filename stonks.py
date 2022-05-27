from discord.ext import commands
import datetime
import time
from collections import defaultdict
from io import BytesIO
import random
from PIL import Image, ImageFont, ImageDraw
import discord

class Stonks(commands.Cog):

    def __init__(self, bot):

        self.bot = bot
        self.awaited_answers = {}
        self.super_users = defaultdict(lambda: 0)

    async def explain(self, chan):

        await chan.send("Format of command is: snek buy/sell [tag] [price] e.g. to invest 1000 snekbux in the "
                        "'sideboob' "
                        "tag type 'snek buy sideboob 1000'. Each time an image with that tag is posted, 50 snekbux"
                        " will be divided among users who own a share of that tag.")

    def check_high_rate(self, uid):

        if self.super_users[uid] > 3:
            return True
        return False

    async def captcha(self, chan, uid):

        pic, answer = self.captcha_image()
        byts = BytesIO()
        pic.save(byts, format="png")
        byts.seek(0)
        await chan.send("To continue using this function, provide your answer with "
                        "'snek the_answer_to_this_captcha_is [answer]'")
        await chan.send(file=discord.File(byts, "captcha.png"))
        self.awaited_answers[uid] = answer

    @commands.command()
    async def buy(self, ctx, *args):

        #TODO
        ########### put this in a decorator ##########
        uid = ctx.message.author.id

        if uid in self.awaited_answers.keys():
            return

        if self.check_high_rate(uid) and uid in self.bot.watch_list:
            if not uid in self.awaited_answers.keys():
                await self.captcha(ctx.message.channel, uid)
            return

        self.super_users[uid] += 1  # count the number of times the user used this command
        #################################################

        if len(args) == 1:  # just asking about a stonk
            pass
        try:
            tag, cost = args
            cost = int(cost)
        except:
            await self.explain(ctx.message.channel)
            return

        if cost < 0:
            await ctx.message.channel.send("You can't buy a negative amount, nice try!")
            return
        funds = self.bot.buxman.get_bux(ctx.message.author.id)

        if cost > funds:
            await ctx.message.channel.send(f"You are too poor! That order is for {cost} snekbux and you only have"
                                           f" {funds} snekbux!")
            return

        uid = str(ctx.message.author.id)
        self.bot.buxman.adjust_stonk(uid, tag, cost)
        self.bot.buxman.adjust_bux(uid, -1 * cost)  # negative because we are buying
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
            await ctx.message.channel.send("You can't sell a negative amount!")
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
        self.bot.buxman.adjust_bux(uid, cost)  # positive because we are selling
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
            if len(out) > 1600:
                break  # stop message getting too long, limit is 2000 characters

        await ctx.message.channel.send(out)

        divi = self.bot.buxman.print_dividend(ctx.message.author.id)
        if not divi == 0:
            await ctx.message.channel.send(
                f"\nYou have gained {divi} snekbux from your investments since you last checked!")

    def captcha_image(self):

        num1 = random.randint(1, 10000)
        num2 = random.randint(1, 10000)

        text = f"{num1} x {num2}"

        font = ImageFont.truetype("arial.ttf", 20)

        image_width = font.getlength(text)
        print(image_width)
        white = Image.new("RGBA", (int(image_width) + 3, 24), (225, 225, 225))
        ctx = ImageDraw.Draw(white)  # drawing context to write text

        for _ in range(5):
            coord1 = (random.randint(0, int(image_width)), 0)
            coord2 = (random.randint(0, int(image_width)), 24)
            ctx.line((coord1, coord2), (10, 10, 10))

        ctx.text((2, 2), text, font=font, fill=(10, 10, 10))

        return white, num1 * num2

    @commands.command()
    @commands.cooldown(2, 1800, type=commands.BucketType.user)
    async def the_answer_to_this_captcha_is(self, ctx, ans):

        try:
            wanted_answer = self.awaited_answers[ctx.message.author.id]
        except KeyError:
            return
        if str(wanted_answer) == str(ans):
            await ctx.message.channel.send("OK, you can continue using this function.")
            self.awaited_answers.pop(ctx.message.author.id)
            self.super_users[ctx.message.author.id] = 0
        else:
            await ctx.message.channel.send("Wrong answer!")


def setup(bot):
    bot.add_cog(Stonks(bot))