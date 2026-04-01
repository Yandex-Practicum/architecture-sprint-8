-- Задание 4: KafkaEngine + MaterializedView → витрина mart_user_prosthesis_daily
CREATE DATABASE IF NOT EXISTS reporting;

-- Очереди Kafka (топики Debezium: crm.public.*)
CREATE TABLE IF NOT EXISTS reporting.customers_kafka_queue (
    raw String
) ENGINE = Kafka()
SETTINGS
    kafka_broker_list = 'kafka:9092',
    kafka_topic_list = 'crm.public.customers',
    kafka_group_name = 'ch_reporting_customers',
    kafka_format = 'JSONAsString',
    kafka_num_consumers = 1;

CREATE TABLE IF NOT EXISTS reporting.telemetry_kafka_queue (
    raw String
) ENGINE = Kafka()
SETTINGS
    kafka_broker_list = 'kafka:9092',
    kafka_topic_list = 'crm.public.telemetry_events',
    kafka_group_name = 'ch_reporting_telemetry',
    kafka_format = 'JSONAsString',
    kafka_num_consumers = 1;

-- Измерение CRM (из CDC customers)
CREATE TABLE IF NOT EXISTS reporting.customers (
    customer_id String,
    email String,
    keycloak_subject String,
    prosthesis_model String,
    region String,
    updated_at DateTime64(3)
) ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (customer_id);

CREATE MATERIALIZED VIEW IF NOT EXISTS reporting.customers_from_kafka_mv TO reporting.customers
AS
SELECT
    JSONExtractString(raw, 'customer_id') AS customer_id,
    JSONExtractString(raw, 'email') AS email,
    JSONExtractString(raw, 'keycloak_subject') AS keycloak_subject,
    JSONExtractString(raw, 'prosthesis_model') AS prosthesis_model,
    JSONExtractString(raw, 'region') AS region,
    if(
        length(JSONExtractString(raw, 'updated_at')) > 0,
        parseDateTime64BestEffortOrNull(JSONExtractString(raw, 'updated_at'), 3),
        now64(3)
    ) AS updated_at
FROM reporting.customers_kafka_queue
WHERE coalesce(JSONExtractBool(raw, '__deleted'), false) = false
  AND length(JSONExtractString(raw, 'customer_id')) > 0;

-- Факты телеметрии (из CDC telemetry_events)
CREATE TABLE IF NOT EXISTS reporting.telemetry_stg (
    id Int64,
    user_subject String,
    event_date Date,
    active_minutes Int32,
    steps UInt64,
    updated_at DateTime64(3)
) ENGINE = MergeTree
ORDER BY (user_subject, event_date, id);

CREATE MATERIALIZED VIEW IF NOT EXISTS reporting.telemetry_from_kafka_mv TO reporting.telemetry_stg
AS
SELECT
    toInt64(JSONExtractInt(raw, 'id')) AS id,
    JSONExtractString(raw, 'user_subject') AS user_subject,
    if(
        length(JSONExtractString(raw, 'event_date')) >= 10,
        toDate(JSONExtractString(raw, 'event_date')),
        addDays(toDate('1970-01-01'), toInt32(JSONExtractInt(raw, 'event_date')))
    ) AS event_date,
    toInt32(JSONExtractInt(raw, 'active_minutes')) AS active_minutes,
    toUInt64(JSONExtractInt(raw, 'steps')) AS steps,
    if(
        length(JSONExtractString(raw, 'updated_at')) > 0,
        parseDateTime64BestEffortOrNull(JSONExtractString(raw, 'updated_at'), 3),
        now64(3)
    ) AS updated_at
FROM reporting.telemetry_kafka_queue
WHERE coalesce(JSONExtractBool(raw, '__deleted'), false) = false
  AND JSONExtractInt(raw, 'id') > 0;

-- Витрина отчётности (JOIN CRM + телеметрия)
CREATE TABLE IF NOT EXISTS reporting.mart_user_prosthesis_daily (
    user_subject String,
    stat_date Date,
    active_hours Float64,
    steps UInt64,
    prosthesis_model Nullable(String),
    crm_region Nullable(String),
    updated_at DateTime64(3)
) ENGINE = MergeTree
ORDER BY (user_subject, stat_date, updated_at);

CREATE MATERIALIZED VIEW IF NOT EXISTS reporting.mart_from_telemetry_mv TO reporting.mart_user_prosthesis_daily
AS
SELECT
    t.user_subject AS user_subject,
    toDate(t.event_date) AS stat_date,
    toFloat64(t.active_minutes) / 60.0 AS active_hours,
    t.steps AS steps,
    c.prosthesis_model AS prosthesis_model,
    c.region AS crm_region,
    t.updated_at AS updated_at
FROM reporting.telemetry_stg AS t
LEFT JOIN (
    SELECT
        keycloak_subject,
        argMax(prosthesis_model, updated_at) AS prosthesis_model,
        argMax(region, updated_at) AS region
    FROM reporting.customers
    GROUP BY keycloak_subject
) AS c ON c.keycloak_subject = t.user_subject;
