-- Базовые таблицы (нужны до создания MaterializedView)

CREATE DATABASE IF NOT EXISTS bionicpro;

CREATE TABLE IF NOT EXISTS bionicpro.crm_customers (
    customer_id String,
    full_name   String,
    email       String,
    phone       String,
    created_at  DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree()
ORDER BY customer_id;

CREATE TABLE IF NOT EXISTS bionicpro.telemetry_events (
    event_id        String,
    customer_id     String,
    event_ts        DateTime,
    signal_strength Float64,
    movement_type   String,
    battery_level   Float64
) ENGINE = MergeTree()
ORDER BY (customer_id, event_ts);

CREATE TABLE IF NOT EXISTS bionicpro.user_daily_telemetry (
    customer_id        String,
    report_date        Date,
    total_events       UInt64,
    avg_signal_strength Float64,
    active_hours       Float64,
    movement_count     UInt64,
    updated_at         DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (customer_id, report_date);

-- Таблица-источник: читает CDC-события из Kafka-топика crm.public.customers
-- Debezium публикует JSON-сообщения об изменениях в таблице customers

CREATE TABLE IF NOT EXISTS bionicpro.crm_customers_kafka (
    `after.customer_id`  String,
    `after.full_name`    String,
    `after.email`        String,
    `after.phone`        String,
    `after.created_at`   Nullable(Int64)
) ENGINE = Kafka
SETTINGS
    kafka_broker_list = 'kafka:29092',
    kafka_topic_list = 'crm.public.customers',
    kafka_group_name = 'clickhouse-crm-consumer',
    kafka_format = 'JSONEachRow',
    kafka_num_consumers = 1,
    kafka_skip_broken_messages = 10,
    input_format_import_nested_json = 1;

-- Целевая таблица для хранения CRM-данных, полученных через CDC
CREATE TABLE IF NOT EXISTS bionicpro.crm_customers_cdc (
    customer_id  String,
    full_name    String,
    email        String,
    phone        String,
    created_at   DateTime DEFAULT now(),
    _version     UInt64 DEFAULT toUInt64(now())
) ENGINE = ReplacingMergeTree(_version)
ORDER BY customer_id;
