import sqlite3
import re
from collections import defaultdict


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
            insert into stats (uid, bux) select ?, ? where (select changes() = 0)
            ''', (uid, 0))
            return 0
        
        return restuple[0]  # if the user just wants one value, return a value rather than tuple

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

        try:
            self.cursor.execute('''update stats set bux = bux + ? where uid = ?''', (amt, uid))
        except sqlite3.IntegrityError:
            # constraint is bux must be > 0, just set to 0 if it would otherwise go below
            self.cursor.execute('''update stats set bux = 0 where uid = ?''', (uid,))

        self.cursor.execute('''
        insert into stats (uid, bux) select ?, ? where (select changes() = 0)
        ''', (uid, amt))
        # this statement only runs if changes() = 0 i.e. nothing was changed by the previous statement
        # because the uid wasn't present in the database keys. This saves having to check for the presence
        # of the uid every time, just add the entry if it didn't exist already.

        self.db.commit()

    def add_reminder(self, uid, time, message, channel_id):

        self.cursor.execute('''
        insert into reminders (uid, timestamp, message, channel_id) values(?, ?, ?, ?)''',
                            (uid, time, message, channel_id))
        self.db.commit()

    def get_reminders(self, now):

        # return a list of tuples of all reminders whose time is greater than now (seconds since epoch)

        self.cursor.execute('''select * from reminders where timestamp > ?''', (now,))
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







