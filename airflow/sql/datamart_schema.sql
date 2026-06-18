-- Витрина отчётности по протезам.
-- Движок: MergeTree. Партиция по месяцу, сортировка по (user_id, report_date).
-- Это обеспечивает быстрый доступ к данным конкретного пользователя за период.

CREATE DATABASE IF NOT EXISTS bionicpro_dm;

CREATE TABLE IF NOT EXISTS bionicpro_dm.prosthesis_user_report
(
    user_id            UInt64,
    user_email         String,
    user_first_name    String,
    user_last_name     String,
    user_country       LowCardinality(String),
    prosthesis_id      UInt64,
    prosthesis_model   LowCardinality(String),
    prosthesis_serial  String,

    report_date        Date,

    sessions_count          UInt32,
    total_active_minutes    UInt32,
    avg_signal_strength     Float32,
    max_signal_strength     Float32,
    error_events_count      UInt32,
    battery_avg_percent     Float32,
    actuator_cycles_total   UInt64,

    loaded_at           DateTime DEFAULT now()
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(report_date)
ORDER BY (user_id, report_date)
TTL report_date + INTERVAL 3 YEAR;

-- Вспомогательная таблица со списком протезов пользователя.
-- Нужна для JOIN при подготовке витрины.
CREATE TABLE IF NOT EXISTS bionicpro_dm.user_prosthesis_map
(
    user_id          UInt64,
    prosthesis_id    UInt64,
    prosthesis_model LowCardinality(String),
    prosthesis_serial String,
    assigned_at      DateTime
)
ENGINE = ReplacingMergeTree(assigned_at)
ORDER BY (user_id, prosthesis_id);