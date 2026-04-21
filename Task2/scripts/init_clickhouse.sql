-- Создание базы данных для витрины
CREATE DATABASE IF NOT EXISTS bionicpro;

-- Создание витрины отчётов
CREATE TABLE IF NOT EXISTS bionicpro.user_report_mart (
    -- Идентификаторы
    user_id String,
    user_email String,
    user_name String,
    country String,
    prosthesis_id String,
    prosthesis_type String,
    
    -- Временные метки
    report_date Date,
    first_signal_time DateTime,
    last_signal_time DateTime,
    
    -- Агрегированные метрики
    total_signals UInt32,
    avg_reaction_time_ms Float32,
    max_reaction_time_ms UInt32,
    min_reaction_time_ms UInt32,
    stddev_reaction_time_ms Float32,
    
    -- Качество работы
    successful_movements UInt32,
    failed_movements UInt32,
    success_rate Float32,
    misclassification_rate Float32,
    
    -- Состояние батареи
    avg_battery_level Float32,
    min_battery_level UInt8,
    avg_signal_quality Float32,
    
    -- Метрики качества
    quality_ok UInt8,
    needs_tuning UInt8,
    
    -- Информация о протезе
    tuning_count UInt32,
    last_tuning_date DateTime,
    prosthesis_age_days UInt32,
    
    -- Метаданные ETL
    etl_created_at DateTime DEFAULT now()
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(report_date)
ORDER BY (user_id, report_date)
SETTINGS index_granularity = 8192;

-- Создание индекса для быстрого поиска по пользователю
ALTER TABLE bionicpro.user_report_mart ADD INDEX idx_user_id user_id TYPE bloom_filter GRANULARITY 1;
ALTER TABLE bionicpro.user_report_mart ADD INDEX idx_email user_email TYPE bloom_filter GRANULARITY 1;




--    ==========================.    TASK 4 ==========================
-- ======================================================================
-- ======================================================================
-- ======================================================================
-- ======================================================================


-- Создание базы данных
CREATE DATABASE IF NOT EXISTS crm_analytics;

-- ============================================
-- Kafka Engine таблицы для raw данных
-- ============================================

-- Raw таблица для users
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

-- Raw таблица для prostheses
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

-- Таблица для users (без FINAL в определении)
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
    `deleted_at` Nullable(DateTime),
    `is_deleted` UInt8 DEFAULT 0,
    `_cdc_version` UInt64,
    `_cdc_operation` LowCardinality(String)
)
ENGINE = ReplacingMergeTree(_cdc_version)
ORDER BY (id)
SETTINGS index_granularity = 8192;

-- Таблица для prostheses
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
ORDER BY (id);

-- ============================================
-- Materialized Views (без FINAL)
-- ============================================

-- MV для users
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
-- Витрины для отчетности (без FINAL в MV)
-- ============================================

-- Витрина по пользователям
CREATE TABLE crm_analytics.users_stats_mart
(
    `report_date` Date DEFAULT today(),
    `total_users` UInt64,
    `active_users` UInt64,
    `updated_at` DateTime DEFAULT now()
)
ENGINE = SummingMergeTree()
ORDER BY (report_date);

-- MV для витрины пользователей (без FINAL)
CREATE MATERIALIZED VIEW crm_analytics.mv_users_stats_mart
TO crm_analytics.users_stats_mart
AS
SELECT
    today() AS report_date,
    count() AS total_users,
    countIf(deleted_at IS NULL) AS active_users,
    now() AS updated_at
FROM crm_analytics.users
WHERE is_deleted = 0;

-- Витрина по протезам
CREATE TABLE crm_analytics.prostheses_stats_mart
(
    `report_date` Date DEFAULT today(),
    `prosthesis_type` String,
    `total_count` UInt64,
    `active_count` UInt64,
    `avg_tuning_count` Float64,
    `updated_at` DateTime DEFAULT now()
)
ENGINE = SummingMergeTree()
ORDER BY (report_date, prosthesis_type);

-- MV для витрины протезов (без FINAL)
CREATE MATERIALIZED VIEW crm_analytics.mv_prostheses_stats_mart
TO crm_analytics.prostheses_stats_mart
AS
SELECT
    today() AS report_date,
    prosthesis_type,
    count() AS total_count,
    countIf(status = 'active') AS active_count,
    avg(tuning_count) AS avg_tuning_count,
    now() AS updated_at
FROM crm_analytics.prostheses
WHERE is_deleted = 0
GROUP BY prosthesis_type;