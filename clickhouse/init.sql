CREATE DATABASE IF NOT EXISTS reports_db;

CREATE USER IF NOT EXISTS airflow IDENTIFIED WITH plaintext_password BY 'airflow123';
GRANT ALL ON reports_db.* TO airflow;

CREATE TABLE IF NOT EXISTS reports_db.prosthesis_report
(
    user_uuid UUID,
    user_name String,
    prosthesis_id UUID,
    report_date Date,
    total_usage_seconds UInt64,
    avg_response_time_ms Float32,
    movements_count UInt32,
    battery_cycles UInt16,
    last_telemetry_time DateTime,
    firmware_version String,
    region String,
    created_at DateTime DEFAULT now()
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(report_date)
ORDER BY (user_uuid, report_date);