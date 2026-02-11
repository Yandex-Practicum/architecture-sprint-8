-- OLAP: витрина для сервиса отчётов (данные за периоды, уже обработанные Airflow)

CREATE TABLE IF NOT EXISTS staging_crm (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    full_name VARCHAR(255),
    prosthesis_id VARCHAR(255),
    synced_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS staging_telemetry (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    event_time TIMESTAMPTZ NOT NULL,
    metric_name VARCHAR(100),
    value NUMERIC(12,4),
    synced_at TIMESTAMPTZ DEFAULT NOW()
);

-- Витрина: отчёт по пользователю за период (заполняется Airflow ETL)
CREATE TABLE IF NOT EXISTS datamart_reports (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    period_from DATE NOT NULL,
    period_to DATE NOT NULL,
    report_generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    summary JSONB,
    CONSTRAINT uq_user_period UNIQUE (user_id, period_from, period_to)
);

CREATE INDEX IF NOT EXISTS idx_datamart_user ON datamart_reports (user_id);
CREATE INDEX IF NOT EXISTS idx_datamart_period ON datamart_reports (period_from, period_to);
