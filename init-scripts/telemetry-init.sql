-- База данных телеметрии
CREATE TABLE IF NOT EXISTS device_telemetry (
    telemetry_id BIGSERIAL PRIMARY KEY,
    device_id VARCHAR(50) NOT NULL,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    battery_level DECIMAL(5,2) CHECK (battery_level >= 0 AND battery_level <= 100),
    temperature DECIMAL(5,2),
    pressure_sensor_reading DECIMAL(8,4),
    flexion_angle DECIMAL(6,2),
    step_count INTEGER DEFAULT 0,
    error_code INTEGER DEFAULT 0,
    accelerometer_x DECIMAL(8,4),
    accelerometer_y DECIMAL(8,4),
    accelerometer_z DECIMAL(8,4)
);

COMMENT ON TABLE device_telemetry IS 'Телеметрия с датчиков протезов';
COMMENT ON COLUMN device_telemetry.temperature IS 'Температура протеза в градусах Цельсия';
COMMENT ON COLUMN device_telemetry.pressure_sensor_reading IS 'Давление в точке контакта в кПа';
COMMENT ON COLUMN device_telemetry.flexion_angle IS 'Угол сгиба сустава в градусах';
COMMENT ON COLUMN device_telemetry.error_code IS 'Код ошибки устройства (0 = нет ошибок)';

CREATE INDEX IF NOT EXISTS idx_telemetry_device_timestamp ON device_telemetry(device_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_telemetry_timestamp ON device_telemetry(timestamp);

-- Вставляем тестовые данные телеметрии (опционально)
INSERT INTO device_telemetry (device_id, battery_level, temperature, pressure_sensor_reading, flexion_angle, step_count, accelerometer_x, accelerometer_y, accelerometer_z) VALUES
('device_001', 85.5, 28.5, 12.3456, 45.2, 0, 0.1234, -0.9876, 0.5432),
('device_001', 84.2, 29.1, 11.8765, 42.1, 0, 0.2345, -0.8765, 0.6543),
('device_003', 92.0, 26.8, 15.4321, 15.5, 125, 0.8765, 0.1234, -0.2345),
('device_002', 78.3, 30.2, 10.5678, 38.7, 0, 0.3456, -0.7654, 0.7654);