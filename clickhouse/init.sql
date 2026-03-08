-- ClickHouse инициализация БД BionicPRO
-- Задание 4: KafkaEngine + MaterializedView для CDC

CREATE DATABASE IF NOT EXISTS bionicpro;

-- ── 1. Таблица-приёмник из Kafka (KafkaEngine) ───────────────────────────────
-- KafkaEngine читает из Kafka topic и передаёт данные в MaterializedView.
-- Сами данные в этой таблице НЕ хранятся (движок потоковый).
CREATE TABLE IF NOT EXISTS bionicpro.kafka_crm_events
(
    id                    Int64,
    prosthesis_id         Int64,
    recorded_at           Int64,   -- microseconds since epoch
    signal_value          Float64,
    movement_type         String,
    response_ms           Float64,
    __deleted             String
) ENGINE = Kafka
SETTINGS
    kafka_broker_list    = 'kafka:9092',
    kafka_topic_list     = 'bionicpro.public.telemetry',
    kafka_group_name     = 'clickhouse-consumer',
    kafka_format         = 'JSONEachRow',
    kafka_num_consumers  = 1,
    kafka_skip_broken_messages = 100;


-- ── 2. Целевая таблица (MergeTree) ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS bionicpro.raw_telemetry_cdc
(
    id                    Int64,
    prosthesis_id         Int64,
    recorded_at           DateTime,
    signal_value          Float64,
    movement_type         String,
    response_ms           Float64,
    _loaded_at            DateTime DEFAULT now()
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(recorded_at)
ORDER BY (prosthesis_id, recorded_at);


-- ── 3. MaterializedView: при появлении записи в Kafka → вставляет в таблицу ─
-- Это «триггер» ClickHouse: автоматически срабатывает при чтении из KafkaEngine.
CREATE MATERIALIZED VIEW IF NOT EXISTS bionicpro.mv_kafka_to_raw
TO bionicpro.raw_telemetry_cdc AS
SELECT
    id,
    prosthesis_id,
    toDateTime(intDiv(recorded_at, 1000000)) AS recorded_at,
    signal_value,
    movement_type,
    response_ms
FROM bionicpro.kafka_crm_events
WHERE __deleted != 'true';   -- не пишем удалённые записи


-- ── 4. Витрина отчётов (ReplacingMergeTree) ──────────────────────────────────
-- Эту таблицу читает Report API. ReplacingMergeTree дедуплицирует по ключу.
CREATE TABLE IF NOT EXISTS bionicpro.user_reports_summary
(
    user_id          String,
    username         String,
    email            String,
    prosthesis_id    String,
    model            String,
    total_movements  UInt64,
    avg_response_ms  Float64,
    min_response_ms  Float64,
    max_response_ms  Float64,
    last_activity    DateTime,
    report_date      Date
) ENGINE = ReplacingMergeTree()
ORDER BY (user_id, prosthesis_id, report_date);


-- ── 5. MaterializedView: raw_telemetry_cdc → витрина (агрегация по дням) ────
CREATE MATERIALIZED VIEW IF NOT EXISTS bionicpro.mv_raw_to_summary
TO bionicpro.user_reports_summary AS
SELECT
    toString(prosthesis_id) AS user_id,
    ''                      AS username,
    ''                      AS email,
    toString(prosthesis_id) AS prosthesis_id,
    ''                      AS model,
    count()                 AS total_movements,
    avg(response_ms)        AS avg_response_ms,
    min(response_ms)        AS min_response_ms,
    max(response_ms)        AS max_response_ms,
    max(recorded_at)        AS last_activity,
    toDate(recorded_at)     AS report_date
FROM bionicpro.raw_telemetry_cdc
GROUP BY prosthesis_id, toDate(recorded_at);
