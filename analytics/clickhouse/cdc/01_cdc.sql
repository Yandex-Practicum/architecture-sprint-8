CREATE TABLE IF NOT EXISTS reports.cdc_clients
(
    client_id         UInt64,
    username          String,
    full_name         String,
    prosthesis_serial String,
    region            String,
    is_deleted        UInt8,
    ts_ms             UInt64
)
ENGINE = ReplacingMergeTree(ts_ms)
ORDER BY client_id;

CREATE TABLE IF NOT EXISTS reports.cdc_telemetry
(
    id               UInt64,
    client_id        UInt64,
    report_date      Date,
    response_time_ms Int64,
    signal_quality   Float64,
    movements        Int64,
    battery_pct      Float64,
    is_deleted       UInt8,
    ts_ms            UInt64
)
ENGINE = ReplacingMergeTree(ts_ms)
ORDER BY id;

-- 2) Reporting mart (pre-aggregated telemetry per client per day).
CREATE TABLE IF NOT EXISTS reports.telemetry_daily
(
    client_id     UInt64,
    report_date   Date,
    events        SimpleAggregateFunction(sum, UInt64),
    sum_response  SimpleAggregateFunction(sum, Int64),
    max_response  SimpleAggregateFunction(max, Int64),
    sum_signal    SimpleAggregateFunction(sum, Float64),
    sum_movements SimpleAggregateFunction(sum, Int64),
    sum_battery   SimpleAggregateFunction(sum, Float64)
)
ENGINE = AggregatingMergeTree
ORDER BY (client_id, report_date);

-- MaterializedView that builds the витрина from the telemetry CDC stream.
CREATE MATERIALIZED VIEW IF NOT EXISTS reports.mv_report_mart TO reports.telemetry_daily AS
SELECT
    client_id,
    report_date,
    count()                  AS events,
    sum(response_time_ms)    AS sum_response,
    max(response_time_ms)    AS max_response,
    sum(signal_quality)      AS sum_signal,
    sum(movements)           AS sum_movements,
    sum(battery_pct)         AS sum_battery
FROM reports.cdc_telemetry
WHERE is_deleted = 0
GROUP BY client_id, report_date;

-- 3) Reporting view consumed by reports-api (same columns as the Airflow mart).
CREATE VIEW IF NOT EXISTS reports.user_report_mart_cdc AS
SELECT
    d.report_date                     AS report_date,
    d.client_id                       AS client_id,
    c.username                        AS username,
    c.full_name                       AS full_name,
    c.prosthesis_serial               AS prosthesis_serial,
    c.region                          AS region,
    d.events                          AS telemetry_events,
    d.sum_response / d.events         AS avg_response_ms,
    d.max_response                    AS max_response_ms,
    d.sum_signal / d.events           AS avg_signal_quality,
    d.sum_movements                   AS total_movements,
    d.sum_battery / d.events          AS avg_battery_pct
FROM
(
    SELECT
        client_id,
        report_date,
        sum(events)        AS events,
        sum(sum_response)  AS sum_response,
        max(max_response)  AS max_response,
        sum(sum_signal)    AS sum_signal,
        sum(sum_movements) AS sum_movements,
        sum(sum_battery)   AS sum_battery
    FROM reports.telemetry_daily
    GROUP BY client_id, report_date
) AS d
INNER JOIN
(
    SELECT
        client_id,
        argMax(username, ts_ms)          AS username,
        argMax(full_name, ts_ms)         AS full_name,
        argMax(prosthesis_serial, ts_ms) AS prosthesis_serial,
        argMax(region, ts_ms)            AS region,
        argMax(is_deleted, ts_ms)        AS is_deleted
    FROM reports.cdc_clients
    GROUP BY client_id
) AS c ON c.client_id = d.client_id
WHERE c.is_deleted = 0;

-- 4) Kafka engine consumer tables (Debezium topics, unwrapped JSON rows).
CREATE TABLE IF NOT EXISTS reports.kafka_clients
(
    client_id         UInt64,
    username          String,
    full_name         String,
    prosthesis_serial String,
    region            String,
    __deleted         String,
    __op              LowCardinality(String),
    __ts_ms           UInt64
)
ENGINE = Kafka
SETTINGS kafka_broker_list = 'kafka:9092',
         kafka_topic_list   = 'crm.public.clients',
         kafka_group_name   = 'ch_clients',
         kafka_format       = 'JSONEachRow',
         kafka_num_consumers = 1,
         input_format_skip_unknown_fields = 1;

CREATE TABLE IF NOT EXISTS reports.kafka_telemetry
(
    id               UInt64,
    client_id        UInt64,
    ts               Int64,
    response_time_ms Int64,
    signal_quality   Float64,
    movements        Int64,
    battery_pct      Float64,
    __deleted        String,
    __op             LowCardinality(String),
    __ts_ms          UInt64
)
ENGINE = Kafka
SETTINGS kafka_broker_list = 'kafka:9092',
         kafka_topic_list   = 'crm.public.telemetry',
         kafka_group_name   = 'ch_telemetry',
         kafka_format       = 'JSONEachRow',
         kafka_num_consumers = 1,
         input_format_skip_unknown_fields = 1;

-- 5) MaterializedViews that move Kafka rows into the CDC state tables. Creating
-- these last starts the consumers once the whole downstream pipeline is ready.
CREATE MATERIALIZED VIEW IF NOT EXISTS reports.mv_cdc_clients TO reports.cdc_clients AS
SELECT
    client_id,
    username,
    full_name,
    prosthesis_serial,
    region,
    (__deleted = 'true') AS is_deleted,
    __ts_ms              AS ts_ms
FROM reports.kafka_clients;

CREATE MATERIALIZED VIEW IF NOT EXISTS reports.mv_cdc_telemetry TO reports.cdc_telemetry AS
SELECT
    id,
    client_id,
    toDate(toDateTime(intDiv(ts, 1000))) AS report_date,
    response_time_ms,
    signal_quality,
    movements,
    battery_pct,
    (__deleted = 'true')                 AS is_deleted,
    __ts_ms                              AS ts_ms
FROM reports.kafka_telemetry;
