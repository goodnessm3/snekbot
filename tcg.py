from discord.ext import commands
import random
import asyncio
from collections import defaultdict
from math import ceil
from PIL import Image, ImageFont, ImageDraw
import os
import time
import re
from prettytable import PrettyTable
from mydecorators import captcha, annoy

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
muon_uses = ["improve your chances for opening loot crates",
             "purchase additional loot crates (coming soon)",
             "use snek commands more often",
             "gain additional muon",
             "unlock secret snek functions",
             "enhance your card trades",
             "gain a bonus to damage",
             "diversify your portfolio",
             "access the secret snek channel",
             "impress girls",
             "gain additional loot crate chances",
             "augment loot crate probability",
             "change loot crate distribution",
             "gain additional snekbux",
             "buy items in the premium store",
             "unlock season passes",
             "access exclusive DLC",
             "access exclusive features",
             "buy a season pass"]

NPC_NAMES = ["Diogenes Pontifex (NPC)",
             "Millmillamin Swimwambli (NPC)",
             "William McGillian (NPC)",
             "Audifax O'Hanlon (NPC)",
             "Blast Hardcheese (NPC)"]

serial_verifier = re.compile('''^[0-9]{5}$''')
discord_id_verifier = re.compile('''^[0-9]{17,19}$''')  # can be 17 digits only if quite an old ID!

RANDOM_MIN = 7200
RANDOM_MAX = 86400
GACHA_LUCK_TIME = 180
CRATE_COST_TIME = 120
TRADE_TIMEOUT = 300
DEFAULT_AUCTION_LENGTH = 2  # hours


