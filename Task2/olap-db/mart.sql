-- Создание витрины данных
CREATE TABLE IF NOT EXISTS customer_report (
    user_id UInt32,
    name String,
    email String,
    age Decimal(3,0),
    gender String,
    country String,
    prosthesis_type String,
    total_sessions UInt64,
    total_signal_duration UInt64,
    avg_signal_frequency Float64,
    avg_signal_amplitude Float64,
    last_signal_time DateTime,
    created_at DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY (user_id, last_signal_time);

-- Для быстрого доступа по user_id
CREATE TABLE IF NOT EXISTS customer_report_final (
    user_id UInt32,
    name String,
    email String,
    age Decimal(3,0),
    gender String,
    country String,
    prosthesis_type String,
    total_sessions UInt64,
    total_signal_duration UInt64,
    avg_signal_frequency Float64,
    avg_signal_amplitude Float64,
    last_signal_time DateTime,
    updated_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (user_id, prosthesis_type);