-- ============================================================
-- BionicPRO ClickHouse schema — CDC ingestion via KafkaEngine
-- ============================================================
-- Debezium type mapping (with time.precision.mode=connect, decimal.handling.mode=double):
--   PostgreSQL DATE       → int32 (days since epoch)  → toDate(fromUnixTimestamp(val * 86400))
--   PostgreSQL TIMESTAMP  → int64 (ms since epoch)    → toDateTime(intDiv(val, 1000))
--   PostgreSQL DECIMAL    → Float64
--   PostgreSQL VARCHAR    → String / Nullable(String)
--   __op field            → 'c'=insert, 'u'=update, 'd'=delete, 'r'=snapshot read
-- ============================================================

CREATE DATABASE IF NOT EXISTS bionicpro;

-- ── KafkaEngine: patients ──────────────────────────────────────────────────
-- Reads from Debezium CDC topic. Messages are flat JSON (ExtractNewRecordState SMT).
CREATE TABLE IF NOT EXISTS bionicpro.kafka_patients
(
    id                Int32,
    username          String,
    email             Nullable(String),
    full_name         Nullable(String),
    device_serial     Nullable(String),
    device_model      Nullable(String),
    registration_date Int32,           -- days since epoch (Debezium Date with connect mode)
    __op              String,          -- c/u/d/r
    __ts_ms           Int64            -- event timestamp ms since epoch
) ENGINE = Kafka()
SETTINGS
    kafka_broker_list        = 'kafka:9092',
    kafka_topic_list         = 'bionicpro.public.patients',
    kafka_group_name         = 'clickhouse_patients',
    kafka_format             = 'JSONEachRow',
    kafka_skip_broken_messages = 10;

-- ── Storage: patients_local ────────────────────────────────────────────────
-- ReplacingMergeTree deduplicates by username on background merge.
CREATE TABLE IF NOT EXISTS bionicpro.patients_local
(
    id                Int32,
    username          String,
    email             Nullable(String),
    full_name         Nullable(String),
    device_serial     Nullable(String),
    device_model      Nullable(String),
    registration_date Date,
    _ingested_at      DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(_ingested_at)
ORDER BY username;

-- ── MV: kafka_patients → patients_local ────────────────────────────────────
CREATE MATERIALIZED VIEW IF NOT EXISTS bionicpro.patients_mv
TO bionicpro.patients_local AS
SELECT
    id,
    username,
    email,
    full_name,
    device_serial,
    device_model,
    -- Convert days-since-epoch to Date
    toDate(fromUnixTimestamp(toInt64(registration_date) * 86400)) AS registration_date,
    now()                                                          AS _ingested_at
FROM bionicpro.kafka_patients
WHERE __op IN ('c', 'u', 'r');   -- skip deletes (patients are never hard-deleted)

-- ── KafkaEngine: telemetry ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS bionicpro.kafka_telemetry
(
    id               Int32,
    patient_username String,
    recorded_at      Int64,            -- ms since epoch (Debezium Timestamp with connect mode)
    battery_level    Nullable(Float64),
    active_hours     Nullable(Float64),
    steps_count      Nullable(Int32),
    event_type       Nullable(String),
    __op             String,
    __ts_ms          Int64
) ENGINE = Kafka()
SETTINGS
    kafka_broker_list        = 'kafka:9092',
    kafka_topic_list         = 'bionicpro.public.telemetry',
    kafka_group_name         = 'clickhouse_telemetry',
    kafka_format             = 'JSONEachRow',
    kafka_skip_broken_messages = 10;

-- ── Storage: telemetry_local ───────────────────────────────────────────────
-- Append-only MergeTree. Partitioned by month for efficient time-range scans.
CREATE TABLE IF NOT EXISTS bionicpro.telemetry_local
(
    id               Int32,
    patient_username String,
    recorded_at      DateTime,
    battery_level    Nullable(Float64),
    active_hours     Nullable(Float64),
    steps_count      Nullable(Int32),
    event_type       Nullable(String),
    _ingested_at     DateTime DEFAULT now()
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(recorded_at)
ORDER BY (patient_username, recorded_at);

-- ── MV: kafka_telemetry → telemetry_local ──────────────────────────────────
CREATE MATERIALIZED VIEW IF NOT EXISTS bionicpro.telemetry_mv
TO bionicpro.telemetry_local AS
SELECT
    id,
    patient_username,
    toDateTime(intDiv(recorded_at, 1000)) AS recorded_at,  -- ms → seconds
    battery_level,
    active_hours,
    steps_count,
    event_type,
    now() AS _ingested_at
FROM bionicpro.kafka_telemetry
WHERE __op IN ('c', 'r');   -- telemetry is append-only

-- ── Dictionary: patients_dict ──────────────────────────────────────────────
-- Used by report_mart_mv to enrich telemetry rows with patient profile.
-- Refreshes from patients_local every 60-300 seconds.
CREATE DICTIONARY IF NOT EXISTS bionicpro.patients_dict
(
    username      String,
    full_name     String,
    device_serial String,
    device_model  String
)
PRIMARY KEY username
SOURCE(CLICKHOUSE(TABLE 'patients_local' DB 'bionicpro'))
LIFETIME(MIN 60 MAX 300)
LAYOUT(HASHED());

-- ── Reporting mart ─────────────────────────────────────────────────────────
-- SummingMergeTree accumulates partial sums from each Kafka poll batch.
-- Reading with GROUP BY + sum() gives correct totals even before background merge.
-- avg_battery_level = total_battery_sum / event_count (computed at query time).
CREATE TABLE IF NOT EXISTS bionicpro.user_report_mart
(
    username           String,
    report_date        Date,
    full_name          String,
    device_serial      String,
    device_model       String,
    total_active_hours Float64,
    total_battery_sum  Float64,   -- sum of battery_level values (for computing avg)
    total_steps        Int64,
    event_count        Int64,
    etl_updated_at     DateTime DEFAULT now()
) ENGINE = SummingMergeTree((total_active_hours, total_battery_sum, total_steps, event_count))
ORDER BY (username, report_date);

-- ── MV: kafka_telemetry → user_report_mart ─────────────────────────────────
-- Triggered on each Kafka poll. Inserts partial aggregates per (username, date).
-- dictGet fetches patient profile from the patients_dict (HASHED, in-memory).
-- Note: kafka_telemetry can have TWO consumers (this MV + telemetry_mv)
--       because ClickHouse triggers all attached MVs from the same poll batch.
CREATE MATERIALIZED VIEW IF NOT EXISTS bionicpro.report_mart_mv
TO bionicpro.user_report_mart AS
SELECT
    patient_username                                                  AS username,
    toDate(toDateTime(intDiv(recorded_at, 1000)))                     AS report_date,
    dictGetString('bionicpro.patients_dict', 'full_name',     patient_username) AS full_name,
    dictGetString('bionicpro.patients_dict', 'device_serial', patient_username) AS device_serial,
    dictGetString('bionicpro.patients_dict', 'device_model',  patient_username) AS device_model,
    sum(ifNull(active_hours, 0))              AS total_active_hours,
    sum(ifNull(battery_level, 0))             AS total_battery_sum,
    sum(toInt64(ifNull(steps_count, 0)))      AS total_steps,
    count()                                   AS event_count,
    now()                                     AS etl_updated_at
FROM bionicpro.kafka_telemetry
WHERE __op IN ('c', 'r')
GROUP BY patient_username, toDate(toDateTime(intDiv(recorded_at, 1000)));
