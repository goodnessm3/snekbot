CREATE TABLE stats (
	uid INTEGER PRIMARY KEY,
	bux INTEGER,
	CONSTRAINT CHK_bux CHECK(bux >= 0)
);