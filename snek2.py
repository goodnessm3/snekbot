import discord
from discord.ext import commands
import json
import random
import sys
import datetime
import slot_machine
from iskill import is_kill
import re
from user_stats import Manager
import clean_text as ct
import pronouns
from cleverwrap import CleverWrap
import os
import subprocess
import nick

prefixes = ["?", "Snek ", "snek ", "SNEK "]   # note trailing space in name prefix
settings = {}  # overwritten by loading functions below
updating = False  # global variable to determine whether snek is being restarted to update

if len(sys.argv) > 1 and sys.argv[1] == "-t":
    with open("settings_testing.json", "rb") as f:
        settings = json.load(f)
    bot = commands.Bot(command_prefix=["!"])  # testing bot only responds to !-prefixed cmds
        
else:
    with open("settings.json", "rb") as f:
        settings = json.load(f)
    bot = commands.Bot(command_prefix=prefixes)


bot.buxman = Manager(bot)
bot.settings = settings
# bot.sesh = aiohttp.ClientSession(loop=bot.loop)
# this has been moved to an "async with" statement in the gelbooru cog so that the
# session is created inside an async function
cb = CleverWrap(settings["cleverbot_token"])
bot.last_chat = datetime.datetime.now()  # to determine when to reset the cleverbot interaction
bot.cbchannels = settings["cleverbot_channels"]

with open("snektext.json", "r") as f:
    bot.text = json.load(f)


def is_owner(ctx):
    return ctx.message.author.id == bot.settings["owner_id"]


class NickFind():

    """This needs to appear like a compiled regex object with a findall method"""

    @staticmethod
    def findall(astr):

        admonitions = ["How about you stop changing your name?",
                       "You don't have to change your name all the time, you know.",
                       "Instead of changing your name, just b urself!",
                       "Maybe you should pick one name and stick with it, doofus.",
                       "I've run out of nicknames.",
                       "Why don't you just pick one name and stick with it?",
                       "How about you stop confusing people by changing your name every day?",
                       "You know what would be really cool? Choosing one name and sticking with it!",
                       "I don't have time for this nonsense any more.",
                       "Just b urself my man.",
                       "Go ask your mother."]

        if "give" in astr and "me" in astr and "nickname" in astr:
            # I'm not pro enough to work out the regex for this
            return random.choice(admonitions)
            # disabling this "feature" for now
            # chance = random.randint(0, 10)
            # if chance > 4:
                # return nick.get_nick()
            # elif chance > 2:

            # else:
                # return None
        else:
            return None


async def on_yeet(msg, _):

    b = bot.buxman.get_bux(msg.author.id)
    if b > 10:
        await msg.channel.send('''lmao, "yeet" XDDDD (you have been fined 10 snekbux)''')
        bot.buxman.adjust_bux(msg.author.id, -10)
    else:
        await msg.channel.send('''lmao, "yeet" XDDDD''')


async def on_bane(msg, _):

    await msg.channel.send("for you.")


async def on_kill(msg, *args):

    match = ct.discordRemoveUnescapedFormatting(args[0][0])
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


@bot.command()
@commands.check(is_owner)
async def pull(ctx):

    res = subprocess.run(["git", "pull"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=10**8)
    info = res.stdout.decode("utf-8")
    error = res.stderr.decode("utf-8")
    await ctx.message.channel.send(info + "\n" + error)


@bot.command()
@commands.check(is_owner)
async def update(ctx):

    global updating
    updating = True
    try:
        await ctx.message.channel.send("Restarting...")
        await bot.close()
    except Exception as e:
        await ctx.message.channel.send(str(e))


@bot.event
async def on_ready():

    print("Logged in as {0.user}".format(bot))
    # load default cogs
    for cog in ["plant", "gelbooru", "peros", "niko", "remind", "daily", "most_peroed", "game"]:
        bot.load_extension(cog)
    print("loaded default cogs")

@bot.command()
async def test_cmd(ctx):

    await ctx.message.channel.send("Test function")


@bot.command()
async def logout(ctx):

    """increments the accumulator"""

    if ctx.message.author.id == bot.settings["owner_id"]:
        print("logging out")
        await ctx.message.channel.send("Bye bye")
        await bot.close()

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

    thing = pronouns.reversePronouns(thing)

    if random.randint(0, 3) == 2:
        thing = pronouns.asSubject(thing)
        await ctx.message.channel.send("I rate %s %i/10" % (thing, random.randint(0, 10)))
    else:

        join = pronouns.nounIs(thing)

        rating = random.choice(bot.text["ratings"])
        qual = random.choice(bot.text["qualifiers"])

        await ctx.message.channel.send("I think %s %s %s %s." % (thing, join, qual, rating))


@bot.command()
async def bux(ctx):

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
    else:
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
        out += "You lost..."
    else:
        out += "You won {} snekbux!".format(payout + amount)

    tax = 0
    if (bux + payout) % 100 == 0 and not (bux + payout) == 0 and random.randint(0, 4) == 2:
        # forbid people obtaining a nice round number of snekbux
        tax = random.randint(-50,-1)
        while tax % 10 == 0:
            tax = random.randint(-50,-1)
        taxes = ["snek maintenance", "snek developer", "anime girl", "sissy boy", "big chungus", "internet",
                 "snek slots", "C# rewrite fund", "solo sideboob",
                 "watermelon solo swimsuit", "gelbooru"]
        reason = random.choice(taxes)
        out += f" and unfortunately, {abs(tax)} snekbux must be deducted for {reason} tax."

    out += f" You now have {bux + payout + tax} snekbux."

    bot.buxman.adjust_bux(uid, payout + tax)

    await ctx.message.channel.send(out)


@bot.command()
async def xmas(ctx):
    now = datetime.datetime.now()
    now = datetime.datetime(now.year, now.month, now.day)
    christmas = datetime.datetime(now.year, 12, 25)
    if now > christmas:  # christmas is already passed. Get the time until next christmas
        christmas = datetime.datetime(now.year+1, 12, 25)
    
    delta = christmas - now

    await ctx.message.channel.send("{} days until Christmas!".format(delta.days))


bot.regexes = {re.compile('''a big [^\s]+\Z'''): on_bane,
               re.compile('''((?!is kill).*) is kill\.*\Z'''): on_kill,
               re.compile('''yeet'''): on_yeet,
               }


@bot.event
async def on_message(message):

    cont = message.content
    ctx = await bot.get_context(message)

    if message.channel.id in bot.cbchannels:
        if ctx.command is None and message.content.startswith(tuple(prefixes)):
            # the message is addressed to snek but doesn't contain a command, send the text to cleverbot for a response
            q = NickFind.findall(message.content)
            print(q)
            if q:
                await message.channel.send(q)
                return
            now = datetime.datetime.now()
            if (now - bot.last_chat).seconds > 500:
                cb.reset()  # don't resume an old conversation, start a new one
            async with message.channel.typing():
                response = cb.say(message.content[5:])  # strip off "snek "
            await message.channel.send(response)  # probably bad that this API is not async
            bot.last_chat = datetime.datetime.now()
            return  # don't also try to process it as a command

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

if updating:  # this code runs when the bot loop exits
    os.execl(sys.executable, "python3.6", __file__)

