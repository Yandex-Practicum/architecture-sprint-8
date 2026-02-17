CREATE DATABASE IF NOT EXISTS bionicpro;

USE bionicpro;

CREATE TABLE IF NOT EXISTS telemetry_raw (
    id UInt64,
    user_id UInt32,
    device_id String,
    timestamp DateTime,
    sensor_type String,
    sensor_value String,
    processing_time_ms Float32,
    action_executed String,
    created_at DateTime,
    etl_loaded_at DateTime DEFAULT now()
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (user_id, device_id, timestamp)
SETTINGS index_granularity = 8192;

CREATE TABLE IF NOT EXISTS crm_data (
    user_id UInt32,
    email String,
    full_name String,
    phone String,
    country String,
    registration_date DateTime,
    is_active UInt8,
    
    device_id String,
    device_type String,
    serial_number String,
    manufacture_date Date,
    delivery_date Date,
    warranty_until Date,
    device_status String,
    
    date_of_birth Date,
    amputation_type String,
    amputation_date Date,
    
    etl_loaded_at DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY (user_id, device_id)
SETTINGS index_granularity = 8192;

CREATE TABLE IF NOT EXISTS reports_mart (
    user_id UInt32,
    device_id String,
    period_month Date,
    
    full_name String,
    email String,
    country String,
    device_type String,
    
    total_signals UInt64,
    avg_processing_time_ms Float32,
    max_processing_time_ms Float32,
    min_processing_time_ms Float32,
    
    myo_signals_count UInt64,
    battery_checks_count UInt64,
    actuator_events_count UInt64,
    
    total_actions UInt64,
    most_frequent_action String,
    action_frequency UInt64,
    
    device_status String,
    warranty_until Date,
    
    report_generated_at DateTime DEFAULT now(),
    data_freshness_date DateTime
    
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(period_month)
PRIMARY KEY (user_id, period_month)
ORDER BY (user_id, period_month, device_id)
SETTINGS index_granularity = 8192;

CREATE VIEW IF NOT EXISTS data_freshness_view AS
SELECT
    'telemetry' AS source,
    max(timestamp) AS last_data_timestamp,
    max(etl_loaded_at) AS last_etl_run
FROM telemetry_raw
UNION ALL
SELECT
    'crm' AS source,
    max(registration_date) AS last_data_timestamp,
    max(etl_loaded_at) AS last_etl_run
FROM crm_data
UNION ALL
SELECT
    'reports' AS source,
    max(data_freshness_date) AS last_data_timestamp,
    max(report_generated_at) AS last_etl_run
FROM reports_mart;

CREATE VIEW IF NOT EXISTS user_latest_reports AS
SELECT 
    user_id,
    device_id,
    period_month,
    full_name,
    email,
    total_signals,
    avg_processing_time_ms,
    most_frequent_action,
    device_status,
    report_generated_at
FROM reports_mart
ORDER BY user_id, period_month DESC;
