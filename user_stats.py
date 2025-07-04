import psycopg2
import re
from collections import defaultdict
import datetime
import hashlib
import random


def get_max(dc):
    """Takes a dictionary and returns the key and value for the pair with the largest value"""

    max_cnt = 0
    max_key = None
    for k, v in dc.items():
        if v > max_cnt:
            max_cnt = v
            max_key = k

    return max_key, max_cnt


class MyCursor:

    """Looks and quacks like a normal SQL cursor but stores the connection string so that the connection can be
    re-established if lost temporarily. Rolls back failed transactions so the entire bot doesn't grind to
    a halt from one failed transaction."""

    def __init__(self, conn_string):

        self.conn_string = conn_string
        self.conn = psycopg2.connect(conn_string)

    def execute(self, *args, **kwargs):

        self.cur = self.conn.cursor()
        try:
            self.cur.execute(*args, **kwargs)
        except psycopg2.OperationalError:
            print("DB Cursor connection error, reconnecting")
            self.conn = psycopg2.connect(self.conn_string)
            self.cur = self.conn.cursor()
            self.cur.execute(*args, **kwargs)
        except psycopg2.errors.InFailedSqlTransaction:
            print("DB In failed transaction - rolling back")
            self.conn.rollback()
            self.cur.execute(*args, **kwargs)

    def fetchall(self):

        res = self.cur.fetchall()
        self.cur.close()
        return res

    def fetchone(self):

        res = self.cur.fetchone()
        self.cur.close()
        return res


