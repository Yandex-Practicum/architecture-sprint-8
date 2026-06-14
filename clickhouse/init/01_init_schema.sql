-- ============================================================================
-- ClickHouse OLAP Database Schema
-- BionicPRO Reports - Витрина отчётности
-- ============================================================================

-- Создание базы данных для отчётов
CREATE DATABASE IF NOT EXISTS reports;

-- ============================================================================
-- Основная витрина: user_prosthesis_stats
-- Агрегированные данные телеметрии + данные клиентов из CRM
-- Партиционирование по дате для быстрого доступа и TTL
-- ============================================================================
CREATE TABLE IF NOT EXISTS reports.user_prosthesis_stats
(
    -- Ключевые идентификаторы
    user_id             String,                              -- ID пользователя (external_id из CRM)
    prosthesis_id       UInt32,                              -- ID протеза
    chip_id             String,                              -- ID чипа ESP32

    -- Временные измерения
    report_date         Date,                                -- Дата отчёта
    report_hour         UInt8,                               -- Час (0-23)

    -- Данные из CRM (денормализовано для скорости)
    customer_name       String,                              -- ФИО клиента
    customer_email      String,                              -- Email
    customer_region     LowCardinality(String),              -- Регион (russia, europe)
    customer_branch     String,                              -- Филиал
    prosthesis_model    String,                              -- Модель протеза
    prosthesis_category LowCardinality(String),              -- Категория (arm, leg, hand)
    prosthesis_serial   String,                              -- Серийный номер протеза

    -- Метрики использования
    movements_count     UInt32,                              -- Количество движений
    successful_movements UInt32,                             -- Успешные движения
    success_rate        Float32,                             -- Процент успешных движений

    -- Метрики времени отклика (мс)
    avg_response_time   Float32,                             -- Среднее время отклика
    min_response_time   UInt32,                              -- Минимальное
    max_response_time   UInt32,                              -- Максимальное

    -- Метрики батареи
    avg_battery_level   Float32,                             -- Средний уровень заряда
    min_battery_level   UInt8,                               -- Минимальный уровень
    max_battery_level   UInt8,                               -- Максимальный уровень

    -- Метрики температуры (°C)
    avg_actuator_temp   Float32,                             -- Средняя температура актуатора
    max_actuator_temp   Float32,                             -- Максимальная температура

    -- Ошибки и качество
    error_count         UInt32,                              -- Количество ошибок
    warning_count       UInt32,                              -- Количество предупреждений
    avg_connection_quality Float32,                          -- Среднее качество связи

    -- Метрики миосигналов
    avg_myo_amplitude   Float32,                             -- Средняя амплитуда миосигнала

    -- Служебные поля
    etl_processed_at    DateTime DEFAULT now(),              -- Время обработки ETL
    source_updated_at   DateTime                             -- Время обновления в источнике
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(report_date)
ORDER BY (user_id, report_date, report_hour, prosthesis_id)
TTL report_date + INTERVAL 365 DAY
SETTINGS index_granularity = 8192;

-- ============================================================================
-- Материализованное представление: Дневная статистика
-- ============================================================================
CREATE TABLE IF NOT EXISTS reports.user_daily_stats
(
    user_id             String,
    prosthesis_id       UInt32,
    report_date         Date,
    customer_name       String,
    prosthesis_model    String,

    -- Агрегаты за день
    total_movements     UInt64,
    total_successful    UInt64,
    daily_success_rate  Float32,
    avg_response_time   Float32,
    min_battery         UInt8,
    max_temp            Float32,
    total_errors        UInt64,
    active_hours        UInt8,                               -- Количество активных часов

    etl_processed_at    DateTime DEFAULT now()
)
ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(report_date)
ORDER BY (user_id, report_date, prosthesis_id)
TTL report_date + INTERVAL 365 DAY;

-- Материализованное представление для автоматической агрегации
CREATE MATERIALIZED VIEW IF NOT EXISTS reports.mv_user_daily_stats
TO reports.user_daily_stats
AS SELECT
    user_id,
    prosthesis_id,
    report_date,
    any(customer_name) AS customer_name,
    any(prosthesis_model) AS prosthesis_model,
    sum(movements_count) AS total_movements,
    sum(successful_movements) AS total_successful,
    if(sum(movements_count) > 0,
       round(sum(successful_movements) / sum(movements_count) * 100, 2),
       0) AS daily_success_rate,
    avg(avg_response_time) AS avg_response_time,
    min(min_battery_level) AS min_battery,
    max(max_actuator_temp) AS max_temp,
    sum(error_count) AS total_errors,
    count(DISTINCT report_hour) AS active_hours,
    now() AS etl_processed_at
FROM reports.user_prosthesis_stats
GROUP BY user_id, prosthesis_id, report_date;

-- ============================================================================
-- Представление для API: Отчёт пользователя за период
-- ============================================================================
CREATE VIEW IF NOT EXISTS reports.v_user_report AS
SELECT
    user_id,
    customer_name,
    prosthesis_model,
    prosthesis_serial,
    customer_region,
    report_date,

    -- Суммарные метрики за день
    sum(movements_count) AS daily_movements,
    sum(successful_movements) AS daily_successful,
    round(LEAST(sum(successful_movements) / nullIf(sum(movements_count), 0) * 100, 100), 2) AS daily_success_rate,

    -- Средние метрики
    round(avg(avg_response_time), 2) AS avg_response_time_ms,
    round(avg(avg_battery_level), 1) AS avg_battery_percent,
    round(avg(avg_actuator_temp), 1) AS avg_temp_celsius,

    -- Экстремумы
    min(min_battery_level) AS min_battery_percent,
    max(max_actuator_temp) AS max_temp_celsius,

    -- Качество
    sum(error_count) AS daily_errors,
    round(avg(avg_connection_quality), 1) AS avg_connection_quality,

    -- Активность
    count(DISTINCT report_hour) AS active_hours

FROM reports.user_prosthesis_stats
GROUP BY
    user_id,
    customer_name,
    prosthesis_model,
    prosthesis_serial,
    customer_region,
    report_date
ORDER BY report_date DESC;

-- ============================================================================
-- Представление для API: Сводка по пользователю за всё время
-- ============================================================================
CREATE VIEW IF NOT EXISTS reports.v_user_summary AS
SELECT
    user_id,
    any(customer_name) AS customer_name,
    any(prosthesis_model) AS prosthesis_model,
    any(prosthesis_serial) AS prosthesis_serial,
    any(customer_region) AS customer_region,

    min(report_date) AS first_activity_date,
    max(report_date) AS last_activity_date,
    dateDiff('day', min(report_date), max(report_date)) + 1 AS total_days,
    count(DISTINCT report_date) AS active_days,

    sum(movements_count) AS total_movements,
    sum(successful_movements) AS total_successful,
    round(sum(successful_movements) / nullIf(sum(movements_count), 0) * 100, 2) AS overall_success_rate,

    round(avg(avg_response_time), 2) AS avg_response_time_ms,
    round(avg(avg_battery_level), 1) AS avg_battery_percent,

    sum(error_count) AS total_errors,
    round(sum(error_count) / nullIf(count(DISTINCT report_date), 0), 2) AS avg_errors_per_day

FROM reports.user_prosthesis_stats
GROUP BY user_id;

-- ============================================================================
-- Словарь для быстрого поиска данных пользователя
-- ============================================================================
CREATE DICTIONARY IF NOT EXISTS reports.dict_user_info
(
    user_id String,
    customer_name String,
    customer_email String,
    customer_region String,
    prosthesis_model String,
    prosthesis_serial String
)
PRIMARY KEY user_id
SOURCE(CLICKHOUSE(
    HOST 'localhost'
    PORT 9000
    USER 'default'
    TABLE 'user_prosthesis_stats'
    DB 'reports'
))
LAYOUT(HASHED())
LIFETIME(MIN 300 MAX 600);

-- ============================================================================
-- Демонстрационные данные для отчётов
-- Генерация данных за последние 7 дней для всех тестовых пользователей
-- ИДЕМПОТЕНТНО: данные вставляются только если таблица пустая
-- ============================================================================

-- Вставка демо-данных для ivan.petrov (BionicArm Pro)
-- Используем INSERT ... SELECT с проверкой на существование данных
INSERT INTO reports.user_prosthesis_stats
SELECT
    'ivan.petrov' AS user_id,
    1 AS prosthesis_id,
    'ESP32-ARM-001-A1B2C3' AS chip_id,
    toDate(now() - toIntervalDay(day_offset)) AS report_date,
    hour AS report_hour,
    'Петров Иван Сергеевич' AS customer_name,
    'ivan.petrov@bionicpro.com' AS customer_email,
    'russia' AS customer_region,
    'Москва' AS customer_branch,
    'BionicArm Pro 2024' AS prosthesis_model,
    'arm' AS prosthesis_category,
    'BP-2024-ARM-001' AS prosthesis_serial,
    toUInt32(15 + rand() % 20) AS movements_count,
    toUInt32(14 + rand() % 18) AS successful_movements,
    94.5 + (rand() % 50) / 10.0 AS success_rate,
    75.0 + (rand() % 500) / 10.0 AS avg_response_time,
    toUInt32(50 + rand() % 30) AS min_response_time,
    toUInt32(150 + rand() % 50) AS max_response_time,
    75.0 + (rand() % 250) / 10.0 AS avg_battery_level,
    toUInt8(65 + rand() % 20) AS min_battery_level,
    toUInt8(90 + rand() % 10) AS max_battery_level,
    38.0 + (rand() % 50) / 10.0 AS avg_actuator_temp,
    42.0 + (rand() % 30) / 10.0 AS max_actuator_temp,
    toUInt32(rand() % 2) AS error_count,
    toUInt32(rand() % 3) AS warning_count,
    92.0 + (rand() % 80) / 10.0 AS avg_connection_quality,
    250.0 + (rand() % 1000) / 10.0 AS avg_myo_amplitude,
    now() AS etl_processed_at,
    now() - toIntervalMinute(rand() % 60) AS source_updated_at
FROM (SELECT number AS day_offset FROM system.numbers LIMIT 7) AS days
CROSS JOIN (SELECT number + 8 AS hour FROM system.numbers LIMIT 14) AS hours
WHERE hour <= 22
  AND (SELECT count() FROM reports.user_prosthesis_stats WHERE user_id = 'ivan.petrov') = 0;

-- Вставка демо-данных для maria.sidorova (BionicArm Standard)
INSERT INTO reports.user_prosthesis_stats
SELECT
    'maria.sidorova' AS user_id,
    2 AS prosthesis_id,
    'ESP32-ARM-002-D4E5F6' AS chip_id,
    toDate(now() - toIntervalDay(day_offset)) AS report_date,
    hour AS report_hour,
    'Сидорова Мария Александровна' AS customer_name,
    'maria.sidorova@bionicpro.com' AS customer_email,
    'russia' AS customer_region,
    'Санкт-Петербург' AS customer_branch,
    'BionicArm Standard 2024' AS prosthesis_model,
    'arm' AS prosthesis_category,
    'BP-2024-ARM-002' AS prosthesis_serial,
    toUInt32(12 + rand() % 18) AS movements_count,
    toUInt32(11 + rand() % 16) AS successful_movements,
    93.0 + (rand() % 60) / 10.0 AS success_rate,
    80.0 + (rand() % 400) / 10.0 AS avg_response_time,
    toUInt32(55 + rand() % 25) AS min_response_time,
    toUInt32(140 + rand() % 60) AS max_response_time,
    70.0 + (rand() % 280) / 10.0 AS avg_battery_level,
    toUInt8(60 + rand() % 25) AS min_battery_level,
    toUInt8(88 + rand() % 12) AS max_battery_level,
    37.5 + (rand() % 60) / 10.0 AS avg_actuator_temp,
    41.0 + (rand() % 40) / 10.0 AS max_actuator_temp,
    toUInt32(rand() % 2) AS error_count,
    toUInt32(rand() % 4) AS warning_count,
    90.0 + (rand() % 90) / 10.0 AS avg_connection_quality,
    230.0 + (rand() % 1200) / 10.0 AS avg_myo_amplitude,
    now() AS etl_processed_at,
    now() - toIntervalMinute(rand() % 60) AS source_updated_at
FROM (SELECT number AS day_offset FROM system.numbers LIMIT 7) AS days
CROSS JOIN (SELECT number + 8 AS hour FROM system.numbers LIMIT 14) AS hours
WHERE hour <= 22
  AND (SELECT count() FROM reports.user_prosthesis_stats WHERE user_id = 'maria.sidorova') = 0;

-- Вставка демо-данных для alexey.kozlov (BionicHand Pro)
INSERT INTO reports.user_prosthesis_stats
SELECT
    'alexey.kozlov' AS user_id,
    3 AS prosthesis_id,
    'ESP32-HAND-001-G7H8I9' AS chip_id,
    toDate(now() - toIntervalDay(day_offset)) AS report_date,
    hour AS report_hour,
    'Козлов Алексей Дмитриевич' AS customer_name,
    'alexey.kozlov@bionicpro.com' AS customer_email,
    'russia' AS customer_region,
    'Новосибирск' AS customer_branch,
    'BionicHand Pro 2024' AS prosthesis_model,
    'hand' AS prosthesis_category,
    'BP-2024-HAND-001' AS prosthesis_serial,
    toUInt32(18 + rand() % 25) AS movements_count,
    toUInt32(17 + rand() % 22) AS successful_movements,
    95.0 + (rand() % 40) / 10.0 AS success_rate,
    70.0 + (rand() % 350) / 10.0 AS avg_response_time,
    toUInt32(45 + rand() % 25) AS min_response_time,
    toUInt32(130 + rand() % 50) AS max_response_time,
    78.0 + (rand() % 200) / 10.0 AS avg_battery_level,
    toUInt8(68 + rand() % 18) AS min_battery_level,
    toUInt8(92 + rand() % 8) AS max_battery_level,
    36.5 + (rand() % 55) / 10.0 AS avg_actuator_temp,
    40.0 + (rand() % 35) / 10.0 AS max_actuator_temp,
    toUInt32(rand() % 2) AS error_count,
    toUInt32(rand() % 2) AS warning_count,
    93.0 + (rand() % 70) / 10.0 AS avg_connection_quality,
    270.0 + (rand() % 800) / 10.0 AS avg_myo_amplitude,
    now() AS etl_processed_at,
    now() - toIntervalMinute(rand() % 60) AS source_updated_at
FROM (SELECT number AS day_offset FROM system.numbers LIMIT 7) AS days
CROSS JOIN (SELECT number + 8 AS hour FROM system.numbers LIMIT 14) AS hours
WHERE hour <= 22
  AND (SELECT count() FROM reports.user_prosthesis_stats WHERE user_id = 'alexey.kozlov') = 0;

-- Вставка демо-данных для john.mueller (BionicLeg Pro)
INSERT INTO reports.user_prosthesis_stats
SELECT
    'john.mueller' AS user_id,
    4 AS prosthesis_id,
    'ESP32-LEG-001-J0K1L2' AS chip_id,
    toDate(now() - toIntervalDay(day_offset)) AS report_date,
    hour AS report_hour,
    'John Mueller' AS customer_name,
    'john.mueller@bionicpro.eu' AS customer_email,
    'europe' AS customer_region,
    'Berlin' AS customer_branch,
    'BionicLeg Pro 2024' AS prosthesis_model,
    'leg' AS prosthesis_category,
    'BP-2024-LEG-001' AS prosthesis_serial,
    toUInt32(20 + rand() % 30) AS movements_count,
    toUInt32(19 + rand() % 27) AS successful_movements,
    96.0 + (rand() % 35) / 10.0 AS success_rate,
    65.0 + (rand() % 300) / 10.0 AS avg_response_time,
    toUInt32(40 + rand() % 20) AS min_response_time,
    toUInt32(120 + rand() % 45) AS max_response_time,
    80.0 + (rand() % 180) / 10.0 AS avg_battery_level,
    toUInt8(70 + rand() % 15) AS min_battery_level,
    toUInt8(93 + rand() % 7) AS max_battery_level,
    37.0 + (rand() % 45) / 10.0 AS avg_actuator_temp,
    41.5 + (rand() % 30) / 10.0 AS max_actuator_temp,
    toUInt32(rand() % 2) AS error_count,
    toUInt32(rand() % 3) AS warning_count,
    94.0 + (rand() % 60) / 10.0 AS avg_connection_quality,
    280.0 + (rand() % 700) / 10.0 AS avg_myo_amplitude,
    now() AS etl_processed_at,
    now() - toIntervalMinute(rand() % 60) AS source_updated_at
FROM (SELECT number AS day_offset FROM system.numbers LIMIT 7) AS days
CROSS JOIN (SELECT number + 8 AS hour FROM system.numbers LIMIT 14) AS hours
WHERE hour <= 22
  AND (SELECT count() FROM reports.user_prosthesis_stats WHERE user_id = 'john.mueller') = 0;

-- Вставка демо-данных для anna.schmidt (BionicLeg Standard)
INSERT INTO reports.user_prosthesis_stats
SELECT
    'anna.schmidt' AS user_id,
    5 AS prosthesis_id,
    'ESP32-LEG-002-M3N4O5' AS chip_id,
    toDate(now() - toIntervalDay(day_offset)) AS report_date,
    hour AS report_hour,
    'Anna Schmidt' AS customer_name,
    'anna.schmidt@bionicpro.eu' AS customer_email,
    'europe' AS customer_region,
    'Munich' AS customer_branch,
    'BionicLeg Standard 2024' AS prosthesis_model,
    'leg' AS prosthesis_category,
    'BP-2024-LEG-002' AS prosthesis_serial,
    toUInt32(14 + rand() % 22) AS movements_count,
    toUInt32(13 + rand() % 20) AS successful_movements,
    94.0 + (rand() % 50) / 10.0 AS success_rate,
    78.0 + (rand() % 380) / 10.0 AS avg_response_time,
    toUInt32(52 + rand() % 28) AS min_response_time,
    toUInt32(138 + rand() % 55) AS max_response_time,
    73.0 + (rand() % 240) / 10.0 AS avg_battery_level,
    toUInt8(63 + rand() % 22) AS min_battery_level,
    toUInt8(89 + rand() % 11) AS max_battery_level,
    37.8 + (rand() % 52) / 10.0 AS avg_actuator_temp,
    42.0 + (rand() % 32) / 10.0 AS max_actuator_temp,
    toUInt32(rand() % 2) AS error_count,
    toUInt32(rand() % 4) AS warning_count,
    91.0 + (rand() % 85) / 10.0 AS avg_connection_quality,
    245.0 + (rand() % 900) / 10.0 AS avg_myo_amplitude,
    now() AS etl_processed_at,
    now() - toIntervalMinute(rand() % 60) AS source_updated_at
FROM (SELECT number AS day_offset FROM system.numbers LIMIT 7) AS days
CROSS JOIN (SELECT number + 8 AS hour FROM system.numbers LIMIT 14) AS hours
WHERE hour <= 22
  AND (SELECT count() FROM reports.user_prosthesis_stats WHERE user_id = 'anna.schmidt') = 0;
