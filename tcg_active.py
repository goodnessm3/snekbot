import random
import math
import asyncio  # for scheduling of regular cards
from discord.ext import commands
import datetime

rc = random.choice

CHECK_PROBS = {0: 30, 1: 50, 2: 10, 3:10}  # how likely to get 0, 1 or 2 checks
EFFECT_PROBS = {1: 100}  # eventually there will be more kinds of effects
ELEMENT_LIST = ["air", "fire", "earth", "water",
                "magma", "ooze", "ice", "smoke",
                "ash", "dust", "void", "salt",
                "radiant", "mineral", "lightning", "steam",
                "holy", "dark"]


def ri(a, b):

    """Shorter name, and never returns 0 if we have a range that goes thru 0"""

    res = 0
    while res == 0:
        res = random.randint(a, b)
    return res


def my_sigfig(num):

    """round an int to 2 significant figures"""

    if num == 0:
        return num  # can't take log of 0
    magnitude = math.log10(abs(num))
    mod = max(0, math.floor(magnitude - 1))  # 2 sig figs
    mod2 = 10 ** mod
    return int(num - num % mod2)  # only ever want ints but often these numbers had been multiplied by floats


def nice_number(num):

    return f'{num:,}'  # built-in to the formatting language, thousands separator


def chance(percentage):

    if random.randint(0, 100) < percentage:
        return True
    return False


def weighted_random(prob_dict):

    """prob_dict is in the form {result: probability of result}"""

    #if not sum(prob_dict.values()) == 100:
        #raise ValueError("probabilities must sum to 100.")

    highest = sum(prob_dict.values())  # makes the most sense if they sum to 100, but not vital

    ranges = {}  # a dict of (lower, higher) to value
    start = 0
    for k, v in prob_dict.items():
        #  compile intervals to compare to a d100 die roll
        rng = (start, v + start)
        ranges[rng] = k
        start += v

    roll = random.randint(0, highest)
    for k, v in ranges.items():
        lo, hi = k
        if lo <= roll <= hi:  # found the interval we are within
            return v

    # because of <= the distributions are not perfect, and may be off by 1%
    # this is easier than having specific code to deal with rolling 100 or 0 though

    print("Returning from weighted_random failsafe, something is wrong")
    return random.choice(list(ranges.values()))
    # failsafe if somehow the random roll didn't fall within any range
    # this should never happen


class SpecialMethodsMeta(type):

    """Through magic, this enables the Tcg_active class to keep a dict of methods that are available to active
    trading cards. So we can select from this dict randomly when compiling new card methods."""

    def __new__(mcs, name, bases, namespace, **kwargs):

        card_methods = []  # Todo: can we make this more DRY
        card_checks = []
        card_additives = []

        for key, value in namespace.items():
            # put the funcs in either dict depending on what category they are
            if callable(value) and getattr(value, "cardmethod", None):
                if value.category == "check":
                    card_checks.append(value)
                elif value.category == "effect":
                    card_methods.append(value)
                elif value.category == "additive":
                    card_additives.append(value)

        namespace["card_methods"] = card_methods  # could just combine this with the dicts below rather
        namespace["card_checks"] = card_checks
        namespace["card_additives"] = card_additives
        namespace["card_check_weights"] = {x: x.weight for x in card_checks}
        namespace["card_method_weights"] = {x: x.weight for x in card_methods}

        return super().__new__(mcs, name, bases, namespace, **kwargs)


def card_method(category, weight=100, unique=False):

    """Weight determines how likely this is to be randomly generated. If everything has weight 100 then
    all funcs have an equal chance. If one has weight 50 then it's half as likely as any default.
    E.g. 100, 100, 100 or 20, 50, 100. Can't def"""

    def inner(func):

        func.cardmethod = True  # label it as being put into the card methods dict
        func.category = category  # is it a check (returns True or False) or an action?
        func.weight = weight
        func.unique = unique

        return func

    return inner


