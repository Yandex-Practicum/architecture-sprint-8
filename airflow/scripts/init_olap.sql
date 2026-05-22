CREATE DATABASE IF NOT EXISTS olap_db;

CREATE TABLE IF NOT EXISTS olap_db.prosthetics_data_mart
(
    customer_id String,
    customer_name String,
    customer_email String,
    prosthesis_model String,
    region String,
    purchase_date Date,
    warranty_end_date Date,
    warranty_status String,
    total_usage_hours Float64,
    avg_daily_usage_minutes Float64,
    total_sessions UInt32,
    total_movements UInt64,
    avg_movements_per_session Float64,
    total_errors UInt32,
    errors_per_session Float64,
    last_active_date Date,
    battery_health_avg Float64,
    most_common_movement String,
    data_as_of_date Date
)
ENGINE = ReplacingMergeTree(data_as_of_date)
ORDER BY (customer_id)
COMMENT 'Витрина данных для сервиса отчётов. Агрегированные показатели использования протезов в разрезе клиентов.';
