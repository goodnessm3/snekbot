import asyncio
from discord.ext import commands
from discord import Embed
import re
import json
import aiohttp
from async_timeout import timeout
from hashlib import md5  # for naming saved images
from PIL import Image  # for resizing images to thumbnail
from io import BytesIO
import os


TWITTER_LINK_FINDER = re.compile('''((https://x.com|https://fixvx.com|https://vxtwitter.com|https://twitter.com)\S*)''')
TO_REPLACE = ('''https://vxtwitter.com''', '''https://fixvx.com''')
TRUE_X = '''https://x.com'''
OEMBED_URL = '''https://publish.twitter.com/oembed'''
IMGURL_FINDER = re.compile('''https://.+gelbooru.com/{1,2}images/.+\.(?:jpg|png)''')
# images / any number of non whitespace up to a ., then either .jpg or .png, in non-capturing parentheses
# sometimes we get two //'s between .com and images???
DISCORD_EXTENSION_FINDER = re.compile('''([a-z]{3,4})\?ex=''')  # get the first group from this
# the extension for a discord path is buried in the middle of the url, they changed it so that the content links
# arent permanent, I think.
TERMINAL_EXTENSION_FINDER = re.compile('''\.([a-z]{3,4})$''')  # for URLs that end in the extension


def resize(tup):

    """Not generic - just resizes a picture to 300 px wide"""

    x, y = tup
    ratio = 300.0 / x
    return int(x * ratio), int(y * ratio)


def extract_twitter_url(astr):

    """Pull a link from twitter OR any of the "fixing" services from a string, return the converted URL"""

    if found := TWITTER_LINK_FINDER.search(astr):
        return convert_twitter_url(found.group())
    return None


def extract_gelbooru_url(astr):

    if found := IMGURL_FINDER.search(astr):
        return found.group()


def convert_twitter_url(astr):

    """Replace any of the twitter alternatives with the actual twitter URL to send to the embedding API"""

    if astr.startswith(TRUE_X):
        return astr
    else:
        for alt in TO_REPLACE:
            if astr.startswith(alt):
                out = astr.replace(alt, TRUE_X)
                return out
        return None  # for some reason the func got passed a URL which is not actually a tweet? Shouldn't happen


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
            url, is_tweet = await self.get_image_url(postid, channel)

            if not url:  # not all peroed posts will have an image, so don't try to download one
                self.bot.buxman.add_image_link(postid, channel, url, None, failed=True)
                # record that there was no image, so we don't continually re-try
                print(f"No image associated with postid {postid} in channel {channel}")
                continue

            if is_tweet:
                print(f"Getting twitter embed snippet for {postid}")
                snippet = await self.get_twitter_embed(url)
                if not snippet:
                    continue

                self.bot.buxman.add_twitter_embed(postid, channel, snippet)
                print("Added twitter HTML snibbed :DDD")

            else:
                print(f"Getting image from peroed URL {url}")
                try:
                    thumb = await self.save_image_from_url(url)  # returns the name (md5 hash) of the thumbnail
                    # update: now we are saving the full size image
                except Exception as e:
                    print(e)  # sometimes PIL won't be able to read the URL for whatever reason, e.g. it's a webm
                    continue

                self.bot.buxman.add_image_link(postid, channel, url, thumb)
                print(f"Added a link to best of: {url}")

        print("finished updating links for most peroed posts")
        self.bot.loop.call_later(43200, lambda: asyncio.ensure_future(self.periodic_link_update()))

    async def get_image_url(self, msgid, ch):

        """Save an image locally, that was either a twitter link or a direct image upload
        to include in the best-of gallery

        returns text, and bool for is it a twitter link"""

        channel = self.bot.get_channel(ch)
        try:
            msg = await channel.fetch_message(msgid)
        except Exception as e:
            print(f"Couldn't download message {msgid}")
            print(e)
            return None, False  # still needs to be a 2-tuple to not break downstream fxns

        c = msg.content
        url = None

        print(f"Checking the message whose content is :{c}")

        if msg.attachments:  # an image someone uploaded directly
            url = msg.attachments[0].url
            return url, False  # simplest case, a directly attached image

        if url := extract_gelbooru_url(c):
            return url, False  # a post containing a URL like a gelbooru image link

        # if neither of those two worked, see if it's a tweet

        if twitter_link := extract_twitter_url(c):
            return twitter_link, True  # bool lets the recieving function put it in the appropriate db column

        print(f"nothing found in message: {c}")
        return None, False  # still needs to be a 2-tuple to not break downstream fxns

    async def save_image_from_url(self, url, dest="/var/www/html/bestofhct/"):

        """Download and save an image for use in the gallery, from gelbooru or a discord attachment.
        Returns the name of the saved file."""

        if res := TERMINAL_EXTENSION_FINDER.search(url):
            ext = res.groups()[0]
        elif res := DISCORD_EXTENSION_FINDER.search(url):
            ext = res.groups()[0]
        else:
            print(f"couldn't find extension in URL {url}, not saving image")
            return  # probably could get the data regardless and infer the extension, maybe one day

        if ext == "webm":
            print("Ignoring a webm")
            return

        async with aiohttp.ClientSession(loop=self.bot.loop) as s:
            async with s.get(url) as r:
                async with timeout(60):
                    a = await r.read()

                    # this will make the process get killed if it uses a lot of memory trying to resize a big pic!

                    byts = BytesIO(a)  # make it look like a file so PIL can understand how to open it
                    im = Image.open(byts)
                    new_size = resize(im.size)
                    im = im.resize(new_size)

                    # prev.used to resize image, but now we save the whole thing because we can't linkto discord anymore

                    hasher = md5()  # name the file by its hash
                    hasher.update(a)
                    hsh = hasher.hexdigest()

                    fname = os.path.join(dest, hsh + "." + ext)
                    thumbname = os.path.join(dest, "thumbnails", hsh + "." + ext)

                    im.save(thumbname)  # from PIL

                    with open(fname, "wb") as f:
                        f.write(a)  # save image data directly
                    return hsh + "." + ext

    async def get_twitter_embed(self, url):

        """Using a twitter URL converted to the proper x.com domain, use the oEmbed API to get an HTML snippet
        appropriate for inclusion on the best of page"""

        async with aiohttp.ClientSession(loop=self.bot.loop) as s:
            async with s.get(OEMBED_URL, data={"url": url}) as r:
                async with timeout(10):
                    try:
                        resp = await r.json()  # a status update or youtube link
                    except aiohttp.client_exceptions.ContentTypeError:
                        print("twitter response wasn't JSON:")
                        print(r)
                        ret = None
                        return ret
                    try:
                        ret = resp["html"]
                    except:
                        ret = None
                        print("Error with twitter oembed:")
                        print(resp)
                    return ret


async def setup(bot):

    await bot.add_cog(Mpero(bot))

