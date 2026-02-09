drop table if exists client_info;

create table client_info (
    client_id varchar(36) not null primary key unique,
    client_name varchar(255) not null,
    email varchar(255) not null unique,
    country varchar(50) not null,
    manufacturing_date date not null,
    device_model varchar(50) not null,
    device_sn varchar(30) not null unique
);

insert into client_info values ('user1', 'John Doe', 'john.doe@example.com', 'USA', '2025-01-01', 'leg123', 'SN000001');
insert into client_info values ('user2', 'Jane Smith', 'jane.smith@example.com', 'Canada', '2025-02-01', 'leg456', 'SN000002');
insert into client_info values ('user3', 'Bob Johnson', 'bob.johnson@example.com', 'UK', '2025-03-01', 'leg123', 'SN000003');
insert into client_info values ('user4', 'Alice Brown', 'alice.brown@example.com', 'Australia', '2025-04-01', 'arm101', 'SN000004');
insert into client_info values ('user5', 'Charlie Davis', 'charlie.davis@example.com', 'Germany', '2025-05-01', 'arm101', 'SN000005');
insert into client_info values ('user6', 'David Wilson', 'david.wilson@example.com', 'France', '2025-06-01', 'leg456', 'SN000006');
insert into client_info values ('user7', 'Eva Miller', 'eva.miller@example.com', 'Spain', '2025-07-01', 'arm201', 'SN000007');
insert into client_info values ('user8', 'Frank Moore', 'frank.moore@example.com', 'Italy', '2025-08-01', 'arm101', 'SN000008');
insert into client_info values ('user9', 'Grace Smith', 'grace.smith@example.com', 'Japan', '2025-09-01', 'arm201', 'SN000009');
insert into client_info values ('user10', 'Henry Taylor', 'henry.taylor@example.com', 'China', '2025-10-01', 'arm201', 'SN000010');
insert into client_info values ('user11', 'Ivy Thompson', 'ivy.thompson@example.com', 'Brazil', '2025-11-01', 'leg123', 'SN000011');