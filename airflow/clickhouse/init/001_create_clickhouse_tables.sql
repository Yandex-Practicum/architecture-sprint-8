CREATE
DATABASE IF NOT EXISTS reports;

CREATE TABLE IF NOT EXISTS reports.telemetry_events
(
    event_time
    DateTime,
    prosthetic_id
    String,
    response_time_ms
    Float64,
    battery_level
    UInt8,
    sensor_noise
    Float64,
    movement_type
    String
)
    ENGINE = MergeTree
(
)
    ORDER BY
(
    prosthetic_id,
    event_time
);

CREATE TABLE IF NOT EXISTS reports.user_prosthetic_report_mart
(
    user_id
    String,
    prosthetic_id
    String,
    report_date
    Date,

    user_full_name
    String,
    prosthetic_model
    String,
    serial_number
    String,

    total_events
    UInt64,
    avg_response_time_ms
    Float64,
    max_response_time_ms
    Float64,
    avg_sensor_noise
    Float64,
    low_battery_events
    UInt64,

    last_telemetry_at
    DateTime,
    updated_at
    DateTime
)
    ENGINE = MergeTree
(
)
    ORDER BY
(
    user_id,
    prosthetic_id,
    report_date
);

CREATE TABLE IF NOT EXISTS reports.crm_prosthetics_snapshot (
                                                                user_id String,
                                                                user_full_name String,
                                                                email String,
                                                                prosthetic_id String,
                                                                prosthetic_model String,
                                                                serial_number String,
                                                                loaded_at DateTime
)
    ENGINE = MergeTree()
    ORDER BY (user_id, prosthetic_id);

INSERT INTO reports.telemetry_events
(event_time, prosthetic_id, response_time_ms, battery_level, sensor_noise, movement_type)
VALUES (now() - INTERVAL 5 HOUR, 'prosthetic-001', 85.5, 80, 0.12, 'open_hand'),
       (now() - INTERVAL 4 HOUR, 'prosthetic-001', 92.1, 76, 0.18, 'close_hand'),
       (now() - INTERVAL 3 HOUR, 'prosthetic-001', 110.3, 21, 0.25, 'rotate_wrist'),
       (now() - INTERVAL 2 HOUR, 'prosthetic-002', 78.4, 88, 0.10, 'open_hand'),
       (now() - INTERVAL 1 HOUR, 'prosthetic-002', 95.7, 19, 0.22, 'close_hand');