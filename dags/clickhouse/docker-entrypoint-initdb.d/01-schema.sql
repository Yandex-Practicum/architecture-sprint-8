CREATE DATABASE IF NOT EXISTS bionicpro;

-- Витрина отчётности: агрегаты по пользователю (keycloak_sub) и протезу за календарный день
CREATE TABLE IF NOT EXISTS bionicpro.mart_user_prosthesis_report
(
    report_date        Date,
    keycloak_sub       String,
    customer_id        UInt32,
    prosthesis_id      UInt32,
    serial_number      String,
    model              String,
    orders_count       UInt32,
    orders_sum         Float64,
    telemetry_events   UInt64,
    avg_signal_quality Float64,
    loaded_at          DateTime
)
ENGINE = MergeTree
PARTITION BY report_date
ORDER BY (keycloak_sub, prosthesis_id, report_date);
