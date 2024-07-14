from PIL import Image
import os


"""Standalone script for one-off generation of thumbnails"""


def resize(tup):

    """Not generic - just resizes a picture to 300 px wide"""

    x, y = tup
    ratio = 300.0 / x
    return int(x * ratio), int(y * ratio)


def make_thumb(pth):

    rt, fl = os.path.split(pth)
    im = Image.open(pth)
    new_size = resize(im.size)
    im = im.resize(new_size)

    thumbname = os.path.join(rt, "thumbnails", fl)

    im.save(thumbname)


if __name__ == "__main__":

    for x in os.listdir("/var/www/html/bestofhct"):
        if x == "thumbnails":
            continue
        make_thumb(os.path.join("/var/www/html/bestofhct", x))
        print(f"made thumbnail for {x}")
