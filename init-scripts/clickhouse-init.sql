-- Создаем базу данных
CREATE DATABASE IF NOT EXISTS prosthetics_mart
ENGINE = Atomic;

USE prosthetics_mart;

-- 1. Таблица для сырых данных (landing)
CREATE TABLE IF NOT EXISTS telemetry_landing
(
    telemetry_id UInt64,
    device_id String,
    timestamp DateTime64(3, 'UTC'),
    battery_level Float32,
    temperature Float32,
    pressure_sensor_reading Float32,
    flexion_angle Float32,
    step_count UInt32,
    error_code UInt32,
    accelerometer_x Float32,
    accelerometer_y Float32,
    accelerometer_z Float32,
    ingested_at DateTime DEFAULT now(),
    source_table String
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (device_id, timestamp)
SETTINGS index_granularity = 8192;

-- 2. Справочник клиентов
CREATE TABLE IF NOT EXISTS clients_dimension
(
    client_id UInt32,
    external_client_id String,
    first_name String,
    last_name String,
    email String,
    phone Nullable(String),
    date_of_birth Nullable(Date),
    registration_date DateTime,
    is_active UInt8,
    inserted_at DateTime DEFAULT now(),
    updated_at DateTime DEFAULT now(),
    deleted_at Nullable(DateTime)
)
ENGINE = MergeTree()
ORDER BY (client_id, external_client_id)
SETTINGS index_granularity = 8192;

-- 3. Справочник устройств
CREATE TABLE IF NOT EXISTS devices_dimension
(
    device_id String,
    client_id UInt32,
    device_name Nullable(String),
    device_type String,
    serial_number String,
    manufacturing_date Nullable(Date),
    activation_date DateTime,
    warranty_until Nullable(Date),
    is_active UInt8,
    last_maintenance_date Nullable(Date),
    inserted_at DateTime DEFAULT now(),
    updated_at DateTime DEFAULT now(),
    deleted_at Nullable(DateTime)
)
ENGINE = MergeTree()
ORDER BY (device_id, client_id)
SETTINGS index_granularity = 8192;

-- 4. Витрина: агрегированные данные по дням
CREATE TABLE IF NOT EXISTS client_telemetry_daily_mart
(
    client_id UInt32,
    external_client_id String,
    client_name String,
    email String,
    device_id String,
    device_name String,
    device_type String,
    period_date Date,

    -- Метрики
    telemetry_count UInt32,
    avg_battery_level Float32,
    min_battery_level Float32,
    max_battery_level Float32,
    avg_temperature Float32,
    max_temperature Float32,
    avg_pressure Float32,
    max_pressure Float32,
    avg_flexion_angle Float32,
    max_flexion_angle Float32,
    total_steps UInt32,
    error_count UInt32,
    active_hours Float32,

    -- Временные метки
    first_telemetry_time DateTime,
    last_telemetry_time DateTime,

    -- Акселерометр
    avg_acceleration_magnitude Float32,
    max_acceleration_magnitude Float32,
    movement_intensity Float32,

    -- Флаги
    has_low_battery UInt8,
    has_high_temperature UInt8,
    has_pressure_alert UInt8,

    -- Метаданные
    calculated_at DateTime DEFAULT now(),
    period_start DateTime MATERIALIZED toStartOfDay(period_date),
    period_end DateTime MATERIALIZED toStartOfDay(period_date) + INTERVAL 1 DAY
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(period_date)
ORDER BY (external_client_id, device_id, period_date)
TTL period_date + INTERVAL 2 YEAR DELETE
SETTINGS index_granularity = 8192;

-- 5. Представление для API
CREATE TABLE IF NOT EXISTS client_telemetry_api_view
(
    external_client_id String,
    period_date Date,
    device_id String,
    device_name String,
    device_type String,
    daily_summary String,
    battery_status String,
    device_health_score Float32,
    activity_level String,
    metrics Nested(
        name String,
        value Float32,
        unit String
    ),
    alerts Array(String),
    recommendations Array(String),
    calculated_at DateTime
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(period_date)
ORDER BY (external_client_id, period_date, device_id)
SETTINGS index_granularity = 8192;

-- 6. Представление для внешнего API (без вложенных структур)
CREATE VIEW IF NOT EXISTS api_client_telemetry AS
SELECT 
    external_client_id,
    period_date,
    device_id,
    device_name,
    device_type,
    avg_battery_level,
    min_battery_level,
    max_battery_level,
    avg_temperature,
    total_steps,
    active_hours,
    error_count AS alerts_count,
    100.0 - (error_count * 5.0) - if(has_low_battery=1, 10, 0) - if(has_high_temperature=1, 15, 0) AS device_health,
    telemetry_count / 3600.0 AS daily_usage_hours
FROM client_telemetry_daily_mart;
