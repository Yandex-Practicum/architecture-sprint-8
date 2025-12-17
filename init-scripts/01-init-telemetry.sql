-- Инициализация базы данных для телеметрии
-- Создание таблицы telemetry_data для хранения данных с протезов

CREATE TABLE IF NOT EXISTS telemetry_data (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    prosthesis_id VARCHAR(100) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    response_time_ms FLOAT,
    action_type VARCHAR(50),
    battery_level FLOAT,
    duration_seconds INTEGER
);

-- Создание индексов для оптимизации запросов
CREATE INDEX IF NOT EXISTS idx_telemetry_user_id ON telemetry_data(user_id);
CREATE INDEX IF NOT EXISTS idx_telemetry_prosthesis_id ON telemetry_data(prosthesis_id);
CREATE INDEX IF NOT EXISTS idx_telemetry_created_at ON telemetry_data(created_at);
CREATE INDEX IF NOT EXISTS idx_telemetry_user_date ON telemetry_data(user_id, DATE(created_at));

-- Вставка тестовых данных (для демонстрации)
INSERT INTO telemetry_data (user_id, prosthesis_id, created_at, response_time_ms, action_type, battery_level, duration_seconds)
VALUES
    (1, 'PROT-001', CURRENT_TIMESTAMP - INTERVAL '1 day', 85.5, 'grasp', 75.0, 120),
    (1, 'PROT-001', CURRENT_TIMESTAMP - INTERVAL '1 day', 92.3, 'release', 74.5, 110),
    (1, 'PROT-001', CURRENT_TIMESTAMP - INTERVAL '1 day', 78.1, 'flex', 73.8, 95),
    (1, 'PROT-001', CURRENT_TIMESTAMP - INTERVAL '2 days', 88.2, 'grasp', 80.0, 130),
    (1, 'PROT-001', CURRENT_TIMESTAMP - INTERVAL '2 days', 95.4, 'release', 79.2, 115)
ON CONFLICT DO NOTHING;

