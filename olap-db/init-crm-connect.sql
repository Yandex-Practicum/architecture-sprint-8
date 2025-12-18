-- 
CREATE TABLE IF NOT EXISTS customers_kafka (
    id UInt32,
    name String,
    email String,
    age Decimal(5,2),
    gender String,
    country String,
    address String,
    phone String,
    op String
) ENGINE = Kafka
SETTINGS
    kafka_broker_list = 'kafka:9092',
    kafka_topic_list = 'dbz.public.customers',  -- зависит от имени топика Debezium
    kafka_group_name = 'clickhouse_customers_group',
    kafka_format = 'JSONEachRow',
    kafka_row_delimiter = '\n';



-- Дублирующая таблица customers из PG 
CREATE TABLE IF NOT EXISTS dim_customers (
    id UInt32,
    name String,
    email String,
    age Decimal(5,2),
    gender String,
    country String,
    address String,
    phone String,
    is_deleted UInt8 DEFAULT 0,
    updated_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(updated_at)
ORDER BY id;

-- Сохраняем поток из kafka в db 
CREATE MATERIALIZED VIEW customers_consumer TO dim_customers
AS SELECT 
    id,
    name,
    email,
    age,
    gender,
    country,
    address,
    phone,
    if(op = 'd', 1, 0) as is_deleted,
    now() as updated_at
FROM customers_kafka;