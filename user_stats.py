import sqlite3
import re
from collections import defaultdict
import datetime


def get_max(dc):
    """Takes a dictionary and returns the key and value for the pair with the largest value"""

    max_cnt = 0
    max_key = None
    for k, v in dc.items():
        if v > max_cnt:
            max_cnt = v
            max_key = k

    return max_key, max_cnt


class Manager:

    """Class to manage a database of discord id relating to various attributes"""

    def __init__(self, bot):

        self.db = sqlite3.connect("user_stats.sqlite3")
        self.cursor = self.db.cursor()
        self.bot = bot
        self.input_checker = re.compile("[0-9A-Za-z!,.?&\"'+-]{,50}")

    def check_input_string(self, astr):

        if self.input_checker.fullmatch(astr) is None:
            return False
        else:
            return True

    def get_bux(self, uid):

        self.cursor.execute('''select bux from stats where uid = ?''', (uid,))
        
        restuple = self.cursor.fetchone()
        if restuple is None:  # User has no entry in stats. Make a new one
            self.cursor.execute('''
            insert into stats (uid, bux, level, muon) values (?, 0, 0, 0)
            ''', (str(uid),))
            # the database expects a string, not an int, for the uid
            # todo: why?
            return 0  # we know this is the right value because we just put it in the db
        
        return restuple[0]  # if the user just wants one value, return a value rather than tuple

    def get_muon(self, uid):

        self.cursor.execute('''select muon from stats where uid = ?''', (uid,))

        restuple = self.cursor.fetchone()
        if restuple is None:  # User has no entry in stats. Make a new one
            self.cursor.execute('''
                    insert into stats (uid, bux, level, muon) values (?, 0, 0, 0)
                    ''', (str(uid),))
            return 0

        return restuple[0]

    def get_stats(self, uid, *args):

        query_str = '''select {} from stats where uid = ?'''.format(",".join(args))
        self.cursor.execute(query_str, (uid,))
        return self.cursor.fetchone()  # returns a tuple of the values

    def set_stat(self, uid, stat, value):

        set_str = '''update stats set {} = ? where uid = ?'''.format(stat)
        self.cursor.execute(set_str, (value, uid))

    def set_hiscore(self, name, level, exp):

        name = name.encode("UTF-8")
        self.cursor.execute('''update hiscore set name = ?, level = ?, exp =? where a = ?''', (name, level, exp, "aaa"))

    def get_hiscore(self):

        self.cursor.execute('''select * from hiscore where a = ?''', ("aaa",))
        aaa, name, level, exp = self.cursor.fetchone()
        if name:
            name = name.decode("UTF-8")
        return aaa, name, level, exp

    def adjust_bux(self, uid, amt):

        self.cursor.execute('''SELECT * FROM stats WHERE uid = ?''', (uid,))
        res = self.cursor.fetchone()  # check if user already existed
        if not res:  # we need to add a new entry for them
            self.cursor.execute('''insert into stats (uid, bux) VALUES (?, ?)''', (uid, amt))
        else:
            self.cursor.execute('''update stats set bux = MAX(0, bux + ?) where uid = ?''', (amt, uid))
            # make sure it doesn't go negative

        self.cursor.execute('''INSERT INTO buxlog (uid, amt) VALUES (? ,?)''', (uid, amt))

        """  # old code removed, UNIQUE constraint was failing so make the explicit check above for presence of uid
        self.cursor.execute('''
        insert into stats (uid, bux) select ?, ? where (select changes() = 0)
        ''', (uid, amt))
        # this statement only runs if changes() = 0 i.e. nothing was changed by the previous statement
        # because the uid wasn't present in the database keys. This saves having to check for the presence
        # of the uid every time, just add the entry if it didn't exist already.
        
        # probably the issue was select changes() no longer = 0
        """

        self.db.commit()

    def adjust_muon(self, uid, amt):

        self.cursor.execute('''SELECT * FROM stats WHERE uid = ?''', (uid,))
        res = self.cursor.fetchone()  # check if user already existed
        if not res:  # we need to add a new entry for them
            self.cursor.execute('''insert into stats (uid, bux) VALUES (?, ?)''', (uid, amt))
        else:
            self.cursor.execute('''update stats set muon = MAX(0, muon + ?) where uid = ?''', (amt, uid))
            # make sure it doesn't go negative

        self.db.commit()

    def add_reminder(self, uid, message, channel_id, delay):

        delaystr = f"+{delay} seconds"
        self.cursor.execute(f'''
        insert into reminders (uid, message, channel_id, timestamp) values(?, ?, ?, datetime("now", "{delaystr}"))''',
                            (uid, message, channel_id))
        # need to use an f-string to calculate the delay in the datetime function
        self.db.commit()

    def prune_reminders(self):

        """Delete reminders that are in the past from the db, to be run on bot startup"""

        self.cursor.execute('''delete from reminders where timestamp < datetime("now") or timestamp is null''')
        self.cursor.execute('''delete from reminders where timestamp > datetime("now", "100 years")''')
        # also catch null timestamp for when the command was entered wrong
        self.db.commit()

    def get_reminders(self):

        """return a list of tuples of all reminders whose time is greater than now (seconds since epoch)"""

        self.cursor.execute('''select * from reminders 
        where timestamp > datetime("now")
        and timestamp < datetime("now","1 hour")''')
        return self.cursor.fetchall()

    def insert_monitored(self, tag, channel, last=None):

        """From gelbooru module: add a tag to constantly check gelbooru for"""
        if not last:
            self.cursor.execute('''insert into monitored (tag, channel_id) values(?,?)''', (tag, channel))
        else:
            #  used to update the last-seen md5
            self.cursor.execute(
                '''update monitored set last = ? where tag = ? and channel_id = ?''', (last, tag, channel))
        self.db.commit()

    def get_all_monitored(self):

        """returns a list of all the tags to periodically check gelbooru for"""

        self.cursor.execute('''select tag, channel_id from monitored''')
        return self.cursor.fetchall()

    def get_last_monitored(self, tag, cid):

        self.cursor.execute('''select tag, last from monitored where tag = ? and channel_id = ?''', (tag, cid))
        return self.cursor.fetchone()

    def unmonitor(self, tag):

        self.cursor.execute('''delete from monitored where tag = ?''', (tag,))
        self.db.commit()

    def log_search(self, uid, tags):

        self.cursor.execute('''insert into searches (uid, tags) values (?, ?)''', (uid, " ".join(tags)))
        self.db.commit()

    def peros_exists(self, uid, chid):

        res = self.cursor.execute(''' SELECT userid, channelid FROM Peros WHERE userid = ? AND channelid = ? ''', (uid, chid)).fetchone()
        return False if res is None else True

    def adjust_peros(self, uid, chid, amount):

        # Check if entry exists in DB
        if not self.peros_exists(uid, chid):
            self.cursor.execute(''' INSERT INTO Peros (userid, channelid, count) VALUES (?, ?, ?) ''', (uid, chid, amount))
        else:
            self.cursor.execute('''UPDATE Peros SET count = count + (?) WHERE userid = ? AND channelid = ?''', (amount, uid, chid))
        self.db.commit()

    def get_peros(self, uid, chid):

        return self.cursor.execute('''SELECT count FROM Peros WHERE userid = ? AND channelid = ?''', (uid, chid)).fetchone()[0]

    def set_peros(self, uid, chid, peros):

        self.cursor.execute('''INSERT OR REPLACE INTO Peros (userid, channelid, count) VALUES (?, ?, ?)''', (uid, chid, peros))
        self.db.commit()

    def set_all_peros(self, chid, peros):

        self.cursor.execute('''UPDATE Peros SET count = ? WHERE channelid = ?''', (peros, chid))
        self.db.commit()

    def get_peros_for_channels(self, uid, channels):

        qstring = ",".join(["?"]*len(channels))
        sql = '''SELECT SUM(count) FROM Peros WHERE userid = ? AND channelid IN ({})'''.format(qstring)
        # sqlite can't substitute in a list or tuple so we need to build the query string with the appropriate
        # number of ?'s to satisfy the "IN" query, if passed a comma delimited string it will end up in quote marks
        # which breaks the query.
        res = self.cursor.execute(sql, ((uid,) + tuple(channels))).fetchone()[0]  # execute with the string we built
        if res is None:
            return 0
        return res

    def gelbooru_stats(self):

        self.cursor.execute('''SELECT uid, tags FROM searches WHERE stime > datetime("now", "-7 days")''')
        usr_count = defaultdict(lambda: 0)
        tag_count = defaultdict(lambda: 0)
        total = 0  # total searches made
        for a, b in self.cursor.fetchall():
            total += 1
            usr_count[a] += 1
            for q in b.split(" "):
                tag_count[q] += 1

        return get_max(usr_count) + get_max(tag_count) + (total,)
        #  returns (user ID of most frequent user, how many times in past week, most popular tag, how many times)

    def trending_tag(self):

        def countup(results):

            """Takes the cursor.fetchall() iterator for space-delimited tag lists and returns a dict of {tag: count}"""

            dc = defaultdict(lambda: 0)
            for a in results:
                for b in a[0].split(" "):
                    dc[b] += 1
            return dc

        def max_diff(dc1, dc2):

            """Returns the tag with the biggest increase in counts between dc1 and dc2 (dc2 is the later one)"""
            diff = 0
            tag = None
            for k in dc2.keys():
                d = dc2[k] - dc1[k]
                if d > diff:
                    diff = d
                    tag = k
            return tag, diff

        self.cursor.execute('''SELECT tags FROM searches WHERE stime > datetime("now", "-7 days")''')
        d1 = countup(self.cursor.fetchall())
        self.cursor.execute('''SELECT tags FROM searches
                                WHERE stime > datetime("now", "-14 days")
                                AND stime < datetime("now", "-7 days")''')
        d2 = countup(self.cursor.fetchall())

        return max_diff(d1, d2)

    def daily_time(self, uid):

        """Returns the time the user last used 'snek daily'"""

        self.cursor.execute('''SELECT last_time FROM stats WHERE uid = ?''', (uid,))
        return self.cursor.fetchone()[0]

    def increment_streak(self, uid):

        self.cursor.execute('''UPDATE stats SET level = level + 1 WHERE uid = ?''', (uid,))
        self.db.commit()

    def get_streak(self, uid):

        self.cursor.execute('''SELECT level FROM stats WHERE uid = ?''', (uid,))
        return self.cursor.fetchone()[0]

    def reset_streak(self, uid):

        self.cursor.execute('''UPDATE stats SET level = 0 WHERE uid = ?''', (uid,))
        self.db.commit()

    def increment_daily_time(self, uid, tm):

        self.cursor.execute('''UPDATE stats SET last_time = ? WHERE uid = ?''', (tm, uid))
        self.db.commit()

    def increment_post_pero(self, post_id, channel_id, increment):

        """This code also uses the following trigger in the db

        CREATE TRIGGER update_pero_date UPDATE OF count ON most_peroed
        BEGIN
        UPDATE most_peroed SET last_updated = CURRENT_TIMESTAMP WHERE postid = NEW.postid;
        END;

        """

        self.cursor.execute('''INSERT OR IGNORE INTO most_peroed (postid, channel, count)
                               VALUES (?, ?, ?)''', (post_id, channel_id, 0))
        # always try to create a new entry but silently ignore it if there's a conflict with pre-existing
        self.cursor.execute('''UPDATE most_peroed 
                               SET count = count + ? WHERE postid = ?''', (increment, post_id))
        # now we have definitely made the entry there is always something to update
        self.db.commit()

    def get_most_peroed(self):

        """Returns the post id of the most peroed post."""

        self.cursor.execute('''SELECT postid, channel, count from most_peroed 
                                WHERE count = (SELECT MAX(count) from most_peroed)
                                ORDER BY RANDOM()''')
        return self.cursor.fetchone()

    def get_best_of(self, threshold=4):

        """Returns (channel id, post id) of all posts with more than 5 peros for addition of image links."""

        self.cursor.execute('''SELECT postid, channel FROM most_peroed WHERE count > ? and image_url is NULL''',
                            (threshold,))
        return self.cursor.fetchall()

    def get_gallery_links(self, threshold=4):

        self.cursor.execute('''SELECT thumb, image_url FROM most_peroed WHERE count > ?''', (threshold,))
        return self.cursor.fetchall()

    def add_image_link(self, postid, channel, lnk, thumb, failed=False):

        if failed:  # a value of 0 means we have visited this link before but it didn't resolve to a downloadable image
            self.cursor.execute('''UPDATE most_peroed SET image_url = 0, thumb = 0 WHERE postid = ? AND channel = ?''',
                                (postid, channel))
        else:
            self.cursor.execute('''UPDATE most_peroed SET image_url = ?, thumb = ? WHERE postid = ? AND channel = ?''',
                                (lnk, thumb, postid, channel))
        self.db.commit()

    def mark_as_downloaded(self, channelid, postid):

        self.cursor.execute('''UPDATE most_peroed SET done = 1 WHERE postid = ? AND channel = ?''', (channelid, postid))
        self.db.commit()

    def remove_pero_post(self, postid):

        """For removing a post entry"""

        self.cursor.execute('''DELETE from most_peroed WHERE postid = ?''', (postid,))
        self.db.commit()

    def now(self):

        """Returns the time now according to the SQL DB"""

        self.cursor.execute('''SELECT datetime("now")''')
        return self.cursor.fetchone()

    def anticipate_shop_activation(self, uid, rand, uname):

        """Stores a number to expect from a user using the web interface. When this number
        is received on the web page it is used to associate the cookie ID with the discord ID"""
        # TODO: insert or update
        self.cursor.execute('''UPDATE shop SET (rand, uname, cookie) = (?, ?, NULL) where UID = ?''', (rand, uname, uid))
        # we need to put the user's display name in the table so the web interface knows what to call the user
        # if the user has no pre-existing entry we need to make one though:
        self.cursor.execute('''INSERT INTO shop (uid, rand, uname) SELECT ?, ?, ? WHERE (SELECT CHANGES() = 0)''',
                            (uid, rand, uname))

        self.db.commit()  # MUST commit change so that it's visible to the web code

    def log_tags(self, als):

        for x in als:

            self.cursor.execute('''INSERT OR IGNORE INTO tags (tag, count) VALUES (?, ?)''', (x, 0))
            # always try to create a new entry but silently ignore it if there's a conflict with pre-existing
            self.cursor.execute('''UPDATE tags SET count = count + 1 WHERE tag = ?''', (x,))
            # now we have definitely made the entry there is always something to update

        self.db.commit()

    def distribute_dividend(self, als):

        """Give snekbux dividend to all players owning equity in a tag"""

        for x in als:

            self.cursor.execute('''SELECT SUM(paid) FROM stonks WHERE tag = ?''', (x,))
            total_value = self.cursor.fetchone()[0]
            if not total_value:
                continue
            # TODO: do this all inside SQLite
            self.cursor.execute('''SELECT DISTINCT uid FROM stonks WHERE tag = ?''', (x,))
            lst = list(self.cursor.fetchall())
            for q in lst:
                q = str(q[0])  # unpack tuple, there really must be a better way to do this
                self.cursor.execute('''SELECT paid FROM stonks WHERE uid = ? AND tag = ?''', (q, x))
                z = self.cursor.fetchone()[0]
                dividend = int(float(z)/total_value * 50)
                self.cursor.execute('''UPDATE stonks SET return = return + ? WHERE uid = ? AND tag = ?''',
                                    (dividend, q, x))

        self.db.commit()
            

    def adjust_stonk(self, uid, tag, cost):
        """Quantity may be POSITIVE (player is buying) or NEGATIVE (player is selling)"""

        # do a check for whether the player has enough bux outside this function, first
        # or if they are trying to sell more stonk than they have
        # -ve or +ve numbers will be handled appropriately here

        #self.cursor.execute('''INSERT OR IGNORE INTO stonks (uid, tag, paid) VALUES (?, ?, 0)''',
                            #(uid, tag))
        self.cursor.execute('''SELECT paid FROM stonks WHERE uid = ? and tag = ?''', (uid, tag))
        r = self.cursor.fetchone()
        if not r:
            self.cursor.execute('''INSERT INTO stonks (uid, tag, paid, return) VALUES (?, ?, 0, 0)''', (uid, tag))

        self.cursor.execute('''UPDATE stonks
                                SET paid = paid + ?
                                WHERE tag = ? AND uid = ?''', (cost, tag, uid))

        self.cursor.execute('''DELETE FROM stonks WHERE paid = 0''')
        # might have sold everything, so don't leave zero values hanging around

        self.db.commit()

    def get_stonk(self, uid, tag):

        self.cursor.execute('''SELECT paid FROM stonks WHERE tag = ? AND UID = ?''', (tag, uid))
        res = self.cursor.fetchone()
        if res:
            return res[0]

    def calculate_equity(self, uid, tag):

        self.cursor.execute('''SELECT paid FROM stonks WHERE tag = ? and uid = ?''', (tag, uid))
        user_amt = self.cursor.fetchone()
        self.cursor.execute('''SELECT SUM(paid) FROM stonks WHERE tag = ?''', (tag,))
        total_amt = self.cursor.fetchone()[0]
        if total_amt == 0 or user_amt is None:
            return 0
        equity = 100 * float(user_amt[0])/total_amt  # don't unpack user_amt tuple till here, avoid error

        return round(equity, 1)

    def get_portfolio(self, uid):

        self.cursor.execute('''SELECT tag, paid FROM stonks WHERE uid = ?''', (uid,))
        return self.cursor.fetchall()

    def pay_dividend(self, uid):

        """Transfer all of user's tag returns into their main snekbux balance"""

        self.cursor.execute('''SELECT * FROM stonks WHERE uid = ?''', (uid,))
        res = self.cursor.fetchone()  # need to check if the user actually has any stonks
        if not res:
            return 0

        self.cursor.execute('''UPDATE stats SET bux = bux +
                            (SELECT SUM(return) FROM stonks WHERE uid = ?)
                            WHERE uid = ?''', (uid, uid))

        ### dividend logging function ###
        self.cursor.execute('''INSERT INTO buxlog (uid, amt) VALUES (
                                        ? ,(SELECT SUM(return) FROM stonks WHERE uid = ?)
                                        )''', (uid, uid))

        self.cursor.execute('''UPDATE stonks SET return = 0 WHERE uid = ?''', (uid,))



        self.db.commit()

    def print_dividend(self, uid):

        """Needs to be in this module because it's called from multiple places including the main snek code"""

        old = self.get_bux(uid)
        self.pay_dividend(uid)
        new = self.get_bux(uid)
        delta = new - old

        return(delta)

    def monitor_tag_deltas(self):

        self.cursor.executescript(
            '''CREATE TABLE chng AS 
            SELECT tags.tag, tags."count", tags2."count" AS "newcount", 0 AS "change"
            FROM tags 
            INNER JOIN tags2 ON  tags.tag = tags2.tag;
            UPDATE chng SET "change" = "count"-"newcount";
            INSERT INTO tag_deltas SELECT "tag", "change", CURRENT_TIMESTAMP FROM chng WHERE "change" != 0;
            DROP TABLE chng;
            DROP TABLE tags2;
            CREATE TABLE tags2 AS SELECT * FROM tags;
            '''
        )
        self.db.commit()

    def add_card(self, uid, card):

        self.cursor.execute('''UPDATE cards SET owner = ? WHERE serial = ?''', (uid, card))
        self.db.commit()

    def remove_card(self, card):

        self.cursor.execute('''UPDATE cards SET owner = NULL WHERE serial = ?''', (card,))
        self.db.commit()

    def get_cards(self, uid):

        self.cursor.execute('''SELECT serial, series FROM cards WHERE owner = ?''', (uid,))
        return self.cursor.fetchall()

    def random_unowned_card(self):

        self.cursor.execute('''SELECT serial FROM cards WHERE owner IS NULL ORDER BY RANDOM() LIMIT 1''')
        res = self.cursor.fetchone()
        if not res:
            return
        serial = str(res[0]).zfill(5)  # convert serial number to padded string for file name use
        return serial

    def get_uids_with_cards(self):

        self.cursor.execute('''SELECT DISTINCT owner FROM cards WHERE owner NOT NULL''')
        return [x[0] for x in self.cursor.fetchall()]

    def update_card_trader_names(self, adict):

        self.cursor.execute('''DELETE FROM names''')
        for k, v in adict.items():  # dict of uid: screen name
            self.cursor.execute('''INSERT INTO names (uid, screen_name) VALUES (?, ?)''', (k ,v))
        self.db.commit()

    def verify_ownership(self, serial_list, owner1, owner2=None):

        """Return True only if all cards in serial list are owned either by 1 or 2"""
        query_tuple = f'''({",".join(serial_list)})'''
        self.cursor.execute(f'''SELECT DISTINCT(owner) FROM cards WHERE serial IN {query_tuple}''')
        res = [x[0] for x in self.cursor.fetchall()]
        print(res)
        owner1 = int(owner1)
        if owner2:
            owner2 = int(owner2)

        if owner1 == owner2:
            return False  # could have been devious
        if owner1 in res and owner2 in res and len(res) == 2:
            return True
        if not owner2 and owner1 == res[0]:
            return True  # checking a single user's ownership
        else:
            return False

    def verify_ownership_single(self, card, uid):

        self.cursor.execute('''SELECT owner FROM cards WHERE serial = ?''', (int(card),))
        res = self.cursor.fetchall()
        print("result from owner chec")
        print(res)
        if not res:
            return False
        if int(res[0][0]) == uid:  # holy shit I have got to sort out typing and tuples for this damn code
            return True
        else:
            return False

    def serial_to_name(self, serial):

        self.cursor.execute('''SELECT card_name FROM cards WHERE serial = ?''', (int(serial),))
        res = self.cursor.fetchone()
        if res:
            return res[0]

    def execute_trade(self, serial_list):

        serial_list = list(set(serial_list))
        a, b, a_cards, b_cards = self.get_owners(serial_list)  # disentangle the list into who owns what

        a_tuple = ",".join([str(x) for x in a_cards])
        b_tuple = ",".join([str(x) for x in b_cards])
        print("a tuple", a_tuple)
        print("b tuple", b_tuple)

        self.cursor.execute(f'''UPDATE cards SET owner = ? WHERE serial IN ({a_tuple})''', (b, ))
        self.cursor.execute(f'''UPDATE cards SET owner = ? WHERE serial IN ({b_tuple})''', (a, ))

        self.db.commit()

    def get_owners(self, serial_list):

        "Returns owner a, owner b, list of owner a's cards, list of owner b's cards"

        query_tuple = f'''({",".join(serial_list)})'''
        self.cursor.execute(f'''SELECT DISTINCT(owner) FROM cards WHERE serial IN {query_tuple}''')
        res = [x[0] for x in self.cursor.fetchall()]
        if not res:
            raise KeyError("Serial does not exist")
        if len(res) == 2:
            a, b = res
        elif len(res) == 1:
            a = res[0]
            b = None

        print(f"Distctinct owners are {a} and {b}")
        self.cursor.execute(f'''SELECT serial FROM cards WHERE serial IN {query_tuple} AND owner = ?''', (a, ))
        a_cards = [x[0] for x in self.cursor.fetchall()]
        print("A's cards", a_cards)
        if b:
            self.cursor.execute(f'''SELECT serial FROM cards WHERE serial IN {query_tuple} AND owner = ?''', (b,))
            b_cards = [x[0] for x in self.cursor.fetchall()]
        else:
            b_cards = []

        print("B's cards", b_cards)

        return a, b, a_cards, b_cards

    def card_search(self, astr):

        words = astr.split(" ")
        part = '''(card_name LIKE ? OR series LIKE ?)'''
        start = '''SELECT serial, screen_name, card_name, series FROM cards 
                    INNER JOIN names ON 
                    names.uid = cards.owner WHERE'''

        search_qry = []
        for x in words:
            start += part  # add another clause
            start += '''AND'''
            search_qry.extend([f'''%{x}%''', f'''%{x}%'''])  # stuff to sub into SQL statement
        search_qry = tuple(search_qry)

        start = start[:-3]  # trim final "AND"
        self.cursor.execute(start, search_qry)
        return self.cursor.fetchall()

    def get_graph_data(self, tag, time_ago=14):

        """compiles a list of data points to plot a graph of a tag's trend over time. Returns a cumulative sum
        by date that the tag deltas table was updated."""

        if type(time_ago) is not int:
            raise TypeError("time delta must be an integer number of days")
            # need to be careful with this as an f-string for SQL substitution is being manually assembled

        time_modifier = f"-{time_ago} days"

        self.cursor.execute('''SELECT datetime(CURRENT_TIMESTAMP, ?), SUM(change) FROM tag_deltas
        WHERE tag = ?
        AND time < datetime(CURRENT_TIMESTAMP, ?)''', (time_modifier, tag, time_modifier))
        # this gives the cumulative value up to that point, as the start value for the plot

        qq = self.cursor.fetchall()
        if not qq[0][1]:
            return
        start_value = int(qq[0][1])
        start_date = datetime.datetime.strptime(qq[0][0][:16], "%Y-%m-%d %H:%M")

        self.cursor.execute('''SELECT time, change FROM tag_deltas
        WHERE tag = ?
        and time > datetime(CURRENT_TIMESTAMP, ?)''', (tag, time_modifier))
        res = self.cursor.fetchall()

        cumulatives = [start_value]
        dates = [start_date]

        for x in res:
            new = cumulatives[-1] + x[1]  # add the delta to the last value to get a cumulative sum
            cumulatives.append(new)
            dates.append(datetime.datetime.strptime(x[0][:16], "%Y-%m-%d %H:%M"))

        return dates, cumulatives
