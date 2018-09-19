BEGIN TRANSACTION;

CREATE TABLE IF NOT EXISTS `scene_meta` (
	`ID`	INTEGER PRIMARY KEY AUTOINCREMENT,
	`Sensor`	VARCHAR ( 10 ),
	`Coll_number`	INTEGER,
	`Coll_category`	VARCHAR ( 2 ),
	`Path`	INTEGER NOT NULL,
	`Row`	INTEGER NOT NULL,
	`acqdate`	DATE,
	`Scene_ID`	VARCHAR ( 23 ) NOT NULL,
	`Product_ID`	VARCHAR ( 42 ),
	`CC_Full`	REAL,
	`CC_Land`	REAL,
	`DayNight`	VARCHAR ( 6 ),
	UNIQUE(`Scene_ID`,`Product_ID`)
);

CREATE TABLE IF NOT EXISTS `journal_meta` (
	`ID`	INTEGER PRIMARY KEY AUTOINCREMENT,
	`last_update`	DATE NOT NULL,
	`archive_size`	INTEGER NOT NULL,
	`all_records`	INTEGER NOT NULL,
	`RT_records`	INTEGER NOT NULL
);

COMMIT;
