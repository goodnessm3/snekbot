import random
import sys
import requests
import json
from jellyfish import levenshtein_distance as dist
from PIL import Image, ImageFont, ImageDraw
from io import BytesIO
import sqlite3
import os
import numpy
from blend_modes import lighten_only

with open("make_cards_config.json", "r") as f:
    conf = json.load(f)

DB_PATH = conf["DB_PATH"]
BASE_CARD_PATH = conf["BASE_CARD_PATH"]
HOLO_IMAGE_PATH = conf["HOLO_IMAGE_PATH"]
DB = sqlite3.connect(DB_PATH)
CUR = DB.cursor()
DEST_DIR = conf["DEST_DIR"]


def resize(tup):

    """Not generic"""

    x, y = tup
    ratio = 210.0 / x
    return int(x * ratio), int(y * ratio)
    
def make_holographic(pilimg, opacity=0.75):

    im = pilimg.convert("RGBA")
    arr = numpy.array(im)
    arrf = arr.astype(float)
    
    holo = Image.open(HOLO_IMAGE_PATH)
    holo = holo.convert("RGBA")
    h = holo.resize(im.size)  # need to match for the blending to work
    harr = numpy.array(h)
    harrf = harr.astype(float)
    
    blended_float = lighten_only(arrf, harrf, opacity)
    blended_float2 = numpy.uint8(blended_float)
    done_image = Image.fromarray(blended_float2)
    
    return done_image


def make_card(name, url, series, serial_no, n, m, attack, defense, mana, bg_col, holo=False):

    im1 = Image.open(BASE_CARD_PATH)
    
    #remote_image = requests.get(url)
    #byts = BytesIO(remote_image.content)
    #charimage = Image.open(byts)
    
    charimage = Image.open(url)  # !!CHANGED
    
    #if holo:
        #charimage = make_holographic(charimage)
    blank = Image.new("RGBA", im1.size, bg_col)
    black = Image.new("RGBA", (223, 350), (0, 0, 0))  # most pics are 225x350 but fill with black if smaller

    serial_no = str(serial_no)

    # new_size = resize(charimage.size)  # calculate the new size
    # charimage = charimage.resize(new_size)  # now apply it

    x_loc = int((blank.width - charimage.width) / 2)  # work out where to place the resized image
    if charimage.height < 350:
        y_loc = 106 + int((350 - charimage.height) / 2)
    else:
        y_loc = 106
    blank.paste(black, (39, 106))  # put on blank background first
    blank.paste(charimage, (x_loc, y_loc))  # put on blank background first
    compos = Image.alpha_composite(blank, im1)  # now overlay card with transparent window

    font = ImageFont.truetype("arial.ttf", 20)
    font2 = ImageFont.truetype("arial.ttf", 13)
    ctx = ImageDraw.Draw(compos)  # drawing context to write text

    ctx.text((65, 510), str(attack), font=font, fill=(0, 0, 0))
    ctx.text((142, 510), str(defense), font=font, fill=(0, 0, 0))
    ctx.text((214, 510), str(mana), font=font, fill=(0, 0, 0))

    if len(name) < 20:
        ctx.text((35, 30), name, font=font, fill=(0, 0, 0))
    elif len(name) < 30:
        ctx.text((35, 30), name, font=font2, fill=(0, 0, 0))
    else:
        ctx.text((35, 30), name[:30] + "...", font=font2, fill=(0, 0, 0))  # was name[:-3]
        # when the name is too long just truncate it

    if len(series) < 33:
        ctx.text((35, 60), series, font=font2, fill=(0, 0, 0))
    else:
        ctx.text((35, 60), series[:33] + "...", font=font2, fill=(0, 0, 0))

    if not holo:
        serial_text = "#" + serial_no.zfill(5) + f"  ({n} of {m})"
        ctx.text((79, 545), serial_text, font=font, fill=(0, 0, 0))
    else:
        serial_text = "#" + serial_no.zfill(5)  # holo cards aren't in numbered runs
        ctx.text((120, 545), serial_text, font=font, fill=(0, 0, 0))
        

    if holo:
        return make_holographic(compos)
    else:
        return compos
        

