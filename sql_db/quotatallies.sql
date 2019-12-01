create table quotatallies
(
	name varchar(30) not null,
	quota_type enum('user', 'group', 'class', 'all') not null,
	bytes_in_used float not null,
	bytes_out_used float not null,
	bytes_xfer_used float not null,
	files_in_used int unsigned not null,
	files_out_used int unsigned not null,
	files_xfer_used int unsigned not null
);

