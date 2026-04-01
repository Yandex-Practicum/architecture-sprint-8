-- OLTP CRM: источник CDC → Debezium → Kafka → ClickHouse (задание 4).
CREATE TABLE customers (
    customer_id       VARCHAR(64) PRIMARY KEY,
    email             VARCHAR(255),
    keycloak_subject  VARCHAR(128) NOT NULL,
    prosthesis_model  VARCHAR(128),
    region            VARCHAR(64),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE telemetry_events (
    id                BIGSERIAL PRIMARY KEY,
    user_subject      VARCHAR(128) NOT NULL,
    event_date        DATE NOT NULL,
    active_minutes    INT NOT NULL DEFAULT 0,
    steps             BIGINT NOT NULL DEFAULT 0,
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_telemetry_user_date ON telemetry_events (user_subject, event_date);
CREATE INDEX idx_customers_keycloak ON customers (keycloak_subject);
