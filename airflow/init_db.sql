-- ClickHouse initialization for BionicPRO

CREATE DATABASE IF NOT EXISTS bionicpro;

CREATE TABLE IF NOT EXISTS bionicpro.reports_mart (
    user_id String,
    username String,
    email String,
    first_name String,
    last_name String,
    prosthetic_model String,
    report_date Date,
    total_usage_hours Float64,
    movement_count UInt32,
    avg_response_time_ms Float64,
    battery_cycles UInt32,
    calibration_count UInt32,
    last_sync_at DateTime,
    etl_processed_at DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY (user_id, report_date);

CREATE TABLE IF NOT EXISTS bionicpro.stg_crm_customers (
    user_id String,
    username String,
    email String,
    first_name String,
    last_name String,
    prosthetic_model String,
    created_at DateTime,
    updated_at DateTime
) ENGINE = MergeTree()
ORDER BY user_id;

CREATE TABLE IF NOT EXISTS bionicpro.stg_telemetry (
    user_id String,
    event_date Date,
    usage_hours Float64,
    movement_count UInt32,
    response_time_ms Float64,
    battery_cycle UInt32,
    calibration_flag UInt8,
    sync_timestamp DateTime
) ENGINE = MergeTree()
ORDER BY (user_id, event_date);
