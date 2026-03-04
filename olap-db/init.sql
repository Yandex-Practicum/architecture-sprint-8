CREATE TABLE IF NOT EXISTS user_reports (
    user_id UInt32,
    report_date Date,
    full_name String,
    email String,
    age UInt8,
    gender String,
    country String,
    prosthesis_type String,
    avg_signal_frequency Float32,
    avg_signal_duration Float32,
    avg_signal_amplitude Float32,
    total_signals UInt32,
    last_signal_time DateTime
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(report_date)
ORDER BY (user_id, report_date);