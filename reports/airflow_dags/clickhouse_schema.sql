-- Схема витрины отчётности для системы BionicPRO
-- Таблица оптимизирована для быстрого доступа к данным по пользователям

-- Создание базы данных (если не существует)
CREATE DATABASE IF NOT EXISTS bionicpro_reports;

USE bionicpro_reports;

-- Основная таблица витрины отчётности
-- Структура оптимизирована для быстрых запросов по user_id и date
CREATE TABLE IF NOT EXISTS user_reports_mart
(
    -- Идентификаторы
    user_id UInt64 COMMENT 'Идентификатор пользователя',
    date Date COMMENT 'Дата данных',
    device_id String COMMENT 'Идентификатор устройства протеза',
    
    -- Агрегированные метрики телеметрии
    total_usage_seconds UInt32 COMMENT 'Общее время использования протеза за день (секунды)',
    total_movements UInt32 COMMENT 'Общее количество движений за день',
    avg_sensor_value Float32 COMMENT 'Среднее значение датчика',
    min_sensor_value Float32 COMMENT 'Минимальное значение датчика',
    max_sensor_value Float32 COMMENT 'Максимальное значение датчика',
    usage_hours Float32 COMMENT 'Время использования в часах (вычисляемое поле)',
    
    -- Временные измерения для группировки
    year UInt16 COMMENT 'Год',
    month UInt8 COMMENT 'Месяц (1-12)',
    week UInt8 COMMENT 'Неделя года (1-53)',
    day_of_week UInt8 COMMENT 'День недели (0=понедельник, 6=воскресенье)',
    
    -- Данные из CRM (пользователи)
    user_name Nullable(String) COMMENT 'Имя пользователя',
    prosthesis_install_date Nullable(Date) COMMENT 'Дата установки протеза',
    prosthesis_type Nullable(String) COMMENT 'Тип протеза',
    
    -- Данные из CRM (заказы)
    order_date Nullable(Date) COMMENT 'Дата последнего заказа',
    order_status Nullable(String) COMMENT 'Статус последнего заказа',
    
    -- Данные из CRM (обслуживание)
    maintenance_date Nullable(Date) COMMENT 'Дата последнего обслуживания',
    maintenance_type Nullable(String) COMMENT 'Тип последнего обслуживания',
    maintenance_status Nullable(String) COMMENT 'Статус последнего обслуживания',
    
    -- Метаданные обработки
    processed_at DateTime COMMENT 'Время обработки данных ETL',
    data_period_start DateTime COMMENT 'Начало периода обработанных данных',
    data_period_end DateTime COMMENT 'Конец периода обработанных данных'
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(date)  -- Партиционирование по году и месяцу для быстрого доступа
ORDER BY (user_id, date)     -- Сортировка по user_id и date для быстрых запросов по пользователю
SETTINGS index_granularity = 8192;

-- Создание материализованного представления для агрегированных данных по неделям
CREATE MATERIALIZED VIEW IF NOT EXISTS user_reports_weekly_mv
ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(date)
ORDER BY (user_id, year, week)
AS SELECT
    user_id,
    toMonday(date) as week_start_date,
    year,
    week,
    sum(total_usage_seconds) as total_usage_seconds,
    sum(total_movements) as total_movements,
    avg(avg_sensor_value) as avg_sensor_value,
    min(min_sensor_value) as min_sensor_value,
    max(max_sensor_value) as max_sensor_value,
    sum(usage_hours) as total_usage_hours,
    count() as days_count,
    max(processed_at) as last_processed_at
FROM user_reports_mart
GROUP BY user_id, year, week, toMonday(date);

-- Создание материализованного представления для агрегированных данных по месяцам
CREATE MATERIALIZED VIEW IF NOT EXISTS user_reports_monthly_mv
ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(date)
ORDER BY (user_id, year, month)
AS SELECT
    user_id,
    toStartOfMonth(date) as month_start_date,
    year,
    month,
    sum(total_usage_seconds) as total_usage_seconds,
    sum(total_movements) as total_movements,
    avg(avg_sensor_value) as avg_sensor_value,
    min(min_sensor_value) as min_sensor_value,
    max(max_sensor_value) as max_sensor_value,
    sum(usage_hours) as total_usage_hours,
    count() as days_count,
    max(processed_at) as last_processed_at
FROM user_reports_mart
GROUP BY user_id, year, month, toStartOfMonth(date);

-- Индексы для оптимизации запросов
-- ClickHouse автоматически создает индексы на основе ORDER BY, но можно добавить дополнительные

-- Примеры запросов для получения отчётов:

-- 1. Получить отчёт по пользователю за период
-- SELECT * FROM user_reports_mart 
-- WHERE user_id = 12345 AND date >= '2024-01-01' AND date <= '2024-01-31'
-- ORDER BY date;

-- 2. Получить недельную статистику по пользователю
-- SELECT * FROM user_reports_weekly_mv
-- WHERE user_id = 12345 AND year = 2024
-- ORDER BY week_start_date;

-- 3. Получить месячную статистику по пользователю
-- SELECT * FROM user_reports_monthly_mv
-- WHERE user_id = 12345 AND year = 2024
-- ORDER BY month_start_date;

-- 4. Проверить последнюю обработанную дату
-- SELECT max(date) as last_processed_date, max(processed_at) as last_processed_time
-- FROM user_reports_mart;
