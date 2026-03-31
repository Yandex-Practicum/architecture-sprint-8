-- =============================================
-- BionicPRO: источники данных для ETL
-- Симулирует PostgreSQL (телеметрия) + CRM (Oracle)
-- =============================================

-- Таблица телеметрии с датчиков протезов
CREATE TABLE telemetry (
    id SERIAL PRIMARY KEY,
    prosthesis_id VARCHAR(50) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    signal_strength FLOAT NOT NULL,
    response_time_ms FLOAT NOT NULL,
    battery_level FLOAT NOT NULL,
    movement_type VARCHAR(50) NOT NULL,
    anomaly_detected BOOLEAN DEFAULT FALSE
);

-- CRM: клиенты
CREATE TABLE crm_clients (
    id SERIAL PRIMARY KEY,
    external_id VARCHAR(50) UNIQUE NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    email VARCHAR(200) NOT NULL,
    phone VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);

-- CRM: протезы
CREATE TABLE crm_prostheses (
    id SERIAL PRIMARY KEY,
    prosthesis_id VARCHAR(50) UNIQUE NOT NULL,
    client_id INTEGER REFERENCES crm_clients(id),
    model VARCHAR(100) NOT NULL,
    installation_date DATE NOT NULL,
    status VARCHAR(50) DEFAULT 'active'
);

-- =============================================
-- Тестовые данные
-- =============================================

-- 3 клиента
INSERT INTO crm_clients (external_id, first_name, last_name, email, phone) VALUES
    ('CLT-001', 'Иван', 'Петров', 'ivan.petrov@example.com', '+7-900-111-2233'),
    ('CLT-002', 'Мария', 'Сидорова', 'maria.sidorova@example.com', '+7-900-444-5566'),
    ('CLT-003', 'Алексей', 'Козлов', 'alexey.kozlov@example.com', '+7-900-777-8899');

-- 3 протеза
INSERT INTO crm_prostheses (prosthesis_id, client_id, model, installation_date, status) VALUES
    ('PRO-001', 1, 'BionicHand Pro v3', '2024-06-15', 'active'),
    ('PRO-002', 2, 'BionicHand Lite v2', '2024-08-20', 'active'),
    ('PRO-003', 3, 'BionicHand Pro v3', '2024-09-10', 'active');

