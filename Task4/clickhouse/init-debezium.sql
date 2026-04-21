-- clickhouse/init.sql
-- Создание базы данных
CREATE DATABASE IF NOT EXISTS crm_analytics;

-- ============================================
-- Kafka Engine таблицы для raw данных
-- ============================================

-- Raw таблица для users (из схемы crm)
CREATE TABLE crm_analytics.kafka_users_raw
(
    `before` String,
    `after` String,
    `op` LowCardinality(String),
    `ts_ms` Int64,
    `source` String,
    `transaction` String
)
ENGINE = Kafka
SETTINGS
    kafka_broker_list = 'kafka:9092',
    kafka_topic_list = 'cdc.crm.users',
    kafka_group_name = 'clickhouse_users_consumer',
    kafka_format = 'JSONEachRow',
    kafka_num_consumers = 1,
    kafka_skip_broken_messages = 10;

-- Raw таблица для prostheses (из схемы crm)
CREATE TABLE crm_analytics.kafka_prostheses_raw
(
    `before` String,
    `after` String,
    `op` LowCardinality(String),
    `ts_ms` Int64,
    `source` String,
    `transaction` String
)
ENGINE = Kafka
SETTINGS
    kafka_broker_list = 'kafka:9092',
    kafka_topic_list = 'cdc.crm.prostheses',
    kafka_group_name = 'clickhouse_prostheses_consumer',
    kafka_format = 'JSONEachRow',
    kafka_num_consumers = 1;




-- ============================================
-- Целевые таблицы с ReplacingMergeTree
-- ============================================

-- Таблица для users (соответствует структуре crm.users)
CREATE TABLE crm_analytics.users
(
    `id` String,
    `email` String,
    `phone` String,
    `first_name` String,
    `last_name` String,
    `country` String,
    `city` String,
    `registration_date` DateTime,
    `deleted_at` DateTime,
    `is_deleted` UInt8 DEFAULT 0,
    `_cdc_version` UInt64,
    `_cdc_operation` LowCardinality(String)
)
ENGINE = ReplacingMergeTree(_cdc_version)
ORDER BY (id)
SETTINGS index_granularity = 8192;

-- Таблица для prostheses (соответствует структуре crm.prostheses)
CREATE TABLE crm_analytics.prostheses
(
    `id` String,
    `user_id` String,
    `prosthesis_type` String,
    `manufacture_date` DateTime,
    `last_tuning_date` DateTime,
    `tuning_count` Int32,
    `status` String,
    `is_deleted` UInt8 DEFAULT 0,
    `_cdc_version` UInt64,
    `_cdc_operation` LowCardinality(String)
)
ENGINE = ReplacingMergeTree(_cdc_version)
ORDER BY (id)
SETTINGS index_granularity = 8192;

-- ============================================
-- Materialized Views для трансформации данных
-- ============================================

-- MV для users (извлекаем данные из поля 'after')
CREATE MATERIALIZED VIEW crm_analytics.mv_users
TO crm_analytics.users
AS
SELECT
    JSONExtractString(after, 'id') AS id,
    JSONExtractString(after, 'email') AS email,
    JSONExtractString(after, 'phone') AS phone,
    JSONExtractString(after, 'first_name') AS first_name,
    JSONExtractString(after, 'last_name') AS last_name,
    JSONExtractString(after, 'country') AS country,
    JSONExtractString(after, 'city') AS city,
    toDateTime(JSONExtractString(after, 'registration_date')) AS registration_date,
    toDateTimeOrNull(JSONExtractString(after, 'deleted_at')) AS deleted_at,
    if(op = 'd' OR JSONExtractString(after, 'deleted_at') IS NOT NULL, 1, 0) AS is_deleted,
    JSONExtractUInt(source, 'lsn') AS _cdc_version,
    op AS _cdc_operation
FROM crm_analytics.kafka_users_raw
WHERE op IN ('c', 'u', 'r');

-- MV для prostheses
CREATE MATERIALIZED VIEW crm_analytics.mv_prostheses
TO crm_analytics.prostheses
AS
SELECT
    JSONExtractString(after, 'id') AS id,
    JSONExtractString(after, 'user_id') AS user_id,
    JSONExtractString(after, 'prosthesis_type') AS prosthesis_type,
    toDateTime(JSONExtractString(after, 'manufacture_date')) AS manufacture_date,
    toDateTimeOrNull(JSONExtractString(after, 'last_tuning_date')) AS last_tuning_date,
    JSONExtractInt(after, 'tuning_count') AS tuning_count,
    JSONExtractString(after, 'status') AS status,
    if(op = 'd', 1, 0) AS is_deleted,
    JSONExtractUInt(source, 'lsn') AS _cdc_version,
    op AS _cdc_operation