class Manager:

    """Class to manage a database of discord id relating to various attributes"""

    card_functions = {}

    def __init__(self, bot):

        self.bot = bot
        self.cursor = MyCursor(self.bot.settings["postgres_string"])  # containing dbname, user, host, port, pwd
        self.input_checker = re.compile("[0-9A-Za-z!,.?&\"'+-]{,50}")

    @property
    def db(self):

        """Introduced quite late after having written many funcs that expect a reference to the db. This way
        we can still do commits and rollbacks outside the MyCursor object."""

        return self.cursor.conn  # need to pull out a reference to the connection for db.commit()

    def check_input_string(self, astr):

        if self.input_checker.fullmatch(astr) is None:
            return False
        else:
            return True

    def get_bux(self, uid):

        self.cursor.execute('''select bux from stats where uid = %s''', (uid,))
        
        restuple = self.cursor.fetchone()
        if restuple is None:  # User has no entry in stats. Make a new one
            self.cursor.execute('''
            insert into stats (uid, bux, level, muon) values (%s, 0, 0, 0)
            ''', (str(uid),))
            # the database expects a string, not an int, for the uid
            # todo: why%s
            return 0  # we know this is the right value because we just put it in the db
        
        return restuple[0]  # if the user just wants one value, return a value rather than tuple

    def get_muon(self, uid):

        self.cursor.execute('''select muon from stats where uid = %s''', (uid,))

        restuple = self.cursor.fetchone()
        if restuple is None:  # User has no entry in stats. Make a new one
            self.cursor.execute('''
                    insert into stats (uid, bux, level, muon) values (%s, 0, 0, 0)
                    ''', (str(uid),))
            return 0

        return restuple[0]

    def get_stats(self, uid, *args):

        query_str = '''select {} from stats where uid = %s'''.format(",".join(args))
        self.cursor.execute(query_str, (uid,))
        return self.cursor.fetchone()  # returns a tuple of the values

    def set_stat(self, uid, stat, value):

        set_str = '''update stats set {} = %s where uid = %s'''.format(stat)
        self.cursor.execute(set_str, (value, uid))

    def set_hiscore(self, name, level, exp):

        name = name.encode("UTF-8")
        self.cursor.execute('''update hiscore set name = %s, level = %s, exp =%s where a = %s''', (name, level, exp, "aaa"))

    def get_hiscore(self):

        self.cursor.execute('''select * from hiscore where a = %s''', ("aaa",))
        aaa, name, level, exp = self.cursor.fetchone()
        if name:
            name = name.decode("UTF-8")
        return aaa, name, level, exp

    def adjust_bux(self, uid, amt):

        self.cursor.execute('''SELECT * FROM stats WHERE uid = %s''', (uid,))
        res = self.cursor.fetchone()  # check if user already existed
        if not res:  # we need to add a new entry for them
            self.cursor.execute('''insert into stats (uid, bux) VALUES (%s, %s)''', (uid, amt))
        #else:
            #self.cursor.execute('''update stats set bux = MAX(0, bux + %s) where uid = %s''', (amt, uid))
            # make sure it doesn't go negative
        else:
            self.cursor.execute('''UPDATE stats SET bux = CASE
            WHEN (bux + %s) < 0 THEN 0
            ELSE bux + %s
            END
            WHERE uid = %s''', (amt, amt, uid))  # ensure it doesn't go negative, postgres max function works differe?


        self.cursor.execute('''INSERT INTO buxlog (uid, amt) VALUES (%s ,%s)''', (uid, amt))

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

        self.cursor.execute('''SELECT * FROM stats WHERE uid = %s''', (uid,))
        res = self.cursor.fetchone()  # check if user already existed
        if not res:  # we need to add a new entry for them
            self.cursor.execute('''insert into stats (uid, bux) VALUES (%s, %s)''', (uid, amt))
        else:
            # self.cursor.execute('''update stats set muon = muon + %s where uid = %s''', (amt, uid)) # old fxn

            self.cursor.execute('''UPDATE stats SET muon = CASE
                        WHEN (muon + %s) < 0 THEN 0
                        ELSE muon + %s
                        END
                        WHERE uid = %s''', (amt, amt, uid))

        self.cursor.execute('''INSERT INTO muonlog (uid, amt) VALUES (%s ,%s)''', (uid, amt))

        self.db.commit()

    def add_reminder(self, uid, message, channel_id, delay):

        delaystr = f"{delay} seconds"
        self.cursor.execute(f'''
        insert into reminders (uid, message, channel_id, timestamp) values(%s, %s, %s, NOW() + interval %s)''',
                            (uid, message, channel_id, delaystr))
        # need to use an f-string to calculate the delay in the datetime function
        self.db.commit()

    def prune_reminders(self):

        """Delete reminders that are in the past from the db, to be run on bot startup"""

        self.cursor.execute('''delete from reminders where timestamp < NOW() or timestamp is null''')
        self.cursor.execute('''delete from reminders where timestamp > NOW() + interval '100 years' ''')
        # also catch null timestamp for when the command was entered wrong
        self.db.commit()

    def get_reminders(self):

        """return a list of tuples of all reminders whose time is greater than now (seconds since epoch)"""

        self.cursor.execute('''select * from reminders 
        where timestamp > NOW()
        and timestamp < NOW() + interval '1 hour' ''')
        return self.cursor.fetchall()

    def insert_monitored(self, tag, channel, last=None):

        """From gelbooru module: add a tag to constantly check gelbooru for"""
        if not last:
            self.cursor.execute('''insert into monitored (tag, channel_id) values(%s,%s)''', (tag, channel))
        else:
            #  used to update the last-seen md5
            self.cursor.execute(
                '''update monitored set last = %s where tag = %s and channel_id = %s''', (last, tag, channel))
        self.db.commit()

    def get_all_monitored(self):

        """returns a list of all the tags to periodically check gelbooru for"""

        self.cursor.execute('''select tag, channel_id from monitored''')
        return self.cursor.fetchall()

    def get_last_monitored(self, tag, cid):

        self.cursor.execute('''select tag, last from monitored where tag = %s and channel_id = %s''', (tag, cid))
        return self.cursor.fetchone()

    def unmonitor(self, tag):

        self.cursor.execute('''delete from monitored where tag = %s''', (tag,))
        self.db.commit()

    def log_search(self, uid, tags):

        self.cursor.execute('''insert into searches (uid, tags) values (%s, %s)''', (uid, " ".join(tags)))
        self.db.commit()

    def peros_exists(self, uid, chid):  # had to rename the table with lowercase "p" otherwise postgres complains

        self.cursor.execute('''SELECT userid, channelid FROM peros WHERE userid = %s AND channelid = %s''', (uid, chid))
        res = self.cursor.fetchone()
        return False if res is None else True

    def adjust_peros(self, uid, chid, amount):

        # Check if entry exists in DB
        if not self.peros_exists(uid, chid):
            self.cursor.execute(''' INSERT INTO peros (userid, channelid, count) VALUES (%s, %s, %s) ''', (uid, chid, amount))
        else:
            self.cursor.execute('''UPDATE peros SET count = count + (%s) WHERE userid = %s AND channelid = %s''', (amount, uid, chid))
        self.db.commit()

    def get_peros(self, uid, chid):

        self.cursor.execute('''SELECT count FROM peros WHERE userid = %s AND channelid = %s''', (uid, chid))
        if a := self.cursor.fetchone():
            return a[0]

    def set_peros(self, uid, chid, peros):

        # self.cursor.execute('''INSERT OR REPLACE INTO peros (userid, channelid, count)
        #                         VALUES (%s, %s, %s)''', (uid, chid, peros))

        self.cursor.execute('''INSERT INTO peros (userid, channelid, count)
        VALUES (%s, %s, %s)
        ON CONFLICT (userid, channelid)
        DO UPDATE SET count = EXCLUDED.count''', (uid, chid, peros))

        # it was necessary to add a constraint to the table to ensure uniqueness:
        # ALTER TABLE peros ADD CONSTRAINT unique_userid_channelid UNIQUE (userid, channelid);

        # "WHERE userid > 0" was added to fix
        # "there is no unique or exclusion constraint matching the ON CONFLICT specification" error

        self.db.commit()

    def set_all_peros(self, chid, peros):

        self.cursor.execute('''UPDATE peros SET count = %s WHERE channelid = %s''', (peros, chid))
        self.db.commit()

    def get_peros_for_channels(self, uid, channels):

        #qstring = ",".join(["%s"]*len(channels))
        #sql = '''SELECT SUM(count) FROM peros WHERE userid = %s AND channelid IN ({})'''.format(qstring)
        # sqlite can't substitute in a list or tuple so we need to build the query string with the appropriate
        # number of %s's to satisfy the "IN" query, if passed a comma delimited string it will end up in quote marks
        # which breaks the query.

        # UPDATE: but now we are using PostgreSQL we can safely sub in a tuple instead

        self.cursor.execute('''SELECT SUM(count) 
        FROM peros 
        WHERE userid = %s AND channelid IN %s''', (uid, tuple(channels)))
        res = self.cursor.fetchone()
        if res:
            return res[0]
        else:
            return 0

    def gelbooru_stats(self):

        self.cursor.execute('''SELECT uid, tags FROM searches WHERE stime > NOW() - interval '7 days' ''')
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

        self.cursor.execute('''SELECT tags FROM searches WHERE stime > NOW() - interval '7 days' ''')
        d1 = countup(self.cursor.fetchall())
        self.cursor.execute('''SELECT tags FROM searches
                                WHERE stime > NOW() - interval '14 days' 
                                AND stime < NOW() - interval '7 days' ''')
        d2 = countup(self.cursor.fetchall())

        return max_diff(d1, d2)

    def daily_time(self, uid):

        """Returns the time the user last used 'snek daily'"""

        self.cursor.execute('''SELECT last_time FROM stats WHERE uid = %s''', (uid,))
        return self.cursor.fetchone()[0]

    def increment_streak(self, uid):

        self.cursor.execute('''UPDATE stats SET level = level + 1 WHERE uid = %s''', (uid,))
        self.db.commit()

    def get_streak(self, uid):

        self.cursor.execute('''SELECT level FROM stats WHERE uid = %s''', (uid,))
        return self.cursor.fetchone()[0]

    def reset_streak(self, uid):

        self.cursor.execute('''UPDATE stats SET level = 0 WHERE uid = %s''', (uid,))
        self.db.commit()

    def increment_daily_time(self, uid, tm):

        self.cursor.execute('''UPDATE stats SET last_time = %s WHERE uid = %s''', (tm, uid))
        self.db.commit()

    def increment_post_pero(self, post_id, channel_id, increment):

        """This code also uses the following trigger in the db

        CREATE TRIGGER update_pero_date UPDATE OF count ON most_peroed
        BEGIN
        UPDATE most_peroed SET last_updated = CURRENT_TIMESTAMP WHERE postid = NEW.postid;
        END;

        """

        #self.cursor.execute('''INSERT OR IGNORE INTO most_peroed (postid, channel, count)
                               # VALUES (%s, %s, %s)''', (post_id, channel_id, 0))  # old sqlite code

        self.cursor.execute('''INSERT INTO most_peroed (postid, channel, count)
                                VALUES (%s, %s, %s) ON CONFLICT (postid) DO NOTHING''', (post_id, channel_id, 0))
        # postgresql way

        # always try to create a new entry but silently ignore it if there's a conflict with pre-existing
        self.cursor.execute('''UPDATE most_peroed 
                               SET count = count + %s WHERE postid = %s''', (increment, post_id))
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

        self.cursor.execute('''SELECT postid, channel FROM most_peroed WHERE count > %s and done is FALSE''',
                            (threshold,))
        return self.cursor.fetchall()

    def get_gallery_links(self, threshold=4):

        self.cursor.execute('''SELECT thumb, image_url FROM most_peroed WHERE count > %s''', (threshold,))
        return self.cursor.fetchall()

    def add_image_link(self, postid, channel, lnk, thumb, failed=False):

        if failed:  # a value of 0 means we have visited this link before but it didn't resolve to a downloadable image
            self.cursor.execute('''UPDATE most_peroed SET image_url = 0, thumb = 0 WHERE postid = %s AND channel = %s''',
                                (postid, channel))
        else:
            self.cursor.execute('''UPDATE most_peroed SET image_url = %s, thumb = %s WHERE postid = %s AND channel = %s''',
                                (lnk, thumb, postid, channel))
        self.db.commit()

    def add_twitter_embed(self, postid, channel, snippet):

        self.cursor.execute('''UPDATE most_peroed SET 
                                tweet_html = %s,
                                image_url = 'placeholder' 
                                WHERE postid = %s AND channel = %s''',
                            (snippet, postid, channel))

        # need to add image_url becase some other logic uses that to check for success, change it later

        self.db.commit()

    def store_message_content(self, channelid, postid, content):

        self.cursor.execute('''UPDATE most_peroed
                                SET done = TRUE,
                                message_content = %s
                                WHERE postid = %s
                                AND
                                channel = %s''', (content, postid, channelid))
        self.db.commit()

    def remove_pero_post(self, postid):

        """For removing a post entry"""

        self.cursor.execute('''DELETE from most_peroed WHERE postid = %s''', (postid,))
        self.db.commit()

    def now(self):

        """Returns the time now according to the SQL DB"""

        #self.cursor.execute('''SELECT datetime("now")''')
        #self.cursor.execute('''SELECT NOW()''')  # for postgres
        self.cursor.execute('''SELECT STATEMENT_TIMESTAMP()''')  # NOW() is always giving the same value? Seems to
        # always be the time value of when the connection was first opened...
        return self.cursor.fetchone()[0]

    def anticipate_shop_activation(self, uid, secret, uname):

        """Stores a number to expect from a user using the web interface. When this number
        is received on the web page it is used to associate the cookie ID with the discord ID"""

        #self.cursor.execute('''UPDATE shop SET (rand, uname, cookie) = (%s, %s, NULL) where UID = %s''', (rand, uname, uid))
        # we need to put the user's display name in the table so the web interface knows what to call the user
        # if the user has no pre-existing entry we need to make one though:
        #self.cursor.execute('''INSERT INTO shop (uid, rand, uname) SELECT %s, %s, %s WHERE (SELECT CHANGES() = 0)''',
        #                    (uid, rand, uname))  # SELECT CHANGES() seems to be only a sqlite thing

        # new postgreSQL code:
        self.cursor.execute('''INSERT INTO shop (uid, cookie, uname) VALUES (%s, %s, %s)
                                ON CONFLICT (uid)
                                DO UPDATE SET cookie = %s, uname = %s''', (uid, secret, uname, secret, uname))
        # this assumes there is a unique constraint on the uid column, to trigger the conflict

        self.db.commit()  # MUST commit change so that it's visible to the web code

    def log_tags(self, als):

        for x in als:

            #self.cursor.execute('''INSERT OR IGNORE INTO tags (tag, count) VALUES (%s, %s)''', (x, 0))
            self.cursor.execute('''INSERT INTO tags (tag, count) VALUES (%s, %s)
            ON CONFLICT (tag) DO NOTHING''', (x, 0))  # insert or ignore is sqlite-specific
            # always try to create a new entry but silently ignore it if there's a conflict with pre-existing
            self.cursor.execute('''UPDATE tags SET count = count + 1 WHERE tag = %s''', (x,))
            # now we have definitely made the entry there is always something to update

        self.db.commit()

    def distribute_dividend(self, als):

        """Give snekbux dividend to all players owning equity in a tag"""

        for x in als:

            self.cursor.execute('''SELECT SUM(paid) FROM stonks WHERE tag = %s''', (x,))
            total_value = self.cursor.fetchone()[0]
            if not total_value:
                continue

            self.cursor.execute('''SELECT DISTINCT uid FROM stonks WHERE tag = %s''', (x,))
            lst = list(self.cursor.fetchall())
            for q in lst:
                q = str(q[0])  # unpack tuple, there really must be a better way to do this
                self.cursor.execute('''SELECT paid FROM stonks WHERE uid = %s AND tag = %s''', (q, x))
                z = self.cursor.fetchone()[0]
                dividend = int(float(z)/total_value * 50)
                self.cursor.execute('''UPDATE stonks SET return = return + %s WHERE uid = %s AND tag = %s''',
                                    (dividend, q, x))

        self.db.commit()

    def adjust_stonk(self, uid, tag, cost):

        """Quantity may be POSITIVE (player is buying) or NEGATIVE (player is selling)"""

        # do a check for whether the player has enough bux outside this function, first
        # or if they are trying to sell more stonk than they have
        # -ve or +ve numbers will be handled appropriately here

        #self.cursor.execute('''INSERT OR IGNORE INTO stonks (uid, tag, paid) VALUES (%s, %s, 0)''',
                            #(uid, tag))
        self.cursor.execute('''SELECT paid FROM stonks WHERE uid = %s and tag = %s''', (uid, tag))
        r = self.cursor.fetchone()
        if not r:
            self.cursor.execute('''INSERT INTO stonks (uid, tag, paid, return) VALUES (%s, %s, 0, 0)''', (uid, tag))

        self.cursor.execute('''UPDATE stonks
                                SET paid = paid + %s
                                WHERE tag = %s AND uid = %s''', (cost, tag, uid))

        self.cursor.execute('''DELETE FROM stonks WHERE paid = 0''')
        # might have sold everything, so don't leave zero values hanging around

        self.db.commit()

    def get_stonk(self, uid, tag):

        self.cursor.execute('''SELECT paid FROM stonks WHERE tag = %s AND UID = %s''', (tag, uid))
        res = self.cursor.fetchone()
        if res:
            return res[0]

    def calculate_equity(self, uid, tag):

        self.cursor.execute('''SELECT paid FROM stonks WHERE tag = %s and uid = %s''', (tag, uid))
        user_amt = self.cursor.fetchone()
        self.cursor.execute('''SELECT SUM(paid) FROM stonks WHERE tag = %s''', (tag,))
        total_amt = self.cursor.fetchone()[0]
        if total_amt == 0 or user_amt is None:
            return 0
        equity = 100 * float(user_amt[0])/total_amt  # don't unpack user_amt tuple till here, avoid error

        return round(equity, 1)

    def get_portfolio(self, uid):

        self.cursor.execute('''SELECT tag, paid FROM stonks WHERE uid = %s''', (uid,))
        return self.cursor.fetchall()

    def pay_dividend(self, uid):

        """Transfer all of user's tag returns into their main snekbux balance"""

        self.cursor.execute('''SELECT * FROM stonks WHERE uid = %s''', (uid,))
        res = self.cursor.fetchone()  # need to check if the user actually has any stonks
        if not res:
            return 0

        self.cursor.execute('''UPDATE stats SET bux = bux +
                            (SELECT SUM(return) FROM stonks WHERE uid = %s)
                            WHERE uid = %s''', (uid, uid))

        ### dividend logging function ###
        self.cursor.execute('''INSERT INTO buxlog (uid, amt) VALUES (
                                        %s ,(SELECT SUM(return) FROM stonks WHERE uid = %s)
                                        )''', (uid, uid))

        self.cursor.execute('''UPDATE stonks SET return = 0 WHERE uid = %s''', (uid,))

        self.db.commit()

    def print_dividend(self, uid):

        """Needs to be in this module because it's called from multiple places including the main snek code"""

        old = self.get_bux(uid)
        self.pay_dividend(uid)
        new = self.get_bux(uid)
        delta = new - old

        return(delta)

    def monitor_tag_deltas(self):

        # psycopg2 doesn't have "executescript", just change to "execute"
        # also changed the last CREATE TABLE
        self.cursor.execute(
            '''CREATE TABLE chng AS 
            SELECT tags.tag, tags."count", tags2."count" AS "newcount", 0 AS "change"
            FROM tags 
            INNER JOIN tags2 ON  tags.tag = tags2.tag;
            UPDATE chng SET "change" = "count"-"newcount";
            INSERT INTO tag_deltas SELECT "tag", "change", CURRENT_TIMESTAMP FROM chng WHERE "change" != 0;
            DROP TABLE chng;
            DROP TABLE tags2;
            CREATE TABLE tags2 AS TABLE tags;
            '''
        )
        self.db.commit()

    def add_card(self, uid, card):

        auto_vault = self.get_auto_vault(uid)
        self.cursor.execute('''UPDATE cards SET owner = %s, 
        guarantee_time = NULL,
        vault = %s 
        WHERE serial = %s''', (uid, auto_vault, card))
        # in case it was a guaranteed card, get rid of the guarantee timestamp
        self.cursor.execute('''SELECT timedelta FROM cards WHERE serial = %s''', (card,))
        td = self.cursor.fetchone()[0]
        if td is not None:  # it's an active card with a time delta, we need to reschedule it
            # and make its functions apply to its owner
            self.cursor.execute('''UPDATE cards SET target_uid = owner WHERE serial = %s''', (card,))
            self.reschedule_card(card, reset=True)  # the first time it runs is timedelta away from now

        self.db.commit()

    def remove_card(self, card):

        self.cursor.execute('''UPDATE cards SET owner = NULL, vault = NULL WHERE serial = %s''', (card,))
        self.db.commit()

    def get_cards(self, uid):

        self.cursor.execute('''SELECT serial, series FROM cards WHERE owner = %s''', (uid,))
        return self.cursor.fetchall()

    def check_guaranteed_cards(self):

        gserials = []  # serial numbers that must appear after the date specified in guaranteed.txt

        try:
            with open("guaranteed.txt", "r") as f:
                for line in f:
                    ser, datestr = line.split(":")
                    date = datetime.datetime.fromisoformat(datestr.rstrip("\n"))
                    if date < datetime.datetime.now():  # time to guarantee this pull so add it to the db
                        date = date.replace(tzinfo=datetime.timezone(datetime.timedelta(hours=-4)))
                        # need to specify that the times from the file are in EST - Postgres gives a timezone-aware time
                        self.cursor.execute('''UPDATE cards SET guarantee_time = %s WHERE serial = %s AND owner IS NULL''',
                                            (date, int(ser)))
                        # need owner check if this card happened to be pulled anyway
                        # todo: accidentally already pulled cards will hang around the list 5ever
                        print(f"Card {ser} is guaranteed to be pulled now.")
                    else:
                        gserials.append(line)  # not time to guarantee it yet so just prepare to write it back out
        except FileNotFoundError:
            print("Couldn't find guaranteed.txt")

        with open("guaranteed.txt", "w") as f:  # now just write back out all the lines we didn't ingest
            for line in gserials:
                f.write(line)  # we just saved the lines as they came out the file so they're written back the same

    def random_unowned_card(self):

        # TODO: still consider temporary but population of active and element cards is about the same
        # want to weight the probability of certain types of cards perhaps

        # first, check to see if there are any guaranteed cards, and if so just return one of those
        self.cursor.execute('''SELECT serial FROM cards
         WHERE guarantee_time < STATEMENT_TIMESTAMP() 
         AND owner IS NULL 
         LIMIT 1''')
        res = self.cursor.fetchone()
        if res:
            print("Found a guaranteed card, using that")
            serial = str(res[0]).zfill(5)  # convert serial number to padded string for file name use
            return serial

        # but if the last query came back with nothing, select a truly random card instead.
        self.cursor.execute('''SELECT serial FROM cards WHERE owner IS NULL ORDER BY RANDOM() LIMIT 1''')
        res = self.cursor.fetchone()
        if not res:
            return
        serial = str(res[0]).zfill(5)  # convert serial number to padded string for file name use
        return serial

    def get_uids_with_cards(self):

        self.cursor.execute('''SELECT DISTINCT owner FROM cards WHERE owner IS NOT NULL''')
        #  changed to IS NOT NULL for posgres
        return [x[0] for x in self.cursor.fetchall()]

    def update_card_trader_names(self, adict):

        self.cursor.execute('''DELETE FROM names''')
        for k, v in adict.items():  # dict of uid: screen name
            self.cursor.execute('''INSERT INTO names (uid, screen_name) VALUES (%s, %s)''', (k ,v))
        self.db.commit()

    def verify_ownership(self, serial_list, owner1, owner2=None):

        """Return True only if all cards in serial list are owned either by 1 or 2"""

        if owner1 == owner2:
            return False  # could have been devious (but why?? Found this comment later)

        self.cursor.execute('''SELECT COUNT(serial)
        FROM cards
        WHERE serial IN %s''', (tuple(serial_list),))

        res = self.cursor.fetchone()[0]
        if not res == len(serial_list):
            return False  # some of the provided serial numbers don't even exist in the db

        self.cursor.execute('''SELECT owner FROM cards 
        WHERE serial IN %s''', (tuple(serial_list), ))

        res = self.cursor.fetchall()
        if not owner2:
            return all(own == owner1 for own, in res)  # otherwise NULL compares true to None!!
        else:
            return all(own in {owner1, owner2} for own, in res)
            # trailing comma unpacks a single-value tuple: code for real tough guys
        # we are going thru each owner and verifying they exist in the set of possible owners.

    def verify_ownership_single(self, card, uid):

        self.cursor.execute('''SELECT owner FROM cards WHERE serial = %s''', (int(card),))
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

        self.cursor.execute('''SELECT card_name FROM cards WHERE serial = %s''', (int(serial),))
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

        # self.cursor.execute(f'''UPDATE cards SET owner = %s WHERE serial IN ({a_tuple})''', (b, ))
        # self.cursor.execute(f'''UPDATE cards SET owner = %s WHERE serial IN ({b_tuple})''', (a, ))
        self.cursor.execute('''UPDATE cards SET owner = %s WHERE serial IN %s''', (b, tuple(a_cards)))
        self.cursor.execute('''UPDATE cards SET owner = %s WHERE serial IN %s''', (a, tuple(b_cards)))

        self.db.commit()

    def get_owners(self, serial_list):

        """Returns owner a, owner b, list of owner a's cards, list of owner b's cards"""

        # query_tuple = f'''({",".join(serial_list)})'''  # we are doing proper tuple substitution now
        query_tuple = tuple(serial_list)
        self.cursor.execute('''SELECT DISTINCT(owner) FROM cards WHERE serial IN %s''', (query_tuple,))
        res = [x[0] for x in self.cursor.fetchall()]
        if not res:
            raise KeyError("Serial does not exist")
        if len(res) == 2:
            a, b = res
        elif len(res) == 1:
            a = res[0]
            b = None
        else:
            a = b = None  # should never happen

        print(f"Distinct owners are {a} and {b}")
        self.cursor.execute(f'''SELECT serial FROM cards WHERE serial IN %s AND owner = %s''', (query_tuple, a))
        a_cards = [x[0] for x in self.cursor.fetchall()]
        print("A's cards", a_cards)
        if b:
            self.cursor.execute(f'''SELECT serial FROM cards WHERE serial IN %s AND owner = %s''', (query_tuple, b))
            b_cards = [x[0] for x in self.cursor.fetchall()]
        else:
            b_cards = []

        print("B's cards", b_cards)

        return a, b, a_cards, b_cards

    def card_search(self, astr):

        words = astr.split(" ")
        part = '''(card_name ILIKE %s OR series LIKE %s)'''  # ILIKE = case-insensitive
        start = '''SELECT serial, screen_name, card_name, series FROM cards 
                    INNER JOIN names ON 
                    names.uid = cards.owner WHERE
                    cards.owner IS NOT NULL 
                    AND'''

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

        #time_modifier = f"-{time_ago} days"
        time_modifier = f"{time_ago} days"

        #self.cursor.execute('''SELECT datetime(CURRENT_TIMESTAMP, %s), SUM(change) FROM tag_deltas
        #WHERE tag = %s
        #AND time < datetime(CURRENT_TIMESTAMP, %s)''', (time_modifier, tag, time_modifier))

        self.cursor.execute('''SELECT NOW() - interval %s, SUM(change) FROM tag_deltas
        WHERE tag = %s AND time < NOW() - interval %s''', (time_modifier, tag, time_modifier))
        # this gives the cumulative value up to that point, as the start value for the plot

        qq = self.cursor.fetchall()
        if not qq[0][1]:
            return
        start_value = int(qq[0][1])
        #start_date = datetime.datetime.strptime(qq[0][0][:16], "%Y-%m-%d %H:%M")
        start_date = qq[0][0]

        self.cursor.execute('''SELECT time, change FROM tag_deltas
        WHERE tag = %s
        and time > NOW() - interval %s''', (tag, time_modifier))
        res = self.cursor.fetchall()

        cumulatives = [start_value]
        dates = [start_date]

        for x in res:
            new = cumulatives[-1] + x[1]  # add the delta to the last value to get a cumulative sum
            cumulatives.append(new)
            dates.append(x[0])

        return dates, cumulatives

    def bux_graph_data(self, uid):

        """For showing a user's wealth over time"""

        self.cursor.execute('''SELECT bux FROM stats WHERE uid = %s''', (uid,))
        bux_now = self.cursor.fetchall()[0][0]

        self.cursor.execute('''SELECT date, amt FROM buxlog WHERE uid = %s ORDER BY date DESC''', (uid,))
        points = []
        dates = []
        b = bux_now
        for date, amt in self.cursor.fetchall():
            bux_next = b - amt
            #date = datetime.datetime.strptime(date, "%Y-%m-%d %H:%M:%S")
            points.append(b)
            dates.append(date)
            b = bux_next

        return dates, points

    def random_image_tags(self):

        results = []
        while len(results) < 3:
            '''
            self.cursor.execute(SELECT tag FROM tags 
                                   WHERE random() < 0.01
                                   AND count > 100
                                   LIMIT 3)
            '''
            # not perfect, but quick. In a loop for the one in a million chance
            # that we don't get three results the first time
            # let's try something different

            self.cursor.execute('''SELECT tag FROM tags 
                                    WHERE count > 100''')  # about 1500 tags

            rs = self.cursor.fetchall()
            results = random.sample(rs, 3)

        return results  # you were working on this on November 3rd 2024 and stopped before committing it
        # untested as of now TODO

    # --- ACTIVE TRADING CARD FUNCTIONS ---

    def count_cards(self, uid, element):

        """Return the number of cards of a given element owned by the user with uid"""

        self.cursor.execute('''SELECT COUNT(*) FROM cards WHERE owner = %s AND element = %s''', (uid, element))
        return self.cursor.fetchone()[0]

    def get_card(self, serial):

        """Returns all db rows corresponding to this card, probably because it's an active card
        and we want to run its functions."""

        self.cursor.execute('''SELECT * FROM cards WHERE serial = %s''', (serial,))
        return self.cursor.fetchone()

    def get_scheduled_cards(self):

        """return a list of tuples of all cards due to be run in the next increment. The tuples contain the serial
        and the number of seconds from now that the funcs should be run. Doing all the time calculations inside
        the database seems to be less of a headache..."""

        self.cursor.execute('''SELECT serial, next_runtime - STATEMENT_TIMESTAMP()
                            FROM cards 
                            WHERE next_runtime < STATEMENT_TIMESTAMP() + interval '5 minutes' 
                            AND owner IS NOT NULL''')
        # cards scheduled to be run in the next 5 minutes
        return self.cursor.fetchall()  # a list of tuples of serial and timedelta

    def reschedule_card(self, serial, reset=False):

        """This function is scheduled in the bot loop to run at the same time as the card's actual function"""

        if reset:  # the next_runtime was in the past. Reschedule it to run x hours from now where x is the interval.
            self.cursor.execute('''UPDATE cards 
                                SET next_runtime = STATEMENT_TIMESTAMP() + timedelta WHERE serial = %s''', (serial,))
        else:
            self.cursor.execute('''UPDATE cards 
                                SET next_runtime = next_runtime + timedelta WHERE serial = %s''', (serial,))

        self.db.commit()

    def vault_cards(self, uid, vault=True, ser=0):

        """Assumes we want uid's cards that are in the vault, but can also specify cards that are not in it."""

        self.cursor.execute('''SELECT serial FROM cards 
        WHERE owner = %s 
        AND vault is %s
        AND serial > %s''', (uid, vault, ser))
        # min serial number specified so people only lose AI cards while this is still in development
        results = self.cursor.fetchall()
        return [x[0] for x in results]

    def card_owners(self):

        self.cursor.execute('''SELECT DISTINCT owner FROM cards WHERE owner IS NOT NULL''')
        results = self.cursor.fetchall()
        return [x[0] for x in results]

    def null_owner(self, lst):

        """Set the owner to NULL of all cards in the list of serial numbers"""

        if not lst:
            return  # somehow, no cards were stolen and postgres will complain if we
                    # give it an empty tuple
        #part = f'''({",".join([str(q) for q in lst])})'''
        print("Nulling owner for ", lst)
        self.cursor.execute(f'''UPDATE cards SET owner = NULL WHERE serial IN %s''', (tuple(lst),))
        self.db.commit()

    def set_auto_vault(self, uid, status):

        self.cursor.execute('''UPDATE stats SET auto_vault = %s WHERE uid = %s''', (status, uid))
        self.db.commit()

    def get_auto_vault(self, uid):

        self.cursor.execute('''SELECT auto_vault FROM stats WHERE uid = %s''', (uid,))
        return self.cursor.fetchone()[0]

    def change_vault_status(self, lst, status):

        """Set vault status to True or False for cards in lst"""

        self.cursor.execute(f'''UPDATE cards SET vault = %s WHERE serial IN %s''', (status, tuple(lst)))
        self.db.commit()

    def log_chatgpt_message(self, uid, cid, role, message, tokens, moderated=False):

        """Keep a record of interactions with ChatGPT for moderation, etc"""

        self.cursor.execute(
            '''INSERT INTO chats (uid, channelid, role, message, tokens, moderated) 
            VALUES (%s, %s, %s, %s, %s, %s)''',
            (uid, cid, role, message, tokens, moderated))
        self.db.commit()

    def uid_to_screen_name(self, uid):

        self.cursor.execute("SELECT screen_name FROM names WHERE uid = %s", (uid,))
        if q := self.cursor.fetchone():
            return q[0]

    def get_anonymous_uid(self, uid):

        """Get an anonymized ID to track ChatGPT correspondence. Generate a new one if it doesn't already exist"""

        self.cursor.execute("SELECT anonymous_id FROM names WHERE uid = %s", (uid,))
        result = self.cursor.fetchone()

        if result and result[0]:  # the uid at least exists in the DB, but might not have a hash yet
            # a tuple (None,) evaluates to True!! We can risk unpacking a NoneType here because it will
            # never happen, if result is None then result[0] will never be tried
            return result[0]
        else:

            # first time we are hashing the uid, insert then return it
            salt = self.bot.settings["chatgpt_salt"]
            hasher = hashlib.sha256()
            hasher.update((str(uid) + salt).encode("UTF-8"))
            hashed = hasher.hexdigest()
            self.cursor.execute('''UPDATE names SET anonymous_id = %s WHERE uid = %s''', (hashed, uid))
            self.db.commit()
            return hashed

    def insert_prompt(self, uid, text):

        self.cursor.execute('''INSERT INTO prompts (uid, prompt) VALUES (%s, %s)''', (uid, text))
        self.db.commit()

    def get_max_prompt_serial(self):

        self.cursor.execute('''SELECT MAX(identifier) FROM prompts''')
        res = self.cursor.fetchone()
        return res[0]

    def remove_prompt(self, serial):

        self.cursor.execute('''DELETE FROM prompts WHERE identifier = %s''', (serial,))
        self.db.commit()

    def get_prompt(self, serial):

        self.cursor.execute('''SELECT prompt FROM prompts WHERE identifier = %s''', (serial,))
        return self.cursor.fetchone()[0]



