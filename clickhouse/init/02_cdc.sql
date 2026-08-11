CREATE TABLE IF NOT EXISTS reports.customers_kafka
(
    payload String
)
ENGINE = Kafka
SETTINGS
    kafka_broker_list = 'kafka:9092',
    kafka_topic_list = 'crm.public.customers',
    kafka_group_name = 'clickhouse_customers_cdc',
    kafka_format = 'JSONAsString';

CREATE TABLE IF NOT EXISTS reports.customers_cdc
(
    username        String,
    first_name      String,
    last_name       String,
    prosthetic_id   String,
    country         String,
    updated_at      DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY username;

CREATE MATERIALIZED VIEW IF NOT EXISTS reports.customers_cdc_mv TO reports.customers_cdc AS
SELECT
    JSONExtractString(payload, 'after', 'username')      AS username,
    JSONExtractString(payload, 'after', 'first_name')     AS first_name,
    JSONExtractString(payload, 'after', 'last_name')      AS last_name,
    JSONExtractString(payload, 'after', 'prosthetic_id')  AS prosthetic_id,
    JSONExtractString(payload, 'after', 'country')        AS country,
    now()                                                 AS updated_at
FROM reports.customers_kafka
WHERE JSONExtractString(payload, 'after', 'username') != '';

CREATE TABLE IF NOT EXISTS reports.telemetry_agg
(
    username        String,
    period_start    DateTime,
    period_end      DateTime,
    events_count    UInt32,
    avg_latency_ms  Float32,
    avg_signal_quality Float32,
    updated_at      DateTime DEFAULT now()
)
ENGINE = MergeTree
ORDER BY (username, period_start);

CREATE TABLE IF NOT EXISTS reports.customer_mart_v2
(
    username        String,
    first_name      String,
    last_name       String,
    prosthetic_id   String,
    country         String,
    period_start    DateTime,
    period_end      DateTime,
    events_count    UInt32,
    avg_latency_ms  Float32,
    avg_signal_quality Float32,
    updated_at      DateTime DEFAULT now()
)
ENGINE = MergeTree
ORDER BY (username, period_start);

CREATE MATERIALIZED VIEW IF NOT EXISTS reports.customer_mart_v2_mv TO reports.customer_mart_v2 AS
SELECT
    t.username             AS username,
    c.first_name            AS first_name,
    c.last_name             AS last_name,
    c.prosthetic_id         AS prosthetic_id,
    c.country               AS country,
    t.period_start          AS period_start,
    t.period_end            AS period_end,
    t.events_count          AS events_count,
    t.avg_latency_ms        AS avg_latency_ms,
    t.avg_signal_quality    AS avg_signal_quality,
    now()                   AS updated_at
FROM reports.telemetry_agg AS t
LEFT JOIN reports.customers_cdc AS c ON t.username = c.username;
