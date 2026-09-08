-- Создаём таблицу с KafkaEngine для чтения из топика clients
CREATE TABLE IF NOT EXISTS bionicpro.kafka_clients
(
    payload String
)
    ENGINE = Kafka
    SETTINGS
    kafka_broker_list = 'kafka:29092',
    kafka_topic_list = 'crm.public.clients',
    kafka_group_name = 'clickhouse-clients',
    kafka_format = 'JSONAsString';

-- Создаём таблицу с KafkaEngine для телеметрии
CREATE TABLE IF NOT EXISTS bionicpro.kafka_telemetry
(
    payload String
)
    ENGINE = Kafka
    SETTINGS
    kafka_broker_list = 'kafka:29092',
    kafka_topic_list = 'crm.public.prosthesis_telemetry',
    kafka_group_name = 'clickhouse-telemetry',
    kafka_format = 'JSONAsString';

-- Целевая таблица для клиентов
CREATE TABLE IF NOT EXISTS bionicpro.clients_cdc
(
    id Int32,
    username String,
    full_name String,
    email String,
    created_at DateTime,
    _updated_at DateTime DEFAULT now()
    )
    ENGINE = ReplacingMergeTree(_updated_at)
    ORDER BY id;

-- Целевая таблица для телеметрии
CREATE TABLE IF NOT EXISTS bionicpro.telemetry_cdc
(
    id Int32,
    client_id Int32,
    prosthesis_id String,
    usage_hours Float64,
    battery_cycles Int32,
    movements_count Int32,
    recorded_at DateTime,
    _updated_at DateTime DEFAULT now()
    )
    ENGINE = ReplacingMergeTree(_updated_at)
    ORDER BY id;

-- MaterializedView для клиентов
CREATE MATERIALIZED VIEW IF NOT EXISTS bionicpro.mv_clients
TO bionicpro.clients_cdc
AS SELECT
              JSONExtractInt(payload, 'payload', 'after', 'id') as id,
              JSONExtractString(payload, 'payload', 'after', 'username') as username,
              JSONExtractString(payload, 'payload', 'after', 'full_name') as full_name,
              JSONExtractString(payload, 'payload', 'after', 'email') as email,
              now() as created_at
   FROM bionicpro.kafka_clients
   WHERE JSONExtractString(payload, 'payload', 'op') != 'd';

-- MaterializedView для телеметрии
CREATE MATERIALIZED VIEW IF NOT EXISTS bionicpro.mv_telemetry
TO bionicpro.telemetry_cdc
AS SELECT
              JSONExtractInt(payload, 'payload', 'after', 'id') as id,
              JSONExtractInt(payload, 'payload', 'after', 'client_id') as client_id,
              JSONExtractString(payload, 'payload', 'after', 'prosthesis_id') as prosthesis_id,
              JSONExtractFloat(payload, 'payload', 'after', 'usage_hours') as usage_hours,
              JSONExtractInt(payload, 'payload', 'after', 'battery_cycles') as battery_cycles,
              JSONExtractInt(payload, 'payload', 'after', 'movements_count') as movements_count,
              now() as recorded_at
   FROM bionicpro.kafka_telemetry
   WHERE JSONExtractString(payload, 'payload', 'op') != 'd';

-- Витрина для отчётности объединяющая данные
CREATE TABLE IF NOT EXISTS bionicpro.prosthesis_report_cdc
(
    username String,
    full_name String,
    email String,
    prosthesis_id String,
    total_usage_hours Float64,
    total_battery_cycles Int64,
    total_movements Int64,
    last_recorded_at DateTime,
    updated_at DateTime DEFAULT now()
    )
    ENGINE = ReplacingMergeTree(updated_at)
    ORDER BY (username, prosthesis_id);