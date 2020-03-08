import random


def weighter():

    while 1:
        yield 1.2
        yield 0.8


symbols = ["1F346", "1F344", "1F345", "1F34D", "1F34B", "1F347", "1F349"]
wt = weighter()
weights = [next(wt) for x in symbols]
mydc = {x: y for x, y in zip(symbols, weights)}
spinners = 3
long_term_payout = 0.96
jackpot_prob = ((1.0/len(symbols))**spinners) * len(symbols)
two_prob = ((1.0/len(symbols))**2) * 2 * len(symbols)
loss_prob = 1 - jackpot_prob - two_prob

two_mult = (long_term_payout + loss_prob)/(two_prob + (4 * two_prob))
jp_mult = 4 * two_mult


def spin():

    out = []
    for x in range(3):
        out.append(random.choice(symbols))
    return out


def is_jackpot(ls):

    if ls.count(ls[0]) == 3:
        return True
    else:
        return False


def is_double(ls):

    mid = ls[1]
    if ls[0] == mid or ls[2] == mid:
        return True
    else:
        return False


def calc_payout(ls):

    mult = mydc[ls[1]]
    if is_jackpot(ls):
        return jp_mult * mult
    elif is_double(ls):
        return two_mult * mult
    else:
        return -1.0


def gamble(amount):

    res = spin()
    payout = int(calc_payout(res) * amount)
    return res, payout
