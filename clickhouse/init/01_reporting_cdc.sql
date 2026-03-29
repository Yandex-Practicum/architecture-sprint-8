CREATE DATABASE IF NOT EXISTS reporting;

CREATE TABLE IF NOT EXISTS reporting.crm_customers_cdc
(
    customer_id Int32,
    username String,
    email String,
    full_name String,
    country String,
    city String,
    is_deleted UInt8,
    operation LowCardinality(String),
    source_ts_ms UInt64,
    event_time DateTime64(3)
)
ENGINE = ReplacingMergeTree(source_ts_ms)
ORDER BY customer_id;

CREATE TABLE IF NOT EXISTS reporting.crm_customers_queue
(
    raw_message String
)
ENGINE = Kafka
SETTINGS
    kafka_broker_list = 'kafka:9092',
    kafka_topic_list = 'crmdb.public.customers',
    kafka_group_name = 'clickhouse.crm.customers',
    kafka_format = 'JSONAsString',
    kafka_num_consumers = 1;

DROP TABLE IF EXISTS reporting.crm_customers_consumer;

CREATE MATERIALIZED VIEW reporting.crm_customers_consumer
TO reporting.crm_customers_cdc
AS
SELECT
    toInt32(JSONExtractInt(raw_message, 'customer_id')) AS customer_id,
    JSONExtractString(raw_message, 'username') AS username,
    JSONExtractString(raw_message, 'email') AS email,
    JSONExtractString(raw_message, 'full_name') AS full_name,
    JSONExtractString(raw_message, 'country') AS country,
    JSONExtractString(raw_message, 'city') AS city,
    toUInt8(lowerUTF8(JSONExtractString(raw_message, '__deleted')) = 'true') AS is_deleted,
    if(JSONHas(raw_message, '__op'), JSONExtractString(raw_message, '__op'), 'r') AS operation,
    if(
        JSONHas(raw_message, '__source_ts_ms'),
        toUInt64(JSONExtractInt(raw_message, '__source_ts_ms')),
        toUInt64(toUnixTimestamp64Milli(now64(3)))
    ) AS source_ts_ms,
    fromUnixTimestamp64Milli(
        toInt64(
            if(
                JSONHas(raw_message, '__source_ts_ms'),
                toUInt64(JSONExtractInt(raw_message, '__source_ts_ms')),
                toUInt64(toUnixTimestamp64Milli(now64(3)))
            )
        )
    ) AS event_time
FROM reporting.crm_customers_queue;

DROP VIEW IF EXISTS reporting.crm_customers_current;

CREATE VIEW reporting.crm_customers_current
AS
SELECT
    customer_id,
    argMax(username, source_ts_ms) AS username,
    argMax(email, source_ts_ms) AS email,
    argMax(full_name, source_ts_ms) AS full_name,
    argMax(country, source_ts_ms) AS country,
    argMax(city, source_ts_ms) AS city
FROM reporting.crm_customers_cdc
GROUP BY customer_id
HAVING argMax(is_deleted, source_ts_ms) = 0;

CREATE TABLE IF NOT EXISTS reporting.crm_prostheses_cdc
(
    prosthesis_id String,
    customer_id Int32,
    prosthesis_model String,
    support_tier String,
    fitted_at Date,
    last_service_date Date,
    is_deleted UInt8,
    operation LowCardinality(String),
    source_ts_ms UInt64,
    event_time DateTime64(3)
)
ENGINE = ReplacingMergeTree(source_ts_ms)
ORDER BY prosthesis_id;

CREATE TABLE IF NOT EXISTS reporting.crm_prostheses_queue
(
    raw_message String
)
ENGINE = Kafka
SETTINGS
    kafka_broker_list = 'kafka:9092',
    kafka_topic_list = 'crmdb.public.prostheses',
    kafka_group_name = 'clickhouse.crm.prostheses',
    kafka_format = 'JSONAsString',
    kafka_num_consumers = 1;

DROP TABLE IF EXISTS reporting.crm_prostheses_consumer;

