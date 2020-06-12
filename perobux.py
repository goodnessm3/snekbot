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
perosargs = re.compile(r"(?:.+peros )(.*)")

def getEmoteName(emoteTag):
	return emoteTag.split(":")[1]

class Perobux(commands.Cog):

	def __init__(self, bot):
		self.client = bot
		self.buxman = bot.buxman
		
		with open("perobux_channels.json", "r") as f:
			self.channels = json.load(f)

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
	async def peros(self, ctx):
		args = perosargs.match(ctx.message.content)
		if not args is None:
			args = args.group(1)
		else:
			args = ""
		
		chid = ctx.channel.id
		uid = ctx.author.id
		
		if args == "here" or args == "h":
			if not chid in self.channels:
				await ctx.channel.send("Peros are not tracked in this channel.")
				return
			if not self.buxman.perobux_exists(uid, chid):
				self.buxman.set_perobux(uid, chid, 0)
			
			await ctx.channel.send("<@{0}>, You currently have {1} perobux in this channel!".format(ctx.author.id, self.buxman.get_perobux(uid, chid)))
			return
		
		await ctx.channel.send("<@{0}>, You currently have {1} perobux!".format(ctx.author.id, self.buxman.get_perobux_for_channels(uid, self.channels)))

	async def on_reaction(self, payload, isAdd):
		amount = 1 if isAdd else -1
		# Get user id and channel id
		uid = payload.user_id
		chid = payload.channel_id
		if not chid in self.channels:
			return
		
		channel = self.client.get_channel(chid)
		msg = await channel.fetch_message(payload.message_id)
		
		# Check if peroentry exists. If not, do nothing
		if not self.buxman.perobux_exists(uid, chid):
			if not isAdd:
				return
			self.buxman.set_perobux(uid, chid, 0)
		
		# Check that it is poipero
		if payload.emoji.name.lower() == "poipero":
			self.buxman.adjust_perobux(uid, chid, amount)

	@commands.Cog.listener()
	async def on_raw_reaction_add(self, payload):
		await self.on_reaction(payload, True)

	@commands.Cog.listener()
	async def on_raw_reaction_remove(self, payload):
		await self.on_reaction(payload, False)

def setup(bot):
	bot.add_cog(Perobux(bot))
