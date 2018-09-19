BEGIN TRANSACTION;

CREATE TABLE IF NOT EXISTS `workflows` (
	`wfid`	integer PRIMARY KEY AUTOINCREMENT,
	`name`	varchar ( 100 ) NOT NULL,
	`rootdir`	varchar ( 300 ) NOT NULL,
	`desc`	varchar ( 100 ),
	UNIQUE(`name`,`rootdir`)
);

CREATE TABLE IF NOT EXISTS `process_run` (
	`ID`	INTEGER PRIMARY KEY AUTOINCREMENT,
	`pUID`	INTEGER,
	`Desc`	VARCHAR ( 200 ) NOT NULL,
	`PATH`	CHAR ( 3 ),
	`ROW`	CHAR ( 3 ),
	`Acqdate`	VARCHAR ( 10 ),
	`fk_wfid`	integer NOT NULL,
	FOREIGN KEY(`fk_wfid`) REFERENCES `workflows`(`wfid`) on update cascade on delete cascade
);

COMMIT;
