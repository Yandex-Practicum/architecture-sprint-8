-- Materialized Views: consume from Kafka engine tables and write to staging tables
-- These parse Debezium CDC JSON events and extract the "after" payload.
-- Debezium format: {"before": ..., "after": {...}, "source": {...}, "op": "c|u|d", "ts_ms": 1234567890}

-- MV: kafka_customers -> customers
CREATE MATERIALIZED VIEW IF NOT EXISTS bionicpro.mv_customers TO bionicpro.customers AS
SELECT
    JSONExtractInt(JSONExtractRaw(payload, 'after'), 'id') AS id,
    JSONExtractString(JSONExtractRaw(payload, 'after'), 'keycloak_user_id') AS keycloak_user_id,
    JSONExtractString(JSONExtractRaw(payload, 'after'), 'email') AS email,
    JSONExtractString(JSONExtractRaw(payload, 'after'), 'first_name') AS first_name,
    JSONExtractString(JSONExtractRaw(payload, 'after'), 'last_name') AS last_name,
    toDateTime(intDiv(JSONExtractUInt(payload, 'ts_ms'), 1000)) AS created_at,
    JSONExtractString(payload, 'op') AS _op
FROM bionicpro.kafka_customers
WHERE JSONExtractRaw(payload, 'after') != 'null';

-- MV: kafka_orders -> orders
CREATE MATERIALIZED VIEW IF NOT EXISTS bionicpro.mv_orders TO bionicpro.orders AS
SELECT
    JSONExtractInt(JSONExtractRaw(payload, 'after'), 'id') AS id,
    JSONExtractInt(JSONExtractRaw(payload, 'after'), 'customer_id') AS customer_id,
    JSONExtractString(JSONExtractRaw(payload, 'after'), 'product_name') AS product_name,
    JSONExtractString(JSONExtractRaw(payload, 'after'), 'product_type') AS product_type,
    toDate(JSONExtractString(JSONExtractRaw(payload, 'after'), 'order_date')) AS order_date,
    JSONExtractString(JSONExtractRaw(payload, 'after'), 'status') AS status,
    toDateTime(intDiv(JSONExtractUInt(payload, 'ts_ms'), 1000)) AS created_at,
    JSONExtractString(payload, 'op') AS _op
FROM bionicpro.kafka_orders
WHERE JSONExtractRaw(payload, 'after') != 'null';

-- MV: kafka_telemetry -> telemetry
CREATE MATERIALIZED VIEW IF NOT EXISTS bionicpro.mv_telemetry TO bionicpro.telemetry AS
SELECT
    JSONExtractInt(JSONExtractRaw(payload, 'after'), 'id') AS id,
    JSONExtractString(JSONExtractRaw(payload, 'after'), 'device_id') AS device_id,
    JSONExtractInt(JSONExtractRaw(payload, 'after'), 'customer_id') AS customer_id,
    JSONExtractFloat(JSONExtractRaw(payload, 'after'), 'signal_strength') AS signal_strength,
    JSONExtractFloat(JSONExtractRaw(payload, 'after'), 'usage_hours') AS usage_hours,
    JSONExtractInt(JSONExtractRaw(payload, 'after'), 'active_movements') AS active_movements,
    JSONExtractInt(JSONExtractRaw(payload, 'after'), 'battery_cycles') AS battery_cycles,
    JSONExtractInt(JSONExtractRaw(payload, 'after'), 'error_count') AS error_count,
    toDateTime(intDiv(JSONExtractUInt(payload, 'ts_ms'), 1000)) AS recorded_at,
    JSONExtractString(payload, 'op') AS _op
FROM bionicpro.kafka_telemetry
WHERE JSONExtractRaw(payload, 'after') != 'null';

-- Refresh report_datamart from CDC-fed staging tables
-- This query should be run periodically (e.g., via Airflow or a ClickHouse scheduled task)
-- to update the denormalized data mart used by the reports API.
--
-- Example manual refresh:
-- INSERT INTO bionicpro.report_datamart
-- SELECT
--     c.keycloak_user_id AS user_id,
--     c.email AS user_email,
--     t.device_id,
--     o.product_name,
--     toDate(t.recorded_at) AS order_date,
--     o.status AS order_status,
--     sum(t.usage_hours) AS total_usage_hours,
--     sum(t.active_movements) AS total_active_movements,
--     sum(t.battery_cycles) AS total_battery_cycles,
--     avg(t.signal_strength) AS avg_signal_strength,
--     sum(t.error_count) AS total_error_count,
--     now() AS last_updated
-- FROM bionicpro.customers AS c
-- INNER JOIN bionicpro.orders AS o ON o.customer_id = c.id
-- INNER JOIN bionicpro.telemetry AS t ON t.customer_id = c.id
-- GROUP BY c.keycloak_user_id, c.email, t.device_id, o.product_name,
--          toDate(t.recorded_at), o.status;
