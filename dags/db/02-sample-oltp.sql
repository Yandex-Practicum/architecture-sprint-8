\c sample

-- CRM: клиенты и протезы (связь с Keycloak по keycloak_sub для отчётов)
CREATE TABLE IF NOT EXISTS crm_customer (
    customer_id   SERIAL PRIMARY KEY,
    keycloak_sub  VARCHAR(128) NOT NULL UNIQUE,
    full_name     VARCHAR(255) NOT NULL
);

CREATE TABLE IF NOT EXISTS crm_prosthesis (
    prosthesis_id SERIAL PRIMARY KEY,
    customer_id   INTEGER NOT NULL REFERENCES crm_customer (customer_id),
    serial_number VARCHAR(64) NOT NULL,
    model         VARCHAR(128) NOT NULL
);

CREATE TABLE IF NOT EXISTS crm_order (
    order_id      SERIAL PRIMARY KEY,
    customer_id   INTEGER NOT NULL REFERENCES crm_customer (customer_id),
    prosthesis_id INTEGER REFERENCES crm_prosthesis (prosthesis_id),
    order_number  BIGINT NOT NULL,
    total         NUMERIC(18, 2) NOT NULL DEFAULT 0,
    discount      NUMERIC(18, 2) NOT NULL DEFAULT 0,
    created_at    DATE NOT NULL
);

-- Сырые события телеметрии (высокий объём моделируем несколькими строками)
CREATE TABLE IF NOT EXISTS telemetry_event (
    id            BIGSERIAL PRIMARY KEY,
    prosthesis_id INTEGER NOT NULL REFERENCES crm_prosthesis (prosthesis_id),
    event_time    TIMESTAMPTZ NOT NULL,
    metric_name   VARCHAR(64) NOT NULL,
    metric_value  DOUBLE PRECISION NOT NULL
);

-- Демо-данные (идемпотентные вставки по ключам — только если таблицы пусты)
-- sub = id пользователей prothetic1 / prothetic2 (keycloak/realm-export.json)
INSERT INTO crm_customer (customer_id, keycloak_sub, full_name)
SELECT 1, '1c8027a3-dc09-420a-a798-4fcea26bb5e3', 'Иван Пилот'
WHERE NOT EXISTS (SELECT 1 FROM crm_customer WHERE customer_id = 1);

INSERT INTO crm_customer (customer_id, keycloak_sub, full_name)
SELECT 2, '3d9147b2-ea11-4c9f-b61d-7789aabbcc02', 'Мария Пилот'
WHERE NOT EXISTS (SELECT 1 FROM crm_customer WHERE customer_id = 2);

UPDATE crm_customer
SET keycloak_sub = '1c8027a3-dc09-420a-a798-4fcea26bb5e3', full_name = 'Иван Пилот'
WHERE customer_id = 1;
UPDATE crm_customer
SET keycloak_sub = '3d9147b2-ea11-4c9f-b61d-7789aabbcc02', full_name = 'Мария Пилот'
WHERE customer_id = 2;

SELECT setval(
    'crm_customer_customer_id_seq',
    GREATEST((SELECT COALESCE(MAX(customer_id), 1) FROM crm_customer), 1)
);

INSERT INTO crm_prosthesis (prosthesis_id, customer_id, serial_number, model)
SELECT 1, 1, 'PRS-10001', 'BionicPRO Hand v3'
WHERE NOT EXISTS (SELECT 1 FROM crm_prosthesis WHERE prosthesis_id = 1);

INSERT INTO crm_prosthesis (prosthesis_id, customer_id, serial_number, model)
SELECT 2, 2, 'PRS-10002', 'BionicPRO Hand v3'
WHERE NOT EXISTS (SELECT 1 FROM crm_prosthesis WHERE prosthesis_id = 2);

SELECT setval(
    'crm_prosthesis_prosthesis_id_seq',
    GREATEST((SELECT COALESCE(MAX(prosthesis_id), 1) FROM crm_prosthesis), 1)
);

INSERT INTO crm_order (order_id, customer_id, prosthesis_id, order_number, total, discount, created_at)
SELECT 1, 1, 1, 100001, 120000.00, 5000.00, DATE '2024-11-15'
WHERE NOT EXISTS (SELECT 1 FROM crm_order WHERE order_id = 1);

INSERT INTO crm_order (order_id, customer_id, prosthesis_id, order_number, total, discount, created_at)
SELECT 2, 1, 1, 100002, 15000.00, 0.00, DATE '2024-12-01'
WHERE NOT EXISTS (SELECT 1 FROM crm_order WHERE order_id = 2);

INSERT INTO crm_order (order_id, customer_id, prosthesis_id, order_number, total, discount, created_at)
SELECT 3, 2, 2, 100003, 98000.00, 2000.00, DATE '2024-12-01'
WHERE NOT EXISTS (SELECT 1 FROM crm_order WHERE order_id = 3);

SELECT setval(
    'crm_order_order_id_seq',
    GREATEST((SELECT COALESCE(MAX(order_id), 1) FROM crm_order), 1)
);

-- Телеметрия за 2024-12-01 (под прогон DAG с logical_date = 2024-12-01)
INSERT INTO telemetry_event (prosthesis_id, event_time, metric_name, metric_value)
SELECT 1, TIMESTAMPTZ '2024-12-01 08:15:00+00', 'signal_quality', 0.82
WHERE NOT EXISTS (
    SELECT 1 FROM telemetry_event e
    WHERE e.prosthesis_id = 1 AND e.event_time = TIMESTAMPTZ '2024-12-01 08:15:00+00' AND e.metric_name = 'signal_quality'
);

INSERT INTO telemetry_event (prosthesis_id, event_time, metric_name, metric_value)
SELECT 1, TIMESTAMPTZ '2024-12-01 09:30:00+00', 'signal_quality', 0.77
WHERE NOT EXISTS (
    SELECT 1 FROM telemetry_event e
    WHERE e.prosthesis_id = 1 AND e.event_time = TIMESTAMPTZ '2024-12-01 09:30:00+00' AND e.metric_name = 'signal_quality'
);

INSERT INTO telemetry_event (prosthesis_id, event_time, metric_name, metric_value)
SELECT 1, TIMESTAMPTZ '2024-12-01 10:00:00+00', 'movement_latency_ms', 95
WHERE NOT EXISTS (
    SELECT 1 FROM telemetry_event e
    WHERE e.prosthesis_id = 1 AND e.event_time = TIMESTAMPTZ '2024-12-01 10:00:00+00' AND e.metric_name = 'movement_latency_ms'
);

INSERT INTO telemetry_event (prosthesis_id, event_time, metric_name, metric_value)
SELECT 2, TIMESTAMPTZ '2024-12-01 11:20:00+00', 'signal_quality', 0.91
WHERE NOT EXISTS (
    SELECT 1 FROM telemetry_event e
    WHERE e.prosthesis_id = 2 AND e.event_time = TIMESTAMPTZ '2024-12-01 11:20:00+00' AND e.metric_name = 'signal_quality'
);

SELECT setval(
    'telemetry_event_id_seq',
    GREATEST((SELECT COALESCE(MAX(id), 1) FROM telemetry_event), 1)
);
