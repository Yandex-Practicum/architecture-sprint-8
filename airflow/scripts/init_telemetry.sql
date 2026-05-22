CREATE TABLE IF NOT EXISTS telemetry_sessions (
    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id VARCHAR(50) NOT NULL,
    device_id VARCHAR(100) NOT NULL,
    firmware_version VARCHAR(50),
    started_at TIMESTAMP NOT NULL,
    ended_at TIMESTAMP,
    movements_count INTEGER DEFAULT 0,
    errors_count INTEGER DEFAULT 0,
    battery_start INTEGER CHECK (battery_start BETWEEN 0 AND 100),
    battery_end INTEGER CHECK (battery_end BETWEEN 0 AND 100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS telemetry_events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES telemetry_sessions(session_id),
    event_type VARCHAR(50) NOT NULL,
    movement_type VARCHAR(100),
    myosignal_value DECIMAL(10, 4),
    sensor_temperature DECIMAL(5, 2),
    recorded_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sessions_customer ON telemetry_sessions(customer_id);
CREATE INDEX IF NOT EXISTS idx_sessions_started ON telemetry_sessions(started_at);
CREATE INDEX IF NOT EXISTS idx_events_session ON telemetry_events(session_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON telemetry_events(event_type);

INSERT INTO telemetry_sessions (customer_id, device_id, firmware_version, started_at, ended_at, movements_count, errors_count, battery_start, battery_end) VALUES
('CUST-001', 'BPRO-X1-0001', 'v2.1.0', '2025-05-01 08:00:00', '2025-05-01 14:30:00', 1250, 3, 100, 45),
('CUST-001', 'BPRO-X1-0001', 'v2.1.0', '2025-05-02 09:15:00', '2025-05-02 15:45:00', 1100, 1, 100, 52),
('CUST-001', 'BPRO-X1-0001', 'v2.1.0', '2025-05-03 07:30:00', '2025-05-03 13:00:00', 980, 5, 100, 48),
('CUST-001', 'BPRO-X1-0001', 'v2.2.0', '2025-05-04 08:45:00', '2025-05-04 16:15:00', 1350, 0, 100, 40),
('CUST-002', 'BPRO-X2-0001', 'v2.1.0', '2025-05-01 10:00:00', '2025-05-01 16:30:00', 890, 2, 100, 55),
('CUST-002', 'BPRO-X2-0001', 'v2.1.0', '2025-05-02 08:30:00', '2025-05-02 14:00:00', 950, 0, 100, 50),
('CUST-002', 'BPRO-X2-0001', 'v2.1.0', '2025-05-03 09:00:00', '2025-05-03 17:00:00', 1200, 4, 100, 42),
('CUST-002', 'BPRO-X2-0001', 'v2.2.0', '2025-05-04 07:45:00', '2025-05-04 12:30:00', 780, 1, 100, 60),
('CUST-003', 'BPRO-X1-0002', 'v2.1.0', '2025-05-01 11:00:00', '2025-05-01 15:00:00', 650, 0, 100, 65),
('CUST-003', 'BPRO-X1-0002', 'v2.1.0', '2025-05-02 10:15:00', '2025-05-02 18:30:00', 1450, 3, 100, 38),
('CUST-003', 'BPRO-X1-0002', 'v2.2.0', '2025-05-04 08:00:00', '2025-05-04 13:45:00', 1020, 2, 100, 50),
('CUST-004', 'BPRO-X3-0001', 'v3.0.0', '2025-05-01 06:30:00', '2025-05-01 17:00:00', 2100, 1, 100, 25),
('CUST-004', 'BPRO-X3-0001', 'v3.0.0', '2025-05-02 07:00:00', '2025-05-02 18:30:00', 2300, 0, 100, 20),
('CUST-004', 'BPRO-X3-0001', 'v3.0.0', '2025-05-03 06:45:00', '2025-05-03 16:45:00', 1950, 3, 100, 30),
('CUST-004', 'BPRO-X3-0001', 'v3.1.0', '2025-05-04 08:15:00', '2025-05-04 19:00:00', 2500, 0, 100, 18),
('CUST-005', 'BPRO-X2-0002', 'v2.1.0', '2025-05-02 12:00:00', '2025-05-02 17:30:00', 820, 1, 100, 58),
('CUST-005', 'BPRO-X2-0002', 'v2.2.0', '2025-05-04 09:30:00', '2025-05-04 14:15:00', 710, 0, 100, 62),
('CUST-006', 'BPRO-X1-0003', 'v2.1.0', '2025-05-01 13:00:00', '2025-05-01 18:00:00', 670, 2, 100, 60),
('CUST-006', 'BPRO-X1-0003', 'v2.2.0', '2025-05-04 10:00:00', '2025-05-04 15:30:00', 890, 1, 100, 55),
('CUST-007', 'BPRO-X3-0002', 'v3.0.0', '2025-05-03 08:00:00', '2025-05-03 20:00:00', 3100, 5, 100, 10),
('CUST-007', 'BPRO-X3-0002', 'v3.1.0', '2025-05-04 07:30:00', '2025-05-04 19:30:00', 2800, 2, 100, 15),
('CUST-008', 'BPRO-X2-0003', 'v2.1.0', '2025-05-01 09:00:00', '2025-05-01 12:00:00', 500, 0, 100, 70),
('CUST-008', 'BPRO-X2-0003', 'v2.2.0', '2025-05-04 11:00:00', '2025-05-04 16:00:00', 760, 1, 100, 60);

INSERT INTO telemetry_events (session_id, event_type, movement_type, myosignal_value, sensor_temperature, recorded_at)
SELECT
    s.session_id,
    CASE WHEN e.n % 5 = 0 THEN 'error' ELSE 'movement' END,
    CASE floor(random() * 5)
        WHEN 0 THEN 'grasp'
        WHEN 1 THEN 'release'
        WHEN 2 THEN 'flexion'
        WHEN 3 THEN 'extension'
        WHEN 4 THEN 'rotation'
    END,
    round((random() * 900 + 100)::decimal, 4),
    round((random() * 4 + 35)::decimal, 2),
    s.started_at + (e.n || ' minutes')::interval
FROM telemetry_sessions s
CROSS JOIN generate_series(0, 19) AS e(n);
