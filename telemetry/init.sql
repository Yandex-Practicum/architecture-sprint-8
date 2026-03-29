CREATE TABLE IF NOT EXISTS telemetry_events (
    event_id SERIAL PRIMARY KEY,
    prosthesis_id TEXT NOT NULL,
    event_ts TIMESTAMP NOT NULL,
    usage_minutes INTEGER NOT NULL,
    motion_events INTEGER NOT NULL,
    battery_pct NUMERIC(5,2) NOT NULL,
    signal_quality NUMERIC(5,2) NOT NULL,
    calibration_sessions INTEGER NOT NULL,
    alerts_count INTEGER NOT NULL
);

INSERT INTO telemetry_events (prosthesis_id, event_ts, usage_minutes, motion_events, battery_pct, signal_quality, calibration_sessions, alerts_count) VALUES
    ('BP-1001', '2026-03-20 10:00:00', 72, 420, 84.1, 0.94, 1, 0),
    ('BP-1001', '2026-03-21 10:30:00', 81, 445, 82.6, 0.93, 0, 1),
    ('BP-1001', '2026-03-22 11:00:00', 76, 431, 83.8, 0.95, 1, 0),
    ('BP-1001', '2026-03-24 10:45:00', 88, 470, 81.2, 0.92, 0, 1),
    ('BP-1001', '2026-03-27 09:55:00', 79, 452, 80.7, 0.94, 1, 0),
    ('BP-1002', '2026-03-21 14:20:00', 54, 301, 78.4, 0.89, 1, 0),
    ('BP-1002', '2026-03-23 14:50:00', 58, 318, 77.9, 0.88, 0, 0),
    ('BP-1002', '2026-03-28 15:10:00', 62, 330, 76.8, 0.90, 0, 1),
    ('BP-1003', '2026-03-20 08:40:00', 95, 510, 86.0, 0.96, 1, 0),
    ('BP-1003', '2026-03-22 08:35:00', 92, 498, 85.4, 0.95, 0, 0),
    ('BP-1003', '2026-03-25 08:30:00', 101, 545, 84.2, 0.94, 1, 1),
    ('BP-1004', '2026-03-21 18:15:00', 47, 265, 74.5, 0.87, 0, 1),
    ('BP-1004', '2026-03-24 18:00:00', 49, 276, 73.9, 0.88, 1, 0),
    ('INT-2001', '2026-03-20 12:10:00', 66, 350, 79.5, 0.91, 1, 0),
    ('INT-2001', '2026-03-26 12:15:00', 69, 362, 78.9, 0.92, 0, 0),
    ('INT-2002', '2026-03-22 16:40:00', 73, 388, 82.2, 0.93, 1, 0),
    ('INT-2002', '2026-03-27 16:10:00', 71, 379, 81.7, 0.92, 0, 1);
