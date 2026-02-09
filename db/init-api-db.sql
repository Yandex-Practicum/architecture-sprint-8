drop table if exists device_telemetries;

create table device_telemetries (
    id SMALLSERIAL primary key,
    device_sn varchar(255) not null,
    started_at timestamp  not null,
    response_speed integer not null,
    error_code varchar(255),
    myodensor_id varchar(255) not null,
    myodensor_value float not null,
    actuator_id varchar(255) not null,
    actuator_value float not null,
    battery_level float not null,
    battery_temperature float not null
);

-- Заполняем телеметрию за 3 последних дня для пользователей John Doe и Alice Brown
insert into device_telemetries (device_sn, started_at, response_speed, error_code, myodensor_id, myodensor_value, actuator_id, actuator_value, battery_level, battery_temperature)
values
    ('SN000001', CURRENT_DATE + INTERVAL '1 hour', 10, null, 'myodensor1', 10.0, 'actuator1', 0.55, 40.0, 25.0),
    ('SN000001', CURRENT_DATE + INTERVAL '2 hour', 50, null, 'myodensor2', 10.0, 'actuator2', 0.35, 20.0, 25.0),
    ('SN000001', CURRENT_DATE + INTERVAL '3 hour', 100, null, 'myodensor3', 10.0, 'actuator3', 0.15, 10.0, 35.0),

    ('SN000001', CURRENT_DATE - INTERVAL '1 day' + INTERVAL '1 hour', 120, null, 'myodensor1', 10.0, 'actuator1', 0.55, 40.0, 25.0),
    ('SN000001', CURRENT_DATE - INTERVAL '1 day' + INTERVAL '2 hour', 33, null, 'myodensor2', 10.0, 'actuator2', 0.35, 20.0, 25.0),
    ('SN000001', CURRENT_DATE - INTERVAL '1 day' + INTERVAL '3 hour', 100, 'error_2', 'myodensor3', 10.0, 'actuator3', 0.15, 10.0, 35.0),

    ('SN000001', CURRENT_DATE - INTERVAL '2 day' + INTERVAL '1 hour', 300, 'error_1', 'myodensor1', 10.0, 'actuator1', 0.55, 100.0, 25.0),
    ('SN000001', CURRENT_DATE - INTERVAL '2 day' + INTERVAL '2 hour', 50, null, 'myodensor2', 10.0, 'actuator2', 0.35, 40.0, 45.0),
    ('SN000001', CURRENT_DATE - INTERVAL '2 day' + INTERVAL '3 hour', 100, null, 'myodensor3', 10.0, 'actuator3', 0.15, 5.0, 35.0),


    ('SN000004', CURRENT_DATE - INTERVAL '1 hour', 10, 'error_1', 'myodensor1', 10.0, 'actuator1', 0.55, 40.0, 25.0),
    ('SN000004', CURRENT_DATE - INTERVAL '2 hour', 50, null, 'myodensor2', 10.0, 'actuator2', 0.35, 20.0, 25.0),
    ('SN000004', CURRENT_DATE - INTERVAL '3 hour', 100, null, 'myodensor3', 10.0, 'actuator3', 0.15, 10.0, 35.0),

    ('SN000004', CURRENT_DATE - INTERVAL '1 day' + INTERVAL '1 hour', 120, null, 'myodensor1', 10.0, 'actuator1', 0.55, 40.0, 25.0),
    ('SN000004', CURRENT_DATE - INTERVAL '1 day' + INTERVAL '2 hour', 33, null, 'myodensor2', 10.0, 'actuator2', 0.35, 20.0, 25.0),
    ('SN000004', CURRENT_DATE - INTERVAL '1 day' + INTERVAL '3 hour', 100, null, 'myodensor3', 10.0, 'actuator3', 0.15, 10.0, 35.0),

    ('SN000004', CURRENT_DATE - INTERVAL '2 day' + INTERVAL '1 hour', 300, null, 'myodensor1', 10.0, 'actuator1', 0.55, 100.0, 25.0),
    ('SN000004', CURRENT_DATE - INTERVAL '2 day' + INTERVAL '2 hour', 50, null, 'myodensor2', 10.0, 'actuator2', 0.35, 40.0, 45.0),
    ('SN000004', CURRENT_DATE - INTERVAL '2 day' + INTERVAL '3 hour', 100, null, 'myodensor3', 10.0, 'actuator3', 0.15, 5.0, 35.0);