CREATE MATERIALIZED VIEW reporting.crm_prostheses_consumer
TO reporting.crm_prostheses_cdc
AS
SELECT
    JSONExtractString(raw_message, 'prosthesis_id') AS prosthesis_id,
    toInt32(JSONExtractInt(raw_message, 'customer_id')) AS customer_id,
    JSONExtractString(raw_message, 'prosthesis_model') AS prosthesis_model,
    JSONExtractString(raw_message, 'support_tier') AS support_tier,
    addDays(toDate('1970-01-01'), toInt32(JSONExtractInt(raw_message, 'fitted_at'))) AS fitted_at,
    addDays(toDate('1970-01-01'), toInt32(JSONExtractInt(raw_message, 'last_service_date'))) AS last_service_date,
    toUInt8(lowerUTF8(JSONExtractString(raw_message, '__deleted')) = 'true') AS is_deleted,
    if(JSONHas(raw_message, '__op'), JSONExtractString(raw_message, '__op'), 'r') AS operation,
    if(
        JSONHas(raw_message, '__source_ts_ms'),
        toUInt64(JSONExtractInt(raw_message, '__source_ts_ms')),
        toUInt64(toUnixTimestamp64Milli(now64(3)))
    ) AS source_ts_ms,
    fromUnixTimestamp64Milli(
        toInt64(
            if(
                JSONHas(raw_message, '__source_ts_ms'),
                toUInt64(JSONExtractInt(raw_message, '__source_ts_ms')),
                toUInt64(toUnixTimestamp64Milli(now64(3)))
            )
        )
    ) AS event_time
FROM reporting.crm_prostheses_queue;

DROP VIEW IF EXISTS reporting.crm_prostheses_current;

CREATE VIEW reporting.crm_prostheses_current
AS
SELECT
    prosthesis_id,
    argMax(customer_id, source_ts_ms) AS customer_id,
    argMax(prosthesis_model, source_ts_ms) AS prosthesis_model,
    argMax(support_tier, source_ts_ms) AS support_tier,
    argMax(fitted_at, source_ts_ms) AS fitted_at,
    argMax(last_service_date, source_ts_ms) AS last_service_date
FROM reporting.crm_prostheses_cdc
GROUP BY prosthesis_id
HAVING argMax(is_deleted, source_ts_ms) = 0;

CREATE TABLE IF NOT EXISTS reporting.telemetry_daily_rollups
(
    prosthesis_id String,
    report_date Date,
    usage_minutes UInt32,
    motion_events UInt32,
    average_battery_pct Float32,
    average_signal_quality Float32,
    calibration_sessions UInt32,
    alerts_count UInt32,
    loaded_at DateTime
)
ENGINE = ReplacingMergeTree(loaded_at)
ORDER BY (prosthesis_id, report_date);

CREATE TABLE IF NOT EXISTS reporting.user_daily_reports_cdc
(
    username String,
    email String,
    full_name String,
    country String,
    city String,
    prosthesis_id String,
    prosthesis_model String,
    support_tier String,
    fitted_at Date,
    last_service_date Date,
    report_date Date,
    usage_minutes UInt32,
    motion_events UInt32,
    average_battery_pct Float32,
    average_signal_quality Float32,
    calibration_sessions UInt32,
    alerts_count UInt32,
    loaded_at DateTime
)
ENGINE = ReplacingMergeTree(loaded_at)
ORDER BY (username, report_date, prosthesis_id);

DROP TABLE IF EXISTS reporting.user_daily_reports_cdc_mv;

CREATE MATERIALIZED VIEW reporting.user_daily_reports_cdc_mv
TO reporting.user_daily_reports_cdc
AS
SELECT
    customer.username AS username,
    customer.email AS email,
    customer.full_name AS full_name,
    customer.country AS country,
    customer.city AS city,
    telemetry.prosthesis_id AS prosthesis_id,
    prosthesis.prosthesis_model AS prosthesis_model,
    prosthesis.support_tier AS support_tier,
    prosthesis.fitted_at AS fitted_at,
    prosthesis.last_service_date AS last_service_date,
    telemetry.report_date AS report_date,
    telemetry.usage_minutes AS usage_minutes,
    telemetry.motion_events AS motion_events,
    telemetry.average_battery_pct AS average_battery_pct,
    telemetry.average_signal_quality AS average_signal_quality,
    telemetry.calibration_sessions AS calibration_sessions,
    telemetry.alerts_count AS alerts_count,
    telemetry.loaded_at AS loaded_at
FROM reporting.telemetry_daily_rollups AS telemetry
INNER JOIN reporting.crm_prostheses_current AS prosthesis
    ON telemetry.prosthesis_id = prosthesis.prosthesis_id
INNER JOIN reporting.crm_customers_current AS customer
    ON prosthesis.customer_id = customer.customer_id;

CREATE TABLE IF NOT EXISTS reporting.reporting_load_windows
(
    dataset String,
    available_from Date,
    available_to Date,
    loaded_at DateTime,
    dag_run_id String
)
ENGINE = ReplacingMergeTree(loaded_at)
ORDER BY dataset;
