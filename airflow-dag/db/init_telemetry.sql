-- Создание базы данных для телеметрии

-- Таблица сырых данных телеметрии с протезов
CREATE TABLE IF NOT EXISTS prosthesis_telemetry (
                                                    id SERIAL PRIMARY KEY,
                                                    user_id VARCHAR(100) NOT NULL,
    prosthesis_id VARCHAR(100),
    event_time TIMESTAMP NOT NULL,
    movement_type VARCHAR(50),
    reaction_time_ms INTEGER,
    signal_quality DECIMAL(5,4),
    battery_level INTEGER,
    temperature DECIMAL(5,2),
    signal_strength_dbm INTEGER,
    is_noise BOOLEAN DEFAULT FALSE,
    firmware_version VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

-- Создание индексов
CREATE INDEX IF NOT EXISTS idx_telemetry_user_id ON prosthesis_telemetry(user_id);
CREATE INDEX IF NOT EXISTS idx_telemetry_event_time ON prosthesis_telemetry(event_time);
CREATE INDEX IF NOT EXISTS idx_telemetry_user_time ON prosthesis_telemetry(user_id, event_time);

-- Вывод информации о создании
DO $$
BEGIN
    RAISE NOTICE 'Table prosthesis_telemetry created successfully';
END $$;