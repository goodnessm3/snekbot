import discord
from discord.ext import commands
import aiohttp
import json
import random
import asyncio
from async_timeout import timeout
from itertools import cycle
import getpass
from sys import exit, argv
from collections import defaultdict
import time
import slot_machine
from iskill import is_kill
import re
from user_stats import Manager

prefixes = ["?", "Snek ", "snek ", "SNEK "]   # note trailing space in name prefix
settings = {}  # overwritten by loading functions below

if len(argv) > 1 and argv[1] == "-t":
    with open("settings_testing.json", "rb") as f:
        settings = json.load(f)
    bot = commands.Bot(command_prefix=["!"])  # testing bot only responds to !-prefixed cmds
        
else:
    with open("settings.json", "rb") as f:
        settings = json.load(f)
    bot = commands.Bot(command_prefix=prefixes)


bot.buxman = Manager(bot)
bot.settings = settings
bot.sesh = aiohttp.ClientSession(loop=bot.loop)

with open("snektext.json", "r") as f:
    bot.text = json.load(f)

# load default cogs
for cog in ["plant", "gelbooru"]:
    bot.load_extension(cog)

def is_owner(ctx):
    return ctx.message.author.id == bot.settings["owner_id"]


async def on_yeet(msg, *args):

    b = bot.buxman.get_bux(msg.author.id)
    if b > 10:
        await msg.channel.send('''lmao, "yeet" XDDDD (you have been fined 10 snekbux)''')
        bot.buxman.adjust_bux(msg.author.id, -10)
    else:
        await msg.channel.send('''lmao, "yeet" XDDDD''')


async def on_bane(msg, *args):

    await msg.channel.send("for you.")


async def on_kill(msg, *args):

    match = args[0][0]
    out = is_kill(match)
    await msg.channel.send(out)


@bot.command()
@commands.check(is_owner)
async def load(ctx, extension):

    try:
        bot.load_extension(extension)
        await ctx.message.channel.send('''Loaded {}'''.format(extension))
    except Exception as e:
        await ctx.message.channel.send(str(e))


@bot.command()
@commands.check(is_owner)
async def unload(ctx, extension):

    try:
        bot.unload_extension(extension)
        await ctx.message.channel.send('''Unloaded {}'''.format(extension))
    except Exception as e:
        await ctx.message.channel.send(str(e))


@bot.command()
@commands.check(is_owner)
async def reload(ctx, extension):

    try:
        bot.unload_extension(extension)
        bot.load_extension(extension)
        await ctx.message.channel.send('''Reloaded {}'''.format(extension))
    except Exception as e:
        await ctx.message.channel.send(str(e))


@bot.event
async def on_ready():
    print("Logged in as {0.user}".format(bot))


@bot.command()
async def logout(ctx):

    """increments the accumulator"""

    if ctx.message.author.id == bot.settings["owner_id"]:
        print("logging out")
        await ctx.message.channel.send("Bye bye")
        await bot.logout()

    else:
        await ctx.message.channel.send("No, YOU logout.")


@bot.command()
async def choose(ctx, *rest):

    """chooses a thing"""

    choices = " ".join(rest).split(" or ")
    await ctx.message.channel.send(random.choice(choices))


bot.birb_count = 0

@bot.command()
async def birb(ctx):

    """posts a nice birb"""

    bot.birb_count += 1
    if bot.birb_count == 10:
        filename = "otherbirb.jpg"
    else:
        filename = "birb{}.jpg".format(random.randint(1, 3))
    await ctx.message.channel.send("", file=discord.File(filename))


@bot.command()
async def rate(ctx, *args):

    """rates a thing"""
    thing = " ".join(args)

    thing = thing.replace("your ", "asqw ")
    thing = thing.replace("my ", "your ")
    thing = thing.replace("asqw ", "my ")

    if random.randint(0, 3) == 2:
        await ctx.message.channel.send("I rate %s %i/10" % (thing, random.randint(0, 10)))
    else:

        join = "is"  # surround with plural checking code

        rating = random.choice(bot.text["ratings"])
        qual = random.choice(bot.text["qualifiers"])

        await ctx.message.channel.send("I think %s %s %s %s." % (thing, join, qual, rating))


@bot.command()
async def bux(ctx):

    uid = str(ctx.message.author.id)
    bux = bot.buxman.get_bux(ctx.message.author.id)
    await ctx.message.channel.send("{}, you have {} snekbux.".format(ctx.message.author.mention, bux))

@bot.event
async def on_command_error(ctx, error):

    await ctx.message.channel.send(error)


@bot.command()
async def slots(ctx, *args):

    uid = str(ctx.message.author.id)
    bux = bot.buxman.get_bux(uid)

    if bux < 50:
        await ctx.message.channel.send('''You need to gamble at least 50 snekbux!'''
                                       '''You have {}.'''
                                       '''(type "snek daily" to obtain snekbux)'''.format(bux))
        return

    if not args:
        amount = 50
    if args:
        try:
            amount = int(args[0])
        except ValueError:
            await ctx.message.channel.send("Please enter an integer amount of snekbux to gamble, default is 50.")
            return

    if amount < 50:
        await ctx.message.channel.send('''You need to gamble at least 50 snekbux!''')
        return

    if amount < 0:
        await ctx.message.channel.send('''For attempting to bet a negative amount of snekbux,'''
                                       '''you have been fined 100 snekbux!''')
        bot.buxman.adjust_bux(uid, -100)
        return

    if amount > bux:
        await ctx.message.channel.send('''You can't gamble more than you have! You have {} snekbux.'''.format(bux))
        return

    symbols, payout = slot_machine.gamble(amount)
    emojis = [chr(int(x, 16)) for x in symbols]
    out = '''Gambling {} snekbux...\n{}{}{}\n'''.format(amount, *emojis)
    if payout < 0:
        out += "You lost... you now have {} snekbux.".format(bux + payout)
    else:
        out += "You won {} snekbux! You now have {} snekbux.".format(payout + amount, bux + payout)

    bot.buxman.adjust_bux(uid, payout)

    await ctx.message.channel.send(out)


@bot.command()
async def xmas(ctx):

    then = time.mktime(time.strptime("25 Dec 19", "%d %b %y"))
    now = time.time()
    delta = then - now
    days = delta / 86400
    tosay = int(round(days, 0))

    await ctx.message.channel.send("{} days until Christmas!".format(tosay))


bot.regexes = {re.compile('''a big [^\?^\s]+\Z'''): on_bane,
               re.compile('''(\S*) is kill\Z\.*'''): on_kill,
               re.compile('''yeet'''): on_yeet
               }


@bot.event
async def on_message(message):

    cont = message.content

    if random.randint(0, 150) == 13:
        await message.add_reaction(chr(127814))  # eggplant

    if message.author == bot.user:
        return

    for reg, func in bot.regexes.items():
        ma = reg.findall(cont)
        if ma:
            await func(message, ma)
            return

    await bot.process_commands(message)


print(discord.__version__)
bot.run(bot.settings["client_secret"])
