-- Задание 4: KafkaEngine + MaterializedView — витрина из CDC CRM + телеметрия (без массовой выгрузки из OLTP).
CREATE DATABASE IF NOT EXISTS reports;

CREATE TABLE IF NOT EXISTS reports.telemetry_by_user (
    user_email String,
    report_bucket Date,
    telemetry_samples UInt64,
    telemetry_avg_amplitude Float32,
    inserted_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(inserted_at)
ORDER BY (user_email, report_bucket);

CREATE TABLE IF NOT EXISTS reports.prosthetics_usage_mart_cdc (
    user_sub String DEFAULT '',
    user_email String,
    report_bucket Date,
    telemetry_samples UInt64,
    telemetry_avg_amplitude Float32,
    crm_customer_code String,
    crm_orders_count UInt32,
    etl_batch_id String,
    loaded_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(loaded_at)
PARTITION BY toYYYYMM(report_bucket)
ORDER BY (user_email, report_bucket, crm_customer_code);

CREATE TABLE IF NOT EXISTS reports.etl_watermark (
    pipeline String,
    data_through_date Date,
    last_success_at DateTime
) ENGINE = ReplacingMergeTree(last_success_at)
ORDER BY pipeline;

-- Старую витрину из Airflow-ETL убираем, API переводится на mart_cdc.
DROP TABLE IF EXISTS reports.prosthetics_usage_mart;

DROP VIEW IF EXISTS reports.mv_crm_kafka_to_mart;
DROP TABLE IF EXISTS reports.crm_kafka_queue;

CREATE TABLE reports.crm_kafka_queue (
    raw String
) ENGINE = Kafka()
SETTINGS
    kafka_broker_list = 'kafka:29092',
    kafka_topic_list = 'crm.public.crm_customers',
    kafka_group_name = 'ch_cdc_crm_mart',
    kafka_format = 'JSONAsString',
    kafka_num_consumers = 1,
    kafka_skip_broken_messages = 10;

CREATE MATERIALIZED VIEW reports.mv_crm_kafka_to_mart
TO reports.prosthetics_usage_mart_cdc
AS
SELECT
    '' AS user_sub,
    JSONExtractString(raw, 'after', 'email') AS user_email,
    t.report_bucket AS report_bucket,
    t.telemetry_samples AS telemetry_samples,
    t.telemetry_avg_amplitude AS telemetry_avg_amplitude,
    JSONExtractString(raw, 'after', 'customer_code') AS crm_customer_code,
    toUInt32(JSONExtractInt(raw, 'after', 'orders_count')) AS crm_orders_count,
    concat('cdc-', toString(generateUUIDv4())) AS etl_batch_id,
    now() AS loaded_at
FROM reports.crm_kafka_queue AS k
INNER JOIN reports.telemetry_by_user AS t
    ON lowerUTF8(JSONExtractString(k.raw, 'after', 'email')) = lowerUTF8(t.user_email)
WHERE JSONExtractString(k.raw, 'op') IN ('c', 'r', 'u')
  AND JSONExtractString(k.raw, 'after', 'email') != '';

-- Начальные строки телеметрии (вчера), чтобы snapshot Debezium смог JOIN до первого DAG. Один раз при пустой таблице.
INSERT INTO reports.telemetry_by_user (user_email, report_bucket, telemetry_samples, telemetry_avg_amplitude)
SELECT *
FROM
(
    SELECT 'user1@example.com' AS user_email, today() - 1 AS report_bucket, toUInt64(1000 + sipHash64('user1@example.com') % 5000) AS telemetry_samples, toFloat32(0.35 + (sipHash64('user1@example.com') % 100) / 200.0) AS telemetry_avg_amplitude
    UNION ALL
    SELECT 'user2@example.com', today() - 1, toUInt64(1000 + sipHash64('user2@example.com') % 5000), toFloat32(0.35 + (sipHash64('user2@example.com') % 100) / 200.0)
    UNION ALL
    SELECT 'admin1@example.com', today() - 1, toUInt64(1000 + sipHash64('admin1@example.com') % 5000), toFloat32(0.35 + (sipHash64('admin1@example.com') % 100) / 200.0)
    UNION ALL
    SELECT 'prothetic1@example.com', today() - 1, toUInt64(1000 + sipHash64('prothetic1@example.com') % 5000), toFloat32(0.35 + (sipHash64('prothetic1@example.com') % 100) / 200.0)
    UNION ALL
    SELECT 'prothetic2@example.com', today() - 1, toUInt64(1000 + sipHash64('prothetic2@example.com') % 5000), toFloat32(0.35 + (sipHash64('prothetic2@example.com') % 100) / 200.0)
    UNION ALL
    SELECT 'prothetic3@example.com', today() - 1, toUInt64(1000 + sipHash64('prothetic3@example.com') % 5000), toFloat32(0.35 + (sipHash64('prothetic3@example.com') % 100) / 200.0)
) AS seed
WHERE (SELECT count() FROM reports.telemetry_by_user) = 0;

INSERT INTO reports.etl_watermark (pipeline, data_through_date, last_success_at)
SELECT 'prosthetics_mart', today() - 1, now()
WHERE (SELECT count() FROM reports.etl_watermark WHERE pipeline = 'prosthetics_mart') = 0;
