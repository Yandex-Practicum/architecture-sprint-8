-- Инициализация таблицы sensor_telemetry в PostgreSQL
-- Этот скрипт выполняется при первом запуске контейнера PostgreSQL

-- Создание таблицы для хранения данных телеметрии датчиков
CREATE TABLE IF NOT EXISTS sensor_telemetry (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    device_id VARCHAR(255) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    sensor_type VARCHAR(50),
    sensor_value FLOAT,
    movement_type VARCHAR(50),
    movement_count INTEGER DEFAULT 0,
    usage_duration_seconds INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Создание индексов для оптимизации запросов
CREATE INDEX IF NOT EXISTS idx_sensor_telemetry_user_timestamp 
ON sensor_telemetry(user_id, timestamp);

CREATE INDEX IF NOT EXISTS idx_sensor_telemetry_timestamp 
ON sensor_telemetry(timestamp);

CREATE INDEX IF NOT EXISTS idx_sensor_telemetry_device 
ON sensor_telemetry(device_id);

-- Комментарии к таблице и полям
COMMENT ON TABLE sensor_telemetry IS 'Данные телеметрии с датчиков протеза';
COMMENT ON COLUMN sensor_telemetry.user_id IS 'Идентификатор пользователя';
COMMENT ON COLUMN sensor_telemetry.device_id IS 'Идентификатор устройства протеза';
COMMENT ON COLUMN sensor_telemetry.timestamp IS 'Временная метка записи';
COMMENT ON COLUMN sensor_telemetry.sensor_type IS 'Тип датчика (pressure, temperature, etc.)';
COMMENT ON COLUMN sensor_telemetry.sensor_value IS 'Значение датчика';
COMMENT ON COLUMN sensor_telemetry.movement_type IS 'Тип движения (grip, release, flex, etc.)';
COMMENT ON COLUMN sensor_telemetry.movement_count IS 'Количество движений';
COMMENT ON COLUMN sensor_telemetry.usage_duration_seconds IS 'Длительность использования в секундах';

-- Примеры тестовых данных (опционально, можно закомментировать)
-- INSERT INTO sensor_telemetry (user_id, device_id, timestamp, sensor_type, sensor_value, movement_type, movement_count, usage_duration_seconds)
-- VALUES 
--     (12345, 'DEV-001', '2024-01-15 10:00:00', 'pressure', 45.5, 'grip', 1, 120),
--     (12345, 'DEV-001', '2024-01-15 10:05:00', 'pressure', 48.2, 'release', 1, 125),
--     (12345, 'DEV-001', '2024-01-15 11:00:00', 'temperature', 32.1, 'flex', 2, 180);
