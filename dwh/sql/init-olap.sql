-- OLAP-витрина для сервиса отчётов (PostgreSQL как компактный OLAP-слой для учебного проекта)
CREATE SCHEMA IF NOT EXISTS reporting;

-- Staging: снимок CRM (в DAG загружается из CSV)
CREATE TABLE IF NOT EXISTS reporting.stg_crm (
    customer_id       TEXT PRIMARY KEY,
    email             TEXT,
    keycloak_subject  TEXT NOT NULL,
    prosthesis_model  TEXT,
    region            TEXT
);

-- Staging: события телеметрии (датчики)
CREATE TABLE IF NOT EXISTS reporting.stg_telemetry (
    user_subject     TEXT NOT NULL,
    event_date       DATE NOT NULL,
    active_minutes   INT  NOT NULL DEFAULT 0,
    steps              BIGINT NOT NULL DEFAULT 0
);

-- Витрина: агрегаты по пользователю и дню — быстрый доступ по user_subject
CREATE TABLE IF NOT EXISTS reporting.mart_user_prosthesis_daily (
    user_subject      TEXT NOT NULL,
    stat_date         DATE NOT NULL,
    active_hours      NUMERIC(14, 4) NOT NULL DEFAULT 0,
    steps             BIGINT NOT NULL DEFAULT 0,
    prosthesis_model  TEXT,
    crm_region        TEXT,
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_subject, stat_date)
);

CREATE INDEX IF NOT EXISTS idx_mart_user_subject ON reporting.mart_user_prosthesis_daily (user_subject);
CREATE INDEX IF NOT EXISTS idx_mart_stat_date ON reporting.mart_user_prosthesis_daily (stat_date);

COMMENT ON TABLE reporting.mart_user_prosthesis_daily IS 'Витрина отчётности: готовые агрегаты для API /reports без online-агрегации';
