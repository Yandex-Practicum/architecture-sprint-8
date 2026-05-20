CREATE DATABASE IF NOT EXISTS bionicpro;

CREATE TABLE IF NOT EXISTS bionicpro.crm_clients
(
    user_id          String,
    device_id        String,
    client_name      String,
    client_email     String,
    prosthesis_model String,
    purchase_date    Date
) ENGINE = MergeTree()
ORDER BY user_id;

CREATE TABLE IF NOT EXISTS bionicpro.telemetry
(
    user_id           String,
    device_id         String,
    timestamp         DateTime,
    signal_type       String,
    signal_value      Float64,
    movement_detected String
) ENGINE = MergeTree()
ORDER BY (user_id, timestamp);

CREATE TABLE IF NOT EXISTS bionicpro.user_report_mart
(
    user_id           String,
    device_id         String,
    client_name       String,
    client_email      String,
    prosthesis_model  String,
    purchase_date     Date,
    total_sessions    Int64,
    total_movements   Int64,
    last_activity     Nullable(DateTime),
    avg_signal_quality Float64,
    report_date       Date
) ENGINE = MergeTree()
ORDER BY (user_id, report_date);

-- Seed the mart so the API returns data immediately on first run
INSERT INTO bionicpro.user_report_mart VALUES ('prothetic1', 'device001', 'Prothetic One', 'prothetic1@example.com', 'BionicArm Pro v2', '2024-01-15', 150, 120, '2025-05-15 18:30:00', 0.795, today());
INSERT INTO bionicpro.user_report_mart VALUES ('prothetic2', 'device002', 'Prothetic Two', 'prothetic2@example.com', 'BionicLeg Basic v1', '2024-02-20', 98, 72, '2025-05-15 17:45:00', 0.706, today());
INSERT INTO bionicpro.user_report_mart VALUES ('prothetic3', 'device003', 'Prothetic Three', 'prothetic3@example.com', 'BionicArm Elite v3', '2024-03-10', 210, 185, '2025-05-15 19:00:00', 0.887, today());
