CREATE DATABASE IF NOT EXISTS bionicpro;

CREATE TABLE IF NOT EXISTS bionicpro.crm_customers
(
    user_id String,
    user_name String,
    email String,
    prosthesis_id String,
    country_code LowCardinality(String),
    updated_at DateTime
)
ENGINE = MergeTree
ORDER BY (user_id, prosthesis_id);

CREATE TABLE IF NOT EXISTS bionicpro.prosthesis_telemetry
(
    event_time DateTime,
    user_id String,
    prosthesis_id String,
    movement String,
    reaction_ms UInt16,
    battery_level UInt8
)
ENGINE = MergeTree
ORDER BY (user_id, prosthesis_id, event_time);

CREATE TABLE IF NOT EXISTS bionicpro.report_mart
(
    user_id String,
    user_name String,
    email String,
    prosthesis_id String,
    period_start DateTime,
    period_end DateTime,
    events_count UInt64,
    avg_reaction_ms Float64,
    min_battery_level UInt8,
    last_prepared_at DateTime
)
ENGINE = ReplacingMergeTree(last_prepared_at)
ORDER BY (user_id, prosthesis_id, period_end);