FROM crm_analytics.kafka_prostheses_raw
WHERE op IN ('c', 'u', 'r');

-- ============================================
-- Витрины для отчетности
-- ============================================

-- Витрина 1: Статистика по пользователям
CREATE TABLE crm_analytics.users_stats_mart
(
    `report_date` Date DEFAULT today(),
    `total_users` UInt64,
    `active_users` UInt64,
    `deleted_users` UInt64,
    `users_by_country` String,
    `users_by_city` String,
    `updated_at` DateTime DEFAULT now()
)
ENGINE = SummingMergeTree()
ORDER BY (report_date);

-- MV для наполнения витрины пользователей
CREATE MATERIALIZED VIEW crm_analytics.mv_users_stats_mart
TO crm_analytics.users_stats_mart
AS
SELECT
    today() AS report_date,
    count(*) AS total_users,
    countIf(deleted_at IS NULL) AS active_users,
    countIf(deleted_at IS NOT NULL) AS deleted_users,
    '' AS users_by_country,
    '' AS users_by_city,
    now() AS updated_at
FROM crm_analytics.users FINAL;

-- Витрина 2: Статистика по протезам
CREATE TABLE crm_analytics.prostheses_stats_mart
(
    `report_date` Date DEFAULT today(),
    `prosthesis_type` String,
    `total_count` UInt64,
    `active_count` UInt64,
    `avg_tuning_count` Float64,
    `needs_tuning_count` UInt64,
    `updated_at` DateTime DEFAULT now()
)
ENGINE = SummingMergeTree()
ORDER BY (report_date, prosthesis_type);

-- MV для наполнения витрины протезов
CREATE MATERIALIZED VIEW crm_analytics.mv_prostheses_stats_mart
TO crm_analytics.prostheses_stats_mart
AS
SELECT
    today() AS report_date,
    prosthesis_type,
    count(*) AS total_count,
    countIf(status = 'active') AS active_count,
    avg(tuning_count) AS avg_tuning_count,
    countIf(last_tuning_date < now() - INTERVAL 90 DAY) AS needs_tuning_count,
    now() AS updated_at
FROM crm_analytics.prostheses FINAL
WHERE is_deleted = 0
GROUP BY prosthesis_type;

-- Витрина 3: Детальная информация по пользователям и их протезам (для API)
CREATE TABLE crm_analytics.users_with_prostheses
(
    `user_id` String,
    `user_email` String,
    `user_name` String,
    `user_city` String,
    `prosthesis_id` String,
    `prosthesis_type` String,
    `prosthesis_status` String,
    `last_tuning_date` DateTime,
    `tuning_count` Int32,
    `updated_at` DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (user_id, prosthesis_id);

-- MV для наполнения детальной витрины
CREATE MATERIALIZED VIEW crm_analytics.mv_users_with_prostheses
TO crm_analytics.users_with_prostheses
AS
SELECT
    u.id AS user_id,
    u.email AS user_email,
    concat(coalesce(u.first_name, ''), ' ', coalesce(u.last_name, '')) AS user_name,
    u.city AS user_city,
    p.id AS prosthesis_id,
    p.prosthesis_type,
    p.status AS prosthesis_status,
    p.last_tuning_date,
    p.tuning_count,
    now() AS updated_at
FROM crm_analytics.users FINAL AS u
LEFT JOIN crm_analytics.prostheses FINAL AS p ON u.id = p.user_id AND p.is_deleted = 0
WHERE u.is_deleted = 0;

-- ============================================
-- Функции для проверки
-- ============================================

-- Проверка количества записей
SELECT 'users' AS table_name, count(*) AS count FROM crm_analytics.users FINAL
UNION ALL
SELECT 'prostheses', count(*) FROM crm_analytics.prostheses FINAL;

-- Последние изменения
SELECT 
    'users' AS source,
    id,
    email,
    registration_date,
    _cdc_operation
FROM crm_analytics.users FINAL
ORDER BY _cdc_version DESC
LIMIT 5;