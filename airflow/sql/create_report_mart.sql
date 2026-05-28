CREATE DATABASE IF NOT EXISTS prosthetic_reports;

CREATE TABLE IF NOT EXISTS prosthetic_reports.dim_customers (
    user_id UInt32,
    full_name String,
    email String,
    country String,
    loaded_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(loaded_at)
ORDER BY user_id;

CREATE TABLE IF NOT EXISTS prosthetic_reports.fact_telemetry (
    user_id UInt32,
    date Date,
    total_readings UInt64,
    avg_signal_1 Float64,
    avg_signal_2 Float64,
    avg_signal_3 Float64,
    avg_signal_4 Float64,
    avg_battery_level Float64,
    movement_grasp UInt64,
    movement_release UInt64,
    movement_flex UInt64,
    movement_extend UInt64,
    movement_rotate UInt64,
    loaded_at DateTime DEFAULT now()
) ENGINE = SummingMergeTree((total_readings, movement_grasp, movement_release, movement_flex, movement_extend, movement_rotate))
ORDER BY (user_id, date);

CREATE TABLE IF NOT EXISTS prosthetic_reports.report_mart (
    user_id UInt32,
    full_name String,
    email String,
    country String,
    date Date,
    total_readings UInt64,
    avg_signal_1 Float64,
    avg_signal_2 Float64,
    avg_signal_3 Float64,
    avg_signal_4 Float64,
    avg_battery_level Float64,
    movement_grasp UInt64,
    movement_release UInt64,
    movement_flex UInt64,
    movement_extend UInt64,
    movement_rotate UInt64
) ENGINE = MergeTree()
ORDER BY (user_id, date);
