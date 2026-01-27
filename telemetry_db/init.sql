CREATE TABLE IF NOT EXISTS telemetry (
    id SERIAL PRIMARY KEY,
    prosthesis_id VARCHAR(255) NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    movement_type VARCHAR(100),
    reaction_time FLOAT
);

INSERT INTO telemetry (prosthesis_id, user_id, timestamp, movement_type, reaction_time) VALUES
('prosthesis-001', 'prothetic1', '2024-01-20 10:00:00', 'grasp', 95.5),
('prosthesis-001', 'prothetic1', '2024-01-20 10:05:00', 'release', 88.2),
('prosthesis-001', 'prothetic1', '2024-01-20 10:10:00', 'grasp', 102.3),
('prosthesis-002', 'prothetic2', '2024-02-25 14:00:00', 'flex', 92.1),
('prosthesis-002', 'prothetic2', '2024-02-25 14:05:00', 'extend', 87.5),
('prosthesis-003', 'prothetic3', '2024-03-15 09:00:00', 'grasp', 98.7),
('prosthesis-003', 'prothetic3', '2024-03-15 09:05:00', 'release', 91.2);
