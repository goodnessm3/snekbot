import asyncio
from discord.ext import commands
import secrets
import discord
import aiohttp
from async_timeout import timeout
import os
import re

DOWNLOAD_POLL_INTERVAL = 23  # seconds
youtube_code_matcher = re.compile('''^[A-Za-z0-9_-]{11}$''')


def verify_youtube_link(astr):

    """Does this look like a youtube link?"""

    a = b = False  # checks

    parts = astr.split("?v=")
    if len(parts) == 2:
        if parts[0] == "https://www.youtube.com/watch":
            a = True
        if youtube_code_matcher.match(parts[1]):
            b = True

    return a & b


class Ytvids(commands.Cog):

    def __init__(self, bot):

        self.bot = bot
        self.poll_ids = []  # IDs to check for completion of youtube download

    def get_thumbnail(self, ytid):

        """Most often it's a webp, but sometimes older videos seem to have .jpg instead"""

        for extension in [".webp", ".jpg", ".png"]:
            thumb_loc = os.path.join(self.bot.settings["server_files_root"], "ytthumbs", ytid + extension)
            if os.path.exists(thumb_loc):
                return thumb_loc

        # if all else fails, we still need some attachment so use a placeholder
        return os.path.join(self.bot.settings["server_files_root"], "ytthumbs", "nothumb.png")

    async def poll_for_completion(self, ctx, poll_id):

        poll_url = self.bot.settings["local_video_poll_endpoint"] + "/" + poll_id
        user = ctx.message.author
        ment = user.mention

        async with aiohttp.ClientSession(loop=self.bot.loop) as s:
            async with s.get(poll_url) as r:
                async with timeout(10):
                    resp = await r.json()  # a status update or youtube link

        print(f"Polled {poll_id}: {resp}")
        if resp["status"] == "complete":
            link = self.bot.settings["website"] + "/ytvideo/" + resp["url"]
            alink = "\U0001F508 " + link + "?format=opus"  # TODO: change response to determine what files are avbl
            vlink = "\U0001F4FA " + link + "?format=mkv"
            thumb_loc = self.get_thumbnail(resp["url"])
            await ctx.send(f"{ment}: your file is ready for download!\n{alink}\n{vlink}", file=discord.File(thumb_loc))
        elif resp["status"] == "error":
            await ctx.send(f"{ment}: there was an error downloading your video, try again later.")
        elif resp["status"] == "video too long":
            await ctx.send(f"{ment}: your video is too long, only videos shorter than 1 hour are supported.")
        elif resp["status"] == "livestream":
            await ctx.send(f"{ment}: livestreams are currently not supported.")
        elif resp["status"] == "in progress" or resp["status"] == "in queue":
            # not done yet, try again later
            self.bot.loop.call_later(DOWNLOAD_POLL_INTERVAL,
                                     lambda: asyncio.ensure_future(self.poll_for_completion(ctx, poll_id)))
        else:
            await ctx.send(f"{ment}: something went very wrong and the server sent a response I don't understand.")

    @commands.command()
    async def dlaudio(self, ctx, link):

        """Enqueue a youtube video to be downloaded as opus audio"""

        if verify_youtube_link(link):
            await self.queue_download(ctx, link, audio_only=True)
        else:
            await ctx.send("Must be a youtube video link, and not a playlist, livestream or short.")

    @commands.command()
    async def dlvideo(self, ctx, link):

        if verify_youtube_link(link):
            await self.queue_download(ctx, link, audio_only=False)
        else:
            await ctx.send("Must be a youtube video link, and not a playlist, livestream or short.")

    async def queue_download(self, ctx, link, audio_only):

        """Factored out so we can have different commands for audio and video"""

        uid = ctx.message.author.id
        poll_key = await self.post_video_command(link, audio_only, uid)
        page = self.bot.settings["website"] + "/videos"

        await ctx.send(
            f"I'll notify you when the download is ready! You can also see all your previous downloads at {page}")

        # now we start polling, this function adds itself to the queue until completion
        self.bot.loop.call_soon(lambda: asyncio.ensure_future(
            self.poll_for_completion(ctx, poll_key)))

    async def post_video_command(self, link, audio_only, uid):

        # first make submission form data for the HTTP post

        if audio_only:
            audio_only = "1"
        else:
            audio_only = "0"

        data = {"url": link,
                "audio_only": audio_only,
                "uid": uid}

        print(data)

        async with aiohttp.ClientSession(loop=self.bot.loop) as s:
            async with s.post(self.bot.settings["local_video_queue_endpoint"], data=data) as r:
                async with timeout(10):
                    a = await r.text()

        return a  # the poll  key for the video


async def setup(bot):

    await bot.add_cog(Ytvids(bot))
