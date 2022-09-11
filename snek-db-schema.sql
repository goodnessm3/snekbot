CREATE TABLE sqlite_sequence(name,seq);
CREATE TABLE IF NOT EXISTS "monitored" (
	`tag`	TEXT,
	`last`	TEXT,
	`channel_id`	INTEGER
);
CREATE TABLE IF NOT EXISTS "stats" (
	`uid`	INTEGER,
	`bux`	INTEGER CHECK(bux >= 0),
	`last_time`	real,
	`level`	INTEGER,
	`exp`	INTEGER,
	`inventory`	TEXT, muon,
	PRIMARY KEY(`uid`)
);
CREATE TABLE searches(stime DATETIME DEFAULT CURRENT_TIMESTAMP, uid INTEGER, tags TEXT);
CREATE TABLE Peros (
	userid INTEGER,
	channelid INTEGER,
	count INTEGER,
	PRIMARY KEY (userid, channelid)
);
CREATE TABLE `reminders` (
`uid`INTEGER,
`timestamp`DATETIME,
`message`TEXT,
`rid`INTEGER PRIMARY KEY AUTOINCREMENT,
`channel_id`INTEGER
);
CREATE TABLE most_peroed (postid INTEGER PRIMARY KEY, channel INTEGER, count INTEGER, last_updated DATETIME DEFAULT CURRENT_TIMESTAMP, done, image_url, thumb);
CREATE TRIGGER update_pero_date UPDATE OF count ON most_peroed
BEGIN
UPDATE most_peroed SET last_updated = CURRENT_TIMESTAMP WHERE postid = NEW.postid;
END;
CREATE TABLE IF NOT EXISTS "shop" (
	`uid`	INTEGER,
	`cookie`	TEXT,
	`rand`	TEXT,
	`uname` TEXT
);
CREATE TABLE IF NOT EXISTS "tags" ("tag" TEXT UNIQUE, "count" INTEGER, PRIMARY KEY("tag"));
CREATE TABLE IF NOT EXISTS "stonks" (
	"uid"	INTEGER,
	"tag"	TEXT,
	"amount"	INTEGER,
	"paid"	INTEGER,
	"return"	INTEGER
);
CREATE TABLE IF NOT EXISTS "tag_deltas" ("tag" TEXT, "change" INTEGER, "time" DATETIME DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS "cards" (
	"serial"	INTEGER,
	"owner"	INTEGER,
	"atk"	INTEGER,
	"def"	INTEGER,
	"mana"	INTEGER,
	"card_name"	INTEGER,
	"series"	INTEGER,
	PRIMARY KEY("serial")
);
CREATE TABLE IF NOT EXISTS "names" (
	"uid"	INTEGER UNIQUE,
	"screen_name"	TEXT,
	PRIMARY KEY("uid")
);
CREATE TABLE IF NOT EXISTS "buxlog" (
	"date"	DATETIME DEFAULT CURRENT_TIMESTAMP,
	"uid"	INTEGER,
	"amt"	INTEGER
);
CREATE TABLE tags2(tag TEXT,count INT);
