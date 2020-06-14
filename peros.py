from discord.ext import commands
import sqlite3
import re
import datetime
import threading
import asyncio
import json
from collections import defaultdict
import subprocess

""" Module for counting peros channel-specific """

"""
Requires peros_channels.json, which contains a list of channel ids, where peros will be counted.

Example:
[
	2134567812312,
	9876544444443
]

"""

PERO_CHANNELS_FILE = "peros_channels.json"

def is_owner(ctx):
	return ctx.message.author.id == ctx.cog.settings["owner_id"]

emoteregex = re.compile(r"(?:[^\\]|\\\\|^)(<:[A-Za-z0-9]+:\d{9,}>)")
channelregex = re.compile(r"(?:[^\\]|\\\\|^)<#([0-9]+)>")

def get_channel_id(strid):
	match = channelregex.match(strid)
	if not match is None:
		return match.group(1)
	else:
		return strid

class Peros(commands.Cog):

	def __init__(self, bot):
		self.client = bot
		self.buxman = bot.buxman
		self.settings = bot.settings
		
		
		try:
			with open(PERO_CHANNELS_FILE, "r") as f:
				self.channels = json.load(f)
		except:
			self.channels = []

	@commands.group()
	async def peros(self, ctx):
		if not ctx.invoked_subcommand is None:
			return
		chid = ctx.channel.id
		uid = ctx.author.id
		peros = self.buxman.get_peros_for_channels(uid, self.channels)
		if peros == 1:
			await ctx.channel.send("You currently have 1 pero!")
		else:
			await ctx.channel.send("You currently have {0} peros!".format(peros))

	@peros.command()
	async def here(self, ctx):
		chid = ctx.channel.id
		uid = ctx.author.id
		if not chid in self.channels:
			await ctx.channel.send("Peros are not tracked in this channel.")
			return
		if not self.buxman.peros_exists(uid, chid):
			self.buxman.set_peros(uid, chid, 0)
		
		peros = self.buxman.get_peros(uid, chid)
		if peros == 1:
			await ctx.channel.send("You currently have 1 pero in this channel!")
		else:
			await ctx.channel.send("You currently have {0} peros in this channel!".format(peros))

	@peros.command()
	@commands.check(is_owner)
	async def init(self, ctx, *chs):
		chids = list(map(get_channel_id, chs))
		subprocess.Popen(self.settings["python"] + " peros_gen.py " + str(ctx.channel.id) + " " + (" ".join(chids)), shell=True)

	@peros.command(name="in")
	async def _in(self, ctx, channel):
		chid = ctx.channel.id
		if not channel is None:
			match = channelregex.match(channel)
			if not match is None:
				chid = int(match.group(1))

		if not chid in self.channels:
			await ctx.channel.send("Peros are not tracked in that channel.")
			return
		uid = ctx.author.id
		peros = self.buxman.get_peros(uid, chid)
		if peros == 1:
			await ctx.channel.send("You currently have 1 pero in <#{0}>!".format(chid))
		else:
			await ctx.channel.send("You currently have {0} peros in <#{1}>!".format(peros, chid))

	@peros.command()
	@commands.check(is_owner)
	async def track(self, ctx, *chs):
		new = []
		chids = list(map(get_channel_id, chs))
		for strchid in chids:
			chid = -1
			try:
				chid = int(strchid)
			except:
				continue
			if not self.client.get_channel(chid) is None:
				if not chid in self.channels:
					self.channels.append(chid)
					new.append(chid)
		
		if len(new) == 0:
			await ctx.channel.send("No new channels are being tracked.")
		elif len(new) == 1:
			await ctx.channel.send("<#{0}> is now being tracked.".format(new[0]))
		else:
			await ctx.channel.send("{0} are now being tracked.".format(" ".join(list(map(lambda id: "<#{0}>".format(id), new)))))
		
		with open(PERO_CHANNELS_FILE, "w") as f:
			json.dump(self.channels, f)

	@peros.command()
	@commands.check(is_owner)
	async def untrack(self, ctx, *chs):
		new = []
		chids = list(map(get_channel_id, chs))
		for strchid in chids:
			chid = -1
			try:
				chid = int(strchid)
			except:
				continue
			if not self.client.get_channel(chid) is None:
				if chid in self.channels:
					self.channels.remove(chid)
					new.append(chid)
		
		if len(new) == 0:
			await ctx.channel.send("No new channels have been untracked.")
		elif len(new) == 1:
			await ctx.channel.send("<#{0}> is now no longer being tracked.".format(new[0]))
		else:
			await ctx.channel.send("{0} are now no longer being tracked.".format(" ".join(list(map(lambda id: "<#{0}>".format(id), new)))))
		
		with open(PERO_CHANNELS_FILE, "w") as f:
			json.dump(self.channels, f)

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
		if not self.buxman.peros_exists(uid, chid):
			if not isAdd:
				return
			self.buxman.set_peros(uid, chid, 0)
		
		# Check that it is poipero
		if payload.emoji.name.lower() == "poipero":
			self.buxman.adjust_peros(uid, chid, amount)

	@commands.Cog.listener()
	async def on_raw_reaction_add(self, payload):
		await self.on_reaction(payload, True)

	@commands.Cog.listener()
	async def on_raw_reaction_remove(self, payload):
		await self.on_reaction(payload, False)

def setup(bot):
	bot.add_cog(Peros(bot))
