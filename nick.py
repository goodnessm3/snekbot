import random

names = []
used = []

try:
    with open("nicks.txt", "r") as f:
        for line in f.readlines():
            names.append(line.rstrip("\n"))
except FileNotFoundError:
    pass

a = ["Your new nickname is ",
     "You shall be called ",
     "How about we call you ",
     "Your name is now ",
     "Your nickname is now ",
     "We'll call you ",
     "How about ",
     "Let's call you "]

def get_nick():

    nm = random.choice(names)
    if not names:
        return None  # propagate None if we didn't manage to load a file
    return random.choice(a) + nm + "."