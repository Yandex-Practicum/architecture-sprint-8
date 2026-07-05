CREATE DATABASE IF NOT EXISTS reports;

CREATE TABLE IF NOT EXISTS reports.user_report
(
    username          String,
    full_name         String,
    prosthesis_model  String,
    period_date       Date,
    avg_response_time_ms Float32,
    max_response_time_ms UInt32,
    min_battery_level    UInt8,
    total_movements      UInt64,
    samples_count        UInt64,
    processed_at         DateTime
)
ENGINE = ReplacingMergeTree(processed_at)
ORDER BY (username, period_date);
