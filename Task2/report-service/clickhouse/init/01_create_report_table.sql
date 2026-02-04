CREATE TABLE IF NOT EXISTS user_prosthesis_daily_report
(
    report_date Date,
    user_id UInt64,
    prosthesis_id UInt64,
    prosthesis_model String,
    movements_count UInt32,
    active_time_seconds UInt32,
    battery_avg Float32,
    battery_min UInt8,
    errors_count UInt32
)
    ENGINE = MergeTree
    PARTITION BY toYYYYMM(report_date)
    ORDER BY (user_id, prosthesis_id, report_date);
