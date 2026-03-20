CREATE DATABASE IF NOT EXISTS reports;

CREATE TABLE IF NOT EXISTS reports.user_usage_raw
(
    user_id       String,
    external_id   String,
    full_name     String,
    prosthesis_id String,
    serial_number String,
    event_date    Date,
    event_time    DateTime,
    load_value    Float64,
    duration_sec  UInt32
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_date)
ORDER BY (user_id, event_date, prosthesis_id, event_time);

CREATE TABLE IF NOT EXISTS reports.user_usage_daily
(
    user_id            String,
    external_id        String,
    full_name          String,
    prosthesis_id      String,
    serial_number      String,
    event_date         Date,
    total_duration_sec UInt64,
    avg_load           Float64,
    max_load           Float64,
    events_count       UInt32
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_date)
ORDER BY (user_id, event_date, prosthesis_id);
