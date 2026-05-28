CREATE TABLE telemetry (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(50) NOT NULL,
    recorded_at TIMESTAMP NOT NULL,
    myo_signal_1 FLOAT,
    myo_signal_2 FLOAT,
    myo_signal_3 FLOAT,
    myo_signal_4 FLOAT,
    movement_type VARCHAR(50),
    battery_level FLOAT,
    device_id VARCHAR(50)
);

CREATE TABLE customers (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(50) UNIQUE NOT NULL,
    full_name VARCHAR(100),
    email VARCHAR(100),
    country VARCHAR(50),
    registered_at TIMESTAMP DEFAULT NOW()
);

INSERT INTO customers (user_id, full_name, email, country) VALUES
    ('prothetic1', 'Prothetic One', 'prothetic1@example.com', 'Russia'),
    ('prothetic2', 'Prothetic Two', 'prothetic2@example.com', 'Russia'),
    ('prothetic3', 'Prothetic Three', 'prothetic3@example.com', 'Russia');

INSERT INTO telemetry (user_id, recorded_at, myo_signal_1, myo_signal_2, myo_signal_3, myo_signal_4, movement_type, battery_level, device_id)
SELECT
    'prothetic1',
    generate_series('2025-01-01'::timestamp, '2025-01-31'::timestamp, '1 hour'),
    random() * 100, random() * 100, random() * 100, random() * 100,
    CASE (random() * 4)::int
        WHEN 0 THEN 'grasp'
        WHEN 1 THEN 'release'
        WHEN 2 THEN 'flex'
        WHEN 3 THEN 'extend'
        WHEN 4 THEN 'rotate'
    END,
    random() * 100,
    'device-001';

INSERT INTO telemetry (user_id, recorded_at, myo_signal_1, myo_signal_2, myo_signal_3, myo_signal_4, movement_type, battery_level, device_id)
SELECT
    'prothetic2',
    generate_series('2025-01-01'::timestamp, '2025-01-31'::timestamp, '1 hour'),
    random() * 100, random() * 100, random() * 100, random() * 100,
    CASE (random() * 4)::int
        WHEN 0 THEN 'grasp'
        WHEN 1 THEN 'release'
        WHEN 2 THEN 'flex'
        WHEN 3 THEN 'extend'
        WHEN 4 THEN 'rotate'
    END,
    random() * 100,
    'device-002';

INSERT INTO telemetry (user_id, recorded_at, myo_signal_1, myo_signal_2, myo_signal_3, myo_signal_4, movement_type, battery_level, device_id)
SELECT
    'prothetic3',
    generate_series('2025-01-01'::timestamp, '2025-01-31'::timestamp, '1 hour'),
    random() * 100, random() * 100, random() * 100, random() * 100,
    CASE (random() * 4)::int
        WHEN 0 THEN 'grasp'
        WHEN 1 THEN 'release'
        WHEN 2 THEN 'flex'
        WHEN 3 THEN 'extend'
        WHEN 4 THEN 'rotate'
    END,
    random() * 100,
    'device-003';
