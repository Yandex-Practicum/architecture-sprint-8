-- Витрина отчётности для сервиса отчётов BionicPRO (OLAP).
-- Объединяет данные о клиентах из CRM и агрегаты телеметрии по пользователям.
-- Оптимизирована для быстрого доступа по user_id.

-- Промежуточные таблицы для ETL (заполняются Extract, читаются Transform)
CREATE TABLE IF NOT EXISTS stg_crm (
    user_id             VARCHAR(64) NOT NULL PRIMARY KEY,
    device_id           VARCHAR(64),
    customer_name       VARCHAR(255),
    customer_email      VARCHAR(255),
    contract_date       DATE,
    prosthesis_model    VARCHAR(128),
    delivery_date       DATE
);

CREATE TABLE IF NOT EXISTS stg_telemetry (
    user_id             VARCHAR(64) NOT NULL PRIMARY KEY,
    device_id           VARCHAR(64),
    session_count       INTEGER NOT NULL DEFAULT 0,
    total_usage_seconds BIGINT NOT NULL DEFAULT 0,
    event_count         INTEGER NOT NULL DEFAULT 0,
    error_count         INTEGER NOT NULL DEFAULT 0,
    calibration_count   INTEGER NOT NULL DEFAULT 0,
    last_activity_utc    TIMESTAMP WITH TIME ZONE,
    period_start        TIMESTAMP WITH TIME ZONE,
    period_end          TIMESTAMP WITH TIME ZONE
);

-- Витрина: одна запись на пользователя (текущие агрегаты за период).
-- Индекс по user_id обеспечивает быстрый доступ к отчёту по пользователю.
CREATE TABLE IF NOT EXISTS report_datamart (
    user_id             VARCHAR(64) NOT NULL PRIMARY KEY,
    device_id           VARCHAR(64),
    -- Данные из CRM
    customer_name       VARCHAR(255),
    customer_email      VARCHAR(255),
    contract_date       DATE,
    prosthesis_model    VARCHAR(128),
    delivery_date       DATE,
    -- Агрегаты телеметрии (в разрезе клиента)
    session_count      INTEGER NOT NULL DEFAULT 0,
    total_usage_seconds BIGINT NOT NULL DEFAULT 0,
    event_count        INTEGER NOT NULL DEFAULT 0,
    error_count        INTEGER NOT NULL DEFAULT 0,
    calibration_count  INTEGER NOT NULL DEFAULT 0,
    -- Период, за который посчитаны метрики
    period_start       TIMESTAMP WITH TIME ZONE,
    period_end         TIMESTAMP WITH TIME ZONE,
    last_activity_utc  TIMESTAMP WITH TIME ZONE,
    -- Служебные поля
    updated_at         TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC')
);

-- Дополнительный индекс по device_id для поиска по устройству
CREATE INDEX IF NOT EXISTS idx_report_datamart_device_id ON report_datamart(device_id);
CREATE INDEX IF NOT EXISTS idx_report_datamart_updated_at ON report_datamart(updated_at);

COMMENT ON TABLE report_datamart IS 'Витрина отчётности: клиенты (CRM) + агрегаты телеметрии по пользователям для сервиса отчётов';
