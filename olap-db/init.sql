CREATE TABLE IF NOT EXISTS emg_sensor_data (
    user_id UInt32,
    prosthesis_type String,
    muscle_group String,
    signal_frequency UInt32,
    signal_duration UInt32,
    signal_amplitude Decimal(5,2),
    signal_time DateTime
) ENGINE = MergeTree()
ORDER BY (user_id, prosthesis_type, signal_time);

INSERT INTO emg_sensor_data
SELECT *
FROM file('olap.csv', 'CSV');

-- CDC: consume CRM customers changes from Kafka (Debezium)
CREATE TABLE IF NOT EXISTS crm_customers_kafka (
    id UInt32,
    name String,
    email String,
    age Int32,
    gender String,
    country String,
    address String,
    phone String
) ENGINE = Kafka()
SETTINGS kafka_broker_list = 'kafka:9092',
         kafka_topic_list = 'crm_server.public.customers',
         kafka_group_name = 'clickhouse_consumer',
         kafka_format = 'JSONEachRow',
         kafka_num_consumers = 1;

CREATE TABLE IF NOT EXISTS crm_customers_vitrina (
    id UInt32,
    name String,
    email String,
    age Int32,
    gender String,
    country String,
    address String,
    phone String
) ENGINE = MergeTree()
ORDER BY id;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_crm_customers_to_vitrina TO crm_customers_vitrina AS
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