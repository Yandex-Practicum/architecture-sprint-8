CREATE DATABASE IF NOT EXISTS bionicpro;

CREATE TABLE IF NOT EXISTS bionicpro.crm_customers_cdc_queue
(
    payload String
)
ENGINE = Kafka
SETTINGS
    kafka_broker_list = 'kafka:29092',
    kafka_topic_list = 'crm.public.crm_customers',
    kafka_group_name = 'clickhouse-crm-customers',
    kafka_format = 'JSONAsString',
    kafka_num_consumers = 1,
    kafka_handle_error_mode = 'stream';

CREATE TABLE IF NOT EXISTS bionicpro.crm_customers_cdc_raw
(
    payload String,
    consumed_at DateTime DEFAULT now()
)
ENGINE = MergeTree
ORDER BY consumed_at;

CREATE MATERIALIZED VIEW IF NOT EXISTS bionicpro.crm_customers_cdc_raw_mv
TO bionicpro.crm_customers_cdc_raw
AS SELECT
    payload
FROM bionicpro.crm_customers_cdc_queue;

CREATE TABLE IF NOT EXISTS bionicpro.crm_customers_cdc
(
    user_id String,
    user_name String,
    email String,
    prosthesis_id String,
    country_code LowCardinality(String),
    updated_at DateTime,
    op LowCardinality(String),
    is_deleted UInt8,
    event_ts DateTime64(3)
)
ENGINE = ReplacingMergeTree(event_ts)
ORDER BY (user_id, prosthesis_id);

CREATE MATERIALIZED VIEW IF NOT EXISTS bionicpro.crm_customers_cdc_mv
TO bionicpro.crm_customers_cdc
AS SELECT
    if(JSONExtractString(payload, 'op') = 'd',
        JSONExtractString(payload, 'before', 'user_id'),
        JSONExtractString(payload, 'after', 'user_id')) AS user_id,
    if(JSONExtractString(payload, 'op') = 'd',
        JSONExtractString(payload, 'before', 'user_name'),
        JSONExtractString(payload, 'after', 'user_name')) AS user_name,
    if(JSONExtractString(payload, 'op') = 'd',
        JSONExtractString(payload, 'before', 'email'),
        JSONExtractString(payload, 'after', 'email')) AS email,
    if(JSONExtractString(payload, 'op') = 'd',
        JSONExtractString(payload, 'before', 'prosthesis_id'),
        JSONExtractString(payload, 'after', 'prosthesis_id')) AS prosthesis_id,
    if(JSONExtractString(payload, 'op') = 'd',
        JSONExtractString(payload, 'before', 'country_code'),
        JSONExtractString(payload, 'after', 'country_code')) AS country_code,
    parseDateTimeBestEffortOrZero(if(JSONExtractString(payload, 'op') = 'd',
        JSONExtractString(payload, 'before', 'updated_at'),
        JSONExtractString(payload, 'after', 'updated_at'))) AS updated_at,
    JSONExtractString(payload, 'op') AS op,
    if(JSONExtractString(payload, 'op') = 'd', 1, 0) AS is_deleted,
    fromUnixTimestamp64Milli(JSONExtractInt(payload, 'ts_ms')) AS event_ts
FROM bionicpro.crm_customers_cdc_raw
WHERE JSONExtractString(payload, 'op') IN ('c', 'r', 'u', 'd');

CREATE TABLE IF NOT EXISTS bionicpro.report_mart_cdc
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

CREATE MATERIALIZED VIEW IF NOT EXISTS bionicpro.report_mart_cdc_mv
TO bionicpro.report_mart_cdc
AS SELECT
    c.user_id,
    c.user_name,
    c.email,
    c.prosthesis_id,
    min(t.event_time) AS period_start,
    max(t.event_time) AS period_end,
    count() AS events_count,
    round(avg(t.reaction_ms), 2) AS avg_reaction_ms,
    min(t.battery_level) AS min_battery_level,
    now() AS last_prepared_at
FROM bionicpro.crm_customers_cdc AS c
INNER JOIN bionicpro.prosthesis_telemetry AS t
    ON c.user_id = t.user_id
    AND c.prosthesis_id = t.prosthesis_id
WHERE c.is_deleted = 0
GROUP BY
    c.user_id,
    c.user_name,
    c.email,
    c.prosthesis_id;
