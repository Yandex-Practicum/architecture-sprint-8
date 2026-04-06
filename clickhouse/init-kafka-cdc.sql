-- CDC из CRM через Kafka (Debezium) → измерения и витрина отчётов
-- Сообщения: JSON без обёртки schema (JsonConverter schemas.enable=false)

USE analytics_db;

-- --- Клиенты CRM → client_dimension ---
CREATE TABLE IF NOT EXISTS crm_clients_kafka_queue (
    raw String
) ENGINE = Kafka()
SETTINGS
    kafka_broker_list = 'kafka:9092',
    kafka_topic_list = 'crm.public.crm_clients',
    kafka_group_name = 'clickhouse_crm_clients',
    kafka_format = 'JSONAsString',
    kafka_num_consumers = 1,
    kafka_flush_interval_ms = 5000;

CREATE MATERIALIZED VIEW IF NOT EXISTS crm_clients_kafka_mv TO client_dimension AS
SELECT
    JSONExtract(raw, 'after', 'buyer_id', 'UInt64') AS buyer_id,
    JSONExtract(raw, 'after', 'full_name', 'String') AS full_name,
    JSONExtract(raw, 'after', 'email', 'String') AS email,
    if(
        JSONExtractString(raw, 'after', 'phone') = '',
        '',
        JSONExtractString(raw, 'after', 'phone')
    ) AS phone,
    parseDateTimeBestEffortOrZero(JSONExtractString(raw, 'after', 'registration_date')) AS registration_date,
    if(
        length(trimBoth(JSONExtractString(raw, 'after', 'last_visit_date'))) = 0,
        toDateTime('1970-01-01 00:00:00'),
        parseDateTimeBestEffortOrZero(JSONExtractString(raw, 'after', 'last_visit_date'))
    ) AS last_visit_date,
    JSONExtract(raw, 'after', 'status', 'String') AS status,
    now() AS updated_at
FROM crm_clients_kafka_queue
WHERE JSONExtractString(raw, 'op') IN ('c', 'u', 'r')
  AND JSONHas(raw, 'after');

-- --- Протезы CRM → prosthetic_dimension ---
CREATE TABLE IF NOT EXISTS crm_prosthetics_kafka_queue (
    raw String
) ENGINE = Kafka()
SETTINGS
    kafka_broker_list = 'kafka:9092',
    kafka_topic_list = 'crm.public.crm_prosthetics',
    kafka_group_name = 'clickhouse_crm_prosthetics',
    kafka_format = 'JSONAsString',
    kafka_num_consumers = 1,
    kafka_flush_interval_ms = 5000;

CREATE MATERIALIZED VIEW IF NOT EXISTS crm_prosthetics_kafka_mv TO prosthetic_dimension AS
SELECT
    JSONExtract(raw, 'after', 'prosthetic_id', 'UInt64') AS prosthetic_id,
    JSONExtract(raw, 'after', 'buyer_id', 'UInt64') AS buyer_id,
    JSONExtract(raw, 'after', 'prosthetic_type', 'String') AS prosthetic_type,
    toDate(parseDateTimeBestEffortOrZero(JSONExtractString(raw, 'after', 'manufacture_date'))) AS manufacture_date,
    if(
        length(trimBoth(JSONExtractString(raw, 'after', 'delivery_date'))) = 0,
        toDate('1970-01-01'),
        toDate(parseDateTimeBestEffortOrZero(JSONExtractString(raw, 'after', 'delivery_date')))
    ) AS delivery_date,
    JSONExtract(raw, 'after', 'serial_number', 'String') AS serial_number,
    toUInt16(JSONExtract(raw, 'after', 'warranty_months', 'UInt64')) AS warranty_months,
    toDecimal64(JSONExtract(raw, 'after', 'price', 'Float64'), 2) AS price,
    now() AS updated_at
FROM crm_prosthetics_kafka_queue
WHERE JSONExtractString(raw, 'op') IN ('c', 'u', 'r')
  AND JSONHas(raw, 'after');

-- --- Витрина: при вставке/обновлении измерения протеза пересчитываем строки mart за окно 30 дней ---
CREATE MATERIALIZED VIEW IF NOT EXISTS user_reports_mart_cdc_mv TO user_reports_mart AS
SELECT
    c.buyer_id AS buyer_id,
    anyLast(c.full_name) AS full_name,
    anyLast(c.email) AS email,
    p.prosthetic_type AS prosthetic_type,
    p.serial_number AS serial_number,
    toFloat32(sum(t.usage_hours)) AS total_usage_hours,
    toUInt64(sum(t.movement_count)) AS total_movements,
    toUInt32(sum(t.error_count)) AS total_errors,
    toFloat32(avg(t.battery_level)) AS avg_battery_level,
    max(t.event_timestamp) AS last_telemetry_date,
    min(t.sync_date) AS report_period_start,
    max(t.sync_date) AS report_period_end,
    now() AS created_at
FROM prosthetic_dimension AS p
INNER JOIN client_dimension AS c ON c.buyer_id = p.buyer_id
INNER JOIN telemetry_facts AS t ON t.buyer_id = p.buyer_id AND t.prosthetic_serial = p.serial_number
WHERE t.sync_date >= addDays(today(), -30)
GROUP BY
    c.buyer_id,
    p.prosthetic_type,
    p.serial_number;
