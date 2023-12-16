import discord
from discord.ext import commands
import asyncio
import aiohttp
from async_timeout import timeout
from io import BytesIO
import subprocess as sp


class Stream(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.stream_thumbnail_url = self.bot.settings["stream_thumbnail_url"]
        self.source = self.bot.settings["time_token_source"]
        self.secret = self.bot.settings["time_token_secret"]  # the credential to use to get a key from the source

    @commands.command()
    async def schedule(self, ctx):

        with open(self.bot.settings["now_playing_file"], "r") as f:
            nowplaying = f.read().rstrip("\n")  # it's only ever a one-line file

        with open(self.bot.settings["schedule_file"], "r") as f:
            whole_schedule = list(map(lambda q: q.rstrip("\n"), f))

        out = []
        for q in whole_schedule:
            if q == nowplaying:
                out.append(q + " <-- NOW PLAYING")
            else:
                out.append(q)

        video_list = "\n".join(out)
        await ctx.send(f'''```Snek video queue:\n\n{video_list}```''')

    @commands.command()
    async def tv(self, ctx):

        async with aiohttp.ClientSession(loop=self.bot.loop) as s:
            async with s.post(self.source, data={"key": self.secret}) as r:
                async with timeout(10):
                    stream_token = await r.text()  # used to make a link valid for a limited time

        # for Windows
        #cmd = f'''ffmpeg -i {self.stream_thumbnail_url} -f image2pipe -vframes 1 -q:v 2 -'''
        # for Linux TODO: detect platform and run appropriate command
        cmd = ["ffmpeg", "-i", "{self.stream_thumbnail_url}", "-f", "image2pipe", "-vframes", "1", "-q:v", "2", "-"]
        pipe = sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.PIPE, bufsize=10 ** 8)

        try:
            imagedata2 = pipe.communicate(timeout=15)
        except sp.TimeoutExpired:
            print("ffmpeg timed out getting thumbnails")
            pipe.kill()
            await ctx.send("Error getting stream thumbnail, maybe the stream is broken.")
            return

        imagedata = imagedata2[0]
        flo = BytesIO(imagedata)

        with open(self.bot.settings["now_playing_file"], "r") as f:
            for line in f:
                pass  # just want to get to the very last line
            last = line.rstrip("\n")

        with open(self.bot.settings["schedule_file"], "r") as f:
            whole_schedule = list(map(lambda q: q.rstrip("\n"), f))
            a = False
            next_up = "Not found"  # in case no match is found
            for x in whole_schedule:
                if a:
                    next_up = x
                    break
                if x == last:
                    a = True

        full_stream_url = self.bot.settings['stream_page'] + f'''?token={stream_token}'''
        await ctx.send(f"Now playing: {last} at {full_stream_url}. Next up: {next_up}. "
                       f"Type 'snek schedule' for full listing!",
                       file=discord.File(flo,
                        filename="image.jpg"))


async def setup(bot):

    await bot.add_cog(Stream(bot))
