from discord.ext import commands
import sqlite3
import re
import datetime

""" Module for counting peros channel-specific """



"""
It could count global.
The amount of time it would take to go through all channels and find all messages from one person and add them, seems rather large though.
It would be one initial computation though...

Perhaps a initial run in on a seperated process?
It could be a lot of data though.
8 public channels * however many members at least i would figure.
As of the 07.06.2020 this would be:
8 * 281 entries at least
Of course it could only be loaded in some channels.
This could also limit to the keionbu then.


SQL schema:

CREATE TABLE Perobucks (
	userid INTEGER,
	channelid INTEGER,
	count INTEGER,
	lastupdated DATETIME,
	PRIMARY KEY (userid, channelid)
);

"""

emoteregex = re.compile(r"(?:[^\\]|\\\\|^)(<:[A-Za-z0-9]+:\d{9,}>)")

def getEmoteName(emoteTag):
	return emoteTag.split(":")[1]

""" This module has its own DB-file. This might not be needed, but i didnt want to mess up the current one """
class Perobucks(commands.Cog):

	def __init__(self, bot):
		self.db = sqlite3.connect("perobucks.sqlite3")
		self.c = self.db.cursor()
		""" Check that the table is created """
		tablecount = self.c.execute("SELECT COUNT(name) FROM sqlite_master WHERE type='table' AND name='Perobucks';")
		
		if tablecount.fetchone()[0] == 0:
			self.c.execute("""	CREATE TABLE Perobucks (
									userid INTEGER,
									channelid INTEGER,
									count INTEGER,
									lastupdated DATETIME,
									PRIMARY KEY (userid, channelid)
								);""")

	def getCurrentPeros(self, uid, chid):
		entry = self.c.execute("SELECT count, lastupdated FROM Perobucks WHERE userid = {0} AND channelid = {1}".format(uid, chid)).fetchone()
		if entry is None:
			return (0, None)
		return (entry[0], datetime.datetime.fromisoformat(entry[1]))

	def upsertCurrentPeros(self, uid, chid, peros, time):
		self.c.execute("""
			INSERT OR REPLACE INTO Perobucks (userid, channelid, count, lastupdated)
			VALUES ({0}, {1}, {2}, \"{3}\")
		""".format(uid, chid, peros, time))
		self.db.commit()

	""" Compute perobucks. If start is none, do inital compute """
	async def computebucks(self, ctx, start = None):
		""" Get history in 200 message batches """
		ch = ctx.channel
		uid = ctx.author.id
		oldestMessage = None
		firstmessage = None
		perobucks = 0
		while True:
			msgs = await ctx.channel.history(limit=200, after = start, before = oldestMessage, oldest_first = False).filter(lambda m: m.author.id == uid).flatten()
			if not msgs:
				break
			for msg in msgs:
				if not firstmessage:
					firstmessage = msg
				oldestMessage = msg
				""" check for peros """
				peros = list(filter(lambda r: r.emoji.name.lower() == "poipero", filter(lambda r: not isinstance(r.emoji, str), msg.reactions)))
				if peros:
					perobucks = perobucks + peros[0].count
				
		if oldestMessage is None:
			return (perobucks, start)
		t = firstmessage.created_at
		return (perobucks, datetime.datetime(t.year, t.month, t.day, t.hour, t.minute, t.second, t.microsecond+10000))

	@commands.command()
	async def perobucks(self, ctx):
		await ctx.channel.send("Calculating Perobucks...")
		entry = self.getCurrentPeros(ctx.author.id, ctx.channel.id)
		peros = entry[0]
		new = await self.computebucks(ctx, start = entry[1])
		peros = peros + new[0]
		self.upsertCurrentPeros(ctx.author.id, ctx.channel.id, peros, new[1])
		await ctx.channel.send("<@{0}>, you have {1} peros!".format(ctx.author.id, peros))

def setup(bot):
	bot.add_cog(Perobucks(bot))
