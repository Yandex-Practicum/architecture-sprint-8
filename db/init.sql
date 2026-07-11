-- Source tables for the reports ETL pipeline

CREATE TABLE IF NOT EXISTS crm_clients (
    user_id       VARCHAR(100) PRIMARY KEY,
    username      VARCHAR(100) NOT NULL,
    email         VARCHAR(200),
    first_name    VARCHAR(100),
    last_name     VARCHAR(100),
    prosthesis_id VARCHAR(100),
    prosthesis_type VARCHAR(100),
    purchase_date DATE,
    is_active     BOOLEAN DEFAULT true
);

CREATE TABLE IF NOT EXISTS telemetry (
    id              SERIAL PRIMARY KEY,
    user_id         VARCHAR(100) NOT NULL,
    prosthesis_id   VARCHAR(100) NOT NULL,
    recorded_at     TIMESTAMP NOT NULL DEFAULT NOW(),
    movement_type   VARCHAR(50) NOT NULL,
    signal_strength FLOAT NOT NULL,
    battery_level   FLOAT NOT NULL,
    response_time_ms INTEGER NOT NULL
);

-- Mock CRM data matching Keycloak prothetic users
INSERT INTO crm_clients (user_id, username, email, first_name, last_name, prosthesis_id, prosthesis_type, purchase_date) VALUES
('prothetic1', 'prothetic1', 'prothetic1@example.com', 'Prothetic', 'One',   'PROS-001', 'Bionic Arm Type A', '2024-01-15'),
('prothetic2', 'prothetic2', 'prothetic2@example.com', 'Prothetic', 'Two',   'PROS-002', 'Bionic Arm Type B', '2024-02-20'),
('prothetic3', 'prothetic3', 'prothetic3@example.com', 'Prothetic', 'Three', 'PROS-003', 'Bionic Leg Type A', '2024-03-10')
ON CONFLICT (user_id) DO NOTHING;

-- Sample telemetry: 50 rows per user per day for the last 7 days
INSERT INTO telemetry (user_id, prosthesis_id, recorded_at, movement_type, signal_strength, battery_level, response_time_ms)
SELECT
    c.user_id,
    c.prosthesis_id,
    NOW() - (s.day_offset * INTERVAL '1 day') - (random() * INTERVAL '20 hours'),
    (ARRAY['grip', 'pinch', 'open', 'flex', 'extend'])[floor(random() * 5 + 1)],
    40 + random() * 60,
    50 + random() * 50,
    floor(40 + random() * 80)::INTEGER
FROM
    crm_clients c,
    (SELECT generate_series(0, 6) AS day_offset) s,
    generate_series(1, 50) r;
