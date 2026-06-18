-- Создание таблиц CRM.
-- Включение logical replication для Debezium.

-- Даём crm_user права на репликацию.
ALTER USER crm_user WITH REPLICATION;

CREATE TABLE IF NOT EXISTS users (
    id           BIGSERIAL PRIMARY KEY,
    email        TEXT NOT NULL,
    first_name   TEXT,
    last_name    TEXT,
    country      TEXT,
    created_at   TIMESTAMPTZ DEFAULT now(),
    updated_at   TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS prostheses (
    id            BIGSERIAL PRIMARY KEY,
    user_id       BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    model         TEXT NOT NULL,
    serial_number TEXT NOT NULL,
    assigned_at   TIMESTAMPTZ DEFAULT now(),
    updated_at    TIMESTAMPTZ DEFAULT now()
);

-- Seed: 3 пользователя и протезы.
INSERT INTO users (email, first_name, last_name, country) VALUES
    ('pilot1@bionicpro.de', 'Hans',  'Mueller',  'DE'),
    ('pilot2@bionicpro.de', 'Anna',  'Schmidt',  'DE'),
    ('pilot3@bionicpro.fr', 'Jean',  'Dupont',   'FR')
ON CONFLICT DO NOTHING;

INSERT INTO prostheses (user_id, model, serial_number) VALUES
    (1, 'BionicArm-v3', 'SN-501-AAA'),
    (1, 'BionicLeg-v2', 'SN-601-AAA'),
    (2, 'BionicArm-v3', 'SN-502-BBB'),
    (3, 'BionicHand-v1','SN-703-CCC')
ON CONFLICT DO NOTHING;

-- Replication slot под Debezium (создаётся здесь для предсказуемости).
SELECT pg_create_logical_replication_slot('debezium_crm', 'pgoutput')
WHERE NOT EXISTS (SELECT 1 FROM pg_replication_slots WHERE slot_name = 'debezium_crm');