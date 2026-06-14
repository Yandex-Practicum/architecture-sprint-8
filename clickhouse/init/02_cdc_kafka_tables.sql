-- ============================================================================
-- ClickHouse CDC Tables with KafkaEngine
-- BionicPRO - Задание 4: Change Data Capture
-- ============================================================================
-- Этот скрипт создаёт таблицы для приёма данных из Kafka (Debezium CDC)

-- ============================================================================
-- 1. KAFKA ENGINE TABLES
-- Эти таблицы читают данные напрямую из топиков Kafka
-- ============================================================================

-- Kafka table для crm.customers
CREATE TABLE IF NOT EXISTS reports.kafka_crm_customers
(
    -- Поля из Debezium (после трансформации ExtractNewRecordState)
    customer_id         Int32,
    external_id         String,
    first_name          String,
    last_name           String,
    middle_name         Nullable(String),
    email               String,
    phone               Nullable(String),
    birth_date          Nullable(Date),
    region              String,
    branch              Nullable(String),
    created_at          DateTime64(3),
    updated_at          DateTime64(3),
    -- Debezium metadata
    __op                String,         -- 'c' create, 'u' update, 'd' delete, 'r' read (snapshot)
    __table             String,
    __source_ts_ms      Int64
)
ENGINE = Kafka
SETTINGS
    kafka_broker_list = 'kafka:29092',
    kafka_topic_list = 'crm.crm.customers',
    kafka_group_name = 'clickhouse_crm_customers',
    kafka_format = 'JSONEachRow',
    kafka_num_consumers = 1,
    kafka_skip_broken_messages = 100;

-- Kafka table для crm.prostheses
CREATE TABLE IF NOT EXISTS reports.kafka_crm_prostheses
(
    prosthesis_id       Int32,
    serial_number       String,
    model_id            Int32,
    customer_id         Nullable(Int32),
    chip_id             Nullable(String),
    status              String,
    manufactured_date   Date,
    sold_date           Nullable(Date),
    warranty_end_date   Nullable(Date),
    firmware_version    Nullable(String),
    created_at          DateTime64(3),
    updated_at          DateTime64(3),
    -- Debezium metadata
    __op                String,
    __table             String,
    __source_ts_ms      Int64
)
ENGINE = Kafka
SETTINGS
    kafka_broker_list = 'kafka:29092',
    kafka_topic_list = 'crm.crm.prostheses',
    kafka_group_name = 'clickhouse_crm_prostheses',
    kafka_format = 'JSONEachRow',
    kafka_num_consumers = 1,
    kafka_skip_broken_messages = 100;

-- Kafka table для crm.prosthesis_models
CREATE TABLE IF NOT EXISTS reports.kafka_crm_models
(
    model_id            Int32,
    model_code          String,
    model_name          String,
    category            String,
    description         Nullable(String),
    price               Float64,
    warranty_months     Int32,
    is_active           UInt8,
    created_at          DateTime64(3),
    -- Debezium metadata
    __op                String,
    __table             String,
    __source_ts_ms      Int64
)
ENGINE = Kafka
SETTINGS
    kafka_broker_list = 'kafka:29092',
    kafka_topic_list = 'crm.crm.prosthesis_models',
    kafka_group_name = 'clickhouse_crm_models',
    kafka_format = 'JSONEachRow',
    kafka_num_consumers = 1,
    kafka_skip_broken_messages = 100;


-- ============================================================================
-- 2. TARGET TABLES (ReplacingMergeTree)
-- Эти таблицы хранят актуальные данные из CRM
-- ReplacingMergeTree автоматически удаляет дубликаты по ключу
-- ============================================================================

-- Target table для customers
CREATE TABLE IF NOT EXISTS reports.crm_customers
(
    customer_id         Int32,
    external_id         String,
    first_name          String,
    last_name           String,
    middle_name         Nullable(String),
    email               String,
    phone               Nullable(String),
    birth_date          Nullable(Date),
    region              LowCardinality(String),
    branch              Nullable(String),
    created_at          DateTime64(3),
    updated_at          DateTime64(3),
    -- CDC metadata
    _op                 LowCardinality(String),
    _version            UInt64,      -- для ReplacingMergeTree
    _deleted            UInt8 DEFAULT 0
)
ENGINE = ReplacingMergeTree(_version)
ORDER BY (customer_id)
SETTINGS index_granularity = 8192;

