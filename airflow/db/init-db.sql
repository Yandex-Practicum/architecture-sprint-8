-- =============================================================================
-- Инициализация базы данных Airflow-источника (CRM + Telemetry)
-- =============================================================================

CREATE DATABASE sample;
GRANT ALL PRIVILEGES ON DATABASE sample TO airflow;

-- =============================================================================
-- CRM: таблица клиентов
-- email совпадает с email пользователей Keycloak (reports-realm)
-- =============================================================================
CREATE TABLE IF NOT EXISTS clients (
    client_id       BIGINT       NOT NULL PRIMARY KEY,
    full_name       TEXT         NOT NULL,
    email           TEXT         NOT NULL UNIQUE,
    phone           TEXT,
    segment         VARCHAR(50),     -- 'premium' | 'standard' | 'trial'
    contract_start  DATE,
    contract_end    DATE,
    region          VARCHAR(100),
    deleted_at      TIMESTAMP        -- NULL = активен
);

INSERT INTO clients (client_id, full_name, email, phone, segment, contract_start, contract_end, region) VALUES
    (1001, 'User One',       'user1@example.com',      '+7-900-001-0001', 'premium',  '2024-01-01', NULL,         'Moscow'),
    (1002, 'User Two',       'user2@example.com',      '+7-900-001-0002', 'standard', '2024-03-15', NULL,         'Saint Petersburg'),
    (1003, 'Admin One',      'admin1@example.com',     '+7-900-001-0003', 'premium',  '2023-06-01', NULL,         'Novosibirsk'),
    (1004, 'Prothetic One',  'prothetic1@example.com', '+7-900-001-0004', 'trial',    '2025-01-01', '2026-12-31', 'Kazan'),
    (1005, 'Prothetic Two',  'prothetic2@example.com', '+7-900-001-0005', 'standard', '2024-09-01', NULL,         'Yekaterinburg'),
    (1006, 'Prothetic Three','prothetic3@example.com', '+7-900-001-0006', 'premium',  '2023-11-01', NULL,         'Samara')
ON CONFLICT (client_id) DO NOTHING;

-- =============================================================================
-- Telemetry: события устройств за последние 3 дня
-- event_ts = CURRENT_DATE - N, чтобы DAG (который берёт CURRENT_DATE - 1)
-- всегда находил данные за вчера при первом запуске
-- =============================================================================
CREATE TABLE IF NOT EXISTS telemetry (
    event_id    BIGSERIAL    PRIMARY KEY,
    client_id   BIGINT       NOT NULL REFERENCES clients(client_id),
    device_id   VARCHAR(100) NOT NULL,
    event_type  VARCHAR(100) NOT NULL,  -- 'step_count' | 'battery' | 'sync' | 'calibration'
    value       DOUBLE PRECISION,
    event_ts    TIMESTAMP    NOT NULL
);

-- Вставляем события за CURRENT_DATE - 1 (вчера) и CURRENT_DATE - 2 (позавчера)
-- Каждый клиент: 2 устройства × несколько типов событий × 2 дня

INSERT INTO telemetry (client_id, device_id, event_type, value, event_ts)
SELECT
    c.client_id,
    'DEV-' || c.client_id || '-' || d.device_num   AS device_id,
    e.event_type,
    e.base_value + (random() * e.jitter)            AS value,
    (CURRENT_DATE - d.days_ago)::TIMESTAMP + (interval '1 hour' * (random() * 23))
FROM clients c
CROSS JOIN (
    VALUES (1, 1), (2, 1),   -- device 1 and 2, yesterday
           (1, 2), (2, 2)    -- device 1 and 2, day before yesterday
) AS d(device_num, days_ago)
CROSS JOIN (
    VALUES ('step_count',   3200,  800),
           ('battery',        72,   25),
           ('sync',            1,    0),
           ('calibration',   0.5,  0.3)
) AS e(event_type, base_value, jitter);

-- =============================================================================
-- Дополнительные единичные события для разнообразия агрегатов
-- =============================================================================
INSERT INTO telemetry (client_id, device_id, event_type, value, event_ts) VALUES
    (1001, 'DEV-1001-1', 'step_count',  8200, (CURRENT_DATE - 1)::TIMESTAMP + interval '7 hours'),
    (1001, 'DEV-1001-2', 'step_count',  5100, (CURRENT_DATE - 1)::TIMESTAMP + interval '18 hours'),
    (1002, 'DEV-1002-1', 'battery',       45, (CURRENT_DATE - 1)::TIMESTAMP + interval '9 hours'),
    (1003, 'DEV-1003-1', 'sync',           1, (CURRENT_DATE - 1)::TIMESTAMP + interval '6 hours'),
    (1003, 'DEV-1003-3', 'step_count', 11500, (CURRENT_DATE - 1)::TIMESTAMP + interval '20 hours'),
    (1004, 'DEV-1004-1', 'calibration', 0.85, (CURRENT_DATE - 1)::TIMESTAMP + interval '11 hours'),
    (1005, 'DEV-1005-2', 'step_count',  6700, (CURRENT_DATE - 1)::TIMESTAMP + interval '15 hours'),
    (1006, 'DEV-1006-1', 'battery',       88, (CURRENT_DATE - 1)::TIMESTAMP + interval '8 hours');
