-- Цепочка CDC: Kafka Engine (queue) -> MV -> raw/dim -> MV -> агрегирующая витрина.

CREATE DATABASE IF NOT EXISTS reports;

CREATE TABLE IF NOT EXISTS reports.telemetry_queue
(
    id               Int64,
    client_id        Int32,
    ts               Int64,
    response_time_ms Int32,
    battery_level    Int32,
    movements_count  Int32
)
ENGINE = Kafka
SETTINGS
    kafka_broker_list = 'kafka:9092',
    kafka_topic_list = 'bionic.public.telemetry',
    kafka_group_name = 'ch_telemetry',
    kafka_format = 'JSONEachRow',
    kafka_num_consumers = 1,
    kafka_skip_broken_messages = 100;

CREATE TABLE IF NOT EXISTS reports.clients_queue
(
    id               Int32,
    username         String,
    full_name        String,
    prosthesis_model String,
    created_at       Int64
)
ENGINE = Kafka
SETTINGS
    kafka_broker_list = 'kafka:9092',
    kafka_topic_list = 'bionic.public.clients',
    kafka_group_name = 'ch_clients',
    kafka_format = 'JSONEachRow',
    kafka_num_consumers = 1,
    kafka_skip_broken_messages = 100;

CREATE TABLE IF NOT EXISTS reports.telemetry_raw
(
    id               Int64,
    client_id        Int32,
    ts               DateTime,
    response_time_ms Int32,
    battery_level    Int32,
    movements_count  Int32
)
ENGINE = MergeTree
ORDER BY (client_id, ts);

-- ts из Debezium приходит как epoch в миллисекундах, поэтому fromUnixTimestamp64Milli.
CREATE MATERIALIZED VIEW IF NOT EXISTS reports.telemetry_raw_mv
TO reports.telemetry_raw AS
SELECT
    id,
    client_id,
    fromUnixTimestamp64Milli(ts) AS ts,
    response_time_ms,
    battery_level,
    movements_count
FROM reports.telemetry_queue;

CREATE TABLE IF NOT EXISTS reports.clients_dim
(
    id               Int32,
    username         String,
    full_name        String,
    prosthesis_model String,
    _synced_at       DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(_synced_at)
ORDER BY id;

CREATE MATERIALIZED VIEW IF NOT EXISTS reports.clients_dim_mv
TO reports.clients_dim AS
SELECT id, username, full_name, prosthesis_model
FROM reports.clients_queue;

CREATE TABLE IF NOT EXISTS reports.user_report_rt
(
    client_id          Int32,
    period_date        Date,
    avg_response_state AggregateFunction(avg, Int32),
    max_response_state AggregateFunction(max, Int32),
    min_battery_state  AggregateFunction(min, Int32),
    sum_moves_state    AggregateFunction(sum, Int32),
    samples_state      AggregateFunction(count)
)
ENGINE = AggregatingMergeTree
ORDER BY (client_id, period_date);

CREATE MATERIALIZED VIEW IF NOT EXISTS reports.user_report_rt_mv
TO reports.user_report_rt AS
SELECT
    client_id,
    toDate(ts)                 AS period_date,
    avgState(response_time_ms) AS avg_response_state,
    maxState(response_time_ms) AS max_response_state,
    minState(battery_level)    AS min_battery_state,
    sumState(movements_count)  AS sum_moves_state,
    countState()               AS samples_state
FROM reports.telemetry_raw
GROUP BY client_id, period_date;
