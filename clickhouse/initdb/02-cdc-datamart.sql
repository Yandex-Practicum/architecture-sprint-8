-- CDC-витрина: Debezium -> Kafka -> ClickHouse (KafkaEngine + MaterializedView).
-- Источник изменений: топик crm.public.users (JSON от Debezium).

CREATE DATABASE IF NOT EXISTS bionicpro_dm;

-- 1. Kafka-таблица-приёмник. Читает JSON-сообщения Debezium.
CREATE TABLE IF NOT EXISTS bionicpro_dm.kafka_users_cdc
(
    raw String
)
ENGINE = Kafka
SETTINGS
    kafka_broker_list = 'kafka:9092',
    kafka_topic_list = 'crm.public.users',
    kafka_group_name = 'clickhouse_cdc_users',
    kafka_format = 'JSONAsString',
    kafka_num_consumers = 1;

-- 2. Парсер CDC: достанем из JSON Debezium нужные поля и разложим.
CREATE TABLE IF NOT EXISTS bionicpro_dm.users_cdc_parsed
(
    op            LowCardinality(String),
    user_id       UInt64,
    email         String,
    first_name    String,
    last_name     String,
    country       String,
    updated_at    DateTime DEFAULT now()
)
ENGINE = MergeTree
ORDER BY (user_id, op);

-- 3. MaterializedView: Kafka -> Parsed.
CREATE MATERIALIZED VIEW IF NOT EXISTS bionicpro_dm.users_cdc_mv
TO bionicpro_dm.users_cdc_parsed AS
SELECT
    JSONExtractString(raw, 'op') AS op,
    toUInt64(JSONExtractUInt(JSONExtractString(raw, 'after'), 'id')) AS user_id,
    coalesce(JSONExtractString(JSONExtractString(raw, 'after'), 'email'), '') AS email,
    coalesce(JSONExtractString(JSONExtractString(raw, 'after'), 'first_name'), '') AS first_name,
    coalesce(JSONExtractString(JSONExtractString(raw, 'after'), 'last_name'), '') AS last_name,
    coalesce(JSONExtractString(JSONExtractString(raw, 'after'), 'country'), '') AS country,
    now() AS updated_at
FROM bionicpro_dm.kafka_users_cdc
WHERE JSONExtractString(raw, 'op') IN ('c', 'u', 'r');  -- create / update / read (snapshot)

-- 4. Финальная витрина: ReplacingMergeTree, чтобы свежие версии перебивали старые.
CREATE TABLE IF NOT EXISTS bionicpro_dm.crm_user_report
(
    user_id            UInt64,
    email              String,
    first_name         String,
    last_name          String,
    country            LowCardinality(String),
    prostheses_count   UInt32,
    updated_at         DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY user_id;

-- 5. MaterializedView: Parsed -> crm_user_report.
-- Упрощение: количество протезов считаем join'ом на лету из текущего снимка users.
CREATE MATERIALIZED VIEW IF NOT EXISTS bionicpro_dm.crm_user_report_mv
TO bionicpro_dm.crm_user_report AS
SELECT
    u.user_id AS user_id,
    u.email AS email,
    u.first_name AS first_name,
    u.last_name AS last_name,
    u.country AS country,
    0 AS prostheses_count,   -- заполнится отдельным CDC-потоком по prostheses (для простоты оставим 0)
    u.updated_at AS updated_at
FROM bionicpro_dm.users_cdc_parsed u;