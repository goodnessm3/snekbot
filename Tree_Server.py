import socket
import sys
import random
import asyncio

async def recv_int(conn):
    return socket.ntohl(int.from_bytes(conn.recv(4),sys.byteorder))

async def recv_str(conn):
    len =(await recv_int(conn))
    return conn.recv(len).decode()

async def send_int(conn,val):
    conn.send(socket.htonl(val).to_bytes(4,sys.byteorder))

async def send_str(conn,val):
    eval = val.encode()
    await send_int(conn,len(eval))
    conn.send(eval)

async def send_list(conn,list):
    await send_int(conn,len(list))
    for i in list:
        await send_str(conn,i)

class Tree_Server:
    def __init__(self , Adress , Port):
            self.addr = Adress
            self.port = Port
            self.full_addr = (self.addr,self.port)
            sock = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
            random.seed()

    async def add_tag(self,tags):
            sock = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
            sock.connect(self.full_addr)
            await send_int(sock,1)
            await send_list(sock,tags)
            sock.close()



    async def get_nr_tags(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(self.full_addr)
        await send_int(sock, 3)
        val = (await recv_int(sock))
        sock.close()
        return val


    async def get_random_tag(self):


            len = (await self.get_nr_tags())
            position = random.randint(1,len)


            sock = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
            sock.connect(self.full_addr)
            await send_int(sock,2)
            await send_int(sock,position)
            resp = (await recv_str(sock))
            sock.close()
            return resp

