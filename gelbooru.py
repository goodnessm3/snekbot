from discord.ext import commands
import xml.etree.ElementTree as ElementTree
import random
from async_timeout import timeout
import json
import asyncio
from collections import defaultdict
import clean_text as ct
from Tree_Server import Tree_Server

class Gelbooru(commands.Cog):

    def __init__(self, bot):

        self.bot = bot
        self.sesh = bot.sesh  # aiohttp session for web responses
        self.url = "https://gelbooru.com/index.php?page=dapi&s=post&q=index&tags=rating:safe+{}"
        self.seen = []
        self.last_tags = {}  # the last tags someone asked for, use for repeat searches
        self.cached_xml = None  # for "again" queries, don't need to ask the server again as we already have 100 results
        self.last_search = {}  # the tags of the last image uploaded, a string per channel {channel id:str}
        self.last_scored = defaultdict(lambda: None)  # stop multiple valuations of the same image, per channel
        self.fallback_tags = ["large_breasts", "huge_breasts", "wide_hips"]
        self.dbman = bot.buxman  # interface to the SQL database
        self.monitoring_times = defaultdict(lambda: 25000)  # {tag:int}
        # number of seconds to wait before querying, gradually increases if no new tag is found

        self.serv = Tree_Server(self.bot.settings["tagserver_url"],2012)


        with open("tag_values.json", "r") as f:
            self.tag_values = json.load(f)

        mons = self.dbman.get_all_monitored()
        for x in mons:
            tag, cid = x
            print("aaa")
            print(tag)
            self.bot.loop.create_task(self.check_monitored_tag(tag, cid))
            print("scheduled checking of tag {}".format(tag))

    @commands.command()
    async def nr_tags(self,ctx):
        try:
            await ctx.message.channel.send("I currently know " + str(await self.serv.get_nr_tags()) + " tags")
        except:
            await ctx.message.channel.send("I am not connected to any server!")


    @commands.command()
    @commands.cooldown(1, 120, type=commands.BucketType.user)
    async def value(self, ctx):
        """value the last gelbooru image searched"""


        """
        I guess comparing tags works, but there could be some super rare occasion, where the tags are identical.
        Dont know if gelbooru sorts the tags. If they dont, its even more rare. To have the same tags and the tags
        being listed in the same order.
        """

        if not self.last_search.get(ctx.message.channel.id, None):  
            # returns None if no image was entered into last_search dict
            await ctx.message.channel.send("No image to value!")
            return
        
        if self.last_scored[ctx.message.channel.id] == self.last_search[ctx.message.channel.id]:
            await ctx.message.channel.send("This image has already been valued!")
            return
        score = 0
        for x in self.last_search[ctx.message.channel.id].split(" "):
            try:
                score += self.tag_values[x]
            except KeyError:
                pass

        self.last_scored[ctx.message.channel.id] = self.last_search[ctx.message.channel.id]
        if score == 0:
            await ctx.message.channel.send("That image isn't worth any snekbux...")
        else:
            await ctx.message.channel.send("This image is worth {} snekbux! (Added to your account)".format(score))
        uid = str(ctx.message.author.id)
        self.bot.buxman.adjust_bux(uid, score)

    @commands.command()
    async def tags(self, ctx):

        """get the tags of the last image"""
        if not self.last_search.get(ctx.message.channel.id, None):
            # got a None result
            await ctx.message.channel.send("Nothing was searched yet.")
            return
        
        out = "The last image has tags: {}".format(self.last_search[ctx.message.channel.id])
        out = ct.discordStringEscape(out)
        await ctx.message.channel.send(out)

    async def get_tags(self,ctx):
        if not self.last_search.get(ctx.message.channel.id, None):
            # got a None result
            return []
        return self.last_search[ctx.message.channel.id]

    async def add_tags(self,ctx):
        tag_list =(await self.get_tags(ctx))
        tags = tag_list.split(" ")
        await self.serv.add_tag(tags)



    @commands.command()
    async def gelbooru(self, ctx, *args):

        """look up a picture on gelbooru"""

        if len(args) == 0 or args[0] == "random":
            tagpool = self.last_search.get(ctx.message.channel.id, None)
            if not tagpool:
                tagpool = self.fallback_tags
            else:
                tagpool = tagpool.split(" ")
            candidates = []
            try:
                candidates.append(await self.serv.get_random_tag())
            except:
                candidates = random.sample(tagpool, min(3, len(tagpool)))
            out = "I searched for: {}".format(", ".join(candidates))
            out = ct.discordStringEscape(out)
            await ctx.message.channel.send(out)
            args = candidates
            self.dbman.log_search(ctx.message.author.id, ["random"])
        else:
            self.dbman.log_search(ctx.message.author.id, args)

        self.last_tags[ctx.message.channel.id] = args
        res, tags = await self.get_image(*args)
        self.last_search[ctx.message.channel.id] = tags
        await ctx.message.channel.send(res)
        try:
            await self.add_tags(ctx)
        except:
            pass

    async def get_image(self, *args):

        xml = await self.myget(*args)
        counts, url, tags = await self.get_result(xml)
        if type(counts) == str:
            return '''0 results.'''.format(counts), ""
        else:
            return '''{} results.\n{}'''.format(counts, url), tags

    @commands.command()
    @commands.cooldown(1, 4, type=commands.BucketType.user)
    async def again(self, ctx, *args):

        """repeat the last search, optionally with extra tags"""

        cid = ctx.message.channel.id
        new_tags = []
        if args:
            for x in args:
                if not x == "with" or x == "and":
                    new_tags.append(x)

        if new_tags:
            new_tags = tuple(new_tags)
            self.last_tags[cid] = self.last_tags[cid] + new_tags  # append extra tags for further "again" searches

        res, tags = await self.get_image(*self.last_tags[cid])
        self.last_search[cid] = tags
        await ctx.message.channel.send(res)
        self.dbman.log_search(ctx.message.author.id, self.last_tags[cid])

    async def myget(self, *args):

        tags = [x.replace("&", "%26") for x in args]

        url = self.url.format("+".join(tags))
        async with self.sesh.get(url) as r:
            async with timeout(10):
                a = await r.text()

        xml = ElementTree.fromstring(a)
        return xml

    async def get_result(self, xml):

        results_count = xml.get("count")
        check = xml.findall("post")
        fb = None
        if not check:
            fb = random.choice(self.fallback_tags)
            xml = await self.myget(fb)
        res = random.choice(xml.findall("post"))
        url = res.get("file_url")
        i = 0
        while url in self.seen and i < 23:
            # try to find a novel image but bail out after trying 23 times
            res = random.choice(xml.findall("post"))
            url = res.get("file_url")
            i += 1
            
        tags = res.get("tags")
        self.seen.append(url)
        if not fb:
            return int(results_count), url, tags
        else:
            return fb, url, tags  # I am going to hell

    @commands.command()
    async def monitor_for(self, ctx, *args):

        if not ctx.message.author.id == self.bot.settings["owner_id"]:
            await ctx.message.channel.send("Only my master can do that!")
            return

        arg = "+".join(args)  # make it into a list of tags to send to gelbooru
        self.dbman.insert_monitored(arg, channel=ctx.message.channel.id)
        await ctx.message.channel.send("OK! I'll monitor gelbooru for new {} images.".format(arg))
        self.bot.loop.call_soon(lambda: asyncio.ensure_future(self.check_monitored_tag(arg, ctx.message.channel.id)))

    @commands.command()
    async def unmonitor(self, ctx, *args):

        if not ctx.message.author.id == self.bot.settings["owner_id"]:
            await ctx.message.channel.send("Only my master can do that!")
            return

        tagstring = "+".join(args)
        await ctx.message.channel.send("I will stop monitoring for {} images".format(tagstring))
        self.dbman.unmonitor(tagstring)

    async def check_monitored_tag(self, tag, cid):

        await asyncio.sleep(10)
        print("checking gelbooru for tag {}".format(tag))
        this_tag, last = self.dbman.get_last_monitored(tag, cid)  # it's a tuple, needs to be unpacked
        # format of tuple is (tag, last, channel_id)
        new_xml = await(self.myget(tag, "&limit=1"))
        # including &limit as a tag is a nasty hack but it saves having to use two different URLs
        posts = new_xml.findall("post")
        most_recent = posts[0].get("md5")
        tags = posts[0].get("tags")
        print("old md5 was {}, new is {}".format(last, most_recent))
        base_time = self.monitoring_times[tag]
        if most_recent == last:
            self.monitoring_times[tag] = base_time + 10000  # check less frequently
        else:
            print("found a new image for tag {}".format(tag))
            self.dbman.insert_monitored(tag, channel=cid, last=most_recent)
            # also update db before splitting the tags in case monitoring for a multi-tag query
            new_tags = tags.split(" ")
            print(new_tags)
            all_monitored_tags = [z[0] for z in self.dbman.get_all_monitored()]
            if "+" not in tag:
                for q in new_tags:
                    if q in all_monitored_tags:
                        print("This image matched a monitored tag: {}".format(q))
                        self.dbman.insert_monitored(q, channel=cid, last=most_recent)
            chan = self.bot.get_channel(cid)
            url = posts[0].get("file_url")
            self.last_search[cid] = tags
            await chan.send("I found a new {} image! {}".format(tag, url))

        next_call = max(3600, base_time + random.randint(-6000, 6000))
        # jitter timing to stop all gelbooru requests being simultaneous
        self.bot.loop.call_later(next_call, lambda: asyncio.ensure_future(self.check_monitored_tag(tag, cid)))
        # re-add task to the bot loop, apparently no native asyncio support for periodic tasks
        print("base_time for tag {} is now {}".format(tag, self.monitoring_times[tag]))


def setup(bot):

    bot.add_cog(Gelbooru(bot))
