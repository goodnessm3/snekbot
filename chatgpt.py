from collections import defaultdict
import datetime
from openai import AsyncOpenAI
from collections import deque
import json
import asyncio
from utility import LeakyBuckets


rl = chr(128680)  # emoji siren light character for moderation message


class ConvoTracker:

    def __init__(self):

        with open("chatgpt_settings.json", "r") as f:
            js = json.load(f)
            self.client = AsyncOpenAI(api_key=js["key"])
            self.prompt = js["prompt"]

        self.tracking = defaultdict(lambda: deque(maxlen=6))  # record of {"role":x, "content":message} dicts
        self.times = {}  # record when the user last interacted
        self.moderated = LeakyBuckets(2, 10)  # no more than 2 moderation failures, decrement every 600s
        # record how many times a user trips the moderation filters. Temporarily disable function if they are too crazy.

    async def get_moderation(self, uid, message):

        response = await self.client.moderations.create(input=message)

        out = []

        for x in response.results[0].categories:
            name, result = x
            if result:
                out.append(name)  # just gather where the filter results are True

        return out

    async def get_response(self, uid, message):

        last_query = self.times.get(uid, None)
        now = datetime.datetime.now()

        if last_query:
            delta = now - last_query
            if delta.seconds > 900:
                self.tracking[uid].clear()  # it's been more than 900 seconds, start fresh

        self.times[uid] = now  # update when most recently used

        self.tracking[uid].append(
            {"role": "user", "content": message})  # push new message into deque, old one will be lost
        base = [{"role": "system", "content": self.prompt}]
        response = await self.client.chat.completions.create(messages=base + list(self.tracking[uid]),
                                                             model="gpt-3.5-turbo",
                                                             temperature=0.6,
                                                             top_p=0.6)
        answer = response.choices[0].message.content
        self.tracking[uid].append({"role": "assistant", "content": answer})
        try:
            return answer
        except Exception as e:
            print(e)
            return "Something went wrong!"

    async def get_moderated_response(self, uid, message):

        if self.moderated.check_user(uid):  # it returns True if user has exceeded the threshold
            return "Blocked for tripping the content filter too many times, try again later."

        result = asyncio.gather(self.get_response(uid, message), self.get_moderation(uid, message))
        answer, moderation = await result
        # gather lets us run the moderation and answer simultaneously, so we don't delay the response too much
        if moderation:
            st = f"{rl} Uh oh! Your message tripped the "
            if len(moderation) == 1:
                st += f"{moderation[0]} filter!"
            else:
                st += f"{', '.join(moderation)} filters!"
            st += f" Try to be more careful with your responses! {rl}"
            self.moderated.increment_user(uid)
            return st
        else:
            return answer
