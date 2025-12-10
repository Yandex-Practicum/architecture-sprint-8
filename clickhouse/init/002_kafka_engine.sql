CREATE TABLE IF NOT EXISTS kafka_users_raw
(
    payload String
)
ENGINE = Kafka
SETTINGS kafka_broker_list = 'kafka:9092',
         kafka_topic_list = 'crmdb.public.user_entity',
         kafka_group_name = 'ch_kafka_users_v4',
         kafka_format = 'JSONEachRow';

CREATE TABLE IF NOT EXISTS users_mv
(
    user_id UInt64,
    email String,
    plan String DEFAULT 'basic',
    country String DEFAULT 'RU',
    period_date Date DEFAULT today(),
    actions_total UInt64 DEFAULT 0,
    errors_total UInt64 DEFAULT 0,
    active_minutes_avg Float64 DEFAULT 0
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(period_date)
ORDER BY (user_id, period_date);

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_users_to_reports
TO users_mv
AS
SELECT
    -- хэшируем UUID так же, как в bionicpro-auth: SHA256 -> первые 8 байт big-endian
    reinterpretAsUInt64(reverse(substr(SHA256(JSON_VALUE(payload, '$.after.id')), 1, 8))) AS user_id,
    coalesce(JSON_VALUE(payload, '$.after.email'), '') AS email,
    'basic' AS plan,
    'RU' AS country,
    today() AS period_date,
    0 AS actions_total,
    0 AS errors_total,
    0.0 AS active_minutes_avg
FROM kafka_users_raw;


