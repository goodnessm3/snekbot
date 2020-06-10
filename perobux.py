from discord.ext import commands
import sqlite3
import re
import datetime
import threading
import asyncio

""" Module for counting peros channel-specific """



"""
Could count global.
Always recalculates the last 50 messages.
Just in case someone adds a new pero to a message, that already has been used in computation


SQL schema:

CREATE TABLE Perobux (
	userid INTEGER,
	channelid INTEGER,
	count INTEGER,
	PRIMARY KEY (userid, channelid)
);

TODO: Move DB Stuff to user_stats

"""

"""
Yield to let other perobux operations run.
Include covered datetime to be able to remove increments in queue, that would count double.
For example if the oldest message in a channel has not been summed yet and someone reacts with pero,
there will be no increment queued, since the increment will be taken into account by compute_perobux
as soon as it gets to that message.

If however the message has already been covered, and someone adds a pero, that increment must be added
after compute_perobux.
"""

emoteregex = re.compile(r"(?:[^\\]|\\\\|^)(<:[A-Za-z0-9]+:\d{9,}>)")

def getEmoteName(emoteTag):
	return emoteTag.split(":")[1]

class Perobux(commands.Cog):

	def __init__(self, bot):
		self.client = bot
		self.db = sqlite3.connect("perobux.sqlite3")
		self.c = self.db.cursor()
		""" Check that the table is created """
		tablecount = self.c.execute("SELECT COUNT(name) FROM sqlite_master WHERE type='table' AND name='Perobux';")
		
		if tablecount.fetchone()[0] == 0:
			self.c.execute("""	CREATE TABLE Perobux (
									userid INTEGER,
									channelid INTEGER,
									count INTEGER,
									PRIMARY KEY (userid, channelid)
								);""")

	def get_perobux(self, uid, chid):
		entry = self.c.execute("SELECT count, lastupdated FROM Perobucks WHERE userid = {0} AND channelid = {1}".format(uid, chid)).fetchone()
		if entry is None:
			return (0, None)
		return (entry[0], datetime.datetime.fromisoformat(entry[1]))

	def set_perobux(self, uid, chid, peros):
		self.c.execute("""
			INSERT OR REPLACE INTO Perobucks (userid, channelid, count)
			VALUES ({0}, {1}, {2})
		""".format(uid, chid, peros))
		self.db.commit()

	""" Compute perobucks. If start is none, do inital compute """
	async def compute_perobux(self, ctx, start = None):
		""" Get history in 200 message batches """
		ch = ctx.channel
		uid = ctx.author.id
		oldest_message = None
		while True:
			msgs = await ctx.channel.history(limit=200, after = start, before = oldest_message, oldest_first = False).filter(lambda m: m.author.id == uid).flatten()
			if not msgs:
				break
			for msg in msgs:
				oldest_message = msg
				""" check for peros """
				peros = list(filter(lambda r: r.emoji.name.lower() == "poipero", filter(lambda r: not isinstance(r.emoji, str), msg.reactions)))
				if peros:
					self.adjust_perobux(ctx.author.id, ctx.channel.id, peros[0].count)
				
				(yield oldest_message.created_at)
		
		if oldest_message is None:
			self.set_perobux(ctx.author.id, ctx.channel.id, 0)

	""" Will be moved to buxman """
	async def adjust_perobux(self, uid, chid, amount):
		self.c.execute("UPDATE Perobux SET count = count + ({2}) WHERE userid = {0} AND channelid = {1}".format(uid, chid, amount))

	@commands.command()
	async def perobux(self, ctx):
		msg = await ctx.channel.send("Calculating perobux...")
		
		entry = self.getCurrentPeros(ctx.author.id, ctx.channel.id)
		peros = entry[0]
		
		new = await self.computebucks(ctx, start = entry[1])
		peros = peros + new[0]
		
		self.upsertCurrentPeros(ctx.author.id, ctx.channel.id, peros, new[1])
		
		await ctx.channel.send("<@{0}>, you have {1} perobux!".format(ctx.author.id, peros))
		await msg.delete()

	@commands.Cog.listener()
	async def on_raw_reaction_add(self, payload):
		""" self.worker.queue(self.adjust_perobux( """
		print(payload)

	@commands.Cog.listener()
	async def on_raw_reaction_remove(self, payload):
		
		print(payload)


class PerobuxWorker():
	
	def __init__(self):
		self.comp = {}
		self.q = {}
		self.m = Lock()
		self.t = Thread(target = self.run)
		self.t.deamon = True
		self.t.start()
	
	def run(self):
		while True:
			if
			""" Iterate through all coroutine lists in q """
			toremove = []
			
			
	
	def queue(self, key, coroutine, initial):
		self.m.aquire()
		try:
			
		finally:
			self.m.release()

def setup(bot):
	bot.add_cog(Perobux(bot))