class TcgActive(metaclass=SpecialMethodsMeta):

    def __init__(self, bot):

        self.bot = bot
        self.m = self.bot.buxman
        # self.chan = self.bot.get_channel(bot.settings["robot_zone"])

    def log(self, astr):

        # TODO: some kind of proper logging

        print("Active cards:", astr)

    def amount_check(self, uid, currency, amount, comparator):

        if currency == "snekbux":
            qty = self.m.get_bux(uid)
        elif currency == "muon":
            qty = self.m.get_muon(uid)
        else:
            return  # this is wrong anyway, should never happen

        res = qty > amount
        if comparator == "<":
            res = not res

        self.log(f"Checking {uid} {currency} is {comparator} {amount} -> {res}")
        return res

    @card_method("check", unique=True)
    def random_amount_check(self, interval):

        # generate some kwargs to be fed into the check function

        if chance(90):
            curr = "snekbux"
            amt = my_sigfig(ri(5, 250) * 1000)
        else:
            curr = "muon"
            amt = my_sigfig(ri(5, 250 * 10))

        if chance(66):
            comp = ">"
            compstr = "more than"
        else:
            comp = "<"
            compstr = "less than"

        readable = f"{compstr} {nice_number(amt)} {curr}"
        return self.amount_check,\
               {"uid":"<<owner>>", "currency": curr, "amount": amt, "comparator": comp},\
               readable

    '''  # UNDER CONSTRUCTION
    @card_method("check", weight=20)
    def random_global_card_quantity_check(self, interval):
        
        elem = rc(ELEMENT_LIST)
        amt = ri(10, 40)
        if chance(50):
            comp = ">"
            compstr = "more than"
        else:
            comp = "<"
            compstr = "fewer than"

    def global_card_quantity_check(self):
        
        res = self.m.global_card_quantity_check(amount, element)
    '''

    def card_type_quantity_check(self, uid, amount, element, comparator):

        amt = self.m.count_cards(uid, element)
        res = amt > amount
        if comparator == "<":
            res = not res

        self.log(f"Checking {uid} {element} cards are {comparator} {amount} -> {res}")
        return res

    @card_method("check")
    def random_card_type_quantity_check(self, interval):

        elem = rc(ELEMENT_LIST)
        amt = ri(5, 25)
        if chance(50):
            comp = ">"
            compstr = "more than"
        else:
            comp = "<"
            compstr = "fewer than"

        readable = f"{compstr} {amt} {elem}-type cards"
        return self.card_type_quantity_check,\
               {"uid":"<<owner>>", "amount": amt, "element": elem, "comparator": comp},\
               readable

    def infinity_orb_check(self, uid, comparator):

        print("Checking infinity orb (this doesn't do anything yet lmao)")

        if comparator == ">=":
            return False
        else:
            return True

    @card_method("check", unique=True, weight=20)
    def random_infinity_orb_check(self, interval):

        required = ri(1, 8)
        if chance(50):
            compstr = "at least"
            comp = "<="
        else:
            compstr = "at most"
            comp = ">="

        if required == 1:
            orbtext = "infinity orb"
        else:
            orbtext = "infinity orbs"
        readable = f"{compstr} {required} {orbtext}"

        return self.infinity_orb_check, {"uid":"<<owner>>", "comparator":comp}, readable


    def currency_change(self, uid, snekbux_increment, muon_increment, additive=None):

        # additive is a function that returns a number, it has already been associated with its args
        # e.g. based on the number of cards of a certain type

        if additive:
            extra = additive()
            if snekbux_increment < 0 or muon_increment < 0:  # only ever have one of these if an additive is used
                extra *= -1
                # need to invert it for the case "lose 500 snekbux plus 10 for every fire type card"
                # otherwise with 5 fire cards we'd only lose 450 and the text description wouldn't make sense
        else:
            extra = 0

        self.m.adjust_bux(uid, snekbux_increment + extra)
        self.m.adjust_muon(uid, muon_increment + extra)

        self.log(f"Adjusted {uid}'s bux and muon by {snekbux_increment} and {muon_increment}")

    @card_method("effect")
    def random_currency_change(self, interval):

        """freq
        maximum is 5000 SB per day or 25 muon per day
        """
        frequency = interval/24.0  # convert an hourly interval into a rate per day
        # so for an hourly interval of 6 hours, freq is 0.25 -> max is 1250 per func
        # for 48 hours, freq is 2, can go up to 10k because it happens every other day

        if chance(80):
            sbmod = 1
            sbword = "gain"
        else:
            sbmod = -1
            sbword = "lose"

        if chance(70):
            mumod = 1
            muword = "gain"
        else:
            mumod = -1
            muword = "lose"

        if mumod != sbmod:
            joiner = "but"
        else:
            joiner = "and"

        sb = my_sigfig(ri(500, 3000) * frequency * sbmod)
        mu = my_sigfig(ri(3, 20) * frequency * mumod)
        currency = None

        if chance(15):  # rarer chance of both things
            dc = {"snekbux_increment": sb, "muon_increment": mu}
            readable = f"{sbword} {nice_number(abs(sb))} snekbux {joiner} {muword} {abs(mu)} muon"
        else:
            if chance(80):  # most often, just a snekbux modifier
                dc = {"snekbux_increment": sb, "muon_increment": 0}
                readable = f"{sbword} {nice_number(abs(sb))} snekbux"
                currency = "snekbux"
            else:  # rarest, muon-only
                dc = {"snekbux_increment": 0, "muon_increment": mu}
                readable = f"{muword} {nice_number(abs(mu))} muon"
                currency = "muon"  # needed to scale the optional card-based additive below

        if chance(50) and currency:  # currency will be None if we add both kinds, as would need 2 incrememnts
            elem = rc(ELEMENT_LIST)
            if currency == "snekbux":
                cardnum = my_sigfig(ri(100, 300) * frequency * rc([1, -1]))  # avoid a boring small middle number
            elif currency == "muon":
                cardnum = my_sigfig(ri(5, 25) * frequency * rc([1, -1]))
            additive_args = {"uid": "<<owner>>", "element":elem, "num":cardnum}

            if cardnum > 0:
                cardword = "plus"
            else:
                cardword = "minus"

            readable_extr = f" {cardword} {nice_number(abs(cardnum))} {currency} for every {elem}-type card in your deck"
            dc["additive"] = (self.add_based_on_card_count.__name__, additive_args)  # todo: generic additives
            readable += readable_extr

        dc["uid"] = "<<owner>>"  # TODO: one day this might be the card's target
        return self.currency_change, dc, readable

    # --- functions that return numbers or modifiers etc ---

    @card_method("additive")
    def add_based_on_card_count(self, uid, element, num):

        """Plus x for every card of type y in player's possession"""

        cnt = self.m.count_cards(uid, element)
        return cnt * num  # may be negative

    def random_time_interval(self):

        """Either some days, or some hours, rounded accordingly"""

        if chance(66):
            interval = ri(1, 48)  # between 1 and 2 days
            readable = f"{interval} hours"
        else:
            days = ri(2, 15)
            interval = days * 24
            readable = f"{days} days"

        return interval, readable

    def get_random_checks(self, qty):

        """Return a random selection of criteria for a card to run, not just using random.sample or choices because
        the checks may have weights, may be unique, etc."""

        uniques = []
        out = []
        total_weight = sum([x.weight for x in self.card_checks])
        while len(out) < qty:
            this_check = random.sample(self.card_checks)

    def random_ensemble(self):

        """Generates a time interval to evaluate the card; human-readable description of the card; and dicts
        of the card's functions and arguments, to be stored in the database and interpreted on execution."""

        interval, readable_time = self.random_time_interval()

        readable_output = f"Every {readable_time}, "
        checks_output = []  # lists of tuples of (func: func args). Args may themselves be funcs of the same structure.
        effects_output = []

        num_checks = weighted_random(CHECK_PROBS)
        checks = []

        while len(checks) < num_checks:
            new = weighted_random(self.card_check_weights)
            if new.unique and new in checks:  # stop unique checks going in more than once
                pass
            else:
                checks.append(new)

        if num_checks > 0:
            readable_output += "while you have "

        num_actions = weighted_random(EFFECT_PROBS)
        effects = random.sample(self.card_methods, num_actions)

        for indx, x in enumerate(checks):
            funct, kwargs, rdbl = x(self, interval)  # get the function to be run
            # all function-making functions must take interval as the second argument
            readable_output += rdbl
            if indx < len(checks) - 1:  # don't want a final "and"
                readable_output += " and "
            checks_output.append((funct.__name__, kwargs))
            # we use the function name because we are just storing a recipe for making the function, in JSON

        if len(checks) > 0:
            readable_output += ", "

        # we need 2 separate iterations because need different joiners between strs
        for indx, x in enumerate(effects):
            funct, kwargs, rdbl = x(self, interval)
            # all function-making functions must take interval as the second argument

            readable_output += rdbl
            if indx < len(effects) - 1:
                readable_output += ", "
            effects_output.append((funct.__name__, kwargs))

        readable_output += "."

        return interval, checks_output, effects_output, readable_output

    def json_substitution(self, json, owner, target):

        """replaces instances of '<<owner>>' and '<<target>>' with the respective uids passed in."""

        substs = []

        for k, v in json.items():
            if v == "<<owner>>":
                substs.append((k, owner))
            if v == "<<target>>":
                substs.append((k, target))
            if type(v) == list:  # a list of [func name, {kwargs}] - need to go in and substitute those kwargs too
                newlist = []
                for q in v:
                    if type(q) == dict:
                        newlist.append(self.json_substitution(q, owner, target))
                        # need to recursively evaluate, because some args might be funcs with dicts of their own
                        # the only reason to find a dict here is if it's some kwargs
                    else:
                        newlist.append(q)
                substs.append((k, newlist))

        for tup in substs:
            k, v = tup
            json[k] = v  # didn't want to mutate the dictionary while iterating over it, maybe that's fine

        return json

    def factory(self, func, *args, **kwargs):

        """Returns a function ready to be combined with others and run per time increment"""

        def inner():
            return func(*args, **kwargs)

        return inner

    def function_factory(self, tup):

        """Expects a tuple of (func name, {kwargs}). Returns a function with the kwargs 'baked in', so it can
        be evaluated by passing no arguments. kwargs may be tuples of this kind, which will also be evaluated
        recursively."""

        funcname, kwargs = tup  # first thing we do is unpack the list - the name of the func, and its kwargs
        # we always have kwargs rather than args as well, for simplicity

        f = getattr(self, funcname)  # convert function string name into an actual function

        for a, b in kwargs.items():
            if type(b) == list:  # the only reason to have a list is that we want to make a function
                # these were supposed to be tuples but round-tripping to json and back turns tuples into lists >_<
                kwargs[a] = self.function_factory(b)  # I'm so clever this is unbelievable

        return self.factory(f, **kwargs)  # this "bakes in" the arguments and returns a func to be evaluated

    def evaluate_card(self, serial):

        """Look up a card in the db. Interpret all the checks and functions described by the JSON, and run the funcs
        if the checks succeed."""

        restuple = self.m.get_card(serial)
        serial, owner, atk, defense, mana, card_name, series, element, target_uid,\
        next_runtime, checks, funcs, immunity, readable, timedelta, guarantee_time = restuple
        # todo: DB row factory or whatever it is

        chks = []
        fx = []

        print(restuple)

        for tup in checks:
            a, b = tup
            b = self.json_substitution(b, owner, target_uid)
            evaluated = self.function_factory((a, b))
            chks.append(evaluated)
        for tup in funcs:
            a, b = tup
            b = self.json_substitution(b, owner, target_uid)
            evaluated = self.function_factory((a, b))
            fx.append(evaluated)

        # now we have "compiled" the ensemble of checks and functions, run them!

        self.log(f"Evaluating {card_name}: {readable} for {owner}")

        if all([x() for x in chks]):  # run all checks and make sure they all return true
            for q in fx:
                q()
                self.log(f"Evaluated card {serial}.")
        else:
            self.log(f"Card {serial} was not evaluated because its checks failed.")


