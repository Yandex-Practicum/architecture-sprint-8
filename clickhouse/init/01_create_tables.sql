-- Создание базы данных
CREATE DATABASE IF NOT EXISTS reports;

-- Создание таблицы для статистики
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

-- Вставка тестовых данных
INSERT INTO reports.daily_user_stats VALUES
('prothetic1', 'PROST-001', '2026-05-06', 1245, 0.87, 65, 2, 'RU'),
('prothetic1', 'PROST-001', '2026-05-07', 1382, 0.89, 62, 1, 'RU'),
('prothetic1', 'PROST-001', '2026-05-08', 1100, 0.85, 70, 0, 'RU'),
('prothetic1', 'PROST-001', '2026-05-09', 1450, 0.91, 58, 3, 'RU'),
('prothetic1', 'PROST-001', '2026-05-10', 1280, 0.88, 64, 1, 'RU'),
('prothetic1', 'PROST-001', '2026-05-11', 1190, 0.86, 67, 2, 'RU');