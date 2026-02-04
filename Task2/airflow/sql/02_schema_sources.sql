-- Примерная структура источников для ETL (CRM и основная БД).
-- Используется для локальной разработки и тестов. В проде таблицы уже существуют в CRM DB и основной БД.

-- ---------- CRM DB (источник: заказы, клиенты, привязка устройств) ----------
-- В реальности это может быть Oracle (Bitrix24). Здесь PostgreSQL-эквивалент для разработки.

CREATE TABLE IF NOT EXISTS crm_customers (
    id              SERIAL PRIMARY KEY,
    user_id         VARCHAR(64) NOT NULL UNIQUE,
    full_name       VARCHAR(255),
    email           VARCHAR(255),
    contract_date   DATE,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS crm_devices (
    id              SERIAL PRIMARY KEY,
    user_id         VARCHAR(64) NOT NULL,
    device_id       VARCHAR(64) NOT NULL,
    prosthesis_model VARCHAR(128),
    delivery_date   DATE,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ---------- Основная БД (источник: телеметрия с протезов) ----------

CREATE TABLE IF NOT EXISTS telemetry_sessions (
    id              BIGSERIAL PRIMARY KEY,
    user_id         VARCHAR(64) NOT NULL,
    device_id       VARCHAR(64) NOT NULL,
    started_at      TIMESTAMP WITH TIME ZONE NOT NULL,
    ended_at        TIMESTAMP WITH TIME ZONE,
    duration_seconds INTEGER,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS telemetry_events (
    id              BIGSERIAL PRIMARY KEY,
    user_id         VARCHAR(64) NOT NULL,
    device_id       VARCHAR(64) NOT NULL,
    event_type      VARCHAR(64) NOT NULL,
    event_ts        TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_telemetry_sessions_user_id ON telemetry_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_telemetry_sessions_started_at ON telemetry_sessions(started_at);
CREATE INDEX IF NOT EXISTS idx_telemetry_events_user_id ON telemetry_events(user_id);
CREATE INDEX IF NOT EXISTS idx_telemetry_events_event_ts ON telemetry_events(event_ts);