def time_print(flt):
    flt = int(flt)  # don't care about fractional seconds
    days = flt // 86400
    hours = flt % 86400 // 3600
    minutes = flt % 3600 // 60
    seconds = flt % 60

    return f"{days} days, {hours} hours, {minutes} minutes and {seconds} seconds"


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
        self.trade_proposers = {}  # message ID : proposer ID
        self.waiting_for_response = {}  # players can only have one open trade at a time to avoid MAJOR headaches
        # message id:player
        self.offered_cards = []  # ANY card from ANYONE that is currently offered for trade, make sure unique
        self.trade_timeouts = {}  # mapping of mid:timer handle
        self.cash_offer_proposers = {}  # message id: discord id
        self.cash_offer_recipients = {}  # message id: discord id
        self.cash_offer_quantities = {}  # tuples of (amount, serial no. of card)

        self.auctioned_cards = defaultdict(lambda: [])
        # a dict of serial number: [(price, bidder)], these tuples are used at end of auction
        self.card_auctioners = {}  # card serial : discord ID, so we know who to pay
        self.auction_times = {}  # serial: conclusion time

        self.bot.loop.call_later(10, lambda: asyncio.ensure_future(self.update_player_names()))
        self.bot.loop.call_later(12, lambda: asyncio.ensure_future(self.drop()))
        self.bot.loop.call_later(GACHA_LUCK_TIME, lambda: asyncio.ensure_future(self.decrement_counters()))
        self.bot.loop.call_later(CRATE_COST_TIME, lambda: asyncio.ensure_future(self.modulate_crate_cost()))
        self.bot.loop.call_later(15, lambda: asyncio.ensure_future(self.npc_auction()))

    def make_auction_menu(self):

        out = "The following cards are for sale. To bid, type 'snek bid [card serial] [amount]. To auction your own " \
              "cards, type 'snek auction [card serial] [minimum bid] [duration of auction in seconds].\n"
        for k, v in self.auctioned_cards.items():
            price = max([x[0] for x in v])
            nm = self.bot.buxman.serial_to_name(k)
            tm = int(self.auction_times[k] - time.time())
            out += f"#{k} - {nm}, current high bid: {price}, time remaining: {time_print(tm)}\n"

        if len(self.auctioned_cards.keys()) > 0:
            ''' #TODO
            pilimage = self.make_card_summary({"":list(self.auctioned_cards.keys())}, small=True)

            save_name = str(int(time.time()))[-8:]  # unique enough
            pilimage.save(f"/var/www/html/card_summaries/{save_name}.jpg")
            #pilimage.save(f"C:\\s\\tcg\\{save_name}.jpg")

            out += f"http://raibu.streams.moe/card_summaries/{save_name}.jpg"
            '''

        return out

    async def npc_auction(self):

        uid = 1  # dummy UID for NPC owners
        serial = self.bot.buxman.random_unowned_card()
        if not serial:
            return  # no cards avbl
        self.bot.buxman.add_card(uid, serial)  # assign it to the NPC owner now so it can't be gacha'd in the interim
        price = random.randint(1, 15) * 100
        duration = random.randint(1,5)
        dur_secs = float(duration * 86400)

        self.auctioned_cards[serial].append((int(price), ""))  # this is normally the price and the ID of the bidders
        self.card_auctioners[serial] = uid
        self.offered_cards.append(serial)
        self.auction_times[serial] = time.time() + dur_secs

        card_link = f"http://raibu.streams.moe/cards/{serial}.jpg"  # all cards are uploaded to /var/www and always avb

        await self.chan.send(f"{random.choice(NPC_NAMES)} is selling a card! Bidding starts at {price} "
                                       f"snekbux. The auction will last for {duration} days. {card_link}")
        print(self.auction_times)
        print(self.auctioned_cards)
        self.bot.loop.call_later(dur_secs, lambda: asyncio.ensure_future(self.conclude_auction(serial)))
        print(f"Scheduled completion of auction after {dur_secs}s of serial {serial}")

        next_auction = 86400 + random.randint(0, 86400)
        self.bot.loop.call_later(next_auction, lambda: asyncio.ensure_future(self.npc_auction()))

    @commands.command()
    async def auction(self, ctx, *args):

        """args are card serial, cost, time in seconds if wanted else default to 600 secs"""

        instructions = "Format of the command is snek auction [card serial] [min. price] [hours duration] "\
                        "e.g. to sell card 00123 for a minimum price of 500 snekbux, with a timeout "\
                        "of 2 hours, type 'snek auction 00123 500 2'."

        if not args:
            await ctx.message.channel.send(self.make_auction_menu())
            return

        if not (len(args) == 2 or len(args) == 3):
            await ctx.message.channel.send(instructions)
            return
        if not serial_verifier.match(args[0]):
            await ctx.message.channel.send(instructions)
            return
        if not re.match('''^[0-9]{1,9}$''', args[1]):
            await ctx.message.channel.send(instructions)
            return
        if len(args) == 2:
            args = list(args)  # so we can append the default time
            args.append(float(DEFAULT_AUCTION_LENGTH))  # add the FINISHING time of the auction
        if not re.match('''^[0-9]{2,5}$''', args[2]):  # the duration in hours
            await ctx.message.channel.send(instructions)
            return

        uid = ctx.message.author.id
        serial, price, duration = args
        duration = float(duration * 3600)  # internally use seconds

        if serial in self.offered_cards:
            await ctx.message.channel.send("That card is already involved in an auction or trade")
            return

        if not self.bot.buxman.verify_ownership_single(serial, uid):
            await ctx.message.channel.send("You don't appear to own that card.")
            return

        self.auctioned_cards[serial].append((int(price), ""))  # this is normally the price and the ID of the bidders
        self.card_auctioners[serial] = ctx.message.author.id
        self.offered_cards.append(serial)
        self.auction_times[serial] = time.time() + duration
        card_link = f"http://raibu.streams.moe/cards/{serial}.jpg"
        await ctx.message.channel.send(f"{ctx.message.author.mention} is selling a card! Bidding starts at {price} "
                                       f"snekbux. The auction will last for {time_print(duration)}. {card_link}")
        print(self.auction_times)
        print(self.auctioned_cards)
        self.bot.loop.call_later(duration, lambda: asyncio.ensure_future(self.conclude_auction(serial)))
        print(f"Scheduled completion of auction after {duration} of serial {serial}")

    @commands.command()
    async def bid(self, ctx, *args):

        try:
            serial, cost = args
        except:
            await ctx.message.channel.send(self.make_auction_menu())
            return

        if not serial_verifier.match(serial):
            await ctx.message.channel.send("Problem with serial number - command is 'snek bid [card serial] [amount]'")
            return
        if not serial in self.auctioned_cards.keys():
            await ctx.message.channel.send("That card is not up for auction!")
            return
        if not re.match('''[0-9]{1,8}''', cost):
            await ctx.message.channel.send("The price must be an integer number!")
            return

        cost = int(cost)
        funds = self.bot.buxman.get_bux(ctx.message.author.id)
        if funds < cost:
            await ctx.message.channel.send("You can't place a bid for more than your current snekbux balance.")
            return

        self.auctioned_cards[serial].append((cost, ctx.message.author.id))
        card_name = self.bot.buxman.serial_to_name(serial)
        tm = int(self.auction_times[serial] - time.time())

        highbid = max([x[0] for x in self.auctioned_cards[serial]])

        await ctx.message.channel.send(f"You bid {cost} snekbux on card #{serial}! ({card_name}). {time_print(tm)} seconds remain."
                                       f" The current high bid is {highbid} snekbux.")

    async def conclude_auction(self, serial):

        """Determine the high bidder, deduct the price paid and transfer the card"""

        bidder_list = self.auctioned_cards.pop(serial)  # pop because we will not need it again
        self.auction_times.pop(serial)
        self.offered_cards.remove(serial)
        payee = self.card_auctioners.pop(serial)

        bidder_list.sort(key=lambda x: x[0])
        bidder_list.reverse()  # so we have the big numbers first
        card_name = self.bot.buxman.serial_to_name(serial)
        card_link = f"http://raibu.streams.moe/cards/{serial}.jpg"
        print("Bidder list is:")
        print(bidder_list)
        if len(bidder_list) == 1:
            await self.chan.send(f"Nobody bid on {card_name}! {card_link}")
            return
        for x in bidder_list:
            amount, bidder = x
            if bidder == "":
                return  # this should never actually happen should be captured by above
                # actually it CAN happen, if the only submitted bids are LOWER than the reserve price
            bidder_name = f"<@{bidder}>"
            if payee == 1:
                payee_name = "an NPC"
            else:
                payee_name = f"<@{payee}>"
            funds = self.bot.buxman.get_bux(bidder)
            if funds < amount:
                await self.chan.send(f"{bidder_name} bid for {card_name} but no longer has enough funds to pay, "
                                     f"and is disqualified!")
                continue
            else:
                # the winning bidder can actually pay
                self.bot.buxman.adjust_bux(bidder, -amount)
                if not payee == 1:  # dummy value for NPCs
                    self.bot.buxman.adjust_bux(payee, amount)
                self.bot.buxman.add_card(bidder, serial)
                await self.chan.send(
                    f"{bidder_name} bought {card_name} from {payee_name} for {amount} snekbux! {card_link}")
                return
        await self.chan.send("Nobody won the auction!")

    async def timeout_trade(self, mid, chan):

        proposer = self.trade_proposers[mid]
        recipient = self.trade_owners[mid]
        await chan.send(f"<@{proposer}>, your trade with <@{recipient}> timed out!")
        self.conclude_trade(mid)

    def look_up_trade(self, msg):

        """Return the serial list of the trade which is asked for in message"""

        return self.pending_trades[msg]

    async def update_player_names(self):

        uids = self.bot.buxman.get_uids_with_cards()
        adict = {}
        for x in uids:
            try:
                mem = await self.chan.guild.fetch_member(x)
                adict[x] = mem.display_name
            except:
                print(f"user with id {x} was not found when updating display names")

        self.bot.buxman.update_card_trader_names(adict)
        self.bot.loop.call_later(86400, lambda: asyncio.ensure_future(self.update_player_names()))

    async def decrement_counters(self):

        # print("Decrementing counters")
        # print(self.random_chances)
        for k, v in self.random_chances.items():
            if v > 0:
                new_v = int(v/2)  # int 1/2 is zero btw
                self.random_chances[k] = new_v

        self.bot.loop.call_later(GACHA_LUCK_TIME, lambda: asyncio.ensure_future(self.decrement_counters()))

    async def modulate_crate_cost(self):

        # print("checking crate cost")
        for k, v in self.crate_cost.items():
            if v > 2500:
                self.crate_cost[k] = v-100
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
        if not card:
            await self.chan.send("All cards have been claimed! Wait for pchem to burn some!")
            return
        self.bot.buxman.add_card(uid, card)

        await channel.send(f"{payload.member.mention}, claimed the loot crate! It contained this card. Type 'snek cards'"
                                f"to see all your cards. http://raibu.streams.moe/cards/{card}.jpg")

        self.claimed = False

    def remove_cards_from_offered(self, als):

        print("self.offered cards was", self.offered_cards)
        print("removing", als)
        for x in als:
            self.offered_cards.remove(str(x).zfill(5))

        print("now self.offered cards is", self.offered_cards)

    def conclude_trade(self, mid):

        """Method to remove all the various references to the pending trade. This is either triggered by a player
        accepting or declining (in which case the timeout is cancelled) or this will be called BY the timeout anyway."""

        self.trade_timeouts[mid].cancel()  # cancelling the timeout once it's already fired has no effect
        self.trade_timeouts.pop(mid)  # now we can get rid of the reference entirely

        trd = self.look_up_trade(mid)

        self.pending_trades.pop(mid)
        self.trade_owners.pop(mid)
        self.waiting_for_response.pop(mid)
        self.trade_proposers.pop(mid)
        self.remove_cards_from_offered(trd)

        print("conclude trade function ran")
        # you know, this is probably the time to wrap all these variables up into a new class

    async def cleanup_cash_offer(self, mid):

        try:
            self.cash_offer_proposers.pop(mid)
        except KeyError:
            return  # offer already got accepted/denied
        # TODO: cancel this nicely using the handle from the original scheduled task when I write this properly LMAO
        self.cash_offer_recipients.pop(mid)
        qty, serial = self.cash_offer_quantities.pop(mid)
        self.offered_cards.remove(serial)

    async def conclude_cash_offer(self, mid):

        try:
            value, serial = self.cash_offer_quantities[mid]
        except KeyError:
            return  # offer probably already timed out
        recipient = self.cash_offer_recipients[mid]
        purchaser = self.cash_offer_proposers[mid]
        await self.cleanup_cash_offer(mid)  # remove it from all the lists regardless

        purchaser_bux = self.bot.buxman.get_bux(purchaser)
        if purchaser_bux < value:
            return False, "purchaser didn't have sufficient funds"

        if not self.bot.buxman.verify_ownership_single(serial, recipient):
            return False, "card is now owned by someone else"
            # the proposee doesn't own the card any more

        self.bot.buxman.adjust_bux(recipient, value)
        self.bot.buxman.adjust_bux(purchaser, -1 * value)
        self.bot.buxman.add_card(purchaser, serial)

        return True, f"<@{purchaser}> bought a card from <@{recipient}> for {value} snekbux! http://raibu.streams.moe/cards/{serial}.jpg"

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):

        chan = self.bot.get_channel(payload.channel_id)
        mid = payload.message_id

        if payload.member == self.bot.user:
            return  # ignore own reaction add at start

        if payload.emoji.name == "\U00002705":  # checkmark
            try:
                expected_id = self.trade_owners[mid]
                proposer = self.trade_proposers[mid]  # note, duplicated below
            except KeyError:
                return
            if not payload.member.id == expected_id:
                print("Ignoring a reaction from the wrong person")
                return

            trd = self.look_up_trade(mid)
            await chan.send(f"<@{proposer}>, your trade with {payload.member.mention} trade was successful!")
            self.bot.buxman.execute_trade(trd)
            self.conclude_trade(mid)

        elif payload.emoji.name == "\U0000274C":  # cross
            try:
                expected_id = self.trade_owners[mid]
                proposer = self.trade_proposers[mid]  # note, duplicated above
            except KeyError:
                return
            if payload.member.id == expected_id:  # recipient is accepting or rejecting
                trd = self.look_up_trade(mid)
                await chan.send(f"<@{proposer}>, {payload.member.mention} has rejected your trade!")
                self.conclude_trade(mid)
            elif payload.member.id == proposer:  # proposer also has the option to cancel using the react
                await chan.send(f"<@{proposer}> withdrew the trade offer with <@{expected_id}>!")
                self.conclude_trade(mid)

        elif payload.emoji.name == "\U0001f4e6":  # package
            self.claimed = True   # try to deal with 2 users clicking it in a small window,
            await self.on_reaction(payload)

        elif payload.emoji.name == "\U0001F44D":  # thumbs up
            try:
                expected_recipient = self.cash_offer_recipients[mid]
            except KeyError:
                return
            if payload.member.id == expected_recipient:  # correct person reacting
                proposer = self.cash_offer_proposers[mid]
                success, reason = await self.conclude_cash_offer(mid)
                if not success:
                    await chan.send(f"<@{proposer}>, your offer failed because: {reason}!")
                else:
                    await chan.send(reason)
            else:
                return

        elif payload.emoji.name == "\U0001F44E":  # thumbs down
            try:
                expected_recipient = self.cash_offer_recipients[mid]
            except KeyError:
                return
            if payload.member.id == expected_recipient:  # correct person reacting
                try:
                    proposer = self.cash_offer_proposers[mid]
                except KeyError:
                    return
                await chan.send(f"<@{proposer}>, your offer was rejected! Too bad!")
                await self.cleanup_cash_offer(mid)
            else:
                return

    @commands.command()
    @annoy
    async def cards(self, ctx):

        uid = ctx.message.author.id
        crds = self.bot.buxman.get_cards(uid)

        await ctx.message.channel.send(
            f"Go here to see your card collection: http://raibu.streams.moe/card_summary?user={uid}")

        if len(crds) > 100:
            await ctx.message.channel.send("Too many cards to generate a thumbnail.")
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
        #pilimage.save(f"C:\\s\\tcg\\{uid}.jpg")  # for testing

        await ctx.message.channel.send(f"http://raibu.streams.moe/card_summaries/{save_name}.jpg")

    def make_card_summary(self, files, small=False):

        """Expects a dictionary of series:files so they can be grouped appropriately"""


        if small:
            width = min(3000, len(files[""])*300)  # this dict is not keyed by series, just by empty string
        else:
            width = 3000

        height = 600 * self.calc_height(files)  # how many rows of 10?
        black = Image.new("RGB", (width, height), (0, 0, 0))

        x = 0
        y = 0
        done = []  # for deduplication in case for some reason a number appears multiple times

        for k, v in files.items():  # key is series, v is list of files
            if k in done:
                continue
            else:
                done.append(k)
                for q in v:
                    # TODO
                    continue  # defuse opening of images below that won't be found
                    image_path = f"/var/www/html/cards/{q}.jpg"
                    im = Image.open(image_path)
                    black.paste(im, (x, y))
                    x += 300
                    if x >= 3000:
                        x = 0
                        y += 600

        if width > 1000:
            return black.resize((1000, ceil(height / 3)))
        else:
            return black

    def calc_height(self, files):

        tot = 0
        for v in files.values():
            tot += len(v)
        return ceil(tot / 10)

    @commands.command()
    @captcha
    @annoy
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
            if not card:
                await ctx.message.channel.send("All cards have been claimed! Wait for pchem to burn some!")
                return
            self.bot.buxman.add_card(uid, card)

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

        self.crate_cost[uid] =  self.crate_cost[uid] + 200  # slowly ramp up cost and have it decay back down

    # @commands.command() todo - image generation for trade proposal
    async def trade(self, ctx, *args):

        if ctx.message.author.id in self.waiting_for_response.values():
            await ctx.message.channel.send("You can only have a single trade open at one time.")
            return

        if not args:
            await ctx.message.channel.send("go to http://raibu.streams.moe/snekstore/trade_setup to set up a trade.")
            return

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

        # --- the trade is definitely going ahead now --- #

        self.offered_cards.extend(serial_list)  # reserve cards for this trade only, now that we are past all
        # possible bail out points

        # a and b are ID's of the traders, probably put this on the image too one day
        img = self.make_trade_image(ser1, ser2)
        trade_name = str(int(time.time()))[-8:]
        img.save(f"/var/www/html/trades/{trade_name}.jpg")  # todo!!!

        await ctx.message.channel.send(f"http://raibu.streams.moe/trades/{trade_name}.jpg")
        m = await ctx.message.channel.send(f"{args[0]}, do you accept the trade? Click the react to accept or decline."
                                           f" The proposer can also cancel the trade by clicking the react."
                                           f" The trade will automatically time out after 5 minutes.")
        await m.add_reaction("\U00002705")
        await m.add_reaction("\U0000274C")

        self.trade_proposers[m.id] = ctx.message.author.id  # remember who proposed the trade
        self.waiting_for_response[m.id] = int(source_id)  # for checking the accept/reject react comes from right person
        self.pending_trades[m.id] = serial_list_str
        self.trade_owners[m.id] = int(dest_id)  # only the user with dest_id can confirm the trade
        # need to convert to an int for internal discord use rather than in messages or the database
        handle = self.bot.loop.call_later(TRADE_TIMEOUT,
                                 lambda: asyncio.ensure_future(self.timeout_trade(m.id, ctx.message.channel)))
        self.trade_timeouts[m.id] = handle  # so we can look up the handle and cancel the scheduled task
        # put a pending timeout regardless. Either the trade times out, or acceptance/refusal concludes it anyway.
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
        #arrow = Image.open("C:\\s\\tcg\\arrows.png")

        for h in zip(serials1, coordinate_generator((0, 0), 300, 600, 900)):
            x, coord = h
            full_name = f"/var/www/html/cards/{str(x).zfill(5)}.jpg"
            #full_name = f"C:\\s\\tcg\\cards\\{str(x).zfill(5)}.jpg"
            im = Image.open(full_name)
            black.paste(im, coord)

        for h in zip(serials2, coordinate_generator((1500, 0), 300, 600, 2400)):
            x, coord = h
            full_name = f"/var/www/html/cards/{str(x).zfill(5)}.jpg"
            #full_name = f"C:\\s\\tcg\\cards\\{str(x).zfill(5)}.jpg"
            im = Image.open(full_name)
            black.paste(im, coord)

        black.paste(arrow, (1000, int(height / 2) - 50))

        pic = black.convert("RGB")  # so we can save as jpg
        return pic

    @commands.command()
    async def card_search(self, ctx, *qry):

        qry = " ".join(qry)  # either search for one thing or they want a thing with a space in it
        res = self.bot.buxman.card_search(qry)
        restable = PrettyTable()
        restable.field_names = ["Serial", "Card owner", "Character", "Series"]
        for q in res[:10]:
            qq = list(q)
            qq[0] = str(qq[0]).zfill(5)
            restable.add_row(qq)

        if len(res) > 10:
            await ctx.message.channel.send(f"```{restable}\nPlus {len(res)-10} results omitted```")
        else:
            await ctx.message.channel.send(f"```{restable}```")

        await ctx.message.channel.send("Also go to http://raibu.streams.moe/card_search to more easily view cards!")

    @commands.command()
    @annoy
    async def burn(self, ctx, *args):

        uid = ctx.message.author.id

        print(args)

        for x in args:
            if not serial_verifier.match(x):
                await ctx.message.channel.send("Type 'snek burn' followed by a list of 5-digit card serial numbers.")
                return

        if not self.bot.buxman.verify_ownership(args, uid):
            await ctx.message.channel.send("You can only burn your own cards, doofus!")
            return

        dict_for_layout = {"blank": args}
        print(dict_for_layout)
        #pict = self.make_card_summary(dict_for_layout) #todo!!!
        #save_name = str(int(time.time()))[-8:]  # unique enough
        #pict.save(f"/var/www/html/card_summaries/{save_name}.jpg")
        #picturl = f"http://raibu.streams.moe/card_summaries/{save_name}.jpg"

        reason = random.choice(muon_uses)
        mu = len(set(args)) * 12  # set to stop people being cheeky and claiming multiple times
        self.bot.buxman.adjust_muon(ctx.message.author.id, mu)
        for q in args:
            self.bot.buxman.remove_card(q)

        msg = f"{ctx.message.author.mention}, you burned these cards, returning them to the pool! You have gained {mu}" \
              f" muon. Muon can be used to {reason}! No images generated right now, just use your imagination."

        await ctx.message.channel.send(msg)

    @commands.command()
    async def muon(self, ctx):

        uid = ctx.message.author.id
        mu = self.bot.buxman.get_muon(uid)

        await ctx.message.channel.send(f"{ctx.message.author.mention}, you have {mu} muon. Type snek muon_store to"
                                       f" access muon functions!")

    @commands.command()
    async def muon_store(self, ctx):

        await ctx.message.channel.send("Feature coming soon:tm:")

    @commands.command()
    async def offer(self, ctx, amount, serial):

        instructions = """Format of the command is 'snek offer [amount of snekbux] [card serial] to offer to buy the
        card from the card's owner."""

        if not re.match('''^[0-9]{1,9}$''', amount):
            await ctx.message.channel.send(instructions)
            return

        if not serial_verifier.match(serial):
            await ctx.message.channel.send(instructions)
            return

        if serial in self.offered_cards:
            await ctx.message.channel.send("This card is currently involved in another trade proposal.")
            return

        amount = int(amount)

        purchaser_funds = self.bot.buxman.get_bux(ctx.message.author.id)
        if purchaser_funds < amount:
            await ctx.message.channel.send("You can't offer more snekbux than you have! Doofus!")
            return

        try:
            owner, z, x, y = self.bot.buxman.get_owners([serial])
        except KeyError:  # serial doesn't exist
            await ctx.message.channel.send("Card serial number doesn't exist!")
            return

        if owner is None:
            await ctx.message.channel.send("Nobody owns that card!")
            return

        if owner == ctx.message.author.id:
            await ctx.message.channel.send("You can't buy a card from yourself, numbnuts!")
            return

        mention = f"<@!{owner}>"

        m = await ctx.message.channel.send(f"{mention}, {ctx.message.author.mention} has offered you {amount} snekbux "
                                       f"to buy your card #{serial}. Do you acccept? (Will time out after 2 hours) "
                                       f"http://raibu.streams.moe/cards/{serial}.jpg")

        await m.add_reaction("\U0001F44D")
        await m.add_reaction("\U0001F44E")
        self.offered_cards.append(serial)
        self.cash_offer_proposers[m.id] = ctx.message.author.id
        self.cash_offer_recipients[m.id] = owner
        self.cash_offer_quantities[m.id] = (amount, serial)

        self.bot.loop.call_later(7200, lambda: asyncio.ensure_future(self.cleanup_cash_offer(m.id)))


async def setup(bot):

    await bot.add_cog(Tcg(bot))
