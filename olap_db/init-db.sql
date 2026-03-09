-- --------------------------------
-- Схемы
-- --------------------------------
CREATE SCHEMA IF NOT EXISTS staging;  -- временные данные ETL-процесса
CREATE SCHEMA IF NOT EXISTS mart;     -- витрины для сервисов

-- ----------------------------------------------------------------
-- Staging: сырые клиенты из CRM
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS staging.crm_clients (
    client_id       BIGINT       NOT NULL,
    full_name       TEXT,
    email           TEXT,
    phone           TEXT,
    segment         VARCHAR(50),  -- 'premium' | 'standard' | 'trial'
    contract_start  DATE,
    contract_end    DATE,
    region          VARCHAR(100),
    loaded_at       TIMESTAMP    DEFAULT NOW(),
    PRIMARY KEY (client_id)
);

-- ----------------------------------------------------------------
-- Staging: сырая телеметрия за расчётный период
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS staging.telemetry_raw (
    event_id        BIGINT,
    client_id       BIGINT       NOT NULL,
    device_id       VARCHAR(100),
    event_type      VARCHAR(100),
    value           DOUBLE PRECISION,
    event_ts        TIMESTAMP    NOT NULL,
    loaded_at       TIMESTAMP    DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_telemetry_raw_client
    ON staging.telemetry_raw (client_id, event_ts);

-- ----------------------------------------------------------------
-- Витрина: агрегаты телеметрии + CRM по пользователю / дню
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS mart.user_reports (
    -- Ключ витрины
    client_id           BIGINT       NOT NULL,
    report_date         DATE         NOT NULL,

    -- Данные из CRM
    full_name           TEXT,
    email               TEXT,
    segment             VARCHAR(50),
    region              VARCHAR(100),
    contract_active     BOOLEAN,

    -- Агрегаты телеметрии за report_date
    events_total        BIGINT       DEFAULT 0,
    events_distinct_devices BIGINT  DEFAULT 0,
    value_sum           DOUBLE PRECISION,
    value_avg           DOUBLE PRECISION,
    value_min           DOUBLE PRECISION,
    value_max           DOUBLE PRECISION,
    first_event_ts      TIMESTAMP,
    last_event_ts       TIMESTAMP,

    -- Служебные поля
    updated_at          TIMESTAMP    DEFAULT NOW(),

    PRIMARY KEY (client_id, report_date)
);

-- Индексы для быстрого доступа по пользователю и дате
CREATE INDEX IF NOT EXISTS idx_user_reports_client
    ON mart.user_reports (client_id);
CREATE INDEX IF NOT EXISTS idx_user_reports_date
    ON mart.user_reports (report_date DESC);
CREATE INDEX IF NOT EXISTS idx_user_reports_segment
    ON mart.user_reports (segment, report_date DESC);
