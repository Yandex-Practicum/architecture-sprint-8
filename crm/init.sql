-- CRM OLTP: таблицы для CDC (Debezium) — телеметрия, пользователи
-- Запросы на выгрузку идут в ClickHouse через Kafka, не нагружая эту БД

CREATE TABLE IF NOT EXISTS telemetry_events (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    event_time TIMESTAMPTZ NOT NULL,
    metric_name VARCHAR(100),
    value NUMERIC(12,4),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Для объединения данных в витрине (task: MaterializedView)
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL UNIQUE,
    email VARCHAR(255),
    full_name VARCHAR(255),
    prosthesis_id VARCHAR(255),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Начальные данные (будут захвачены Debezium snapshot)
INSERT INTO users (user_id, email, full_name, prosthesis_id)
VALUES
    ('user1-id', 'user1@example.com', 'User One', 'prosthesis-1'),
    ('user2-id', 'user2@example.com', 'User Two', 'prosthesis-2')
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO telemetry_events (user_id, event_time, metric_name, value)
VALUES
    ('user1-id', NOW() - INTERVAL '1 day', 'usage_hours', 4.5),
    ('user1-id', NOW() - INTERVAL '1 day', 'steps', 1200),
    ('user2-id', NOW() - INTERVAL '1 day', 'usage_hours', 3.0);

-- Публикация для Debezium pgoutput (logical replication)
CREATE PUBLICATION debezium_publication FOR TABLE telemetry_events, users;
