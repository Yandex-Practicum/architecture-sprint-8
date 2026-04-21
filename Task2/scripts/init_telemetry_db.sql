CREATE SCHEMA IF NOT EXISTS telemetry;

CREATE TABLE IF NOT EXISTS telemetry.raw_signals (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL,
    prosthesis_id UUID NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    reaction_time_ms INTEGER NOT NULL,
    movement_type VARCHAR(50),
    is_successful BOOLEAN DEFAULT true,
    battery_level INTEGER,
    signal_quality DECIMAL(3,2),
    error_code INTEGER DEFAULT 0
);

CREATE INDEX idx_user_timestamp ON telemetry.raw_signals(user_id, timestamp);
CREATE INDEX idx_prosthesis_timestamp ON telemetry.raw_signals(prosthesis_id, timestamp);

INSERT INTO telemetry.raw_signals (user_id, prosthesis_id, timestamp, reaction_time_ms, movement_type, is_successful, battery_level, signal_quality) VALUES
    ('0aca56c5-b960-4c50-9f1b-0451aea68fe3', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', '2025-01-15 08:00:00', 85, 'grasp', true, 95, 0.90),
    ('0aca56c5-b960-4c50-9f1b-0451aea68fe3', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', '2025-01-15 08:01:00', 92, 'release', true, 94, 0.88),
    ('0aca56c5-b960-4c50-9f1b-0451aea68fe3', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', '2025-01-15 08:02:00', 120, 'grasp', false, 93, 0.85),
    ('0aca56c5-b960-4c50-9f1b-0451aea68fe3', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', '2025-01-15 08:03:00', 78, 'point', true, 92, 0.92),
    ('0aca56c5-b960-4c50-9f1b-0451aea68fe3', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', '2025-01-16 09:00:00', 88, 'grasp', true, 91, 0.89),
    ('0aca56c5-b960-4c50-9f1b-0451aea68fe3', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', '2025-01-16 09:01:00', 95, 'release', true, 90, 0.87),
    
    ('11b225b9-4fda-4ebd-b508-6c90cefd23a7', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', '2025-01-15 09:00:00', 70, 'grasp', true, 98, 0.95),
    ('11b225b9-4fda-4ebd-b508-6c90cefd23a7', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', '2025-01-15 09:01:00', 68, 'release', true, 97, 0.94),
    ('11b225b9-4fda-4ebd-b508-6c90cefd23a7', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', '2025-01-15 09:02:00', 72, 'grasp', true, 96, 0.93),
    ('11b225b9-4fda-4ebd-b508-6c90cefd23a7', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', '2025-01-16 10:00:00', 65, 'point', true, 95, 0.96),
    
    ('fcf7435c-1f54-4a1e-80cb-6214a733e84a', 'cccccccc-cccc-cccc-cccc-cccccccccccc', '2025-01-15 10:00:00', 95, 'grasp', true, 88, 0.86),
    ('fcf7435c-1f54-4a1e-80cb-6214a733e84a', 'cccccccc-cccc-cccc-cccc-cccccccccccc', '2025-01-15 10:01:00', 105, 'release', false, 87, 0.84),
    ('fcf7435c-1f54-4a1e-80cb-6214a733e84a', 'cccccccc-cccc-cccc-cccc-cccccccccccc', '2025-01-15 10:02:00', 98, 'grasp', true, 86, 0.85),
    
    ('44444444-4444-4444-4444-444444444444', 'dddddddd-dddd-dddd-dddd-dddddddddddd', '2025-01-15 11:00:00', 60, 'grasp', true, 99, 0.97),
    ('44444444-4444-4444-4444-444444444444', 'dddddddd-dddd-dddd-dddd-dddddddddddd', '2025-01-15 11:01:00', 55, 'point', true, 98, 0.96),
    
    ('55555555-5555-5555-5555-555555555555', 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee', '2025-01-15 12:00:00', 110, 'grasp', false, 85, 0.82),
    ('55555555-5555-5555-5555-555555555555', 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee', '2025-01-15 12:01:00', 115, 'release', false, 84, 0.81);