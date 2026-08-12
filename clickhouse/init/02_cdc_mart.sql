-- Путь приёма CDC: Debezium стримит изменения строк из crm.public.customers
-- в топик Kafka 'crm.public.customers'; ClickHouse потребляет его напрямую
-- через движок Kafka, поэтому Airflow больше вообще не выполняет массовое
-- чтение OLTP-базы CRM.
CREATE TABLE IF NOT EXISTS reports.customers_cdc_kafka
(
    customer_id       String,
    full_name         String,
    region            String,
    prosthesis_model  String
)
ENGINE = Kafka
SETTINGS
    kafka_broker_list = 'kafka:9092',
    kafka_topic_list = 'crm.public.customers',
    kafka_group_name = 'clickhouse_reports_consumer',
    kafka_format = 'JSONEachRow',
    kafka_num_consumers = 1,
    kafka_skip_broken_messages = 5;

CREATE TABLE IF NOT EXISTS reports.customers_current
(
    customer_id       String,
    full_name         String,
    region            String,
    prosthesis_model  String,
    updated_at        DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY customer_id;

CREATE MATERIALIZED VIEW IF NOT EXISTS reports.customers_current_mv
TO reports.customers_current AS
SELECT customer_id, full_name, region, prosthesis_model, now() AS updated_at
FROM reports.customers_cdc_kafka;

-- Агрегаты телеметрии по-прежнему формируются пакетно через Airflow DAG
-- (airflow/dags/reports_etl_dag.py), который теперь обращается только к базе
-- телеметрии - никогда к базе CRM.
CREATE TABLE IF NOT EXISTS reports.telemetry_agg
(
    customer_id                 String,
    agg_generated_at            DateTime,
    events_count                UInt32,
    avg_myosignal_quality       Float32,
    avg_recognition_latency_ms  Float32,
    min_battery_level           UInt8,
    last_action_recognized      String
)
ENGINE = MergeTree
ORDER BY (customer_id, agg_generated_at);

-- Итоговая витрина отчётов: объединяет измерение клиентов, поступающее через
-- CDC, с пакетными агрегатами телеметрии через MaterializedView, срабатывающую
-- на каждую вставку Airflow в telemetry_agg. reports-api читает только эту таблицу.
CREATE TABLE IF NOT EXISTS reports.user_report_mart_v2
(
    customer_id                 String,
    report_generated_at         DateTime,
    full_name                   String,
    region                      String,
    prosthesis_model            String,
    events_count                UInt32,
    avg_myosignal_quality       Float32,
    avg_recognition_latency_ms  Float32,
    min_battery_level           UInt8,
    last_action_recognized      String
)
ENGINE = ReplacingMergeTree(report_generated_at)
ORDER BY (customer_id);

CREATE MATERIALIZED VIEW IF NOT EXISTS reports.user_report_mart_v2_mv
TO reports.user_report_mart_v2 AS
SELECT
    t.customer_id AS customer_id,
    t.agg_generated_at AS report_generated_at,
    c.full_name AS full_name,
    c.region AS region,
    c.prosthesis_model AS prosthesis_model,
    t.events_count AS events_count,
    t.avg_myosignal_quality AS avg_myosignal_quality,
    t.avg_recognition_latency_ms AS avg_recognition_latency_ms,
    t.min_battery_level AS min_battery_level,
    t.last_action_recognized AS last_action_recognized
FROM reports.telemetry_agg AS t
LEFT JOIN reports.customers_current AS c FINAL ON c.customer_id = t.customer_id;
