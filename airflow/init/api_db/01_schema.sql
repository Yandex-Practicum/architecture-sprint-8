CREATE TABLE telemetry (
    id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    measured_at TIMESTAMPTZ NOT NULL,
    temperature_c NUMERIC(5, 2),
    pulse_bpm INT
);
