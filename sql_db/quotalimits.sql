create table quotalimits
(
	name varchar(30) null,
	quota_type enum('user', 'group', 'class', 'all') not null,
	per_session enum('false', 'true') not null,
	limit_type enum('soft', 'hard') not null,
	bytes_in_avail float not null,
	bytes_out_avail float not null,
	bytes_xfer_avail float not null,
	files_in_avail int unsigned not null,
	files_out_avail int unsigned not null,
	files_xfer_avail int unsigned not null
);

