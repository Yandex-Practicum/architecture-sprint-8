-- CRM Database schema and seed data for BionicPRO
-- Source system for ETL pipeline (Assignment 2) and CDC pipeline (Assignment 4).
--
-- CDC requirements:
--   The postgres server must be started with wal_level=logical (set in docker-compose).
--   Debezium uses pgoutput plugin and creates a logical replication slot automatically.
--   crm_user (POSTGRES_USER) has superuser rights in this Docker setup → REPLICATION is included.

CREATE TABLE IF NOT EXISTS patients (
    id              SERIAL PRIMARY KEY,
    username        VARCHAR(100) UNIQUE NOT NULL,
    email           VARCHAR(200),
    full_name       VARCHAR(200),
    device_serial   VARCHAR(50),
    device_model    VARCHAR(100),
    registration_date DATE DEFAULT CURRENT_DATE
);

CREATE TABLE IF NOT EXISTS telemetry (
    id               SERIAL PRIMARY KEY,
    patient_username VARCHAR(100) NOT NULL REFERENCES patients(username),
    recorded_at      TIMESTAMP   NOT NULL DEFAULT NOW(),
    battery_level    DECIMAL(5,2),   -- percent 0-100
    active_hours     DECIMAL(10,2),  -- hours of prosthesis activity
    steps_count      INTEGER,
    event_type       VARCHAR(50)     -- 'normal', 'alert', 'calibration'
);

CREATE INDEX IF NOT EXISTS idx_telemetry_username_date
    ON telemetry (patient_username, recorded_at);

-- ── Seed patients ─────────────────────────────────────────────────────────────
INSERT INTO patients (username, email, full_name, device_serial, device_model, registration_date)
VALUES
  ('john.doe',     'john@example.com', 'John Doe',     'SN-10023', 'BionicArm v3',  '2023-01-15'),
  ('jane.smith',   'jane@example.com', 'Jane Smith',   'SN-10047', 'BionicLeg v2',  '2023-03-20'),
  ('alex.johnson', 'alex@example.com', 'Alex Johnson', 'SN-10089', 'BionicArm v3',  '2023-06-01')
ON CONFLICT (username) DO NOTHING;

-- ── Seed telemetry (last 7 days, multiple readings per day per patient) ───────
INSERT INTO telemetry (patient_username, recorded_at, battery_level, active_hours, steps_count, event_type)
SELECT
    p.username,
    NOW() - (d || ' days')::INTERVAL - (h || ' hours')::INTERVAL,
    70 + (random() * 25)::DECIMAL(5,2),
    (random() * 2)::DECIMAL(10,2),
    (random() * 500)::INTEGER,
    (ARRAY['normal','normal','normal','alert','calibration'])[floor(random()*5+1)::INT]
FROM
    patients p,
    generate_series(0, 6) AS d,
    generate_series(0, 5) AS h;
