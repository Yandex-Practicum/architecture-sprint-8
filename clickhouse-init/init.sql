-- clickhouse-init/init.sql
CREATE DATABASE IF NOT EXISTS reports;

CREATE TABLE IF NOT EXISTS reports.report_fact (
    user_id String,
    report_date Date,
    prosthetic_id String,
    total_usage_minutes Float32,
    avg_response_time_ms Float32,
    battery_cycles UInt16,
    movements_count UInt32,
    successful_movements UInt32,
    failed_movements UInt32,
    calibration_count UInt16,
    data_volume_mb Float32,
    created_at DateTime DEFAULT now()
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(report_date)
ORDER BY (user_id, report_date);