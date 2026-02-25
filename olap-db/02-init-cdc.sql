-- Drop old customers table if exists (legacy from ETL)
DROP TABLE IF EXISTS customers;
DROP TABLE IF EXISTS customer_telemetry_datamart;

-- Create customers table
CREATE TABLE IF NOT EXISTS customers
(
    id UInt32,
    name String,
    email String,
    age UInt16,
    gender String,
    country String,
    address String,
    phone String,
    _updated DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(_updated)
ORDER BY id;

-- Create Kafka engine table to consume CDC events
CREATE TABLE IF NOT EXISTS customers_kafka
(
    id UInt32,
    name String,
    email String,
    age UInt16,
    gender String,
    country String,
    address String,
    phone String,
    op String
) ENGINE = Kafka()
SETTINGS
    kafka_broker_list = 'kafka:9092',
    kafka_topic_list = 'crm_db_server.public.customers',
    kafka_group_name = 'clickhouse_customers_group',
    kafka_format = 'JSONEachRow',
    kafka_skip_broken_messages = 100;

-- Create materialized view to move data from Kafka to customers table
CREATE MATERIALIZED VIEW IF NOT EXISTS customers_mv TO customers AS
SELECT
    id,
    name,
    email,
    age,
    gender,
    country,
    address,
    phone,
    now() AS _updated
FROM customers_kafka
WHERE op IN ('c', 'u', 'r'); -- include create, update, read (snapshot) events

-- Create materialized view for reporting datamart
-- This view will automatically update when new data arrives in customers or emg_sensor_data
-- It uses ReplacingMergeTree to handle updates
CREATE TABLE IF NOT EXISTS customer_telemetry_datamart
(
    customer_id UInt32,
    customer_name String,
    email String,
    age UInt16,
    gender String,
    country String,
    prosthesis_type String,
    muscle_group String,
    total_signals UInt64,
    avg_signal_frequency Float64,
    avg_signal_duration Float64,
    avg_signal_amplitude Float64,
    min_signal_amplitude Float64,
    max_signal_amplitude Float64,
    total_signal_duration UInt64,
    first_signal_time DateTime,
    last_signal_time DateTime,
    updated_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (customer_id, prosthesis_type, muscle_group);

-- Materialized view that populates the datamart by joining customers and emg_sensor_data
-- This view is triggered by inserts into customers table (via customers_mv)
CREATE MATERIALIZED VIEW IF NOT EXISTS customer_telemetry_datamart_mv TO customer_telemetry_datamart AS
SELECT
    c.id AS customer_id,
    c.name AS customer_name,
    c.email AS email,
    c.age AS age,
    c.gender AS gender,
    c.country AS country,
    t.prosthesis_type,
    t.muscle_group,
    count(*) AS total_signals,
    round(avg(t.signal_frequency), 2) AS avg_signal_frequency,
    round(avg(t.signal_duration), 2) AS avg_signal_duration,
    round(avg(t.signal_amplitude), 2) AS avg_signal_amplitude,
    min(t.signal_amplitude) AS min_signal_amplitude,
    max(t.signal_amplitude) AS max_signal_amplitude,
    sum(t.signal_duration) AS total_signal_duration,
    min(t.signal_time) AS first_signal_time,
    max(t.signal_time) AS last_signal_time,
    now() AS updated_at
FROM customers AS c
INNER JOIN emg_sensor_data AS t ON t.user_id = c.id
GROUP BY
    c.id,
    c.name,
    c.email,
    c.age,
    c.gender,
    c.country,
    t.prosthesis_type,
    t.muscle_group;