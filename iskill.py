import random

def is_kill(nm):


    do = ["drink brain fluid","eating blini","eat gulyás","watch animes","eat hortobágyi palacsinta","eating töltött káposzta","cook csirkepaprikás","cooking székelykáposzta"]
    name = ["Piotr","Dmitri","Sven","Igor","Ivan"]
    base = '''apology for poor english\nwhere were you when {dead} dies?\ni was at home {doing} when {name} ring\n"{dead} is kill"\n"no"\nand you???'''
    return base.format(dead=nm,doing=random.choice(do),name=random.choice(name))
