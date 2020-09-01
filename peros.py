from discord.ext import commands
import sqlite3
import re
import datetime
import threading
import asyncio
import json
from collections import defaultdict
import subprocess
import collections

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
usermentionregex = re.compile(r"(?:[^\\]|\\\\|^)<@(?:!|)([0-9]+)>")

def remove_duplicates(l):
	i = 0
	while i < len(l):
		j = len(l) - 1
		while j > i:
			if l[i] == l[j]:
				l.pop(j)
			j -= 1
		i += 1

def matches_any_pattern(l, i, ps):
	for p in ps:
		if matches_pattern(l, i, p):
			return p
	return None

def matches_pattern(l, i, p):
	
	# Check if p can fit in l at i
	if i + len(p) > len(l):
		return False
	
	# Check if the values in l match the values in p (starting from 0 in p, i in l)
	res = True
	for j, v in enumerate(p):
		if v != l[i + j]:
			res = False
			break
	
	return res

# List of patterns of arguments, that will be ignored.
ignore_patterns = [
	("and",),
	(",",)
]

# List of tuples, that match arguments. If this tuple is matched in the arguments,
# the following non-specifier arguments will be deemed to be a channel-id, channel-mention
# or a word describing it as position (as example: "here")
channel_specifiers = [
	("in",)
]

positional_channels = [
	("here", lambda ctx, arg: ctx.channel.id),
]

pronoun_users = [
	("me", lambda ctx, arg: ctx.author.id),
	("you", lambda ctx, arg: ctx.cog.client.user.id)
]

async def get_user_id(ctx, arg):
	for pu in pronoun_users:
		if pu[0] == arg.lower():
			return pu[1](ctx, arg)
	match = usermentionregex.match(arg)
	if not match is None:
		return int(match.group(1))

user_specifiers = [
	("for",),
	("given", "to")
]


async def get_channel_id(ctx, arg):
	for pc in positional_channels:
		if pc[0] == arg.lower():
			return pc[1](ctx, arg)
	match = channelregex.match(arg)
	if not match is None:
		return int(match.group(1))

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

	async def track(self, ctx, chs):
		if not is_owner(ctx):
			await ctx.channel.send("Only sneks owner can do that!")
			return
		
		def get_channel_id(arg):
			for pc in positional_channels:
				if pc[0] == arg.lower():
					return pc[1](ctx, arg)
			match = channelregex.match(arg)
			if not match is None:
				return int(match.group(1))
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

	async def untrack(self, ctx, chs):
		if not is_owner(ctx):
			await ctx.channel.send("Only sneks owner can do that!")
			return
		def get_channel_id(arg):
			for pc in positional_channels:
				if pc[0] == arg.lower():
					return pc[1](ctx, arg)
			match = channelregex.match(arg)
			if not match is None:
				return int(match.group(1))
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

	@commands.command()
	async def peros(self, ctx, *args):
		
		# *args broke subcommands, so a manual check is needed
		subcommands = [
			"track",
			"untrack"
		]
		if not args is None:
			if len(args) >= 1:
				if args[0] in subcommands:
					cmd = getattr(self, args[0])
					await cmd(ctx, args[1:len(args)])
					return
		
		# Queries are tuples of 2 lists. The first specifying the users. The second the channels.
		# One call might have multiple commands. If a user_specifier or channel_specifier appears again
		# the currents lists will be added to the queries list, and a new user- and channel-list will
		# will be made for the subsequent query
		queries = []
		
		def clean_query(ctx, ul, chl):
			if ul is None or len(ul) == 0:
				ul = [ctx.author.id]
			remove_duplicates(ul)
			ul.sort()
			
			if chl is None or len(chl) == 0:
				chl = ctx.cog.channels.copy()
			remove_duplicates(chl)
			chl.sort()
			
			return (ul, chl)
		
		if not args is None:
			ulist = None
			chlist = None
			skips = 0
			add_list = None
			add_func = None
			for i, v in enumerate(args):
				# Handle patterns, with a length above 1
				if skips != 0:
					skips -= 1
					continue
				
				# Check for "and" patterns
				p = matches_any_pattern(args, i, ignore_patterns)
				if not p is None:
					skips = len(p)-1
					continue
				
				
				
				# Check for user specifier patterns
				p = matches_any_pattern(args, i, user_specifiers)
				if not p is None:
					if not ulist is None:
						# append query
						queries.append(clean_query(ctx, ulist, chlist))
						ulist = None
						chlist = None
						add_list = None
					
					ulist = ulist if not ulist is None else []
					add_list = ulist
					add_func = get_user_id
					
					continue
				
				
				
				# Check for channel specifier patterns
				p = matches_any_pattern(args, i, channel_specifiers)
				if not p is None:
					if not chlist is None:
						# append query
						queries.append(clean_query(ctx, ulist, chlist))
						ulist = None
						chlist = None
						add_list = None
					
					chlist = chlist if not chlist is None else []
					add_list = chlist
					add_func = get_channel_id
					
					continue
				
				if not add_list is None and not add_func is None:
					v = await add_func(ctx, v)
					if not v is None:
						add_list.append(v)
					continue
			
			queries.append(clean_query(ctx, ulist, chlist))
		else:
			queries.append(clean_query(ctx, None, None))
		
		# Some functions, to make lines shorter or remove duplicate code.
		
		async def get_user_name(ctx, uid):
			if ctx.author.id == uid:
				return "you"
			elif self.client.user.id == uid:
				return "I"
			else:
				u = self.client.get_user(uid)
				return u.name
			
		def as_peros(count):
			return "{0} pero{1}".format(count, "" if count == 1 else "s")
		
		def user_peros(uname, peros):
			return "{0} {1} a total of {2}!".format(uname, "have" if uname == "you" or uname == "I" else "has", as_peros(peros))
		
		def and_join(l):
			if len(l) == 0:
				return ""
			elif len(l) == 1:
				return l[0]
			else:
				return ", ".join(l[0:len(l)-1]) + " and " + l[len(l)-1]
		
		# Remove duplicate queries
		remove_duplicates(queries)
		
		
		messages = []
		# Process queries
		for query in queries:
			
			# Use default values
			ulist = [ctx.author.id] if query[0] is None else query[0]
			if len(ulist) == 0:
				ulist = [ctx.author.id]
			chlist = query[1]
			if not chlist is None:
				if len(chlist) == 0:
					chlist = None
			
			# List channels
			msg = None
			# All channels are specified
			if chlist is None or collections.Counter(chlist) == collections.Counter(self.channels):
				msg = "In all tracked channels"
			else:
				msg = "In " + and_join(list(map(lambda id: "<#{0}>".format(id), chlist)))
			
			if chlist is None:
				chlist = self.channels
			
			
			
			# Only one user
			if len(ulist) == 1:
				
				peros = self.buxman.get_peros_for_channels(ulist[0], chlist)
				
				uid = ulist[0]
				uname = await get_user_name(ctx, uid)
				msg += ", " + user_peros(uname, peros)
				
			else:
				msg += ":"
				for uid in ulist:
					peros = self.buxman.get_peros_for_channels(uid, chlist)
					uname = await get_user_name(ctx, uid)
					msg += "\n  " + user_peros(uname, peros).capitalize()
			
			messages.append(msg)
		
		# Send final message:
		await ctx.channel.send("\n".join(messages))
	
	async def on_reaction(self, payload, isAdd):
		amount = 1 if isAdd else -1
		
		chid = payload.channel_id
		if not chid in self.channels:
			return
		
		channel = self.client.get_channel(payload.channel_id)
		msg = await channel.fetch_message(payload.message_id)
		
		uid = msg.author.id
		
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
