CREATE TABLE IF NOT EXISTS bionicpro.kafka_crm_user_prostheses
(
    user_id           String,
    prosthesis_serial String,
    __op              String,
    __ts_ms           Int64
) ENGINE = Kafka SETTINGS
    kafka_broker_list = 'kafka:9092',
    kafka_topic_list = 'bionicpro.public.user_prostheses',
    kafka_group_name = 'clickhouse-crm-consumer',
    kafka_format = 'JSONEachRow',
    kafka_num_consumers = 1,
    kafka_skip_broken_messages = 10;

CREATE TABLE IF NOT EXISTS bionicpro.crm_user_prostheses
(
    user_id           String,
    prosthesis_serial String,
    __op              String,
    __ts_ms           Int64,
    _version          Int64
) ENGINE = ReplacingMergeTree(_version) ORDER BY (user_id, prosthesis_serial) SETTINGS index_granularity = 8192;

CREATE MATERIALIZED VIEW IF NOT EXISTS bionicpro.move_kafka_to_crm_user_prostheses TO bionicpro.crm_user_prostheses AS
SELECT user_id,
       prosthesis_serial,
       __op,
       __ts_ms,
       __ts_ms AS _version
FROM bionicpro.kafka_crm_user_prostheses
WHERE __op != 'd';

CREATE TABLE IF NOT EXISTS bionicpro.daily_telemetry
(
    prosthesis_serial String,
    total_movements   UInt64,
    avg_response_ms   Float32,
    active_hours      Float32,
    recorded_date     Date,
    airflow_run_id    String,
    processed_at      DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(processed_at) ORDER BY (prosthesis_serial, recorded_date);

CREATE TABLE IF NOT EXISTS bionicpro.prosthesis_report
(
    report_date       Date,
    user_id           String,
    prosthesis_serial String,
    total_movements   UInt64,
    avg_response_ms   Float32,
    active_hours      Float32,
    processed_at      DateTime DEFAULT now()
)
    ENGINE = ReplacingMergeTree(processed_at) PARTITION BY toYYYYMM(report_date) ORDER BY (user_id, prosthesis_serial, report_date);

CREATE MATERIALIZED VIEW IF NOT EXISTS bionicpro.collect_prosthesis_report TO bionicpro.prosthesis_report AS
SELECT t.recorded_date AS report_date,
       c.user_id,
       t.prosthesis_serial,
       t.total_movements,
       t.avg_response_ms,
       t.active_hours,
       t.processed_at
FROM bionicpro.daily_telemetry t
         LEFT JOIN bionicpro.crm_user_prostheses c ON c.prosthesis_serial = t.prosthesis_serial
GROUP BY t.recorded_date, c.user_id, t.prosthesis_serial, t.total_movements, t.avg_response_ms, t.active_hours,
         t.processed_at;
