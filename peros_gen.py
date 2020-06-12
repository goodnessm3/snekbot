import discord
from discord.ext import commands
import json
import datetime
from sys import exit, argv
from user_stats import Manager
import math

"""
Requires the same files as snek2.py
Additionally needs: peros_gen_channels.json
which contains the channels, which will be calculated when init_peros is run
"""

settings = {}  # overwritten by loading functions below

if len(argv) > 1 and argv[1] == "-t":
	with open("settings_testing.json", "rb") as f:
		settings = json.load(f)
	bot = commands.Bot(command_prefix=["!"])
else:
	with open("settings.json", "rb") as f:
		settings = json.load(f)
	bot = commands.Bot(command_prefix=["!"])

printch = int(argv[1 if argv[1] != "-t" else 2])
channels = list(map(int, argv[2 if argv[1] != "-t" else 3: len(argv)]))

def is_owner(ctx):
	return ctx.message.author.id == bot.settings["owner_id"]

@bot.event
async def on_ready():
	print_channel = bot.get_channel(printch)
	await print_channel.send("Started calculating peros for {0} channels".format(len(channels)))
	starttime = datetime.datetime.now()
	msgcount = 0
	""" For each channel in peros_gen_channels, look for poipero reaction and adjust entry for uid, chid """
	for chid in channels:
		channel = bot.get_channel(chid)
		msgcount += await compute_peros(channel)
	
	dt = datetime.datetime.now() - starttime 
	timestr = ""
	timenames = ("days", "hours", "minutes", "seconds")
	timevalues = (dt.days, math.floor(dt.seconds / 3600), math.floor(dt.seconds / 60), dt.seconds % 60)
	for i, _ in enumerate(timenames):
		if timevalues[i] != 0:
			timestr += "{0:.0f} {1} ".format(timevalues[i], timenames[i])
	await print_channel.send("Finished calculating peros for {0} messages in {1}".format(msgcount, timestr))
	await bot.logout()

""" Compute perobucks. If start is none, do inital compute """
async def compute_peros(channel):
	""" Get history in 200 message batches """
	oldest_message = None
	ch = channel.id
	bot.buxman.set_all_peros(ch, 0)
	msgcount = 0
	while True:
		msgs = await channel.history(limit=200,before = oldest_message, oldest_first = False).flatten()
		if not msgs:
			return msgcount
		msgcount += len(msgs)
		for msg in msgs:
			uid = msg.author.id
			oldest_message = msg
			""" check for peros """
			peros = list(filter(lambda r: r.emoji.name.lower() == "poipero", filter(lambda r: not isinstance(r.emoji, str), msg.reactions)))
			if peros:
				bot.buxman.adjust_peros(uid, ch, peros[0].count)

bot.buxman = Manager(bot)
bot.settings = settings

bot.run(bot.settings["client_secret"])