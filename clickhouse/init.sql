-- ClickHouse: KafkaEngine + MaterializedView для витрины отчётности
-- Поток: Debezium → Kafka → KafkaEngine → telemetry_events → datamart_reports

-- 1. Сырые события телеметрии (заполняется MV из Kafka)
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

-- 2. Очередь Kafka (Debezium JSON: before, after, op, source)
CREATE TABLE IF NOT EXISTS kafka_telemetry_queue (
    payload String
) ENGINE = Kafka
SETTINGS
    kafka_broker_list = 'kafka:29092',
    kafka_topic_list = 'crm_db.public.telemetry_events',
    kafka_group_name = 'clickhouse_telemetry',
    kafka_format = 'JSONAsString',
    kafka_num_consumers = 1;

-- 3. MV: парсинг Debezium JSON → telemetry_events (только op in ('c','r','u'), after)
-- _version: d=0, c/r=1, u=2 (updates overwrite inserts in ReplacingMergeTree)
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_telemetry_to_events TO telemetry_events AS
SELECT
    toInt64(JSONExtractString(JSONExtractRaw(payload, 'after'), 'id')) AS id,
    JSONExtractString(JSONExtractRaw(payload, 'after'), 'user_id') AS user_id,
    parseDateTime64BestEffort(JSONExtractString(JSONExtractRaw(payload, 'after'), 'event_time')) AS event_time,
    JSONExtractString(JSONExtractRaw(payload, 'after'), 'metric_name') AS metric_name,
    toFloat64(JSONExtractString(JSONExtractRaw(payload, 'after'), 'value')) AS value,
    nullIf(JSONExtractString(JSONExtractRaw(payload, 'after'), 'created_at'), '') != '' 
        ? parseDateTime64BestEffort(JSONExtractString(JSONExtractRaw(payload, 'after'), 'created_at')) 
        : NULL AS created_at,
    multiIf(JSONExtractString(payload, 'op') = 'd', 0, JSONExtractString(payload, 'op') = 'u', 2, 1) AS _version
FROM kafka_telemetry_queue
WHERE JSONExtractString(payload, 'op') IN ('c', 'r', 'u')
  AND has(JSONExtractKeys(payload), 'after');

-- 4. Витрина отчётности (период = неделя, агрегация по user_id)
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

-- 5. MV: telemetry_events → datamart_reports (агрегация по user_id и неделе)
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