def series_to_cards(name, aid, serial_start=0, holo=False, namels=None):

    info = []
    bg_col = (random.randint(50, 170), random.randint(50, 170), random.randint(50, 170))
    # want a consistent colour for the whole series so set it outside the loop
    charlist = title_to_chars(aid)
    if not charlist:
        return
    m = len(charlist)

    for n, x in enumerate(charlist):
    
        if namels and n not in namels:
            continue  # we are filtering to get only the ones we want
        
        at = random.randint(1, 99)
        de = random.randint(1, 99)
        ma = random.randint(1, 99)
        charname, charlink = x

        if holo:
            charname = "Holo. " + charname

        pic = make_card(charname, charlink, name, serial_start, n + 1, m, at, de, ma, bg_col, holo)

        pic = pic.convert("RGB")  # so we can save as jpg
        pic.save(os.path.join(DEST_DIR, f"{str(serial_start).zfill(5)}.jpg"))

        info.append({"name": x[0],
                     "serial": serial_start,
                     "atk": at,
                     "def": de,
                     "mana": ma})

        serial_start += 1

    return info  # dictionary of all the info to put into the database or something


def title_to_chars(aid):

    out = []
    anime_id = aid

    character_ids = get_main_characters(f'''https://kitsu.io/api/edge/anime/{anime_id}/characters''')

    for x in character_ids:
        nfo = char_id_to_info(x)  # tuples of name, image_url
        if nfo is None:
            continue
        if not nfo in out:  # some characters are in the db twice with two different IDs
            # but they'll have the same name and image URL, so remove dupes
            out.append(nfo)
    return out


def char_id_to_info(charid):

    """Return tuple of (name, image_url)"""

    res = requests.get(f'''https://kitsu.io/api/edge/media-characters/{charid}/character''').json()

    if not res["data"]["attributes"]["image"]:
        return  # no image available

    img = res["data"]["attributes"]["image"]["original"]
    name = res["data"]["attributes"]["canonicalName"]

    return name, img



def get_main_characters(url):

    """this needs to take a URL like https://kitsu.io/api/edge/anime/{anime_id}/characters so that
    it can be recursive and visit all the pages"""

    out = []
    res = requests.get(url).json()
    for char in res["data"]:
        # if not char["attributes"]["role"] == "supporting":  # turns out this is almost everyone, usually
        out.append(char["id"])  # so just add everyone

    if "next" in res["links"].keys():  # the recursive part
        out.extend(get_main_characters(res["links"]["next"]))
    return out


def title_to_id(title):

    res1 = requests.get('''https://kitsu.io/api/edge/anime''', params={"filter[text]": title}).json()
    matches = []  # not necessarily the best, e.g. first match for K-ON is just an anime called "K"
    for x in res1["data"]:
        matches.append(((x["attributes"]["canonicalTitle"]), x["id"]))

    matches.sort(key=lambda x: dist(title, x[0]))  # use lev distance to find title closest to what we want
    return matches  # return the whole list but generally we'll just use the first item of that list


def title_to_cards(title, aid, holo=False, namels=None):

    """The only function to be called directly"""

    CUR.execute('''SELECT DISTINCT(series) FROM cards''')
    res = [x[0] for x in CUR.fetchall()]
    for q in res:
        d = dist(title, q)
        if d < 3:
            print(f"Title {title} too similar to known title {q}, continue? y/n")
            answer = None
            while not answer == "y" or answer == "n":
                answer = input(">")
                if answer == "n": 
                    sys.exit()
                elif answer == "y":
                    break

    CUR.execute('''SELECT MAX(serial) FROM cards''')
    res = CUR.fetchone()[0]
    serial_start = res + 1  # need to add 1 because new serial numbers

    batch = series_to_cards(title, aid, serial_start, holo, namels)
    if not batch:
        raise Exception("series not found")

    for n, q in enumerate(batch):

        ser = n + serial_start
        CUR.execute('''INSERT INTO cards (serial, atk, def, mana, card_name, series)
                        VALUES (?, ?, ?, ?, ?, ?)''', (ser, q["atk"], q["def"], q["mana"], q["name"], title))
    DB.commit()


if __name__ == "__main__":

    series = input("Input series name: ")
    print("Searching...")
    options = title_to_id(series)
    for x, y in enumerate(options):
        print(f"{x} - {y[0]}")
    print("Select series to use for generation: ")
    choice = int(input("> "))
    info = options[choice]  # second value in tuple is anime id   
    print("Holographic?")
    hol = input("> ")
    if hol == "n":
        print("Making cards...")
        title_to_cards(*info)
    else:
        _, aid = info
        print("Downloading character list...")
        charas = title_to_chars(aid)
        for x, y in enumerate(charas):
            print(f"{x} - {y[0]}")
        print("Type which characters to make, space delimited numbers")
        namels = input("> ")
        namels = [int(x) for x in namels.split(" ")]
        print("Making cards...")
        title_to_cards(*info, holo=True, namels=namels)
        


