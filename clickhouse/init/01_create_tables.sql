CREATE DATABASE IF NOT EXISTS reports;

-- Таблица пользователей (из Keycloak/LDAP)
CREATE TABLE IF NOT EXISTS reports.dim_users
(
    user_id      String,
    email        String,
    full_name    String,
    role         LowCardinality(String),
    region       LowCardinality(String),
    created_at   DateTime
)
ENGINE = ReplacingMergeTree()
ORDER BY user_id;

CREATE TABLE IF NOT EXISTS reports.raw_telemetry
(
    timestamp        DateTime64(3),
    prosthesis_id    String,
    user_id          String,
    signal_ch1       Float32,
    signal_ch2       Float32,
    signal_ch3       Float32,
    signal_ch4       Float32,
    movement_type    LowCardinality(String),
    battery_level    UInt8,
    signal_quality   Float32,
    region           LowCardinality(String),
    calibration_id   String
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (user_id, prosthesis_id, timestamp)
TTL timestamp + INTERVAL 3 YEAR;

-- Витрина: ежедневная статистика по пользователю
CREATE TABLE IF NOT EXISTS reports.daily_user_stats
(
    user_id              String,
    prosthesis_id        String,
    date                 Date,
    total_movements      UInt32,
    avg_signal_quality   Float32,
    min_battery_level    UInt8,
    calibration_count    UInt16,
    region               LowCardinality(String)
)
ENGINE = SummingMergeTree()
ORDER BY (user_id, date);
