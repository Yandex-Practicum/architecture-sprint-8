CREATE TABLE IF NOT EXISTS reports_mart
(
    user_id UInt64,
    email String,
    plan String,
    country String,
    period_date Date,
    actions_total UInt64,
    errors_total UInt64,
    active_minutes_avg Float64
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(period_date)
ORDER BY (user_id, period_date);

