import asyncio
from discord.ext import commands
from discord import Embed
import re
import json
from tweepy import OAuthHandler
import tweepy
import aiohttp
from async_timeout import timeout
from hashlib import md5  # for naming saved images

class TwitInfo:

    A = B = C = D = None


TI = TwitInfo()


with open("twitter_keys.json", "r") as f:
    twitinfo = json.load(f)
    for k, v in twitinfo.items():
        TI.__setattr__(k, v)  # this is needlessly complicated


class TweetGetter:

    def __init__(self):

        auth = OAuthHandler(TI.A, TI.B)
        auth.set_access_token(TI.C, TI.D)
        self.client = tweepy.API(auth)

    def get_tweet_image_url(self, tweet_id):

        res = self.client.lookup_statuses([tweet_id])
        if not res:
            print("tweet id not valid?")
            return
        try:
            return res[0].entities["media"][0]["media_url"]
        except KeyError:
            print("couldn't find media in tweet")
            return

TG = TweetGetter()


class Mpero(commands.Cog):

    def __init__(self, bot):

        self.bot = bot
        self.bot.loop.create_task(self.periodic_link_update())

    @commands.command()
    async def most_peroed(self, ctx):

        content = None
        while not content:
            msgid, ch, count = self.bot.buxman.get_most_peroed()
            chan = self.bot.get_channel(ch)
            msg = await chan.fetch_message(msgid)
            content = msg.content
            if not content:
                self.bot.buxman.remove_pero_post(msgid)
                # cleans up entries where a post was deleted

        time, _ = str(msg.created_at).split(" ")
        author = msg.author.display_name
        cname = msg.channel.name
        await ctx.message.channel.send(f'{count} peros on {time} by {author} in \#{cname}:')
        await ctx.message.channel.send(msg.content)
        if msg.attachments:
            await ctx.message.channel.send(msg.attachments[0].url)
            # might have been an uploaded image, twitter posts will be captured in just the content

    async def periodic_link_update(self):

        print("updating image links for most peroed posts")

        best_pictures = self.bot.buxman.get_best_of()
        for tup in best_pictures:
            postid, channel = tup
            url = await self.get_image_url(postid, channel)
            self.bot.buxman.add_image_link(postid, channel, url)
            print(f"Added a link to best of: {url}")

        print("finished updating links for most peroed posts")
        self.bot.loop.call_later(432000, lambda: asyncio.ensure_future(self.periodic_link_update()))

    async def get_image_url(self, msgid, ch):

        """Save an image locally, that was either a twitter link or a direct image upload
        to include in the best-of gallery"""

        tweet_finder = re.compile("/status/([0-9]+)")
        imgurl_finder = re.compile('''https://.+gelbooru.com/images/.+\.(?:jpg|png)''')
        # images / any number of non whitespace up to a ., then either .jpg or .png, in non-capturing parentheses

        channel = self.bot.get_channel(ch)
        msg = await channel.fetch_message(msgid)
        c = msg.content
        url = None
        # print(f"downloading from {msg}")
        # print(f"contet is: {c}")
        if postid := tweet_finder.findall(c):  # look ma, I'm using the walrus operator!
            url = TG.get_tweet_image_url(postid[0])  # [0] index because findall returns a list

        elif msg.attachments:  # an image someone uploaded directly
            url = msg.attachments[0].url

        elif direct_link := imgurl_finder.findall(c):
            url = direct_link[0]

        if not url:
            # print("nothing found in msg")
            return  # nothing to save
        else:
            return url


    async def save_image_from_url(self, url, dest="/var/www/html/bestof/"):

        ext = url.split(".")[-1]  # could be jpg or png
        async with aiohttp.ClientSession(loop=self.bot.loop) as s:
            async with s.get(url) as r:
                async with timeout(60):
                    a = await r.read()
                    hasher = md5()
                    hasher.update(a)
                    hsh = hasher.hexdigest()
                    with open(dest + hsh + "." + ext, "wb") as f:
                        f.write(a)



def setup(bot):
    bot.add_cog(Mpero(bot))

