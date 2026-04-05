CREATE DATABASE IF NOT EXISTS bionicpro;

CREATE TABLE IF NOT EXISTS bionicpro.reports_mart
(
    user_id String,
    period_date Date,
    avg_temperature Nullable(Float64),
    avg_pulse Nullable(Float64),
    plan_code LowCardinality(String),
    data_watermark_date Date,
    mart_loaded_at DateTime DEFAULT now()
)
ENGINE = MergeTree
ORDER BY (user_id, period_date);