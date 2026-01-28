-- Создаем базу данных для витрины
CREATE DATABASE IF NOT EXISTS prosthetics_mart
ENGINE = Atomic;

USE prosthetics_mart;

-- Таблица для хранения сырых данных (стадия landing)
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

-- Таблица для справочника клиентов
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
ENGINE = ReplacingMergeTree(updated_at)
PARTITION BY bitShiftRight(client_id, 20)  -- Для распределения по партициям
ORDER BY (client_id, external_client_id)
SETTINGS index_granularity = 8192;

-- Таблица для справочника устройств
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
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (device_id, client_id)
SETTINGS index_granularity = 8192;

-- Основная витрина данных (агрегированная по дням)
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
    
    -- Агрегированные метрики
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
    
    -- Данные акселерометра (агрегированные)
    avg_acceleration_magnitude Float32,
    max_acceleration_magnitude Float32,
    movement_intensity Float32,
    
    -- Флаги и статусы
    has_low_battery UInt8,
    has_high_temperature UInt8,
    has_pressure_alert UInt8,
    
    -- Метаданные
    calculated_at DateTime DEFAULT now(),
    period_start DateTime MATERIALIZED toStartOfDay(period_date),
    period_end DateTime MATERIALIZED toStartOfDay(period_date) + interval 1 day
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(period_date)
ORDER BY (external_client_id, device_id, period_date)
TTL period_date + INTERVAL 2 YEAR DELETE
SETTINGS index_granularity = 8192;

-- Витрина для API (оптимизированная для быстрого доступа)
CREATE TABLE IF NOT EXISTS client_telemetry_api_view
(
    external_client_id String,
    period_date Date,
    device_id String,
    device_name String,
    device_type String,
    
    -- Основные метрики для отображения
    daily_summary String,
    battery_status String,
    device_health_score Float32,
    activity_level String,
    
    -- Детальные метрики (вложенная структура)
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

-- Материализованное представление для быстрых агрегаций
CREATE MATERIALIZED VIEW IF NOT EXISTS client_telemetry_daily_mv
TO client_telemetry_daily_mart
AS
SELECT 
    c.client_id,
    c.external_client_id,
    concat(c.first_name, ' ', c.last_name) as client_name,
    c.email,
    d.device_id,
    coalesce(d.device_name, d.device_id) as device_name,
    d.device_type,
    toDate(t.timestamp) as period_date,
    
    count() as telemetry_count,
    avg(t.battery_level) as avg_battery_level,
    min(t.battery_level) as min_battery_level,
    max(t.battery_level) as max_battery_level,
    avg(t.temperature) as avg_temperature,
    max(t.temperature) as max_temperature,
    avg(t.pressure_sensor_reading) as avg_pressure,
    max(t.pressure_sensor_reading) as max_pressure,
    avg(t.flexion_angle) as avg_flexion_angle,
    max(t.flexion_angle) as max_flexion_angle,
    sum(t.step_count) as total_steps,
    sum(if(t.error_code > 0, 1, 0)) as error_count,
    countDistinct(toHour(t.timestamp)) as active_hours,
    
    min(t.timestamp) as first_telemetry_time,
    max(t.timestamp) as last_telemetry_time,
    
    avg(sqrt(t.accelerometer_x*t.accelerometer_x + 
             t.accelerometer_y*t.accelerometer_y + 
             t.accelerometer_z*t.accelerometer_z)) as avg_acceleration_magnitude,
    max(sqrt(t.accelerometer_x*t.accelerometer_x + 
             t.accelerometer_y*t.accelerometer_y + 
             t.accelerometer_z*t.accelerometer_z)) as max_acceleration_magnitude,
    sum(if(sqrt(t.accelerometer_x*t.accelerometer_x + 
                t.accelerometer_y*t.accelerometer_y + 
                t.accelerometer_z*t.accelerometer_z) > 1.0, 1, 0)) as movement_intensity,
    
    if(min(t.battery_level) < 20, 1, 0) as has_low_battery,
    if(max(t.temperature) > 40, 1, 0) as has_high_temperature,
    if(max(t.pressure_sensor_reading) > 50, 1, 0) as has_pressure_alert
    
FROM telemetry_landing t
JOIN devices_dimension d ON t.device_id = d.device_id
JOIN clients_dimension c ON d.client_id = c.client_id
WHERE c.is_active = 1 AND d.is_active = 1
GROUP BY 
    c.client_id,
    c.external_client_id,
    client_name,
    c.email,
    d.device_id,
    device_name,
    d.device_type,
    period_date;

-- Создаем представление для API (с учетом безопасности)
CREATE VIEW IF NOT EXISTS api_client_telemetry
(
    external_client_id String,
    period_date Date,
    device_id String,
    device_name String,
    device_type String,
    battery_level_avg Float32,
    battery_level_min Float32,
    battery_level_max Float32,
    temperature_avg Float32,
    steps_total UInt32,
    activity_hours UInt32,
    alerts_count UInt32,
    device_health Float32,
    daily_usage_hours Float32
) AS
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
    error_count,
    100.0 - (error_count * 5.0) - if(has_low_battery=1, 10, 0) - if(has_high_temperature=1, 15, 0) as device_health,
    telemetry_count / 3600.0 as daily_usage_hours  -- Предполагаем 1 запись в секунду
FROM client_telemetry_daily_mart;
