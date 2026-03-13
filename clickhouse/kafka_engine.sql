-- Kafka Engine tables to consume CDC events from Debezium via Kafka
-- These tables act as consumers: ClickHouse reads from Kafka topics automatically.

CREATE TABLE IF NOT EXISTS bionicpro.kafka_customers (
    payload String
) ENGINE = Kafka
SETTINGS
    kafka_broker_list = 'kafka:29092',
    kafka_topic_list = 'crm.public.customers',
    kafka_group_name = 'clickhouse_customers',
    kafka_format = 'JSONAsString',
    kafka_num_consumers = 1;

CREATE TABLE IF NOT EXISTS bionicpro.kafka_orders (
    payload String
) ENGINE = Kafka
SETTINGS
    kafka_broker_list = 'kafka:29092',
    kafka_topic_list = 'crm.public.orders',
    kafka_group_name = 'clickhouse_orders',
    kafka_format = 'JSONAsString',
    kafka_num_consumers = 1;

CREATE TABLE IF NOT EXISTS bionicpro.kafka_telemetry (
    payload String
) ENGINE = Kafka
SETTINGS
    kafka_broker_list = 'kafka:29092',
    kafka_topic_list = 'crm.public.telemetry',
    kafka_group_name = 'clickhouse_telemetry',
    kafka_format = 'JSONAsString',
    kafka_num_consumers = 1;