class ActiveCards(commands.Cog):

    def __init__(self, bot):

        """Just an async class to delegate things to all the active carder code, which is not async"""

        self.carder = TcgActive(bot)
        self.bot = bot
        self.bot.loop.create_task(self.check_schedule())
        self.scheduled_cards = []
        self.check_freq = 10  # how many seconds between checks, this must also be updated in the SQL query!
        # we are checking quite frequently to head off the possibility that someone sells or transfers a card
        # after its task has been scheduled. TODO: really we should keep a handle from scheduled tasks,
        # can cancel them if card ownership changes

    async def check_schedule(self):

        """Runs regularly, looks in the DB for cards that need to be run and adds them into the bot loop
        if there's less than an hour until it runs. This is first added to the bot loop in the init method."""

        print(f"Async check schedule function at {datetime.datetime.now()}")
        print("Scheduled cards list is:", self.scheduled_cards)

        to_run = self.bot.buxman.get_scheduled_cards()
        print("Cards to run from DB are: ", to_run)

        for tup in to_run:
            serial, time_to_run = tup  # time_to_run is a timedelta, the difference between now and when it's scheduled

            if time_to_run.days < 0: # a negative timedelta, which has negative days and then positive everything else
                # next time was in the past, probably the bot has been turned off.
                print(f"Card {serial} next runtime was in the past, updating its schedule")
                self.bot.buxman.reschedule_card(serial, reset=True)  # update the interval into the future
                # reset just adds the current time to the time interval of the card
                # this is an imperfect solution if the time delta is really long, like several days
            else:
                print(f"Card {serial} will run after {time_to_run}")
                if not serial in self.scheduled_cards:
                    #print(f"Scheduling an async task for card {serial}.")
                    #delta = time_to_run - datetime.datetime.now()  # this only works if ttr is in the future!
                    #secs = delta.seconds
                    ttr = time_to_run.seconds  # asyncio loop time is NOT THE SAME AS THE SYSTEM TIME!!!
                    self.scheduled_cards.append(serial)
                    print(f"Evaluation of {serial} in {ttr} seconds.")
                    self.bot.loop.call_at(self.bot.loop.time() + ttr, self.carder.evaluate_card, serial)
                    self.bot.loop.call_at(self.bot.loop.time() + ttr, self.reschedule_card, serial)
                else:
                    print(f"Card {serial} is already enqueued, not creating a task.")

        self.bot.loop.call_later(self.check_freq, lambda: asyncio.ensure_future(self.check_schedule()))

    def reschedule_card(self, serial):

        print(f"Rescheduling {serial}, reset = False")
        self.bot.buxman.reschedule_card(serial)
        self.scheduled_cards.remove(serial)


async def setup(bot):

    await bot.add_cog(ActiveCards(bot))

