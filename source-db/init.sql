CREATE DATABASE crm;
CREATE DATABASE telemetry;

\connect crm

CREATE TABLE clients (
    user_id TEXT PRIMARY KEY,
    full_name TEXT NOT NULL,
    prosthesis_model TEXT NOT NULL
);

INSERT INTO clients (user_id, full_name, prosthesis_model) VALUES
    ('prothetic1', 'Prothetic One', 'BionicPRO Hand X1'),
    ('prothetic2', 'Prothetic Two', 'BionicPRO Hand X2'),
    ('prothetic3', 'Prothetic Three', 'BionicPRO Arm S3');

\connect telemetry

CREATE TABLE prosthesis_telemetry (
    id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL,
    signals_count INTEGER NOT NULL,
    movements_count INTEGER NOT NULL,
    reaction_ms INTEGER NOT NULL,
    battery_level NUMERIC(4, 1) NOT NULL
);

CREATE INDEX ON prosthesis_telemetry (recorded_at);

INSERT INTO prosthesis_telemetry (user_id, recorded_at, signals_count, movements_count, reaction_ms, battery_level)
SELECT c.user_id,
       ts,
       800 + (random() * 400)::int,
       100 + (random() * 100)::int,
       60 + (random() * 60)::int,
       round((20 + random() * 80)::numeric, 1)
FROM (VALUES ('prothetic1'), ('prothetic2'), ('prothetic3')) AS c(user_id),
     generate_series(CURRENT_DATE - INTERVAL '6 days', now(), INTERVAL '6 hours') AS ts;
