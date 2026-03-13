CREATE DATABASE IF NOT EXISTS bionicpro;

-- Main reports table (populated by Airflow ETL)
CREATE TABLE IF NOT EXISTS bionicpro.reports (
    report_id UUID DEFAULT generateUUIDv4(),
    user_id String,
    user_email String,
    report_date Date,
    device_id String,
    product_name String,
    order_date Date,
    order_status String,
    total_usage_hours Float64,
    active_movements Int32,
    battery_cycles Int32,
    avg_signal_strength Float64,
    error_count Int32,
    created_at DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY (user_id, report_date)
PARTITION BY toYYYYMM(report_date);

-- Staging tables for CDC data from Debezium/Kafka
CREATE TABLE IF NOT EXISTS bionicpro.customers (
    id Int32,
    keycloak_user_id String,
    email String,
    first_name String,
    last_name String,
    created_at DateTime DEFAULT now(),
    _op String DEFAULT 'c'
) ENGINE = ReplacingMergeTree(created_at)
ORDER BY id;

CREATE TABLE IF NOT EXISTS bionicpro.orders (
    id Int32,
    customer_id Int32,
    product_name String,
    product_type String,
    order_date Date,
    status String,
    created_at DateTime DEFAULT now(),
    _op String DEFAULT 'c'
) ENGINE = ReplacingMergeTree(created_at)
ORDER BY id;

CREATE TABLE IF NOT EXISTS bionicpro.telemetry (
    id Int32,
    device_id String,
    customer_id Int32,
    signal_strength Float64,
    usage_hours Float64,
    active_movements Int32,
    battery_cycles Int32,
    error_count Int32,
    recorded_at DateTime DEFAULT now(),
    _op String DEFAULT 'c'
) ENGINE = ReplacingMergeTree(recorded_at)
ORDER BY id;

-- Report data mart (populated by CDC pipeline MaterializedViews or Airflow)
CREATE TABLE IF NOT EXISTS bionicpro.report_datamart (
    user_id String,
    user_email String,
    device_id String,
    product_name String,
    order_date Date,
    order_status String,
    total_usage_hours Float64,
    total_active_movements Int64,
    total_battery_cycles Int64,
    avg_signal_strength Float64,
    total_error_count Int64,
    last_updated DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(last_updated)
ORDER BY (user_id, device_id, order_date);

-- ETL metadata: track last processed timestamp
CREATE TABLE IF NOT EXISTS bionicpro.etl_metadata (
    pipeline_name String,
    last_run DateTime,
    status String,
    records_processed Int64
) ENGINE = ReplacingMergeTree(last_run)
ORDER BY pipeline_name;
