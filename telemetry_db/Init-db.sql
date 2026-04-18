CREATE TABLE IF NOT EXISTS telemetry_data (
    id SERIAL PRIMARY KEY,
    event_time TIMESTAMP NOT NULL,
    user_id INT NOT NULL,
    prosthesis_id TEXT NOT NULL,
    movement TEXT,
    battery_level DOUBLE PRECISION NOT NULL,
    active_minutes INTEGER NOT NULL
);

COPY telemetry_data(id, event_time, user_id, prosthesis_id, movement, battery_level, active_minutes)
FROM '/docker-entrypoint-initdb.d/telemetry.csv'
DELIMITER ','
CSV HEADER;