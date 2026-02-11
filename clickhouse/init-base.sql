-- Base tables (no Kafka dependency). Run first.
CREATE TABLE IF NOT EXISTS telemetry_events (
    id Int64,
    user_id String,
    event_time DateTime64(3),
    metric_name String,
    value Float64,
    created_at Nullable(DateTime64(3)),
    _version UInt8 DEFAULT 1
) ENGINE = ReplacingMergeTree(_version)
ORDER BY (user_id, event_time, id)
SETTINGS index_granularity = 8192;

CREATE TABLE IF NOT EXISTS datamart_reports (
    user_id String,
    period_from Date,
    period_to Date,
    usage_hours Float64,
    steps Float64,
    events_count UInt64,
    report_generated_at DateTime64(3) DEFAULT now64(3)
) ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(period_from)
ORDER BY (user_id, period_from)
SETTINGS index_granularity = 8192;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_telemetry_to_datamart TO datamart_reports AS
SELECT
    user_id,
    toMonday(toDate(event_time)) AS period_from,
    toMonday(toDate(event_time)) + 6 AS period_to,
    sumIf(value, metric_name = 'usage_hours') AS usage_hours,
    sumIf(value, metric_name = 'steps') AS steps,
    count() AS events_count,
    now64(3) AS report_generated_at
FROM telemetry_events
GROUP BY user_id, toMonday(toDate(event_time));
