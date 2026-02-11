-- Kafka-dependent tables. Run after Kafka is ready.
CREATE TABLE IF NOT EXISTS kafka_telemetry_queue (
    payload String
) ENGINE = Kafka
SETTINGS
    kafka_broker_list = 'kafka:29092',
    kafka_topic_list = 'crm_db.public.telemetry_events',
    kafka_group_name = 'clickhouse_telemetry',
    kafka_format = 'JSONAsString',
    kafka_num_consumers = 1;

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
