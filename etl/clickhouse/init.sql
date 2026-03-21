CREATE DATABASE IF NOT EXISTS reports;

CREATE TABLE IF NOT EXISTS reports.user_usage_raw
(
    user_id       String,
    external_id   String,
    full_name     String,
    prosthesis_id String,
    serial_number String,
    event_date    Date,
    event_time    DateTime,
    load_value    Float64,
    duration_sec  UInt32
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_date)
ORDER BY (user_id, event_date, prosthesis_id, event_time);

CREATE TABLE IF NOT EXISTS reports.user_usage_daily
(
    user_id            String,
    external_id        String,
    full_name          String,
    prosthesis_id      String,
    serial_number      String,
    event_date         Date,
    total_duration_sec UInt64,
    avg_load           Float64,
    max_load           Float64,
    events_count       UInt32
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_date)
ORDER BY (user_id, event_date, prosthesis_id);

CREATE TABLE IF NOT EXISTS crm_users_ch
(
    id          String,
    external_id String,
    full_name   String
)
ENGINE = MergeTree
ORDER BY id;

CREATE TABLE IF NOT EXISTS crm_prostheses_ch
(
    id            String,
    user_id       String,
    serial_number String
)
ENGINE = MergeTree
ORDER BY id;

CREATE TABLE IF NOT EXISTS telemetry_events_ch
(
    id            String,
    event_time    DateTime,
    serial_number String,
    load_value    Float64,
    duration_sec  UInt32
)
ENGINE = MergeTree
ORDER BY (serial_number, event_time);

CREATE TABLE IF NOT EXISTS kafka_crm_users (
    id          String,
    external_id String,
    full_name   String
)
ENGINE = Kafka
SETTINGS
    kafka_broker_list = 'kafka:9092',
    kafka_topic_list = 'crm.public.crm_users',
    kafka_group_name = 'ch_crm_users',
    kafka_format = 'JSONEachRow',
    kafka_num_consumers = 1;

CREATE TABLE IF NOT EXISTS kafka_crm_prostheses (
    id            String,
    user_id       String,
    serial_number String
)
ENGINE = Kafka
SETTINGS
    kafka_broker_list = 'kafka:9092',
    kafka_topic_list = 'crm.public.crm_prostheses',
    kafka_group_name = 'ch_crm_prostheses',
    kafka_format = 'JSONEachRow',
    kafka_num_consumers = 1;

CREATE TABLE IF NOT EXISTS kafka_telemetry_events (
    id            String,
    event_time    DateTime,
    serial_number String,
    load_value    Float64,
    duration_sec  UInt32
)
ENGINE = Kafka
SETTINGS
    kafka_broker_list = 'kafka:9092',
    kafka_topic_list = 'telemetry.public.telemetry_events',
    kafka_group_name = 'ch_telemetry_events',
    kafka_format = 'JSONEachRow',
    kafka_num_consumers = 1;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_crm_users
TO crm_users_ch
AS
SELECT
    id,
    external_id,
    full_name
FROM kafka_crm_users;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_crm_prostheses
TO crm_prostheses_ch
AS
SELECT
    id,
    user_id,
    serial_number
FROM kafka_crm_prostheses;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_telemetry_events
TO telemetry_events_ch
AS
SELECT
    id,
    event_time,
    serial_number,
    load_value,
    duration_sec
FROM kafka_telemetry_events;

CREATE TABLE IF NOT EXISTS user_usage_daily_cdc
(
    user_id            String,
    external_id        String,
    full_name          String,
    prosthesis_id      String,
    serial_number      String,
    event_date         Date,
    total_duration_sec UInt64,
    avg_load           Float64,
    max_load           Float64,
    events_count       UInt32
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_date)
ORDER BY (user_id, event_date, prosthesis_id);

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_user_usage_daily_cdc
TO user_usage_daily_cdc
AS
SELECT
    cu.id                AS user_id,
    cu.external_id       AS external_id,
    cu.full_name         AS full_name,
    cp.id                AS prosthesis_id,
    cp.serial_number     AS serial_number,
    toDate(t.event_time) AS event_date,
    sum(t.duration_sec)  AS total_duration_sec,
    avg(t.load_value)    AS avg_load,
    max(t.load_value)    AS max_load,
    count(*)             AS events_count
FROM telemetry_events_ch t
JOIN crm_prostheses_ch cp
    ON t.serial_number = cp.serial_number
JOIN crm_users_ch cu
    ON cp.user_id = cu.id
GROUP BY
    user_id,
    external_id,
    full_name,
    prosthesis_id,
    serial_number,
    event_date;
