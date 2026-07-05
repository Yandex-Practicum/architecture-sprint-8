-- username совпадает с пользователями Keycloak/LDAP.
CREATE TABLE IF NOT EXISTS clients (
    id              SERIAL PRIMARY KEY,
    username        VARCHAR(64) UNIQUE NOT NULL,
    full_name       VARCHAR(128) NOT NULL,
    prosthesis_model VARCHAR(64) NOT NULL,
    created_at      TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS telemetry (
    id               BIGSERIAL PRIMARY KEY,
    client_id        INTEGER NOT NULL REFERENCES clients(id),
    ts               TIMESTAMP NOT NULL,
    response_time_ms INTEGER NOT NULL,
    battery_level    INTEGER NOT NULL,
    movements_count  INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_telemetry_client_ts ON telemetry(client_id, ts);

INSERT INTO clients (username, full_name, prosthesis_model) VALUES
    ('prothetic1', 'Prothetic One',   'BionicArm X1'),
    ('prothetic2', 'Prothetic Two',   'BionicArm X2'),
    ('prothetic3', 'Prothetic Three', 'BionicLeg L1')
ON CONFLICT (username) DO NOTHING;

INSERT INTO telemetry (client_id, ts, response_time_ms, battery_level, movements_count)
SELECT
    c.id,
    (now() - (d || ' days')::interval - (h || ' hours')::interval),
    60 + (random() * 50)::int,
    40 + (random() * 60)::int,
    (random() * 500)::int
FROM clients c
CROSS JOIN generate_series(1, 7) AS d
CROSS JOIN generate_series(0, 23, 4) AS h;
