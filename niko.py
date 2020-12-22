from  tweepy import OAuthHandler
import tweepy
import asyncio
import discord
from discord.ext import commands
import json


class TwitInfo:

    A = B = C = D = None


TI = TwitInfo()


with open("twitter_keys.json", "r") as f:
    twitinfo = json.load(f)
    for k, v in twitinfo.items():
        TI.__setattr__(k, v)  # this is needlessly complicated


class twitterlistener(commands.Cog):
    def __init__(self,bot):
        self.bot = bot
        auth = OAuthHandler(TI.A, TI.B)
        auth.set_access_token(TI.C, TI.D)
        self.client = tweepy.API(auth)
        self.chanel_list = []
        try:
            with open("twitter_channels.txt", "r") as f:
                for line in f.readlines():
                    cid = line.rstrip("\n")
                    self.chanel_list.append(self.bot.get_channel(cid))
        except FileNotFoundError:
            pass

        bot.loop.create_task(self.get_tweet())

    async def get_tweet(self):
        latest_tweet = None
        while True:
            tweet = self.client.user_timeline("3096462845", count=1)[0]
            if tweet.in_reply_to_status_id == None and tweet.id != latest_tweet:
                for i in self.chanel_list:
                    await i.send("https://twitter.com/"+tweet.user.name+"/status/"+str(tweet.id))
                    await i.send("https://tenor.com/view/niko-gif-18543948")
                latest_tweet = tweet.id
            await asyncio.sleep(30)

    @commands.command()
    async def add_this(self,ctx):
            if (ctx.message.channel not in self.chanel_list):
                self.chanel_list.append(ctx.message.channel)
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
    async def niko_moment(self,ctx):
        tweet = self.client.user_timeline("3096462845", count=1)[0]
        await ctx.message.channel.send(
            "The latest niko tweet is: https://twitter.com/" + tweet.user.name + "/status/" + str(tweet.id))
        await ctx.message.channel.send("https://tenor.com/view/niko-gif-18543948")



def setup(bot):
    bot.add_cog(twitterlistener(bot))