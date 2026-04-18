CREATE DATABASE IF NOT EXISTS clickhouse_db;


CREATE TABLE IF NOT EXISTS clickhouse_db.report (
    id UUID DEFAULT generateUUIDv4(),
    user_id UInt32,
    full_name String,
    email String,
    age UInt32,
    country String,
    prosthesis_id String,
    movement String,
    battery_level Double,
    active_minutes UInt32,
    event_time DateTime,
    report_date DateTime
) ENGINE = MergeTree()
ORDER BY (user_id, prosthesis_id, event_time);

CREATE TABLE IF NOT EXISTS clickhouse_db.report_date (
    id UInt32,
    report_date DateTime
) ENGINE = ReplacingMergeTree
PRIMARY KEY (id)
ORDER BY (id);