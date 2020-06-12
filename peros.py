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
Requires peros_channels.json, which contains a list of channel ids, where peros will be available.

Example:
[
	2134567812312,
	9876544444443
]

"""

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

def getEmoteName(emoteTag):
	return emoteTag.split(":")[1]

class Peros(commands.Cog):

	def __init__(self, bot):
		self.client = bot
		self.buxman = bot.buxman
		self.settings = bot.settings
		
		with open("peros_channels.json", "r") as f:
			self.channels = json.load(f)

	@commands.group()
	async def peros(self, ctx):
		if not ctx.invoked_subcommand is None:
			return
		chid = ctx.channel.id
		uid = ctx.author.id
		await ctx.channel.send("<@{0}>, You currently have {1} peros!".format(ctx.author.id, self.buxman.get_peros_for_channels(uid, self.channels)))

	@peros.command()
	async def here(self, ctx):
		chid = ctx.channel.id
		uid = ctx.author.id
		if not chid in self.channels:
			await ctx.channel.send("Peros are not tracked in this channel.")
			return
		if not self.buxman.peros_exists(uid, chid):
			self.buxman.set_peros(uid, chid, 0)
		
		await ctx.channel.send("<@{0}>, You currently have {1} peros in this channel!".format(ctx.author.id, self.buxman.get_peros(uid, chid)))
		return

	@peros.command()
	@commands.check(is_owner)
	async def init(self, ctx, *chs):
		chids = list(map(get_channel_id, chs))
		subprocess.Popen(self.settings["python"] + " peros_gen.py " + str(ctx.channel.id) + " " + (" ".join(chids)))

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
		await ctx.channel.send("<@{0}>, You currently have {1} peros in <#{2}>!".format(ctx.author.id, self.buxman.get_peros_for_channels(uid, self.channels), chid))

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
