-- Инициализация базы данных для телеметрии
CREATE TABLE IF NOT EXISTS telemetry_data (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    prosthesis_id VARCHAR(255) NOT NULL,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    action_type VARCHAR(50),
    response_time_ms INTEGER,
    battery_level FLOAT,
    signal_quality FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Создание индексов для оптимизации запросов
CREATE INDEX IF NOT EXISTS idx_telemetry_user_id ON telemetry_data(user_id);
CREATE INDEX IF NOT EXISTS idx_telemetry_prosthesis_id ON telemetry_data(prosthesis_id);
CREATE INDEX IF NOT EXISTS idx_telemetry_timestamp ON telemetry_data(timestamp);
CREATE INDEX IF NOT EXISTS idx_telemetry_user_timestamp ON telemetry_data(user_id, timestamp);

-- Вставка тестовых данных
INSERT INTO telemetry_data (user_id, prosthesis_id, timestamp, action_type, response_time_ms, battery_level, signal_quality)
VALUES
    ('user1', 'prosthesis_001', '2024-01-15 10:00:00', 'grasp', 95, 85.5, 92.3),
    ('user1', 'prosthesis_001', '2024-01-15 10:01:00', 'release', 98, 85.2, 91.8),
    ('user1', 'prosthesis_001', '2024-01-15 10:02:00', 'flex', 97, 85.0, 92.1),
    ('user2', 'prosthesis_002', '2024-02-20 14:00:00', 'grasp', 88, 90.2, 94.5),
    ('user2', 'prosthesis_002', '2024-02-20 14:01:00', 'release', 92, 90.0, 94.2),
    ('prothetic1', 'prosthesis_003', '2024-03-10 09:00:00', 'grasp', 102, 78.5, 89.2),
    ('prothetic1', 'prosthesis_003', '2024-03-10 09:01:00', 'flex', 105, 78.3, 88.9)
ON CONFLICT DO NOTHING;
