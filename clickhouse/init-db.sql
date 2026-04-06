-- Инициализация ClickHouse базы данных для аналитики

-- Создаем базу данных
CREATE DATABASE IF NOT EXISTS analytics_db;

-- Используем созданную базу
USE analytics_db;

-- Таблица фактов телеметрии протезов
CREATE TABLE IF NOT EXISTS telemetry_facts (
    telemetry_id UInt64,
    buyer_id UInt64,
    prosthetic_serial String,
    event_timestamp DateTime,
    battery_level Float32,
    movement_count UInt32,
    error_count UInt16,
    usage_hours Float32,
    sync_date Date
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(event_timestamp)
ORDER BY (buyer_id, event_timestamp)
SETTINGS index_granularity = 8192;

-- Таблица измерений клиентов (из CRM)
CREATE TABLE IF NOT EXISTS client_dimension (
    buyer_id UInt64,
    full_name String,
    email String,
    phone String,
    registration_date DateTime,
    last_visit_date DateTime,
    status String,
    updated_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(updated_at)
ORDER BY buyer_id
SETTINGS index_granularity = 8192;

-- Таблица измерений протезов (из CRM)
CREATE TABLE IF NOT EXISTS prosthetic_dimension (
    prosthetic_id UInt64,
    buyer_id UInt64,
    prosthetic_type String,
    manufacture_date Date,
    delivery_date Date,
    serial_number String,
    warranty_months UInt16,
    price Decimal(10,2),
    updated_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (buyer_id, prosthetic_id)
SETTINGS index_granularity = 8192;

-- Витрина данных для отчетов пользователей
CREATE TABLE IF NOT EXISTS user_reports_mart (
    buyer_id UInt64,
    full_name String,
    email String,
    prosthetic_type String,
    serial_number String,
    total_usage_hours Float32,
    total_movements UInt64,
    total_errors UInt32,
    avg_battery_level Float32,
    last_telemetry_date DateTime,
    report_period_start Date,
    report_period_end Date,
    created_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(created_at)
PARTITION BY toYYYYMM(report_period_end)
ORDER BY (buyer_id, report_period_end)
SETTINGS index_granularity = 8192;

-- Вставляем тестовые данные телеметрии
INSERT INTO telemetry_facts (telemetry_id, buyer_id, prosthetic_serial, event_timestamp, battery_level, movement_count, error_count, usage_hours, sync_date) VALUES
(1, 648821, 'BP-ARM-2023-001', now() - INTERVAL 7 DAY, 85.5, 1523, 2, 6.5, today() - INTERVAL 7 DAY),
(2, 648821, 'BP-ARM-2023-001', now() - INTERVAL 6 DAY, 78.2, 1834, 1, 7.2, today() - INTERVAL 6 DAY),
(3, 648821, 'BP-ARM-2023-001', now() - INTERVAL 5 DAY, 91.0, 1245, 0, 5.8, today() - INTERVAL 5 DAY),
(4, 6488214, 'BP-HAND-2023-001', now() - INTERVAL 7 DAY, 88.3, 2156, 3, 8.1, today() - INTERVAL 7 DAY),
(5, 6488214, 'BP-HAND-2023-001', now() - INTERVAL 6 DAY, 82.7, 1987, 2, 7.5, today() - INTERVAL 6 DAY),
(6, 6488211, 'BP-ARM-PRO-2023-001', now() - INTERVAL 7 DAY, 92.5, 2543, 0, 9.3, today() - INTERVAL 7 DAY),
(7, 6488211, 'BP-ARM-PRO-2023-001', now() - INTERVAL 6 DAY, 87.8, 2234, 1, 8.7, today() - INTERVAL 6 DAY),
(8, 6488219, 'BP-HAND-2023-002', now() - INTERVAL 7 DAY, 75.4, 1678, 4, 6.9, today() - INTERVAL 7 DAY),
(9, 648801, 'BP-ARM-PREM-2023-001', now() - INTERVAL 7 DAY, 95.2, 3012, 0, 10.2, today() - INTERVAL 7 DAY),
(10, 648801, 'BP-ARM-PREM-2023-001', now() - INTERVAL 6 DAY, 89.6, 2876, 1, 9.8, today() - INTERVAL 6 DAY);
