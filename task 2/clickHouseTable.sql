CREATE TABLE IF NOT EXISTS bionic.user_daily_report (
    user_id          UInt64,
    report_date      Date,
    total_movements  UInt32,
    avg_response_ms  Float32,
    battery_drain_pct Float32,
    session_count    UInt32,
    firmware_version String
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(report_date)
ORDER BY (user_id, report_date);