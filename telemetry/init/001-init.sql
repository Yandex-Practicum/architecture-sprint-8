CREATE TABLE telemetry_events (
    id SERIAL PRIMARY KEY,
    prosthesis_code VARCHAR(64) NOT NULL,
    event_time TIMESTAMP NOT NULL,
    active_minutes INTEGER NOT NULL,
    grip_actions INTEGER NOT NULL,
    avg_signal NUMERIC(10, 4) NOT NULL,
    battery_level NUMERIC(10, 4) NOT NULL
);

INSERT INTO telemetry_events (prosthesis_code, event_time, active_minutes, grip_actions, avg_signal, battery_level) VALUES
    ('BP-RU-001', NOW() - INTERVAL '3 days', 65, 140, 0.82, 81.3),
    ('BP-RU-001', NOW() - INTERVAL '2 days', 72, 155, 0.85, 79.5),
    ('BP-RU-001', NOW() - INTERVAL '1 day', 70, 148, 0.83, 77.2),
    ('BP-RU-002', NOW() - INTERVAL '3 days', 58, 124, 0.79, 75.8),
    ('BP-RU-002', NOW() - INTERVAL '2 days', 61, 131, 0.81, 74.0),
    ('BP-RU-002', NOW() - INTERVAL '1 day', 63, 129, 0.80, 72.6),
    ('BP-KZ-003', NOW() - INTERVAL '3 days', 49, 102, 0.76, 69.1),
    ('BP-KZ-003', NOW() - INTERVAL '2 days', 52, 111, 0.78, 67.4),
    ('BP-KZ-003', NOW() - INTERVAL '1 day', 56, 118, 0.79, 66.0);
