import datetime
from collections import defaultdict


class LeakyBuckets:

    """Per-user tracking. Rate refers to how long to wait in seconds between decrements. Check function
    returns true if increments have exceeded threshold. Updates happen before each check."""

    # TODO: there is also a bucket tracker in mydecorators, make this generic

    def __init__(self, threshold, rate):

        self.buckets = defaultdict(lambda: 0)
        self.update_times = {}
        self.threshold = threshold
        self.rate = rate

    def increment_user(self, uid):

        self.buckets[uid] += 1
        self.update_times[uid] = datetime.datetime.now()

    def check_user(self, uid):

        now = datetime.datetime.now()
        prev = self.update_times.get(uid, None)  # user might not be in the dict yet
        if not prev:
            return False  # user wasn't even in the tracker, so isn't limited, return early

        delta = now - prev
        # first, we check how long it's been since the last increment, and decrement based on the rate
        decrement = delta.seconds//self.rate
        newval = max(self.buckets[uid] - decrement, 0)  # stop it going negative
        self.buckets[uid] = newval

        return self.buckets[uid] > self.threshold