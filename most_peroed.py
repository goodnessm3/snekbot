from discord.ext import commands
from discord import Embed

class Mpero(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

    @commands.command()
    async def most_peroed(self, ctx):

        msgid, ch, count = self.bot.buxman.get_most_peroed()
        chan = self.bot.get_channel(ch)
        msg = await chan.fetch_message(msgid)
        time, _ = str(msg.created_at).split(" ")
        author = msg.author.display_name
        cname = msg.channel.name
        await ctx.message.channel.send(f'{count} peros on {time} by {author} in \#{cname}:')
        await ctx.message.channel.send(msg.content)
        if msg.attachments:
            await ctx.message.channel.send(msg.attachments[0].url)
            # might have been an uploaded image, twitter posts will be captured in just the content


def setup(bot):
    bot.add_cog(Mpero(bot))

