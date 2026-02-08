-- ============================================================================
-- CLICKHOUSE ANALYTICAL DATABASE SCHEMA
-- Схема аналитического хранилища для витрин данных и отчетности
-- ============================================================================

-- ============================================================================
-- STAGING LAYER: Промежуточные таблицы для загрузки данных из источников
-- ============================================================================

-- ----------------------------------------------------------------------------
-- ТАБЛИЦА: default.stg_crm_customers
-- Описание: Staging таблица для данных клиентов из CRM
-- Источник: PostgreSQL crm.customers
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS default.stg_crm_customers (
    customer_id UInt64 COMMENT 'ID клиента из CRM',
    user_external_id String COMMENT 'Внешний ID пользователя из Keycloak',
    full_name String COMMENT 'Полное имя клиента',
    email String COMMENT 'Email адрес',
    phone String COMMENT 'Телефон',
    country LowCardinality(String) COMMENT 'Код страны (ISO 3166-1 alpha-2)',
    created_at DateTime COMMENT 'Дата создания записи в CRM',
    updated_at DateTime COMMENT 'Дата последнего обновления в CRM'
) ENGINE = MergeTree()
ORDER BY (customer_id)
SETTINGS index_granularity = 8192
COMMENT 'Staging: Клиенты из CRM';

-- ----------------------------------------------------------------------------
-- ТАБЛИЦА: default.stg_crm_prostheses
-- Описание: Staging таблица для данных протезов из CRM
-- Источник: PostgreSQL crm.prostheses
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS default.stg_crm_prostheses (
    prosthesis_id UInt64 COMMENT 'ID протеза',
    customer_id UInt64 COMMENT 'ID клиента-владельца',
    model LowCardinality(String) COMMENT 'Модель протеза (BP-ARM-X, BP-LEG-Z и т.д.)',
    activated_at DateTime COMMENT 'Дата активации протеза',
    deactivated_at Nullable(DateTime) COMMENT 'Дата деактивации (NULL если активен)',
    updated_at DateTime COMMENT 'Дата последнего обновления'
) ENGINE = MergeTree()
ORDER BY (prosthesis_id)
SETTINGS index_granularity = 8192
COMMENT 'Staging: Протезы из CRM';

-- ============================================================================
-- DIMENSIONAL LAYER: Измерения для аналитики
-- ============================================================================

-- ----------------------------------------------------------------------------
-- ТАБЛИЦА: default.dim_user
-- Описание: Измерение пользователей (SCD Type 1 - только текущее состояние)
-- Движок: ReplacingMergeTree для автоматической дедупликации
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS default.dim_user (
    customer_id UInt64 COMMENT 'ID клиента (первичный ключ)',
    user_external_id String COMMENT 'Внешний ID из Keycloak для связи с JWT',
    full_name String COMMENT 'Полное имя клиента',
    email String COMMENT 'Email адрес',
    country LowCardinality(String) COMMENT 'Код страны',
    updated_at DateTime COMMENT 'Дата последнего обновления (версия записи)'
) ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (customer_id)
SETTINGS index_granularity = 8192
COMMENT 'Измерение: Пользователи (SCD Type 1)';

-- Индекс для быстрого поиска по внешнему ID (используется в API)
ALTER TABLE default.dim_user ADD INDEX IF NOT EXISTS idx_user_external_id user_external_id TYPE bloom_filter GRANULARITY 1;

-- ============================================================================
-- FACT LAYER: Факты для аналитики
-- ============================================================================

-- ----------------------------------------------------------------------------
-- ТАБЛИЦА: default.fact_telemetry_daily
-- Описание: Агрегированная дневная телеметрия по протезам
-- Партиционирование: По месяцам для оптимизации запросов и управления данными
-- Движок: ReplacingMergeTree для инкрементальных обновлений
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS default.fact_telemetry_daily (
    event_date Date COMMENT 'Дата события',
    customer_id UInt64 COMMENT 'ID клиента',
    prosthesis_id UInt64 COMMENT 'ID протеза',
    
    -- Агрегированные метрики
    events_cnt UInt64 COMMENT 'Количество событий за день',
    avg_response_ms Float64 COMMENT 'Среднее время отклика в миллисекундах',
    err_cnt UInt64 COMMENT 'Количество ошибок за день',
    battery_avg Float64 COMMENT 'Средний уровень заряда батареи',
    
    -- Дополнительные метрики для детального анализа
    min_response_ms Float64 DEFAULT 0 COMMENT 'Минимальное время отклика',
    max_response_ms Float64 DEFAULT 0 COMMENT 'Максимальное время отклика',
    p95_response_ms Float64 DEFAULT 0 COMMENT '95-й перцентиль времени отклика',
    min_battery Float64 DEFAULT 0 COMMENT 'Минимальный уровень батареи',
    
    updated_at DateTime COMMENT 'Дата последнего обновления (версия записи)'
) ENGINE = ReplacingMergeTree(updated_at)
PARTITION BY toYYYYMM(event_date)
ORDER BY (event_date, customer_id, prosthesis_id)
SETTINGS index_granularity = 8192
COMMENT 'Факт: Дневная агрегированная телеметрия протезов';