-- Target table для prostheses
CREATE TABLE IF NOT EXISTS reports.crm_prostheses
(
    prosthesis_id       Int32,
    serial_number       String,
    model_id            Int32,
    customer_id         Nullable(Int32),
    chip_id             Nullable(String),
    status              LowCardinality(String),
    manufactured_date   Date,
    sold_date           Nullable(Date),
    warranty_end_date   Nullable(Date),
    firmware_version    Nullable(String),
    created_at          DateTime64(3),
    updated_at          DateTime64(3),
    -- CDC metadata
    _op                 LowCardinality(String),
    _version            UInt64,
    _deleted            UInt8 DEFAULT 0
)
ENGINE = ReplacingMergeTree(_version)
ORDER BY (prosthesis_id)
SETTINGS index_granularity = 8192;

-- Target table для prosthesis_models
CREATE TABLE IF NOT EXISTS reports.crm_prosthesis_models
(
    model_id            Int32,
    model_code          String,
    model_name          String,
    category            LowCardinality(String),
    description         Nullable(String),
    price               Float64,
    warranty_months     Int32,
    is_active           UInt8,
    created_at          DateTime64(3),
    -- CDC metadata
    _op                 LowCardinality(String),
    _version            UInt64,
    _deleted            UInt8 DEFAULT 0
)
ENGINE = ReplacingMergeTree(_version)
ORDER BY (model_id)
SETTINGS index_granularity = 8192;


-- ============================================================================
-- 3. MATERIALIZED VIEWS
-- Автоматически переносят данные из Kafka tables в Target tables
-- ============================================================================

-- MV для customers
CREATE MATERIALIZED VIEW IF NOT EXISTS reports.mv_kafka_customers
TO reports.crm_customers
AS SELECT
    customer_id,
    external_id,
    first_name,
    last_name,
    middle_name,
    email,
    phone,
    birth_date,
    region,
    branch,
    created_at,
    updated_at,
    __op AS _op,
    __source_ts_ms AS _version,
    if(__op = 'd', 1, 0) AS _deleted
FROM reports.kafka_crm_customers;

-- MV для prostheses
CREATE MATERIALIZED VIEW IF NOT EXISTS reports.mv_kafka_prostheses
TO reports.crm_prostheses
AS SELECT
    prosthesis_id,
    serial_number,
    model_id,
    customer_id,
    chip_id,
    status,
    manufactured_date,
    sold_date,
    warranty_end_date,
    firmware_version,
    created_at,
    updated_at,
    __op AS _op,
    __source_ts_ms AS _version,
    if(__op = 'd', 1, 0) AS _deleted
FROM reports.kafka_crm_prostheses;

-- MV для models
CREATE MATERIALIZED VIEW IF NOT EXISTS reports.mv_kafka_models
TO reports.crm_prosthesis_models
AS SELECT
    model_id,
    model_code,
    model_name,
    category,
    description,
    price,
    warranty_months,
    is_active,
    created_at,
    __op AS _op,
    __source_ts_ms AS _version,
    if(__op = 'd', 1, 0) AS _deleted
FROM reports.kafka_crm_models;


-- ============================================================================
-- 4. VIEW для объединения CRM данных (аналог crm.v_customer_prosthesis)
-- ============================================================================

CREATE OR REPLACE VIEW reports.v_cdc_customer_prosthesis AS
SELECT
    c.customer_id,
    c.external_id AS user_id,
    c.first_name,
    c.last_name,
    c.middle_name,
    concat(c.last_name, ' ', c.first_name, if(c.middle_name IS NOT NULL, concat(' ', c.middle_name), '')) AS customer_full_name,
    c.email AS customer_email,
    c.phone,
    c.region AS customer_region,
    c.branch AS customer_branch,
    p.prosthesis_id,
    p.serial_number AS prosthesis_serial,
    p.chip_id,
    p.status AS prosthesis_status,
    p.firmware_version,
    m.model_code,
    m.model_name AS prosthesis_model,
    m.category AS prosthesis_category,
    p.sold_date,
    p.warranty_end_date,
    c.updated_at AS customer_updated_at,
    p.updated_at AS prosthesis_updated_at,
    greatest(c.updated_at, p.updated_at) AS last_updated_at
FROM reports.crm_customers c
JOIN reports.crm_prostheses p ON c.customer_id = p.customer_id
JOIN reports.crm_prosthesis_models m ON p.model_id = m.model_id
WHERE p.status = 'active'
  AND c._deleted = 0
  AND p._deleted = 0
  AND m._deleted = 0;


