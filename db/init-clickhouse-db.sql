CREATE DATABASE IF NOT EXISTS bionicpro;

CREATE TABLE IF NOT EXISTS bionicpro.user_report_mart (
    user_id String,
    user_email String,
    user_name String,
    total_steps UInt64,
    total_active_minutes UInt64,
    battery_avg_usage Float64,
    error_count UInt64,
    report_date Date
)
ENGINE = MergeTree()
ORDER BY (user_id, report_date);

CREATE TABLE IF NOT EXISTS crm_kafka_queue (
    user_id String,
    user_name String,
    user_email String,
    phone String,
    region String,
    prosthesis_model String,
    purchase_date Date,
    updated_at DateTime
) ENGINE = Kafka()
SETTINGS
    kafka_broker_list = 'kafka:9092',
    kafka_topic_list = 'crm.public.clients',
    kafka_group_name = 'clickhouse_consumer',
    kafka_format = 'JSONEachRow';

CREATE TABLE IF NOT EXISTS crm_clients (
    user_id String,
    user_name String,
    user_email String,
    phone String,
    region String,
    prosthesis_model String,
    purchase_date Date,
    updated_at DateTime
) ENGINE = MergeTree()
ORDER BY (user_id, updated_at);

CREATE MATERIALIZED VIEW mv_crm_to_clients
TO crm_clients
AS SELECT
    user_id,
    user_name,
    user_email,
    phone,
    region,
    prosthesis_model,
    purchase_date,
    updated_at
FROM crm_kafka_queue;