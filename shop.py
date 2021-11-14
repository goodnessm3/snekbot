from discord.ext import commands
import secrets
import socket
import os
import xml.etree.ElementTree as ElementTree
import random
from async_timeout import timeout
import json
import asyncio
from collections import defaultdict
import clean_text as ct
from Tree_Server import Tree_Server
import aiohttp


class Shop(commands.Cog):

    def __init__(self, bot):

        self.bot = bot
        self.bot.loop.create_task(self.shop_socket())

    @commands.command()
    async def shop(self, ctx):

        u = ctx.message.author
        rand = secrets.token_hex(4)
        self.bot.buxman.anticipate_shop_activation(u.id, rand, u.display_name)
        await u.send(f"Enter this code on the snekbux store web page: {rand}")

    async def shop_socket(self):

        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind(('127.0.0.1', 12434))
        while True:
            server.listen(1)
            client, _ = await self.bot.loop.sock_accept(server)
            while True:
                await asyncio.sleep(1)
                data = await self.bot.loop.sock_recv(client, 4096)  # a GET request from the store web page
                if data:
                    await self.bot.loop.sock_sendall(client, bytes("HTTP/2 200 OK", "UTF-8"))
                    # have to send a 200 OK back, otherwise the browser will keep sending the request
                    q = (data.decode("UTF-8"))
                    first = q.split(os.linesep)[0]
                    if first:
                        command = (first[4:-9])  # strip off "GET " and " HTTP/1.1"
                        await self.process_socket(command)

                client.close()
                break

    async def process_socket(self, command):

        parts = command.split("/")  # it's basically in URL format
        print(parts)

def setup(bot):

    bot.add_cog(Shop(bot))
