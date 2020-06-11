from discord.ext import commands
import sqlite3
import re
import datetime
import threading
import asyncio
import json
from collections import defaultdict

""" Module for counting peros channel-specific """

"""
Require perobux_channels.json, which contains a list of channel ids, where perobux will be available.

Example:
[
	2134567812312,
	9876544444443
]

"""

emoteregex = re.compile(r"(?:[^\\]|\\\\|^)(<:[A-Za-z0-9]+:\d{9,}>)")

def getEmoteName(emoteTag):
	return emoteTag.split(":")[1]

class Perobux(commands.Cog):

	def __init__(self, bot):
		self.ic = {} # Initial compute timestamp
		self.chain = {}
		self.client = bot
		self.buxman = bot.buxman
		
		with open("perobux_channels.json", "r") as f:
			settings = json.load(f)
			self.channels = []
			for chsetting in settings:
				if chsetting["enabled"]:
					self.channels.append(chsetting["channel"])

	""" Compute perobucks. If start is none, do inital compute """
	async def compute_perobux(self, uid, channel, start = None):
		""" Get history in 200 message batches """
		oldest_message = None
		ch = channel.id
		self.buxman.set_perobux(uid, ch, 0)
		
		self.ic[(uid, ch)] = datetime.datetime.now()
		while True:
			msgs = await channel.history(limit=200, after = start, before = oldest_message, oldest_first = False).filter(lambda m: m.author.id == uid).flatten()
			if not msgs:
				break
			for msg in msgs:
				oldest_message = msg
				""" check for peros """
				peros = list(filter(lambda r: r.emoji.name.lower() == "poipero", filter(lambda r: not isinstance(r.emoji, str), msg.reactions)))
				if peros:
					self.buxman.adjust_perobux(uid, ch, peros[0].count)
				
				self.ic[(uid, ch)] = oldest_message.created_at
		
		self.ic.pop((uid, ch))
		
		# This needs to be at the end of any coroutine, that changes the perobux
		if (uid, ch) in self.chain:
			l = self.chain[(uid, ch)]
			if len(l) == 0:
				self.chain.pop(uid, ch)
			else:
				await l.pop(0)

	@commands.command()
	async def testbux(self, ctx):
		await self.compute_perobux(ctx.author.id, ctx.channel)
		await ctx.channel.send("Test Done!")

	async def change_perobux(self, uid, chid, amount):
		
		self.buxman.adjust_perobux(uid, chid, amount)
		
		# This needs to be at the end of any coroutine, that changes the perobux
		if (uid, chid) in self.chain:
			l = self.chain[(uid, chid)]
			if len(l) == 0:
				self.chain.pop(uid, chid)
			else:
				await l.pop(0)

	@commands.command()
	async def perobux(self, ctx):
		chid = ctx.channel.id
		uid = ctx.author.id
		
		if not chid in self.channels:
			await ctx.channel.send("Peros are not tracked in this channel")
			return
		
		if not self.buxman.perobux_exists(uid, chid):
			# I dont know if this is a good message.
			await ctx.channel.send("Calculating perobux...\nPerobux may change a bit from here on for a while.\n<@{0}>, Currently starting at 0".format(uid))
			await self.compute_perobux(uid, ctx.channel)
		else:
			await ctx.channel.send("<@{0}>, You currently have {1} perobux!".format(ctx.author.id, self.buxman.get_perobux(uid, chid)))

	async def on_reaction(self, payload, isAdd):
		amount = 1 if isAdd else -1
		# Get user id and channel id
		uid = payload.user_id
		chid = payload.channel_id
		channel = self.client.get_channel(chid)
		msg = await channel.fetch_message(payload.message_id)
		
		# Check if peroentry exists. If not, do nothing
		if not self.buxman.perobux_exists(uid, chid):
			return
		
		# Check that it is poipero
		if payload.emoji.name.lower() == "poipero":
			time = self.ic.get((uid, chid), None)
			if time is None:
				# Initial not running, simply adjust perobux
				self.buxman.adjust_perobux(uid, chid, amount)
			else:
				# Initial is running
				# Add adjust to chain, if it is on a message already covered by initial compute
				if msg.created_at > time:
					if (uid, chid) in self.chain:
						self.chain[(uid, chid)].append(change_perobux(uid, chid, amount))

	@commands.Cog.listener()
	async def on_raw_reaction_add(self, payload):
		await self.on_reaction(payload, True)

	@commands.Cog.listener()
	async def on_raw_reaction_remove(self, payload):
		await self.on_reaction(payload, False)

def setup(bot):
	bot.add_cog(Perobux(bot))
