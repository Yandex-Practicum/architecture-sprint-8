-- =============================================
-- BionicPRO: ClickHouse OLAP схема
-- Raw-таблицы + витрина отчётности
-- =============================================

-- Сырые данные телеметрии (загружаются из PostgreSQL)
CREATE TABLE IF NOT EXISTS raw_telemetry (
    prosthesis_id String,
    timestamp DateTime,
    signal_strength Float64,
    response_time_ms Float64,
    battery_level Float64,
    movement_type String,
    anomaly_detected UInt8
) ENGINE = MergeTree()
ORDER BY (prosthesis_id, timestamp);

-- Сырые данные клиентов из CRM (загружаются из Oracle/PostgreSQL)
CREATE TABLE IF NOT EXISTS raw_crm_clients (
    client_id String,
    first_name String,
    last_name String,
    email String,
    prosthesis_id String,
    prosthesis_model String,
    installation_date Date
) ENGINE = ReplacingMergeTree()
ORDER BY (client_id, prosthesis_id);

-- Витрина отчётности: агрегация телеметрии в разрезе клиентов
CREATE TABLE IF NOT EXISTS report_user_prosthesis (
    client_id String,
    client_name String,
    email String,
    prosthesis_id String,
    prosthesis_model String,
    report_date Date,
    total_movements UInt64,
    avg_response_time_ms Float64,
    avg_signal_strength Float64,
    avg_battery_level Float64,
    active_minutes UInt64,
    anomaly_count UInt64
) ENGINE = ReplacingMergeTree()
PARTITION BY toYYYYMM(report_date)
ORDER BY (client_id, prosthesis_id, report_date);
