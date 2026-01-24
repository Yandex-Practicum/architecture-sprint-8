ATTACH TABLE _ UUID '4c294068-d338-446e-b31d-8c6d4e7b9cd7'
(
    `user_id` UInt64,
    `date` Date,
    `device_id` String,
    `total_usage_seconds` UInt32,
    `total_movements` UInt32,
    `avg_sensor_value` Float32,
    `min_sensor_value` Float32,
    `max_sensor_value` Float32,
    `usage_hours` Float32,
    `year` UInt16,
    `month` UInt8,
    `week` UInt8,
    `day_of_week` UInt8,
    `user_name` Nullable(String),
    `prosthesis_install_date` Nullable(Date),
    `prosthesis_type` Nullable(String),
    `order_date` Nullable(Date),
    `order_status` Nullable(String),
    `maintenance_date` Nullable(Date),
    `maintenance_type` Nullable(String),
    `maintenance_status` Nullable(String),
    `processed_at` DateTime,
    `data_period_start` DateTime,
    `data_period_end` DateTime
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(date)
ORDER BY (user_id, date)
SETTINGS index_granularity = 8192