-- Телеметрия: ~60 записей за 3 дня для 3 протезов
-- Типы движений: grip, release, pinch, point, wave
INSERT INTO telemetry (prosthesis_id, timestamp, signal_strength, response_time_ms, battery_level, movement_type, anomaly_detected) VALUES
    -- PRO-001, день 1
    ('PRO-001', '2024-11-01 08:00:00', 0.85, 45.2, 98.0, 'grip', FALSE),
    ('PRO-001', '2024-11-01 08:15:00', 0.82, 52.1, 97.5, 'release', FALSE),
    ('PRO-001', '2024-11-01 09:00:00', 0.78, 68.3, 95.0, 'pinch', FALSE),
    ('PRO-001', '2024-11-01 10:30:00', 0.90, 42.0, 92.0, 'grip', FALSE),
    ('PRO-001', '2024-11-01 11:00:00', 0.65, 110.5, 90.0, 'wave', TRUE),
    ('PRO-001', '2024-11-01 14:00:00', 0.88, 48.7, 85.0, 'point', FALSE),
    ('PRO-001', '2024-11-01 16:00:00', 0.80, 55.0, 78.0, 'grip', FALSE),
    -- PRO-001, день 2
    ('PRO-001', '2024-11-02 08:30:00', 0.87, 44.0, 99.0, 'grip', FALSE),
    ('PRO-001', '2024-11-02 09:15:00', 0.83, 50.5, 97.0, 'release', FALSE),
    ('PRO-001', '2024-11-02 10:00:00', 0.79, 62.0, 94.0, 'pinch', FALSE),
    ('PRO-001', '2024-11-02 11:30:00', 0.91, 40.1, 91.0, 'grip', FALSE),
    ('PRO-001', '2024-11-02 13:00:00', 0.86, 47.3, 87.0, 'wave', FALSE),
    ('PRO-001', '2024-11-02 15:00:00', 0.75, 72.0, 80.0, 'point', FALSE),
    ('PRO-001', '2024-11-02 17:00:00', 0.60, 120.0, 72.0, 'grip', TRUE),
    -- PRO-001, день 3
    ('PRO-001', '2024-11-03 09:00:00', 0.89, 43.0, 100.0, 'grip', FALSE),
    ('PRO-001', '2024-11-03 10:00:00', 0.84, 51.0, 96.0, 'release', FALSE),
    ('PRO-001', '2024-11-03 11:00:00', 0.81, 58.0, 93.0, 'pinch', FALSE),
    ('PRO-001', '2024-11-03 14:00:00', 0.88, 46.0, 88.0, 'grip', FALSE),
    ('PRO-001', '2024-11-03 16:00:00', 0.82, 54.0, 82.0, 'wave', FALSE),

    -- PRO-002, день 1
    ('PRO-002', '2024-11-01 07:30:00', 0.72, 78.0, 95.0, 'grip', FALSE),
    ('PRO-002', '2024-11-01 08:00:00', 0.70, 85.2, 93.0, 'release', FALSE),
    ('PRO-002', '2024-11-01 09:30:00', 0.68, 92.0, 90.0, 'pinch', TRUE),
    ('PRO-002', '2024-11-01 11:00:00', 0.75, 70.0, 86.0, 'grip', FALSE),
    ('PRO-002', '2024-11-01 13:00:00', 0.73, 76.5, 80.0, 'wave', FALSE),
    ('PRO-002', '2024-11-01 15:00:00', 0.69, 88.0, 74.0, 'point', FALSE),
    ('PRO-002', '2024-11-01 17:00:00', 0.64, 105.0, 68.0, 'grip', TRUE),
    -- PRO-002, день 2
    ('PRO-002', '2024-11-02 08:00:00', 0.74, 75.0, 96.0, 'grip', FALSE),
    ('PRO-002', '2024-11-02 09:00:00', 0.71, 82.0, 93.0, 'release', FALSE),
    ('PRO-002', '2024-11-02 10:30:00', 0.69, 90.0, 89.0, 'pinch', FALSE),
    ('PRO-002', '2024-11-02 12:00:00', 0.76, 68.0, 84.0, 'grip', FALSE),
    ('PRO-002', '2024-11-02 14:00:00', 0.72, 79.0, 78.0, 'wave', FALSE),
    ('PRO-002', '2024-11-02 16:00:00', 0.67, 95.0, 72.0, 'point', TRUE),
    -- PRO-002, день 3
    ('PRO-002', '2024-11-03 08:30:00', 0.73, 77.0, 97.0, 'grip', FALSE),
    ('PRO-002', '2024-11-03 10:00:00', 0.70, 84.0, 92.0, 'release', FALSE),
    ('PRO-002', '2024-11-03 11:30:00', 0.68, 91.0, 87.0, 'pinch', FALSE),
    ('PRO-002', '2024-11-03 14:00:00', 0.75, 72.0, 81.0, 'grip', FALSE),
    ('PRO-002', '2024-11-03 16:00:00', 0.71, 80.0, 75.0, 'wave', FALSE),

    -- PRO-003, день 1
    ('PRO-003', '2024-11-01 09:00:00', 0.92, 38.0, 100.0, 'grip', FALSE),
    ('PRO-003', '2024-11-01 09:30:00', 0.90, 41.0, 98.0, 'release', FALSE),
    ('PRO-003', '2024-11-01 10:00:00', 0.88, 45.0, 96.0, 'pinch', FALSE),
    ('PRO-003', '2024-11-01 12:00:00', 0.93, 36.0, 92.0, 'grip', FALSE),
    ('PRO-003', '2024-11-01 14:00:00', 0.91, 39.5, 88.0, 'wave', FALSE),
    ('PRO-003', '2024-11-01 16:00:00', 0.87, 47.0, 83.0, 'point', FALSE),
    ('PRO-003', '2024-11-01 18:00:00', 0.85, 50.0, 77.0, 'grip', FALSE),
    -- PRO-003, день 2
    ('PRO-003', '2024-11-02 08:00:00', 0.91, 39.0, 99.0, 'grip', FALSE),
    ('PRO-003', '2024-11-02 09:00:00', 0.89, 42.0, 97.0, 'release', FALSE),
    ('PRO-003', '2024-11-02 10:30:00', 0.87, 46.0, 94.0, 'pinch', FALSE),
    ('PRO-003', '2024-11-02 12:00:00', 0.92, 37.0, 90.0, 'grip', FALSE),
    ('PRO-003', '2024-11-02 14:00:00', 0.90, 40.0, 86.0, 'wave', FALSE),
    ('PRO-003', '2024-11-02 16:00:00', 0.86, 48.0, 80.0, 'point', FALSE),
    -- PRO-003, день 3
    ('PRO-003', '2024-11-03 09:00:00', 0.93, 37.0, 100.0, 'grip', FALSE),
    ('PRO-003', '2024-11-03 10:00:00', 0.90, 41.0, 96.0, 'release', FALSE),
    ('PRO-003', '2024-11-03 11:00:00', 0.88, 44.0, 93.0, 'pinch', FALSE),
    ('PRO-003', '2024-11-03 13:00:00', 0.94, 35.0, 89.0, 'grip', FALSE),
    ('PRO-003', '2024-11-03 15:00:00', 0.91, 40.0, 84.0, 'wave', FALSE),
    ('PRO-003', '2024-11-03 17:00:00', 0.87, 46.0, 78.0, 'point', FALSE);

-- Индексы для быстрого извлечения
CREATE INDEX idx_telemetry_prosthesis ON telemetry(prosthesis_id);
CREATE INDEX idx_telemetry_timestamp ON telemetry(timestamp);
