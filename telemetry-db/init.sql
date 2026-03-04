CREATE TABLE IF NOT EXISTS telemetry (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    prosthesis_type VARCHAR(50) NOT NULL,
    muscle_group VARCHAR(50) NOT NULL,
    signal_frequency INTEGER NOT NULL,
    signal_duration INTEGER NOT NULL,
    signal_amplitude DECIMAL(5,2) NOT NULL,
    signal_time TIMESTAMP NOT NULL
);

COPY telemetry(user_id, prosthesis_type, muscle_group, signal_frequency, signal_duration, signal_amplitude, signal_time)
FROM '/docker-entrypoint-initdb.d/telemetry.csv'
DELIMITER ','
CSV HEADER;