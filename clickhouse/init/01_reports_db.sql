CREATE DATABASE IF NOT EXISTS reports;

CREATE TABLE IF NOT EXISTS reports.customer_mart
(
    username        String,
    first_name      String,
    last_name       String,
    prosthetic_id   String,
    country         String,
    period_start    DateTime,
    period_end      DateTime,
    events_count    UInt32,
    avg_latency_ms  Float32,
    avg_signal_quality Float32,
    updated_at      DateTime DEFAULT now()
)
ENGINE = MergeTree
ORDER BY (username, period_start);
