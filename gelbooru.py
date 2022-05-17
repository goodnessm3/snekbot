from discord.ext import commands
import xml.etree.ElementTree as ElementTree
import random
from async_timeout import timeout
import json
import asyncio
from collections import defaultdict
import clean_text as ct
from Tree_Server import Tree_Server
import aiohttp


class Gelbooru(commands.Cog):

    def __init__(self, bot):

        self.bot = bot
        #self.sesh = bot.sesh  # aiohttp session for web responses
        self.url = "https://gelbooru.com/index.php?page=dapi&s=post&q=index&pid={}&tags=rating:safe+{}"
        self.seen = []
        self.last_tags = {}  # the last tags someone asked for, use for repeat searches
        self.cached_xml = None  # for "again" queries, don't need to ask the server again as we already have 100 results
        self.last_search = {}  # the tags of the last image uploaded, a string per channel {channel id:str}
        self.last_count = 0  # once we know how many pages were returned, we can look in other pages for "again" search
        self.last_scored = defaultdict(lambda: None)  # stop multiple valuations of the same image, per channel
        self.fallback_tags = ["large_breasts", "huge_breasts", "wide_hips"]
        self.dbman = bot.buxman  # interface to the SQL database
        self.monitoring_times = defaultdict(lambda: 25000)  # {tag:int}
        # number of seconds to wait before querying, gradually increases if no new tag is found
        self.tag_hashes = []  # don't distribute dividend for the same image searched twice within a period of time

        self.serv = Tree_Server(self.bot.settings["tagserver_url"], 2012)

        self.recent_image_user = None  # the USER who caused the most recent image to be posted

        with open("tag_values.json", "r") as f:
            self.tag_values = json.load(f)

        mons = self.dbman.get_all_monitored()
        for x in mons:
            tag, cid = x
            self.bot.loop.create_task(self.check_monitored_tag(tag, cid))
            print("scheduled checking of tag {}".format(tag))

        self.bot.loop.create_task(self.purge_tag_hashes())
        self.bot.loop.create_task(self.monitor_tag_deltas())

    @commands.command()
    async def nr_tags(self, ctx):
        try:
            await ctx.message.channel.send("I currently know " + str(await self.serv.get_nr_tags()) + " tags")
        except:
            await ctx.message.channel.send("I am not connected to any server!")

    @commands.command()
    # @commands.cooldown(1, 120, type=commands.BucketType.user)
    async def value(self, ctx):
        """value the last gelbooru image searched

        I guess comparing tags works, but there could be some super rare occasion, where the tags are identical.
        Dont know if gelbooru sorts the tags. If they dont, its even more rare. To have the same tags and the tags
        being listed in the same order.
        """

        if ctx.message.author == self.recent_image_user:
            await ctx.message.channel.send("You can only value other peoples' images, not your own!")
            return

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

    async def get_tags(self, ctx):

        if not self.last_search.get(ctx.message.channel.id, None):
            # got a None result
            return None  # should this really be an empty list?
        return self.last_search[ctx.message.channel.id]

    async def add_tags(self, ctx):

        tag_list = (await self.get_tags(ctx))
        if not tag_list:
            return  # no tags because the search gave 0 results
        tags = tag_list.split(" ")
        try:
            await self.serv.add_tag(tags)
        except:
            pass  # tag server not talking to us
        self.dbman.log_tags(tags)  # a record of how many times each tag came up

        hashed = hash("".join(tags))
        if not hashed in self.tag_hashes:
            self.tag_hashes.append(hashed)
            self.dbman.distribute_dividend(tags)

    @commands.command()
    @commands.cooldown(6, 1200, type=commands.BucketType.user)
    async def gelbooru(self, ctx, *args):

        """look up a picture on gelbooru"""

        out = ""

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
            out += "I searched for: {}".format(", ".join(candidates))

            args = candidates
            self.dbman.log_search(ctx.message.author.id, ["random"])
        else:
            self.dbman.log_search(ctx.message.author.id, args)

        self.last_tags[ctx.message.channel.id] = list(args)
        res, tags = await self.get_image(*args)
        self.last_search[ctx.message.channel.id] = tags

        out = ct.discordStringEscape(out)
        self.recent_image_user = ctx.message.author
        out += "\n"
        out += res
        await ctx.message.channel.send(out)
        await self.add_tags(ctx)

    async def get_image(self, *args, **kwargs):

        xml = await self.myget(*args, **kwargs)
        counts, url, tags = await self.get_result(xml)
        self.last_count = counts  # remember how many images for page offset with "again" command
        if type(counts) == str:
            return '''0 results.'''.format(counts), ""
        else:
            return '''{} results.\n{}'''.format(counts, url), tags

    @commands.command()
    @commands.cooldown(6, 1200, type=commands.BucketType.user)
    async def again(self, ctx, *args):

        """repeat the last search, optionally with extra tags"""

        cid = ctx.message.channel.id
        new_tags = []
        if args:
            for x in args:
                if not x == "with" or x == "and":
                    new_tags.append(x)

        if new_tags:
            #  new_tags = tuple(new_tags)  we are using lists now instead, the gelbooru func converts its args tuple
            #  to a list before storing it
            self.last_tags[cid] = self.last_tags[cid] + new_tags  # append extra tags for further "again" searches

        max_page = self.last_count//100
        ceiling = min(100, max_page)
        offset = random.randint(0, ceiling)  # gelbooru won't let you ask for a page more than 200 deep

        res, tags = await self.get_image(*self.last_tags[cid], offset=offset)
        self.last_search[cid] = tags
        await ctx.message.channel.send(res)
        self.dbman.log_search(ctx.message.author.id, self.last_tags[cid])

        # TODO: this tag adding code is duplicated in the "gelbooru" command, probably better if
        # it only happened in one place

        self.recent_image_user = ctx.message.author
        await self.add_tags(ctx)


    async def myget(self, *args, limit=False, offset=0):

        tags = [x.replace("&", "%26") for x in args]  
        # TODO: actually use a nice url escaping function that handles all special characters not just &

        url = self.url.format(str(offset), "+".join(tags))
        if limit:
            url += "&limit=1"
        async with aiohttp.ClientSession(loop=self.bot.loop) as s:
            async with s.get(url) as r:
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
        url = res.find("file_url").text
        i = 0
        while url in self.seen and i < 23:
            # try to find a novel image but bail out after trying 23 times
            res = random.choice(xml.findall("post"))
            url = res.find("file_url").text
            i += 1
            
        tags = res.find("tags").text
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

    async def purge_tag_hashes(self):

        #print(self.tag_hashes)
        #print("purging tag hashes")
        self.tag_hashes = []
        self.bot.loop.call_later(1000000, lambda: asyncio.ensure_future(self.purge_tag_hashes()))
        # 11.5 days = 1000000 seconds

    async def check_monitored_tag(self, tag, cid):

        await asyncio.sleep(10)
        print("checking gelbooru for tag {}".format(tag))
        this_tag, last = self.dbman.get_last_monitored(tag, cid)  # it's a tuple, needs to be unpacked
        # format of tuple is (tag, last, channel_id)
        new_xml = await(self.myget(tag, limit=True))
        
        posts = new_xml.findall("post")
        most_recent = posts[0].find("md5").text
        tags = posts[0].find("tags").text
        # print("old md5 was {}, new is {}".format(last, most_recent))
        base_time = self.monitoring_times[tag]

        if not most_recent == last:  # new image
            print("found a new image for tag {}".format(tag))
            self.dbman.insert_monitored(tag, channel=cid, last=most_recent)
            # also update db before splitting the tags in case monitoring for a multi-tag query
            new_tags = tags.split(" ")
            all_monitored_tags = [z[0] for z in self.dbman.get_all_monitored()]
            if "+" not in tag:
                for q in new_tags:
                    if q in all_monitored_tags:
                        print("This image matched a monitored tag: {}".format(q))
                        self.dbman.insert_monitored(q, channel=cid, last=most_recent)
            chan = self.bot.get_channel(cid)
            url = posts[0].find("file_url").text
            self.last_search[cid] = tags
            await chan.send("I found a new {} image! {}".format(tag, url))

        next_call = max(3600, base_time + random.randint(-6000, 6000))
        # jitter timing to stop all gelbooru requests being simultaneous
        self.bot.loop.call_later(next_call, lambda: asyncio.ensure_future(self.check_monitored_tag(tag, cid)))
        # re-add task to the bot loop, apparently no native asyncio support for periodic tasks
        print("base_time for tag {} is now {}".format(tag, self.monitoring_times[tag]))

    @commands.command()
    async def gelbooru_stats(self, ctx):

        user, cnt1, tag, cnt2, total = self.dbman.gelbooru_stats()

        msg = f"The most popular tag for the last week is \"{tag}\", with {cnt2} searches! " \
              f"A total of {total} gelbooru searches have been made in the last week."

        await ctx.message.channel.send(msg)

    @commands.command()
    async def trending_tag(self, ctx):

        hot_tag, counts = self.dbman.trending_tag()
        word = random.choice(["hottest", "hippest", "trending", "most popular"])

        res, tags = await self.get_image(hot_tag)
        self.last_search[ctx.message.channel.id] = tags

        msg = f"The {word} new tag this week is **{hot_tag}**, with **{counts}** more searches " \
              f"than the previous week! Here's an example: {res}"

        await ctx.message.channel.send(msg)

    async def monitor_tag_deltas(self):

        print("Updating gelbooru tag frequency history")
        self.dbman.monitor_tag_deltas()
        # this command tracks how many times the tag came up in a result since the last time checked,
        # all done inside the SQL command in the DB manager
        self.bot.loop.call_later(86400, lambda: asyncio.ensure_future(self.monitor_tag_deltas()))


def setup(bot):

    bot.add_cog(Gelbooru(bot))
