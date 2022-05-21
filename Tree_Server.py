import socket
import sys
import random
import asyncio

async def recv_int(conn):
    loop = asyncio.get_running_loop()
    bytes = await loop.sock_recv(conn, 4)
    return socket.ntohl(int.from_bytes(bytes, sys.byteorder))

async def recv_str(conn):
    loop = asyncio.get_running_loop()
    len = await recv_int(conn)
    bytes = await loop.sock_recv(conn, len)
    return bytes.decode()

async def send_int(conn,val):
    loop = asyncio.get_running_loop()
    bytes = socket.htonl(val).to_bytes(4,sys.byteorder)
    await loop.sock_sendall(conn, bytes)

async def send_str(conn,val):
    loop = asyncio.get_running_loop()
    encval = val.encode()
    await send_int(conn,len(encval))
    await loop.sock_sendall(conn, encval)

async def send_list(conn,list):
    await send_int(conn,len(list))
    for i in list:
        await send_str(conn,i)

class Tree_Server:
    def __init__(self , Adress , Port):
        self.addr = Adress
        self.port = Port
        self.full_addr = (self.addr,self.port)
        random.seed()

    async def add_tag(self,tags):
        loop = asyncio.get_running_loop()
        sock = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        await loop.sock_connect(sock, self.full_addr)
        await send_int(sock,1)
        await send_list(sock,tags)
        sock.close()



    async def get_nr_tags(self):
        loop = asyncio.get_running_loop()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        await loop.sock_connect(sock, self.full_addr)
        await send_int(sock, 3)
        val = (await recv_int(sock))
        sock.close()
        return val


    async def get_random_tag(self):
        loop = asyncio.get_running_loop()
        
        len = (await self.get_nr_tags())
        position = random.randint(1,len)
        
        sock = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        await loop.sock_connect(sock, self.full_addr)
        await send_int(sock,2)
        await send_int(sock,position)
        resp = await recv_str(sock)
        sock.close()
        return resp

