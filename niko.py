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


class TwitterListener(commands.Cog):

    def __init__(self, bot):

        self.bot = bot
        auth = OAuthHandler(TI.A, TI.B)
        auth.set_access_token(TI.C, TI.D)
        self.client = tweepy.API(auth)
        self.channel_list = []
        self.latest_tweet = None
        try:
            with open("twitter_channels.txt", "r") as f:
                for line in f.readlines():
                    cid = line.rstrip("\n")
                    # bot.get_channel will just return None if you give it a string
                    self.channel_list.append(cid)
        except FileNotFoundError:
            pass

        self.bot.loop.call_later(10, lambda: asyncio.ensure_future(self.get_tweet()))
        # wait 10 seconds until bot is logged in

    async def get_tweet(self):

        print(self.channel_list)
        tweet = self.client.user_timeline("3096462845", count=1)[0]

        if tweet.in_reply_to_status_id is None and tweet.id != self.latest_tweet:
            for q in self.channel_list:
                i = self.bot.get_channel(q)
                await i.send("https://twitter.com/"+tweet.user.name+"/status/"+str(tweet.id))
                await i.send("https://tenor.com/view/niko-gif-18543948")
            self.latest_tweet = tweet.id

        self.bot.loop.call_later(300, lambda: asyncio.ensure_future(self.get_tweet()))
        # schedule to check again in 5 mins

    @commands.command()
    async def add_this(self, ctx):

        if str(ctx.message.channel.id) not in self.channel_list:
            self.channel_list.append(str(ctx.message.channel.id))
            with open("twitter_channels.txt", "a") as f:
                f.write(str(ctx.message.channel.id))
                f.write("\n")
            await ctx.message.channel.send("Added this channel to the list!")
            tweet = self.client.user_timeline("3096462845", count=1)[0]
            await ctx.message.channel.send(
                "The latest tweet is: https://twitter.com/" + tweet.user.name + "/status/" + str(tweet.id))
            await ctx.message.channel.send("https://tenor.com/view/niko-gif-18543948")
        else:
            await ctx.message.channel.send("This channel is already in the list!")

    @commands.command()
    async def niko_moment(self, ctx):

        tweet = self.client.user_timeline("3096462845", count=1)[0]
        await ctx.message.channel.send(
            "The latest niko tweet is: https://twitter.com/" + tweet.user.name + "/status/" + str(tweet.id))
        await ctx.message.channel.send("https://tenor.com/view/niko-gif-18543948")


def setup(bot):
    bot.add_cog(TwitterListener(bot))
