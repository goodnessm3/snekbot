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
import re

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
              "room-temperature Coca-cola",
              "sweer potato",
              "chicken nugger",
              "snek's source code from one year ago",
              "a urinal cake",
              "half a jar of salsa",
              ]

RANDOM_MIN = 500
RANDOM_MAX = 7200
GACHA_LUCK_TIME = 180
CRATE_COST_TIME = 120

class Tcg(commands.Cog):

    def __init__(self, bot):

        self.bot = bot
        self.chan = self.bot.get_channel(bot.settings["robot_zone"])
        self.claimed = False  # try to prevent double-claiming
        self.msg = None  # reference to the loot crate message so we can be sure we are getting reacts to the right one
        self.random_chances = defaultdict(lambda: 0)
        self.crate_cost = defaultdict(lambda: 2500)  # a dictionary of user:cost
        self.pending_trades = {}  # a dict of message id: serial list. When the message is reacted to,
        # the trade described by serial list will trigger
        self.trade_owners = {}  # only pay attention to reacts from this person
        self.waiting_for_response = {}  # players can only have one open trade at a time to avoid MAJOR headaches
        # message id:player
        self.offered_cards = []  # ANY card from ANYONE that is currently offered for trade, make sure unique

        self.bot.loop.call_later(10, lambda: asyncio.ensure_future(self.update_player_names()))
        self.bot.loop.call_later(12, lambda: asyncio.ensure_future(self.drop()))
        self.bot.loop.call_later(GACHA_LUCK_TIME, lambda: asyncio.ensure_future(self.decrement_counters()))
        self.bot.loop.call_later(CRATE_COST_TIME, lambda: asyncio.ensure_future(self.modulate_crate_cost()))

    def look_up_trade(self, msg):

        """Return the serial list of the trade which is asked for in message"""

        return self.pending_trades[msg]

    def remove_trade(self, msg):

        print("removing from pending trades")
        print(self.pending_trades)
        self.pending_trades.pop(msg)
        print("after removal")
        print(self.pending_trades)

    async def update_player_names(self):

        uids = self.bot.buxman.get_uids_with_cards()
        adict = {}
        for x in uids:
            mem = await self.chan.guild.fetch_member(x)
            adict[x] = mem.display_name

        self.bot.buxman.update_card_trader_names(adict)
        self.bot.loop.call_later(86400, lambda: asyncio.ensure_future(self.update_player_names()))

    async def decrement_counters(self):

        print("Decrementing counters")
        print(self.random_chances)
        for k, v in self.random_chances.items():
            if v > 0:
                new_v = int(v/2)  # int 1/2 is zero btw
                self.random_chances[k] = new_v

        self.bot.loop.call_later(GACHA_LUCK_TIME, lambda: asyncio.ensure_future(self.decrement_counters()))

    async def modulate_crate_cost(self):

        print("checking crate cost")
        for k, v in self.crate_cost.items():
            if v > 2500:
                self.crate_cost[k] = v-250
        print(self.crate_cost)

        self.bot.loop.call_later(CRATE_COST_TIME, lambda: asyncio.ensure_future(self.modulate_crate_cost()))

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

    def remove_cards_from_offered(self, als):

        print("self.offered cards was", self.offered_cards)
        print("removing", als)
        for x in als:
            self.offered_cards.remove(str(x).zfill(5))

        print("now self.offered cards is", self.offered_cards)


    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):

        chan = self.bot.get_channel(payload.channel_id)
        mid = payload.message_id

        if payload.member == self.bot.user:
            return  # ignore own reaction add at start

        if payload.emoji.name == "\U00002705":  # checkmark
            try:
                expected_id = self.trade_owners[mid]
            except KeyError:
                return
            if not payload.member.id == expected_id:
                print("Ignoring a reaction from the wrong person")
                return

            trd = self.look_up_trade(mid)
            await chan.send("The trade was successful!")
            print(trd)
            self.bot.buxman.execute_trade(trd)
            self.pending_trades.pop(mid)
            self.trade_owners.pop(mid)
            self.waiting_for_response.pop(mid)
            self.remove_cards_from_offered(trd)

        elif payload.emoji.name == "\U0000274C":  # cross
            try:
                expected_id = self.trade_owners[mid]
            except KeyError:
                return
            if not payload.member.id == expected_id:
                print("Ignoring a reaction from the wrong person")
                return

            trd = self.look_up_trade(mid)
            await chan.send("The trade was rejected!")
            self.pending_trades.pop(mid)
            self.trade_owners.pop(mid)
            self.waiting_for_response.pop(mid)
            self.remove_cards_from_offered(trd)

        elif payload.emoji.name == "\U0001f4e6":  # package
            self.claimed = True   # try to deal with 2 users clicking it in a small window,
            await self.on_reaction(payload)

    @commands.command()
    async def cards(self, ctx):

        uid = ctx.message.author.id
        crds = self.bot.buxman.get_cards(uid)
        if len(crds) > 100:
            await ctx.message.channel.send("Too many cards, wait for a new way to check this. In the meantime you"
                                           "can go to the trade interface.")
            return
        if not crds:
            await ctx.message.channel.send(f"You have no cards! Claim random loot crates, or type 'snek crate'"
                                           "to buy a loot crate.")
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

        cost = self.crate_cost[ctx.message.author.id]
        funds = self.bot.buxman.get_bux(ctx.message.author.id)
        if funds < cost:
            mess = f'''A loot crate currently costs {cost} snekbux for you and you only have {funds}!'''
            if cost > 2500:
                mess += ''' The cost will drop soon, so check back later!'''
            await ctx.message.channel.send(mess)
            return
        self.bot.buxman.adjust_bux(ctx.message.author.id, -cost)

        uid = ctx.message.author.id
        max_rand = max(100 - 20 * self.random_chances[uid], 10)
        chance = random.randint(0, 100)

        if chance < max_rand:
            self.random_chances[uid] += 1  # only make chance harder if the player won
            uid = ctx.message.author.id
            card = self.bot.buxman.random_unowned_card()
            self.bot.buxman.add_card(uid, card)
            shutil.move(f"/home/rargh/cards/{card}.jpg", f"/var/www/html/cards/{card}.jpg")
            await ctx.message.channel.send(f'''{ctx.message.author.mention}, you bought a loot crate for {cost}'''
                                            f''' snekbux and it contained: http://raibu.streams.moe/cards/{card}.jpg''')
        else:
            if random.randint(0, 100) < max_rand:
                won_bux = random.randint(50, 7000)
                self.bot.buxman.adjust_bux(uid, won_bux)
                await ctx.message.channel.send(f'''{ctx.message.author.mention}, you bought a loot crate for'''
                                                f''' {cost} snekbux and it contained {won_bux} snekbux!''')
            else:
                item = random.choice(dud_items)
                await ctx.message.channel.send(f'''{ctx.message.author.mention}, you bought a loot crate for {cost}'''
                                                f''' snekbux and it contained: ```{item}```''')

        self.crate_cost[uid] =  self.crate_cost[uid] * 2  # slowly ramp up cost and have it decay back down

    @commands.command()
    async def trade(self, ctx, *args):

        if ctx.message.author.id in self.waiting_for_response.values():
            await ctx.message.channel.send("You can only have a single trade open at one time.")
            return

        if not args:
            await ctx.message.channel.send("go to http://raibu.streams.moe/snekstore/trade_setup to set up a trade.")
            return

        serial_verifier = re.compile('''^[0-9]{5}$''')
        discord_id_verifier = re.compile('''^[0-9]{17,19}$''')  # can be 17 digits only if quite an old ID!

        source_id = ctx.message.author.id
        dest_id = args[0][2:-1]

        serial_list = args[1:]

        if not discord_id_verifier.match(dest_id):
            await ctx.message.channel.send("Something is wrong with the ID of the trading partner.")
            return

        for q in serial_list:
            if not serial_verifier.match(q):
                await ctx.message.channel.send("Something is wrong with the card serial numbers.")
                return

        bad = []
        for x in serial_list:
            if x in self.offered_cards:
                bad.append(x)
        if not bad == []:
            await ctx.message.channel.send("These cards are already involved in other trade proposals:")
            await ctx.message.channel.send(",".join(bad))
            return

        serial_list_str = [str(int(x)) for x in serial_list]  # now that we have done the check, convert serials to ints

        owner_check = self.bot.buxman.verify_ownership(serial_list_str, source_id, dest_id)
        if not owner_check:
            await ctx.message.channel.send("This trade contains cards not owned by either party, "
                                           "or cards only owned by one party.")
            return

        a, b, ser1, ser2 = self.bot.buxman.get_owners(serial_list_str)

        if len(ser1) > 9 or len(ser2) > 9:
            await ctx.message.channel.send("Maximum of 18 cards at a time! (Max 9 from each party).")
            return

        self.offered_cards.extend(serial_list)  # reserve cards for this trade only, now that we are past all
        # possible bail out points

        # a and b are ID's of the traders, probably put this on the image too one day
        img = self.make_trade_image(ser1, ser2)
        trade_name = str(int(time.time()))[-8:]
        img.save(f"/var/www/html/trades/{trade_name}.jpg")
        # self.bot.buxman.execute_trade(serial_list) don't actually execute it here, make the image
        await ctx.message.channel.send(f"http://raibu.streams.moe/trades/{trade_name}.jpg")
        m = await ctx.message.channel.send(f"{args[0]}, do you accept the trade? Click the react to accept or decline.")
        await m.add_reaction("\U00002705")
        await m.add_reaction("\U0000274C")

        self.waiting_for_response[m.id] = int(source_id)
        self.pending_trades[m.id] = serial_list_str
        self.trade_owners[m.id] = int(dest_id)  # only the user with dest_id can confirm the trade
        # need to convert to an int for internal discord use rather than in messages or the database
        print("added a trade, pending list is now")
        print(self.pending_trades)
        print("and added a trade owner:")
        print(self.trade_owners)

    def make_trade_image(self, serials1, serials2):

        def coordinate_generator(start, xinc, yinc, xthresh):

            x, y = start
            startx = x
            starty = y
            yield start
            for _ in range(8):
                x += xinc
                if x >= xthresh:
                    x = startx
                    y += yinc
                yield (x, y)

        width = 2400  # 3 per side horz
        height = ((max(len(serials1), len(serials2)) - 1) // 3 + 1) * 600
        black = Image.new("RGBA", (width, height), (0, 0, 0))

        x = 0
        y = 0

        arrow = Image.open("/home/rargh/cards/arrows.png")

        for h in zip(serials1, coordinate_generator((0, 0), 300, 600, 900)):
            x, coord = h
            full_name = f"/var/www/html/cards/{str(x).zfill(5)}.jpg"
            im = Image.open(full_name)
            black.paste(im, coord)

        for h in zip(serials2, coordinate_generator((1500, 0), 300, 600, 2400)):
            x, coord = h
            full_name = f"/var/www/html/cards/{str(x).zfill(5)}.jpg"
            im = Image.open(full_name)
            black.paste(im, coord)

        black.paste(arrow, (1000, int(height / 2) - 50))

        pic = black.convert("RGB")  # so we can save as jpg
        return pic




def setup(bot):

    bot.add_cog(Tcg(bot))
