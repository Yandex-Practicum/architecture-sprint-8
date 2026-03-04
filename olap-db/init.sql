CREATE TABLE crm_customers_kafka (
    id UInt32,
    name String,
    email String,
    age UInt8,
    gender String,
    country String,
    address String,
    phone String
) ENGINE = Kafka
SETTINGS
    kafka_broker_list = 'kafka:29092',
    kafka_topic_list = 'crm-server.public.customers',
    kafka_group_name = 'clickhouse_consumer_group',
    kafka_format = 'JSONEachRow';

CREATE TABLE crm_customers (
    id UInt32,
    name String,
    email String,
    age UInt8,
    gender String,
    country String,
    address String,
    phone String,
    _timestamp DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY id;

CREATE MATERIALIZED VIEW crm_customers_mv TO crm_customers AS
SELECT
    id,
    name,
    email,
    age,
    gender,
    country,
    address,
    phone
FROM crm_customers_kafka;

CREATE TABLE IF NOT EXISTS user_reports (
    user_id UInt32,
    report_date Date,
    prosthesis_type String,
    avg_signal_frequency Float32,
    avg_signal_duration Float32,
    avg_signal_amplitude Float32,
    total_signals UInt32,
    last_signal_time DateTime
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(report_date)
ORDER BY (user_id, report_date);