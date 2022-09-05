import random
import datetime
import asyncio
import functools
from collections import defaultdict
import json

with open("watch_list.json", "r") as f:
    WATCH_LIST = json.load(f)

FUNC_TIMES = defaultdict(lambda: defaultdict(TimeTracker))
FUNC_LEAKYBUCKETS = defaultdict(lambda: defaultdict(lambda: BucketTracker(6, 60)))
FUNC_TOTALBUCKETS = defaultdict(lambda: defaultdict(TotalTracker))
# we can look up by [user][function] to see what times a given user used a given function

REACTION_EMOJIS = [
            ("\U00002705", "check mark"),
            ("\U0001F49A", "green heart"),
            ("\U0001F341", "maple leaf"),
            ("\U0001F34B", "lemon"),
            ("\U0001F955", "carrot"),
            ("\U0001F980", "crab"),
            ("\U0001F9F1", "brick"),
            ("\U0001F4CE", "paperclip"),
        ]


class TimeTracker:

    tolerance = datetime.timedelta(seconds=5.0)

    def __init__(self):

        self.times = []
        self.awaiting = False  # if we are waiting for a captcha response, don't send any more captchas

    def update(self):

        self.times.append(datetime.datetime.now())
        if len(self.times) > 10:
            self.times.pop(0)

    def check_repetition(self):

        if len(self.times) < 2:
            return False  # too new to know whether repetition happened

        deltas = []
        for x in range(1, len(self.times)):
            deltas.append(abs(self.times[x] - self.times[x - 1]))

        count = 0
        delta = self.times[-1] - self.times[-2]
        for x in deltas[::-1]:
            if delta - self.tolerance < x < delta + self.tolerance:
                count += 1
            else:
                break

        if count > 4:
            return True
        else:
            return False


class BucketTracker:

    """Every 'per' seconds, the counter is decremented by 1. While the counter exceeds 'threshold', captchas
    will be required."""

    def __init__(self, threshold, per):

        self.count = 0
        self.threshold = threshold
        self.per = per
        self.last_updated = datetime.datetime.now()
        self.awaiting = False

    def update(self):

        timenow = datetime.datetime.now()
        delta = timenow - self.last_updated
        increments = int(delta.seconds/self.per)
        self.count -= increments
        self.last_updated = timenow
        self.count += 1

    def check(self):

        return self.count > self.threshold


class TotalTracker:

    def __init__(self):

        self.count = 1
        self.awaiting = False

    def update(self):

        self.count += 1
        if self.count > 100:
            self.count = 0

    def check(self):

        return self.count % 4 == 0


def captcha(coro):

    @functools.wraps(coro)  # I don't understand why I need this
    async def inner(*args, **kwargs):

        ctx = args[1]
        cog = args[0]
        user = ctx.message.author.id

        if user in WATCH_LIST:  # stringent trackers based on total command use for heavy users
            tracker_obj = FUNC_TOTALBUCKETS[user][coro]
        else:  # more lenient time-based buckets for regular users
            tracker_obj = FUNC_LEAKYBUCKETS[user][coro]

        repeated = tracker_obj.check()
        if not repeated:
            tracker_obj.update()
            # stop updating when threshold reached otherwise we'll continue to increment the counter regardless
            # of whether the captcha gets solved

        if tracker_obj.awaiting:
            return  # user is trying to use this command again without solving the captcha, ignore

        if not repeated:
            return await coro(*args, **kwargs)  # complete function as normal, tracker did not reach threshold

        # otherwise, we need to present a captcha before the user can get the result of their command
        tracker_obj.awaiting = True  # block other captchas appearing until we get a response for this one
        tracker_obj.update()  # TODO: think more carefully about where this should happen

        emojicode, emojiname = random.choice(REACTION_EMOJIS)  # the one we want the user to react with
        samp = []
        while len(samp) < 5:
            # we can't just use random.sample() because all must be unique
            new = random.choice(REACTION_EMOJIS)
            if new[0] == emojicode or new in samp:
                continue
            else:
                samp.append(new)
        others = [x[0] for x in samp]  # just the emoji symbol itself, not the name
        others.append(emojicode)
        msg = await ctx.message.channel.send(
            f"It looks like you're enjoying this feature a lot! Click the {emojiname} to continue using it!")

        random.shuffle(others)  # the desired emoji must not appear in a consistent place that can be clicked
        for x in others:
            await msg.add_reaction(x)

        counter = 0  # just cancel if the captcha isn't fulfilled in a certain amount of time
        while True:  # loop for awaiting the user's reaction
            await asyncio.sleep(1.0)
            counter += 1
            ms = await ctx.message.channel.fetch_message(msg.id)
            # need to re-get the message now that reactions have been added
            users = set()
            for x in ms.reactions:
                if not x.emoji == emojicode:
                    continue  # only care about the desired react
                async for u in x.users():
                    users.add(u)  # accumulate everyone who reacted

            if ctx.message.author in users:  # the author of the original message has reacted correctly
                break

            if counter > 10:  # 10 second timeout based on sleep interval
                tracker_obj.awaiting = False
                return await ctx.message.channel.send("The captcha timed out!")

        # having broken out of the loop we can now return the result of the original command that was requested
        tracker_obj.awaiting = False
        return await coro(*args, **kwargs)

    return inner
