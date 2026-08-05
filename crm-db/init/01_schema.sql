CREATE TABLE customers (
    id              SERIAL PRIMARY KEY,
    username        VARCHAR(64) UNIQUE NOT NULL,
    first_name      VARCHAR(128) NOT NULL,
    last_name       VARCHAR(128) NOT NULL,
    email           VARCHAR(256) NOT NULL,
    prosthetic_id   VARCHAR(32) NOT NULL,
    country         VARCHAR(64) NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE telemetry_events (
    id                  BIGSERIAL PRIMARY KEY,
    customer_username   VARCHAR(64) NOT NULL REFERENCES customers(username),
    prosthetic_id       VARCHAR(32) NOT NULL,
    event_time          TIMESTAMPTZ NOT NULL,
    action_type         VARCHAR(32) NOT NULL,
    latency_ms          NUMERIC(6, 2) NOT NULL,
    signal_quality      NUMERIC(4, 3) NOT NULL
);

CREATE INDEX idx_telemetry_customer_time ON telemetry_events (customer_username, event_time);
