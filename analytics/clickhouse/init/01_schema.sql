CREATE DATABASE IF NOT EXISTS reports;

CREATE TABLE IF NOT EXISTS reports.user_report_mart
(
    report_date        Date,
    client_id          UInt64,
    username           String,
    full_name          String,
    prosthesis_serial  String,
    region             String,
    telemetry_events   UInt64,
    avg_response_ms    Float64,
    max_response_ms    Float64,
    avg_signal_quality Float64,
    total_movements    UInt64,
    avg_battery_pct    Float64,
    updated_at         DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (username, report_date);
