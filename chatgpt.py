from collections import defaultdict
import datetime
from openai import AsyncOpenAI, BadRequestError
from collections import deque
import json
import asyncio
from utility import LeakyBuckets
import re
import hashlib

rl = chr(128680)  # emoji siren light character for moderation message
DISCORD_ID_FINDER = re.compile("<@[0-9]+>")
DISCORD_ID_EXTRACTOR = re.compile("<@([0-9]+)>")


class ConvoTracker:

    def __init__(self, buxman):

        with open("chatgpt_settings.json", "r") as f:
            js = json.load(f)
            self.client = AsyncOpenAI(api_key=js["key"])
            self.prompt = js["prompt"]

        self.tracking = defaultdict(lambda: deque(maxlen=12))  # record of {"role":x, "content":message} dicts
        self.times = {}  # record when the user last interacted
        self.moderated = LeakyBuckets(2, 10)  # no more than 2 moderation failures, decrement every 600s
        # record how many times a user trips the moderation filters. Temporarily disable function if they are too crazy.
        self.buxman = buxman  # need a reference to this to log convos

    def reload_prompt(self):

        with open("chatgpt_settings.json", "r") as f:
            js = json.load(f)
            self.prompt = js["prompt"]

    def substitute_uids(self, astr):

        ids = DISCORD_ID_FINDER.findall(astr)
        if not ids:
            return astr  # nothing to do, the most frequent case
        mapping = {}
        for x in ids:
            numeric = DISCORD_ID_EXTRACTOR.search(x)
            name = self.buxman.uid_to_screen_name(numeric.groups()[0])
            mapping[x] = name

        for k, v in mapping.items():
            if v:  # don't try to substitute a None, this might happen if the user isn't in the names table somehow
                astr = astr.replace(k, v)

        return astr

    async def get_moderation(self, uid, message):

        response = await self.client.moderations.create(input=message)

        out = []

        for x in response.results[0].categories:
            name, result = x
            if result:
                out.append(name)  # just gather where the filter results are True

        return out

    async def get_response(self, cid, message):

        """Returns the answer, and the amount of prompt tokens and completion tokens it used."""

        message = self.substitute_uids(message)  # replace discord mentions with the actual screen name

        last_query = self.times.get(cid, None)
        now = datetime.datetime.now()

        if last_query:
            delta = now - last_query
            if delta.seconds > 900:
                self.tracking[cid].clear()  # it's been more than 900 seconds, start fresh

        self.times[cid] = now  # update when most recently used

        self.tracking[cid].append({"role": "user", "content": message})
        # push new message into deque, old one will be lost
        base = [{"role": "system", "content": self.prompt}]
        anon = self.buxman.get_anonymous_uid(cid)
        try:
            response = await self.client.chat.completions.create(messages=base + list(self.tracking[cid]),
                                                                 model="gpt-3.5-turbo",
                                                                 temperature=0.8,
                                                                 top_p=0.8,
                                                                 user=anon,
                                                                 max_tokens=2500)
            # temp and top p changed to 0.8 from 0.6
            answer = response.choices[0].message.content
            context_length = response.usage.total_tokens
            print(context_length)  # temporary, to track how much context is typically used
            pt = response.usage.prompt_tokens
            ct = response.usage.completion_tokens

        except BadRequestError:
            answer = "The context got too long, please try again."
            pt = ct = 0
            for x in range(4):
                self.tracking[cid].popleft()  # pop the oldest 4 messages to cut down the context length

        self.tracking[cid].append({"role": "assistant", "content": answer})

        try:
            return answer, pt, ct
        except Exception as e:
            print(e)
            return "Something went wrong!", 0, 0

    async def get_moderated_response(self, uid, cid, message):

        if self.moderated.check_user(uid):  # it returns True if user has exceeded the threshold
            return "Blocked for tripping the content filter too many times, try again later."

        if len(message) > 400:
            message = "The user tried to submit a very long message, please ask them to submit shorter ones."

        result = asyncio.gather(self.get_response(cid, message), self.get_moderation(uid, message))
        answer_tuple, moderation = await result
        # gather lets us run the moderation and answer simultaneously, so we don't delay the response too much
        if moderation:
            st = f"{rl} Uh oh! Your message tripped the "
            if len(moderation) == 1:
                st += f"{moderation[0]} filter!"
            else:
                st += f"{', '.join(moderation)} filters!"
            st += f" Try to be more careful with your responses! {rl}"

            self.buxman.log_chatgpt_message(uid, cid, "user", message, 0, True)  # 0 tokens
            self.moderated.increment_user(uid)
            return st
        else:
            answer, pt, ct = answer_tuple
            self.buxman.log_chatgpt_message(uid, cid, "user", message, pt)
            self.buxman.log_chatgpt_message(uid, cid, "assistant", answer, ct)
            return answer