-- ============================================================================
-- 5. MATERIALIZED VIEW для автоматического обновления витрины
-- Объединяет CDC данные CRM с телеметрией
-- ============================================================================

-- Таблица для CDC-части витрины (только CRM данные)
-- Телеметрия по-прежнему загружается через ETL
CREATE TABLE IF NOT EXISTS reports.cdc_customer_data
(
    user_id             String,
    customer_id         Int32,
    customer_name       String,
    customer_email      String,
    customer_region     LowCardinality(String),
    customer_branch     Nullable(String),
    prosthesis_id       Int32,
    prosthesis_serial   String,
    chip_id             String,
    prosthesis_model    String,
    prosthesis_category LowCardinality(String),
    firmware_version    Nullable(String),
    last_updated_at     DateTime64(3),
    _version            UInt64
)
ENGINE = ReplacingMergeTree(_version)
ORDER BY (chip_id, user_id)
SETTINGS index_granularity = 8192;

-- MV для автоматического обновления данных клиентов из CDC
CREATE MATERIALIZED VIEW IF NOT EXISTS reports.mv_cdc_customer_data
TO reports.cdc_customer_data
AS SELECT
    c.external_id AS user_id,
    c.customer_id,
    concat(c.last_name, ' ', c.first_name, if(c.middle_name IS NOT NULL, concat(' ', c.middle_name), '')) AS customer_name,
    c.email AS customer_email,
    c.region AS customer_region,
    c.branch AS customer_branch,
    p.prosthesis_id,
    p.serial_number AS prosthesis_serial,
    assumeNotNull(p.chip_id) AS chip_id,
    m.model_name AS prosthesis_model,
    m.category AS prosthesis_category,
    p.firmware_version,
    greatest(c.updated_at, p.updated_at) AS last_updated_at,
    toUInt64(greatest(c._version, p._version)) AS _version
FROM reports.crm_customers c
JOIN reports.crm_prostheses p ON c.customer_id = p.customer_id
JOIN reports.crm_prosthesis_models m ON p.model_id = m.model_id
WHERE p.status = 'active'
  AND p.chip_id IS NOT NULL
  AND c._deleted = 0
  AND p._deleted = 0
  AND m._deleted = 0;


-- ============================================================================
-- 6. Обновлённая витрина для отчётов (с поддержкой CDC)
-- ============================================================================

-- View для API, который использует CDC данные клиентов
-- и объединяет их с телеметрией из основной витрины
CREATE OR REPLACE VIEW reports.v_user_report_cdc AS
SELECT
    t.user_id,
    c.customer_name,
    c.prosthesis_model,
    c.prosthesis_serial,
    c.customer_region,
    t.report_date,

    -- Суммарные метрики за день
    sum(t.movements_count) AS daily_movements,
    sum(t.successful_movements) AS daily_successful,
    round(sum(t.successful_movements) / nullIf(sum(t.movements_count), 0) * 100, 2) AS daily_success_rate,

    -- Средние метрики
    round(avg(t.avg_response_time), 2) AS avg_response_time_ms,
    round(avg(t.avg_battery_level), 1) AS avg_battery_percent,
    round(avg(t.avg_actuator_temp), 1) AS avg_temp_celsius,

    -- Экстремумы
    min(t.min_battery_level) AS min_battery_percent,
    max(t.max_actuator_temp) AS max_temp_celsius,

    -- Качество
    sum(t.error_count) AS daily_errors,
    round(avg(t.avg_connection_quality), 1) AS avg_connection_quality,

    -- Активность
    count() AS active_hours

FROM reports.user_prosthesis_stats t
LEFT JOIN reports.cdc_customer_data c ON t.chip_id = c.chip_id
GROUP BY
    t.user_id,
    c.customer_name,
    c.prosthesis_model,
    c.prosthesis_serial,
    c.customer_region,
    t.report_date
ORDER BY t.report_date DESC;


-- ============================================================================
-- Индексы и оптимизации
-- ИДЕМПОТЕНТНО: индексы создаются только если их ещё нет
-- ============================================================================

-- Создаём индекс для быстрого поиска по chip_id
ALTER TABLE reports.crm_prostheses
    ADD INDEX IF NOT EXISTS idx_chip_id chip_id TYPE bloom_filter GRANULARITY 1;

-- Создаём индекс для быстрого поиска по external_id
ALTER TABLE reports.crm_customers
    ADD INDEX IF NOT EXISTS idx_external_id external_id TYPE bloom_filter GRANULARITY 1;
