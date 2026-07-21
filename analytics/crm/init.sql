CREATE TABLE IF NOT EXISTS clients (
    client_id         BIGSERIAL PRIMARY KEY,
    username          TEXT UNIQUE NOT NULL,   -- matches the Keycloak preferred_username
    full_name         TEXT NOT NULL,
    prosthesis_serial TEXT NOT NULL,
    region            TEXT NOT NULL,
    registered_at     DATE NOT NULL DEFAULT CURRENT_DATE
);

CREATE TABLE IF NOT EXISTS telemetry (
    id               BIGSERIAL PRIMARY KEY,
    client_id        BIGINT NOT NULL REFERENCES clients(client_id),
    ts               TIMESTAMP NOT NULL,
    response_time_ms INT NOT NULL,
    signal_quality   REAL NOT NULL,
    movements        INT NOT NULL,
    battery_pct      REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_telemetry_client_ts ON telemetry (client_id, ts);

ALTER TABLE clients REPLICA IDENTITY FULL;
ALTER TABLE telemetry REPLICA IDENTITY FULL;

INSERT INTO clients (username, full_name, prosthesis_serial, region) VALUES
    ('prothetic1',   'Prothetic One',   'BP-1001', 'RU'),
    ('prothetic2',   'Prothetic Two',   'BP-1002', 'RU'),
    ('prothetic3',   'Prothetic Three', 'BP-1003', 'RU'),
    ('john.doe',     'John Doe',        'BP-2001', 'DE'),
    ('alex.johnson', 'Alex Johnson',    'BP-2002', 'DE')
ON CONFLICT (username) DO NOTHING;

INSERT INTO telemetry (client_id, ts, response_time_ms, signal_quality, movements, battery_pct)
SELECT
    c.client_id,
    (CURRENT_DATE - d) + (make_interval(hours => s * 2))            AS ts,
    60 + (random() * 80)::int                                       AS response_time_ms,
    0.80 + random() * 0.18                                          AS signal_quality,
    20 + (random() * 90)::int                                       AS movements,
    40 + random() * 60                                              AS battery_pct
FROM clients c
CROSS JOIN generate_series(0, 13) AS d       -- last 14 days
CROSS JOIN generate_series(1, 8)  AS s;      -- 8 samples/day
