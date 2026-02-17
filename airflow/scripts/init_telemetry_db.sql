CREATE TABLE IF NOT EXISTS sensor_data (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    device_id VARCHAR(50) NOT NULL,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    sensor_type VARCHAR(50) NOT NULL,
    sensor_value JSONB NOT NULL,
    processing_time_ms FLOAT,
    action_executed VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_sensor_data_user_id ON sensor_data(user_id);
CREATE INDEX idx_sensor_data_device_id ON sensor_data(device_id);
CREATE INDEX idx_sensor_data_timestamp ON sensor_data(timestamp);
CREATE INDEX idx_sensor_data_user_timestamp ON sensor_data(user_id, timestamp DESC);

INSERT INTO sensor_data (user_id, device_id, sensor_type, sensor_value, processing_time_ms, action_executed)
VALUES 
    (1, 'DEVICE-001', 'myo', '{"signal_strength": 0.85, "noise_level": 0.12}', 45.3, 'grip_open'),
    (1, 'DEVICE-001', 'myo', '{"signal_strength": 0.92, "noise_level": 0.08}', 38.7, 'grip_close'),
    (1, 'DEVICE-001', 'battery', '{"voltage": 12.5, "charge_percent": 87}', 5.2, NULL),
    (2, 'DEVICE-002', 'myo', '{"signal_strength": 0.78, "noise_level": 0.15}', 52.1, 'rotate_wrist'),
    (2, 'DEVICE-002', 'actuator', '{"torque": 2.3, "angle": 45}', 12.8, 'rotate_wrist'),
    (3, 'DEVICE-003', 'myo', '{"signal_strength": 0.88, "noise_level": 0.10}', 41.5, 'pinch'),
    (3, 'DEVICE-003', 'battery', '{"voltage": 11.8, "charge_percent": 65}', 4.9, NULL);

COMMENT ON TABLE sensor_data IS 'Телеметрия от чипов бионических протезов';
COMMENT ON COLUMN sensor_data.user_id IS 'ID пользователя (пилота протеза)';
COMMENT ON COLUMN sensor_data.device_id IS 'Уникальный идентификатор протеза';
COMMENT ON COLUMN sensor_data.sensor_type IS 'Тип датчика: myo (миодатчик), battery (батарея), actuator (актуатор)';
COMMENT ON COLUMN sensor_data.sensor_value IS 'JSON с показаниями датчика';
COMMENT ON COLUMN sensor_data.processing_time_ms IS 'Время обработки сигнала чипом ESP32 в миллисекундах';
COMMENT ON COLUMN sensor_data.action_executed IS 'Действие, выполненное протезом по команде';
