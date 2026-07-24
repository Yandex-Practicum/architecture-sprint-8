CREATE DATABASE IF NOT EXISTS bionicpro;

CREATE TABLE IF NOT EXISTS bionicpro.user_report_mart (
    user_id String,
    user_email String,
    user_name String,
    total_steps UInt64,
    total_active_minutes UInt64,
    battery_avg_usage Float64,
    error_count UInt64,
    report_date Date
)
ENGINE = MergeTree()
ORDER BY (user_id, report_date);