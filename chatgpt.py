from collections import defaultdict
import datetime
from openai import AsyncOpenAI
from collections import deque
import json


class ConvoTracker:

    def __init__(self):

        with open("chatgpt_settings.json", "r") as f:
            js = json.load(f)
            self.client = AsyncOpenAI(api_key=js["key"])
            self.prompt = js["prompt"]

        self.tracking = defaultdict(lambda: deque(maxlen=6))  # record of {"role":x, "content":message} dicts
        self.times = {}  # record when the user last interacted

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
