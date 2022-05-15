from discord.ext import commands
import xml.etree.ElementTree as ElementTree
import random
from async_timeout import timeout
import json
import asyncio
from collections import defaultdict
from math import ceil
from PIL import Image
import shutil
import os
import time

dud_items = ["single dirty sock",
              "packet of broken biscuits",
              "completed colouring book",
              "blunt pencil",
              "Blu-ray box set of Akikan!",
              "two-pronged fork",
              "episode 2 of the Xebec Negima anime",
              "damp towel",
              "used bandages",
              "dusty old nutshells",
              "pre-chewed gum",
              "opened box of cereal",
              "just the capsule from inside a Kinder egg",
              "burned-out light bulb",
              "single rubber glove",
              "some wool",
              "screenplay of 'A talking Cat!?!'",
              "room-temperature Coca-cola"]

crate_cost = 2500
RANDOM_MIN = 1800
RANDOM_MAX = 10000
GACHA_LUCK_TIME = 180

class Tcg(commands.Cog):

    def __init__(self, bot):

        self.bot = bot
        self.chan = self.bot.get_channel(bot.settings["robot_zone"])
        self.claimed = False  # try to prevent double-claiming
        self.msg = None  # reference to the loot crate message so we can be sure we are getting reacts to the right one
        self.random_chances = defaultdict(lambda: 0)

        self.bot.loop.call_later(12, lambda: asyncio.ensure_future(self.drop()))
        self.bot.loop.call_later(GACHA_LUCK_TIME, lambda: asyncio.ensure_future(self.decrement_counters()))


    async def decrement_counters(self):

        print("Decrementing counters")
        print(self.random_chances)
        for k, v in self.random_chances.items():
            if v > 0:
                new_v = int(v/2)  # int 1/2 is zero btw
                self.random_chances[k] = new_v

        self.bot.loop.call_later(GACHA_LUCK_TIME, lambda: asyncio.ensure_future(self.decrement_counters()))

    async def drop(self):

        if self.msg:
            await self.msg.delete()  # only one message up at a time
        self.msg = await self.chan.send("A random loot crate has appeared! Click the react to claim it.")
        await self.msg.add_reaction("\U0001f4e6")

        self.bot.loop.call_later(random.randint(RANDOM_MIN, RANDOM_MAX), lambda: asyncio.ensure_future(self.drop()))

    async def on_reaction(self, payload):

        channel = self.bot.get_channel(payload.channel_id)
        ms = await channel.fetch_message(payload.message_id)
        if not ms == self.msg:
            return  # don't care, not the right message, maybe there's some kind of clever filter for this

        self.claimed = True

        await self.msg.delete()
        self.msg = None

        uid = payload.member.id
        card = self.bot.buxman.random_unowned_card()
        self.bot.buxman.add_card(uid, card)

        shutil.move(f"/home/rargh/cards/{card}.jpg", f"/var/www/html/cards/{card}.jpg")
        # move from card repository into somewhere they can actually be served from

        await channel.send(f"{payload.member.mention}, claimed the loot crate! It contained this card. Type 'snek cards'"
                                f"to see all your cards. http://raibu.streams.moe/cards/{card}.jpg")

        self.claimed = False


    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.member == self.bot.user:
            return  # ignore own reaction add at start

        self.claimed = True   # try to deal with 2 users clicking it in a small window,
        await self.on_reaction(payload)

    @commands.command()
    async def cards(self, ctx):

        uid = ctx.message.author.id
        crds = self.bot.buxman.get_cards(uid)
        if not crds:
            await ctx.message.channel.send(f"You have no cards! Claim random loot crates, or type 'snek crate'"
                                           "to buy a loot crate for {crate_cost} snekbux.")
            return
        dict_for_layout = defaultdict(list)

        for x in crds:
            serial, series = x
            serial = str(serial).zfill(5)  # leading zeroes
            dict_for_layout[series].append(serial)
        pilimage = self.make_card_summary(dict_for_layout)

        max_name = len(os.listdir("/var/www/html/card_summaries/"))
        save_name = str(int(time.time()))[-8:]  # unique enough

        pilimage.save(f"/var/www/html/card_summaries/{save_name}.jpg")
        # pilimage.save(f"C:\\s\\tcg\\{uid}.jpg") for testing

        await ctx.message.channel.send(f"http://raibu.streams.moe/card_summaries/{save_name}.jpg")

    def make_card_summary(self, files):

        """Expects a dictionary of series:files so they can be grouped appropriately"""

        width = 3000
        height = 600 * self.calc_height(files)  # how many rows of 10?
        black = Image.new("RGB", (width, height), (0, 0, 0))

        x = 0
        y = 0

        for k, v in files.items():  # key is series, v is list of files
            for q in v:
                #  image_path = f"C:\\s\\tcg\\cards\\{str(q).zfill(5)}.jpg"  for testing
                image_path = f"/var/www/html/cards/{q}.jpg"
                im = Image.open(image_path)
                black.paste(im, (x, y))
                x += 300
                if x >= 3000:
                    x = 0
                    y += 600

        return black.resize((1000, ceil(height / 3)))

    def calc_height(self, files):

        tot = 0
        for v in files.values():
            tot += len(v)
        return ceil(tot / 10)

    @commands.command()
    async def crate(self, ctx):

        funds = self.bot.buxman.get_bux(ctx.message.author.id)
        if funds < crate_cost:
            await ctx.message.channel.send(f'''A loot crate costs {crate_cost} snekbux and you only have {funds}!''')
            return
        self.bot.buxman.adjust_bux(ctx.message.author.id, -crate_cost)

        uid = ctx.message.author.id
        max_rand = max(100 - 10 * self.random_chances[uid], 10)
        chance = random.randint(0, 100)

        if chance < max_rand:
            self.random_chances[uid] += 1  # only make chance harder if the player won
            uid = ctx.message.author.id
            card = self.bot.buxman.random_unowned_card()
            self.bot.buxman.add_card(uid, card)
            shutil.move(f"/home/rargh/cards/{card}.jpg", f"/var/www/html/cards/{card}.jpg")
            await ctx.message.channel.send(f'''{ctx.message.author.mention}, you bought a loot crate for {crate_cost}'''
                                            f''' snekbux and it contained: http://raibu.streams.moe/cards/{card}.jpg''')
        else:
            if random.randint(0, 100) > 70:
                won_bux = random.randint(50, 7000)
                self.bot.buxman.adjust_bux(uid, won_bux)
                await ctx.message.channel.send(f'''{ctx.message.author.mention}, you bought a loot crate for'''
                                                f''' {crate_cost} snekbux and it contained {won_bux} snekbux!''')
            else:
                item = random.choice(dud_items)
                await ctx.message.channel.send(f'''{ctx.message.author.mention}, you bought a loot crate for {crate_cost}'''
                                                f''' snekbux and it contained: ```{item}```''')




def setup(bot):

    bot.add_cog(Tcg(bot))
