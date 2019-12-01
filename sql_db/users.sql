create table users
(
	primary_key int unsigned auto_increment
		primary key,
	username varchar(20) not null,
	password varchar(50) null,
	uid int unsigned not null,
	gid int unsigned not null,
	homedir varchar(500) not null,
	shell varchar(20) null
);

