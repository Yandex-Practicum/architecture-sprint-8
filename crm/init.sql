-- CRM DB schema for BionicPRO

CREATE TABLE IF NOT EXISTS users (
    id          SERIAL PRIMARY KEY,
    username    VARCHAR(100) NOT NULL,
    email       VARCHAR(200) NOT NULL,
    created_at  TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS prostheses (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER REFERENCES users(id),
    model       VARCHAR(100) NOT NULL,
    created_at  TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS telemetry (
    id              SERIAL PRIMARY KEY,
    prosthesis_id   INTEGER REFERENCES prostheses(id),
    recorded_at     TIMESTAMP DEFAULT NOW(),
    signal_value    NUMERIC(10,4),
    movement_type   VARCHAR(50),
    response_ms     NUMERIC(10,2)
);

-- Seed data
INSERT INTO users (username, email) VALUES
    ('user1',       'user1@example.com'),
    ('prothetic1',  'prothetic1@example.com'),
    ('prothetic2',  'prothetic2@example.com');

INSERT INTO prostheses (user_id, model) VALUES
    (1, 'BionicArm-X1'),
    (2, 'BionicArm-X2'),
    (3, 'BionicLeg-L1');

INSERT INTO telemetry (prosthesis_id, recorded_at, signal_value, movement_type, response_ms) VALUES
    (1, NOW() - INTERVAL '30 minutes', 0.85, 'grip',    45.2),
    (1, NOW() - INTERVAL '20 minutes', 0.90, 'release', 42.1),
    (2, NOW() - INTERVAL '45 minutes', 0.78, 'flex',    55.3),
    (2, NOW() - INTERVAL '15 minutes', 0.82, 'extend',  48.7),
    (3, NOW() - INTERVAL '60 minutes', 0.91, 'step',    38.5),
    (3, NOW() - INTERVAL '10 minutes', 0.88, 'balance', 41.9);