-- Индексы для оптимизации запросов
ALTER TABLE default.fact_telemetry_daily ADD INDEX IF NOT EXISTS idx_customer_date customer_id TYPE minmax GRANULARITY 1;
ALTER TABLE default.fact_telemetry_daily ADD INDEX IF NOT EXISTS idx_prosthesis prosthesis_id TYPE minmax GRANULARITY 1;

-- ============================================================================
-- REPORTING LAYER: Представления для отчетности
-- ============================================================================

-- ----------------------------------------------------------------------------
-- ПРЕДСТАВЛЕНИЕ: default.vw_user_telemetry_daily
-- Описание: Витрина данных для API отчетов
-- Объединяет факты телеметрии с измерением пользователей
-- ----------------------------------------------------------------------------
CREATE VIEW IF NOT EXISTS default.vw_user_telemetry_daily AS
SELECT
    f.event_date,
    f.customer_id,
    u.user_external_id,
    u.full_name,
    f.prosthesis_id,
    f.events_cnt,
    f.avg_response_ms,
    f.err_cnt,
    f.battery_avg,
    -- Дополнительные метрики
    f.min_response_ms,
    f.max_response_ms,
    f.p95_response_ms,
    f.min_battery
FROM default.fact_telemetry_daily f
INNER JOIN default.dim_user u ON f.customer_id = u.customer_id
COMMENT 'Витрина: Дневная телеметрия пользователей для API';

-- ----------------------------------------------------------------------------
-- ПРЕДСТАВЛЕНИЕ: default.vw_prosthesis_performance
-- Описание: Анализ производительности протезов
-- ----------------------------------------------------------------------------
CREATE VIEW IF NOT EXISTS default.vw_prosthesis_performance AS
SELECT
    f.prosthesis_id,
    u.user_external_id,
    u.full_name,
    COUNT(*) AS days_active,
    SUM(f.events_cnt) AS total_events,
    AVG(f.avg_response_ms) AS overall_avg_response_ms,
    AVG(f.p95_response_ms) AS overall_p95_response_ms,
    SUM(f.err_cnt) AS total_errors,
    (SUM(f.err_cnt) * 100.0 / SUM(f.events_cnt)) AS error_rate_pct,
    AVG(f.battery_avg) AS avg_battery_level,
    MIN(f.event_date) AS first_event_date,
    MAX(f.event_date) AS last_event_date
FROM default.fact_telemetry_daily f
INNER JOIN default.dim_user u ON f.customer_id = u.customer_id
GROUP BY f.prosthesis_id, u.user_external_id, u.full_name
COMMENT 'Витрина: Общая производительность протезов';

-- ----------------------------------------------------------------------------
-- ПРЕДСТАВЛЕНИЕ: default.vw_critical_performance
-- Описание: Протезы с критическими показателями производительности
-- ----------------------------------------------------------------------------
CREATE VIEW IF NOT EXISTS default.vw_critical_performance AS
SELECT
    f.event_date,
    f.prosthesis_id,
    u.user_external_id,
    u.full_name,
    f.avg_response_ms,
    f.p95_response_ms,
    f.err_cnt,
    f.events_cnt,
    (f.err_cnt * 100.0 / f.events_cnt) AS error_rate_pct,
    f.battery_avg,
    CASE
        WHEN f.avg_response_ms > 100 THEN 'Медленный отклик'
        WHEN f.p95_response_ms > 150 THEN 'Высокий P95'
        WHEN (f.err_cnt * 100.0 / f.events_cnt) > 5 THEN 'Высокий процент ошибок'
        WHEN f.battery_avg < 20 THEN 'Низкий заряд батареи'
    END AS issue_type
FROM default.fact_telemetry_daily f
INNER JOIN default.dim_user u ON f.customer_id = u.customer_id
WHERE 
    f.avg_response_ms > 100 
    OR f.p95_response_ms > 150
    OR (f.err_cnt * 100.0 / f.events_cnt) > 5
    OR f.battery_avg < 20
ORDER BY f.event_date DESC
COMMENT 'Витрина: Критические показатели производительности';

-- ============================================================================
-- КОММЕНТАРИИ К БАЗЕ ДАННЫХ
-- ============================================================================
-- База данных default используется для всех аналитических объектов
-- Структура слоев:
-- 1. Staging (stg_*) - промежуточные таблицы для загрузки из источников
-- 2. Dimensional (dim_*) - измерения для аналитики
-- 3. Fact (fact_*) - факты с метриками
-- 4. Reporting (vw_*) - представления для отчетности и API
