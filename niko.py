from tweepy import OAuthHandler
import tweepy
import asyncio
from discord.ext import commands
import json


class TwitInfo:

    A = B = C = D = None


TI = TwitInfo()


with open("twitter_keys.json", "r") as f:
    twitinfo = json.load(f)
    for k, v in twitinfo.items():
        TI.__setattr__(k, v)  # this is needlessly complicated


class TwitterCheck:

    """Object for a vtuber twitter user. The consoom_tweets function will go through all recent tweets until
    it sees the newest tweet the last time it checked. If a tweet mentioning 'schedule' is found,
    consoom_tweets returns the URL of that tweet."""

    def __init__(self, user, myclient):

        new = myclient.user_timeline(screen_name=user, count=1)
        self.last = new[0].id
        self.user = user
        self.myclient = myclient

    def consoom_tweets(self):

        print(f"Checking for a schedule from {self.user}")
        tweets = self.myclient.user_timeline(screen_name=self.user,count=10,exclude_replies=True)
        # get 10 at a time and stop when we find the most recent one from last time we looked
        current_id = None
        t = iter(tweets)
        total = 0
        found = False
        while not current_id == self.last:
            total += 1
            try:
                tw = next(t)
            except StopIteration:
                # time to get a new batch. We can't just count the index because if we ask for 10
                # but exclude replies, we might actually get less than 10 back
                tweets = self.myclient.user_timeline(screen_name=self.user, count=10, max_id=current_id)
                t = iter(tweets)
                tw = next(t)
            if "schedule" in tw.text.lower():
                if "media" in tw.entities.keys():  # check if the tweet has an image
                    found = True
                    break
            current_id = tw.id

            if total > 100:
                break  # safeguard, something has gone wrong
        self.last = current_id
        if found:
            return f"https://twitter.com/{self.user}/status/{str(tw.id)}"


class TwitterListener(commands.Cog):

    def __init__(self, bot):

        self.bot = bot
        auth = OAuthHandler(TI.A, TI.B)
        auth.set_access_token(TI.C, TI.D)
        self.client = tweepy.API(auth)
        self.channel_list = []
        self.latest_tweet = None
        self.chuubas = []
        self.thread = None  # where we post the vtuber schedules
        with open("vtubechannel.txt", "r") as f:
            self.thread = self.bot.get_channel(int(f.read().rstrip("\n")))
        self.bot.loop.call_soon(lambda: asyncio.ensure_future(self.thread.send("I'll post vtuber schedules here.")))

        try:
            with open("twitter_channels.txt", "r") as f:
                for line in f.readlines():
                    cid = int(line.rstrip("\n"))
                    # bot.get_channel will just return None if you give it a string
                    self.channel_list.append(cid)
        except FileNotFoundError:
            pass

        with open("vtubers.txt", "r") as f:
            for line in f.readlines():
                self.chuubas.append(TwitterCheck(line.rstrip("\n"), self.client))
                # set up objects to monitor each vtuber twitter account

        self.bot.loop.call_later(10, lambda: asyncio.ensure_future(self.get_tweet()))
        # wait 10 seconds until bot is logged in

        self.bot.loop.call_later(5, lambda: asyncio.ensure_future(self.monitor_chuubas()))

    async def get_tweet(self):

        tweet = self.client.user_timeline(user_id="3096462845", count=1)[0]

        if tweet.in_reply_to_status_id is None and tweet.id != self.latest_tweet:
            for q in self.channel_list:
                i = self.bot.get_channel(q)  # get_channel expects an INT
                await i.send("https://twitter.com/"+tweet.user.name+"/status/"+str(tweet.id))
                await i.send("https://tenor.com/view/niko-gif-18543948")
            self.latest_tweet = tweet.id

        self.bot.loop.call_later(300, lambda: asyncio.ensure_future(self.get_tweet()))
        # schedule to check again in 5 mins

    async def monitor_chuubas(self):

        for q in self.chuubas:
            tw = q.consoom_tweets()
            if tw:
                await self.thread.send(tw)
            await asyncio.sleep(500)  # space out the checking

        print("checked all vtube schedules, re-scheduling check function")
        self.bot.loop.call_later(500, lambda: asyncio.ensure_future(self.monitor_chuubas()))


    @commands.command()
    async def add_this(self, ctx):

        if ctx.message.channel.id not in self.channel_list:
            self.channel_list.append(ctx.message.channel.id)
            with open("twitter_channels.txt", "a") as f:
                f.write(str(ctx.message.channel.id))
                f.write("\n")
            await ctx.message.channel.send("Added this channel to the list!")
            tweet = self.client.user_timeline(user_id="3096462845", count=1)[0]
            await ctx.message.channel.send(
                "The latest tweet is: https://twitter.com/" + tweet.user.name + "/status/" + str(tweet.id))
            await ctx.message.channel.send("https://tenor.com/view/niko-gif-18543948")
        else:
            await ctx.message.channel.send("This channel is already in the list!")

    @commands.command()
    async def niko_moment(self, ctx):

        tweet = self.client.user_timeline(user_id="3096462845", count=1)[0]
        await ctx.message.channel.send(
            "The latest niko tweet is: https://twitter.com/" + tweet.user.name + "/status/" + str(tweet.id))
        await ctx.message.channel.send("https://tenor.com/view/niko-gif-18543948")

    @commands.command()
    async def smonitor(self, ctx, chuuba):

        try:
            tweet = self.client.user_timeline(screen_name=chuuba, count=1)[0]
        except:
            await ctx.message.channel.send("Doesn't look like that's a valid twitter handle.")
            return

        with open("vtubers.txt", "a") as f:
            f.write(chuuba)
            f.write("\n")

        self.chuubas.append(TwitterCheck(chuuba, self.client))
        await ctx.message.channel.send(f"I'll monitor for schedules from {chuuba}.")

    @commands.command()
    async def monitoreds(self, ctx):

        with open("vtubers.txt", "r") as f:
            ms = f.read()
        await ctx.message.channel.send("I am currently monitoring:\n" + ms)




def setup(bot):
    bot.add_cog(TwitterListener(bot))
