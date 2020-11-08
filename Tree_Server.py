import socket
import sys
import random

def recv_int(conn):
    return socket.ntohl(int.from_bytes(conn.recv(4),sys.byteorder))

def recv_str(conn):
    len = recv_int(conn)
    return conn.recv(len).decode()

def send_int(conn,val):
    conn.send(socket.htonl(val).to_bytes(4,sys.byteorder))

def send_str(conn,val):
    eval = val.encode()
    send_int(conn,len(eval))
    conn.send(eval)


class Tree_Server:
    def __init__(self , Adress , Port):
            self.addr = Adress
            self.port = Port
            self.full_addr = (self.addr,self.port)
            sock = socket.socket(socket.AF_INET,socket.SOCK_STREAM)

    def add_tag(self,tag):
            sock = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
            sock.connect(self.full_addr)
            send_int(sock,1)
            send_str(sock,tag)
            sock.close()



    def get_nr_tags(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(self.full_addr)
        send_int(sock, 3)
        val = recv_int(sock)
        sock.close()
        return val


    def get_random_tag(self):


            len = self.get_nr_tags()
            random.seed()
            position = random.randint(1,len)


            sock = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
            sock.connect(self.full_addr)
            send_int(sock,2)
            send_int(sock,position)
            resp = recv_str(sock)
            sock.close()
            return resp


