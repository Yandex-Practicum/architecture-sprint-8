CREATE TABLE IF NOT EXISTS prosthesis_telemetry (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(50),
    prosthesis_id VARCHAR(50),
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    movement_type VARCHAR(50),
    battery_level FLOAT
);

INSERT INTO prosthesis_telemetry (user_id, prosthesis_id, movement_type, battery_level) 
VALUES 
('user_123', 'proto_A1', 'grip', 85.5),
('user_456', 'proto_B2', 'wave', 92.0);