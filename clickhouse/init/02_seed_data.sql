-- Вставка тестовых данных для dim_users
INSERT INTO reports.dim_users
(user_id, email, full_name, role, region, created_at)
VALUES
('prothetic1', 'prothetic1@example.com', 'Prothetic One', 'prothetic_user', 'RU', now()),
('prothetic2', 'prothetic2@example.com', 'Prothetic Two', 'prothetic_user', 'RU', now()),
('user1', 'user1@example.com', 'User One', 'user', 'RU', now()),
('admin1', 'admin1@example.com', 'Admin One', 'administrator', 'RU', now());

-- Вставка тестовых данных для daily_user_stats
INSERT INTO reports.daily_user_stats
(user_id, prosthesis_id, date, total_movements, avg_signal_quality, min_battery_level, calibration_count, region)
VALUES
('prothetic1', 'PROST-001', today() - 5, 1245, 0.87, 65, 2, 'RU'),
('prothetic1', 'PROST-001', today() - 4, 1382, 0.89, 62, 1, 'RU'),
('prothetic1', 'PROST-001', today() - 3, 1100, 0.85, 70, 0, 'RU'),
('prothetic1', 'PROST-001', today() - 2, 1450, 0.91, 58, 3, 'RU'),
('prothetic1', 'PROST-001', today() - 1, 1280, 0.88, 64, 1, 'RU'),
('prothetic2', 'PROST-002', today() - 1, 890, 0.82, 72, 1, 'RU');