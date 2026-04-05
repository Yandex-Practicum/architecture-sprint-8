CREATE DATABASE IF NOT EXISTS bionicpro;

CREATE TABLE IF NOT EXISTS bionicpro.telemetry_daily_agg
(
    user_id String,
    period_date Date,
    avg_temperature Nullable(Float64),
    avg_pulse Nullable(Float64)
)
ENGINE = MergeTree
ORDER BY (user_id, period_date);

CREATE TABLE IF NOT EXISTS bionicpro.crm_customer_plan
(
    user_id String,
    plan_code LowCardinality(String),
    updated_at DateTime64(3)
)
ENGINE = MergeTree
ORDER BY (user_id, updated_at);

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
