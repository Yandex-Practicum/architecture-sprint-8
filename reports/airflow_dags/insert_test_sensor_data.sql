-- Скрипт для генерации тестовых данных sensor_telemetry
-- Данные связаны с пользователями из CRM файлов (user_id: 12345, 12346, 12347)
-- Генерируются данные за последние 7 дней для каждого пользователя

-- Очистка существующих тестовых данных (опционально, раскомментируйте при необходимости)
-- DELETE FROM sensor_telemetry WHERE user_id IN (12345, 12346, 12347);

-- ============================================================================
-- Генерация данных для пользователя 12345 (Иван Иванов, Type A, установлен 2023-01-15)
-- Device ID: DEV-12345
-- ============================================================================

-- День 1 (7 дней назад)
INSERT INTO sensor_telemetry (user_id, device_id, timestamp, sensor_type, sensor_value, movement_type, movement_count, usage_duration_seconds) VALUES
(12345, 'DEV-12345', CURRENT_TIMESTAMP - INTERVAL '7 days' + INTERVAL '8 hours', 'pressure', 45.5, 'grip', 1, 120),
(12345, 'DEV-12345', CURRENT_TIMESTAMP - INTERVAL '7 days' + INTERVAL '8 hours 5 minutes', 'pressure', 48.2, 'release', 1, 125),
(12345, 'DEV-12345', CURRENT_TIMESTAMP - INTERVAL '7 days' + INTERVAL '9 hours', 'temperature', 32.1, 'flex', 2, 180),
(12345, 'DEV-12345', CURRENT_TIMESTAMP - INTERVAL '7 days' + INTERVAL '14 hours', 'pressure', 52.3, 'grip', 3, 240),
(12345, 'DEV-12345', CURRENT_TIMESTAMP - INTERVAL '7 days' + INTERVAL '14 hours 10 minutes', 'pressure', 49.8, 'release', 3, 245),
(12345, 'DEV-12345', CURRENT_TIMESTAMP - INTERVAL '7 days' + INTERVAL '15 hours', 'temperature', 33.5, 'flex', 1, 150);

-- День 2
INSERT INTO sensor_telemetry (user_id, device_id, timestamp, sensor_type, sensor_value, movement_type, movement_count, usage_duration_seconds) VALUES
(12345, 'DEV-12345', CURRENT_TIMESTAMP - INTERVAL '6 days' + INTERVAL '9 hours', 'pressure', 47.1, 'grip', 2, 135),
(12345, 'DEV-12345', CURRENT_TIMESTAMP - INTERVAL '6 days' + INTERVAL '9 hours 8 minutes', 'pressure', 46.5, 'release', 2, 140),
(12345, 'DEV-12345', CURRENT_TIMESTAMP - INTERVAL '6 days' + INTERVAL '10 hours', 'temperature', 31.8, 'flex', 3, 200),
(12345, 'DEV-12345', CURRENT_TIMESTAMP - INTERVAL '6 days' + INTERVAL '16 hours', 'pressure', 50.2, 'grip', 4, 280),
(12345, 'DEV-12345', CURRENT_TIMESTAMP - INTERVAL '6 days' + INTERVAL '16 hours 12 minutes', 'pressure', 48.9, 'release', 4, 285);

-- День 3
INSERT INTO sensor_telemetry (user_id, device_id, timestamp, sensor_type, sensor_value, movement_type, movement_count, usage_duration_seconds) VALUES
(12345, 'DEV-12345', CURRENT_TIMESTAMP - INTERVAL '5 days' + INTERVAL '8 hours 30 minutes', 'pressure', 46.8, 'grip', 1, 110),
(12345, 'DEV-12345', CURRENT_TIMESTAMP - INTERVAL '5 days' + INTERVAL '8 hours 35 minutes', 'pressure', 45.2, 'release', 1, 115),
(12345, 'DEV-12345', CURRENT_TIMESTAMP - INTERVAL '5 days' + INTERVAL '11 hours', 'temperature', 32.8, 'flex', 2, 165),
(12345, 'DEV-12345', CURRENT_TIMESTAMP - INTERVAL '5 days' + INTERVAL '13 hours', 'pressure', 51.5, 'grip', 5, 300),
(12345, 'DEV-12345', CURRENT_TIMESTAMP - INTERVAL '5 days' + INTERVAL '13 hours 15 minutes', 'pressure', 49.1, 'release', 5, 305);

-- День 4
INSERT INTO sensor_telemetry (user_id, device_id, timestamp, sensor_type, sensor_value, movement_type, movement_count, usage_duration_seconds) VALUES
(12345, 'DEV-12345', CURRENT_TIMESTAMP - INTERVAL '4 days' + INTERVAL '7 hours', 'pressure', 44.9, 'grip', 2, 130),
(12345, 'DEV-12345', CURRENT_TIMESTAMP - INTERVAL '4 days' + INTERVAL '7 hours 6 minutes', 'pressure', 47.3, 'release', 2, 135),
(12345, 'DEV-12345', CURRENT_TIMESTAMP - INTERVAL '4 days' + INTERVAL '12 hours', 'temperature', 33.2, 'flex', 1, 140),
(12345, 'DEV-12345', CURRENT_TIMESTAMP - INTERVAL '4 days' + INTERVAL '17 hours', 'pressure', 53.1, 'grip', 3, 220);

-- День 5
INSERT INTO sensor_telemetry (user_id, device_id, timestamp, sensor_type, sensor_value, movement_type, movement_count, usage_duration_seconds) VALUES
(12345, 'DEV-12345', CURRENT_TIMESTAMP - INTERVAL '3 days' + INTERVAL '10 hours', 'pressure', 48.5, 'grip', 1, 125),
(12345, 'DEV-12345', CURRENT_TIMESTAMP - INTERVAL '3 days' + INTERVAL '10 hours 4 minutes', 'pressure', 46.7, 'release', 1, 130),
(12345, 'DEV-12345', CURRENT_TIMESTAMP - INTERVAL '3 days' + INTERVAL '15 hours', 'temperature', 32.5, 'flex', 4, 250),
(12345, 'DEV-12345', CURRENT_TIMESTAMP - INTERVAL '3 days' + INTERVAL '18 hours', 'pressure', 49.8, 'grip', 2, 160);

-- День 6
INSERT INTO sensor_telemetry (user_id, device_id, timestamp, sensor_type, sensor_value, movement_type, movement_count, usage_duration_seconds) VALUES
(12345, 'DEV-12345', CURRENT_TIMESTAMP - INTERVAL '2 days' + INTERVAL '8 hours 15 minutes', 'pressure', 47.6, 'grip', 3, 190),
(12345, 'DEV-12345', CURRENT_TIMESTAMP - INTERVAL '2 days' + INTERVAL '8 hours 20 minutes', 'pressure', 45.9, 'release', 3, 195),
(12345, 'DEV-12345', CURRENT_TIMESTAMP - INTERVAL '2 days' + INTERVAL '14 hours', 'temperature', 31.9, 'flex', 2, 170),
(12345, 'DEV-12345', CURRENT_TIMESTAMP - INTERVAL '2 days' + INTERVAL '16 hours', 'pressure', 52.4, 'grip', 4, 270);

-- День 7 (вчера)
INSERT INTO sensor_telemetry (user_id, device_id, timestamp, sensor_type, sensor_value, movement_type, movement_count, usage_duration_seconds) VALUES
(12345, 'DEV-12345', CURRENT_TIMESTAMP - INTERVAL '1 day' + INTERVAL '9 hours', 'pressure', 46.2, 'grip', 2, 140),
(12345, 'DEV-12345', CURRENT_TIMESTAMP - INTERVAL '1 day' + INTERVAL '9 hours 7 minutes', 'pressure', 48.7, 'release', 2, 145),
(12345, 'DEV-12345', CURRENT_TIMESTAMP - INTERVAL '1 day' + INTERVAL '11 hours', 'temperature', 33.1, 'flex', 3, 210),
(12345, 'DEV-12345', CURRENT_TIMESTAMP - INTERVAL '1 day' + INTERVAL '15 hours', 'pressure', 50.6, 'grip', 5, 320),
(12345, 'DEV-12345', CURRENT_TIMESTAMP - INTERVAL '1 day' + INTERVAL '15 hours 18 minutes', 'pressure', 49.3, 'release', 5, 325);

-- ============================================================================
-- Генерация данных для пользователя 12346 (Петр Петров, Type B, установлен 2023-03-20)
-- Device ID: DEV-12346
-- ============================================================================

-- День 1
INSERT INTO sensor_telemetry (user_id, device_id, timestamp, sensor_type, sensor_value, movement_type, movement_count, usage_duration_seconds) VALUES
(12346, 'DEV-12346', CURRENT_TIMESTAMP - INTERVAL '7 days' + INTERVAL '7 hours', 'pressure', 42.3, 'grip', 1, 100),
(12346, 'DEV-12346', CURRENT_TIMESTAMP - INTERVAL '7 days' + INTERVAL '7 hours 3 minutes', 'pressure', 44.1, 'release', 1, 105),
(12346, 'DEV-12346', CURRENT_TIMESTAMP - INTERVAL '7 days' + INTERVAL '10 hours', 'temperature', 30.5, 'flex', 1, 120),
(12346, 'DEV-12346', CURRENT_TIMESTAMP - INTERVAL '7 days' + INTERVAL '13 hours', 'pressure', 48.7, 'grip', 2, 180);

-- День 2
INSERT INTO sensor_telemetry (user_id, device_id, timestamp, sensor_type, sensor_value, movement_type, movement_count, usage_duration_seconds) VALUES
(12346, 'DEV-12346', CURRENT_TIMESTAMP - INTERVAL '6 days' + INTERVAL '8 hours', 'pressure', 43.5, 'grip', 1, 115),
(12346, 'DEV-12346', CURRENT_TIMESTAMP - INTERVAL '6 days' + INTERVAL '8 hours 5 minutes', 'pressure', 45.2, 'release', 1, 120),
(12346, 'DEV-12346', CURRENT_TIMESTAMP - INTERVAL '6 days' + INTERVAL '11 hours', 'temperature', 31.2, 'flex', 2, 150),
(12346, 'DEV-12346', CURRENT_TIMESTAMP - INTERVAL '6 days' + INTERVAL '15 hours', 'pressure', 47.9, 'grip', 3, 200);

-- День 3
INSERT INTO sensor_telemetry (user_id, device_id, timestamp, sensor_type, sensor_value, movement_type, movement_count, usage_duration_seconds) VALUES
(12346, 'DEV-12346', CURRENT_TIMESTAMP - INTERVAL '5 days' + INTERVAL '9 hours 20 minutes', 'pressure', 44.8, 'grip', 2, 130),
(12346, 'DEV-12346', CURRENT_TIMESTAMP - INTERVAL '5 days' + INTERVAL '9 hours 25 minutes', 'pressure', 43.6, 'release', 2, 135),
(12346, 'DEV-12346', CURRENT_TIMESTAMP - INTERVAL '5 days' + INTERVAL '12 hours', 'temperature', 30.8, 'flex', 1, 110),
(12346, 'DEV-12346', CURRENT_TIMESTAMP - INTERVAL '5 days' + INTERVAL '16 hours', 'pressure', 49.3, 'grip', 4, 240);

-- День 4
INSERT INTO sensor_telemetry (user_id, device_id, timestamp, sensor_type, sensor_value, movement_type, movement_count, usage_duration_seconds) VALUES
(12346, 'DEV-12346', CURRENT_TIMESTAMP - INTERVAL '4 days' + INTERVAL '7 hours 30 minutes', 'pressure', 42.9, 'grip', 1, 105),
(12346, 'DEV-12346', CURRENT_TIMESTAMP - INTERVAL '4 days' + INTERVAL '7 hours 35 minutes', 'pressure', 44.5, 'release', 1, 110),
(12346, 'DEV-12346', CURRENT_TIMESTAMP - INTERVAL '4 days' + INTERVAL '14 hours', 'temperature', 31.5, 'flex', 3, 190);

-- День 5
INSERT INTO sensor_telemetry (user_id, device_id, timestamp, sensor_type, sensor_value, movement_type, movement_count, usage_duration_seconds) VALUES
(12346, 'DEV-12346', CURRENT_TIMESTAMP - INTERVAL '3 days' + INTERVAL '8 hours', 'pressure', 45.1, 'grip', 2, 140),
(12346, 'DEV-12346', CURRENT_TIMESTAMP - INTERVAL '3 days' + INTERVAL '8 hours 6 minutes', 'pressure', 46.8, 'release', 2, 145),
(12346, 'DEV-12346', CURRENT_TIMESTAMP - INTERVAL '3 days' + INTERVAL '17 hours', 'pressure', 48.2, 'grip', 3, 210);

-- День 6
INSERT INTO sensor_telemetry (user_id, device_id, timestamp, sensor_type, sensor_value, movement_type, movement_count, usage_duration_seconds) VALUES
(12346, 'DEV-12346', CURRENT_TIMESTAMP - INTERVAL '2 days' + INTERVAL '10 hours', 'pressure', 43.7, 'grip', 1, 125),
(12346, 'DEV-12346', CURRENT_TIMESTAMP - INTERVAL '2 days' + INTERVAL '10 hours 4 minutes', 'pressure', 45.4, 'release', 1, 130),
(12346, 'DEV-12346', CURRENT_TIMESTAMP - INTERVAL '2 days' + INTERVAL '13 hours', 'temperature', 30.9, 'flex', 2, 160),
(12346, 'DEV-12346', CURRENT_TIMESTAMP - INTERVAL '2 days' + INTERVAL '18 hours', 'pressure', 47.5, 'grip', 5, 280);

-- День 7 (вчера)
INSERT INTO sensor_telemetry (user_id, device_id, timestamp, sensor_type, sensor_value, movement_type, movement_count, usage_duration_seconds) VALUES
(12346, 'DEV-12346', CURRENT_TIMESTAMP - INTERVAL '1 day' + INTERVAL '9 hours 15 minutes', 'pressure', 44.3, 'grip', 2, 135),
(12346, 'DEV-12346', CURRENT_TIMESTAMP - INTERVAL '1 day' + INTERVAL '9 hours 20 minutes', 'pressure', 46.1, 'release', 2, 140),
(12346, 'DEV-12346', CURRENT_TIMESTAMP - INTERVAL '1 day' + INTERVAL '15 hours', 'temperature', 31.8, 'flex', 4, 230),
(12346, 'DEV-12346', CURRENT_TIMESTAMP - INTERVAL '1 day' + INTERVAL '19 hours', 'pressure', 49.8, 'grip', 3, 220);

-- ============================================================================
-- Генерация данных для пользователя 12347 (Мария Сидорова, Type A, установлен 2023-05-10)
-- Device ID: DEV-12347
-- ============================================================================

-- День 1
INSERT INTO sensor_telemetry (user_id, device_id, timestamp, sensor_type, sensor_value, movement_type, movement_count, usage_duration_seconds) VALUES
(12347, 'DEV-12347', CURRENT_TIMESTAMP - INTERVAL '7 days' + INTERVAL '6 hours', 'pressure', 41.2, 'grip', 1, 95),
(12347, 'DEV-12347', CURRENT_TIMESTAMP - INTERVAL '7 days' + INTERVAL '6 hours 2 minutes', 'pressure', 43.8, 'release', 1, 100),
(12347, 'DEV-12347', CURRENT_TIMESTAMP - INTERVAL '7 days' + INTERVAL '9 hours', 'temperature', 29.8, 'flex', 1, 110),
(12347, 'DEV-12347', CURRENT_TIMESTAMP - INTERVAL '7 days' + INTERVAL '12 hours', 'pressure', 46.5, 'grip', 2, 160),
(12347, 'DEV-12347', CURRENT_TIMESTAMP - INTERVAL '7 days' + INTERVAL '12 hours 8 minutes', 'pressure', 45.1, 'release', 2, 165);

-- День 2
INSERT INTO sensor_telemetry (user_id, device_id, timestamp, sensor_type, sensor_value, movement_type, movement_count, usage_duration_seconds) VALUES
(12347, 'DEV-12347', CURRENT_TIMESTAMP - INTERVAL '6 days' + INTERVAL '7 hours 15 minutes', 'pressure', 42.4, 'grip', 1, 108),
(12347, 'DEV-12347', CURRENT_TIMESTAMP - INTERVAL '6 days' + INTERVAL '7 hours 20 minutes', 'pressure', 44.2, 'release', 1, 113),
(12347, 'DEV-12347', CURRENT_TIMESTAMP - INTERVAL '6 days' + INTERVAL '10 hours', 'temperature', 30.1, 'flex', 2, 140),
(12347, 'DEV-12347', CURRENT_TIMESTAMP - INTERVAL '6 days' + INTERVAL '14 hours', 'pressure', 47.8, 'grip', 3, 190);

-- День 3
INSERT INTO sensor_telemetry (user_id, device_id, timestamp, sensor_type, sensor_value, movement_type, movement_count, usage_duration_seconds) VALUES
(12347, 'DEV-12347', CURRENT_TIMESTAMP - INTERVAL '5 days' + INTERVAL '8 hours', 'pressure', 41.9, 'grip', 1, 102),
(12347, 'DEV-12347', CURRENT_TIMESTAMP - INTERVAL '5 days' + INTERVAL '8 hours 4 minutes', 'pressure', 43.5, 'release', 1, 107),
(12347, 'DEV-12347', CURRENT_TIMESTAMP - INTERVAL '5 days' + INTERVAL '11 hours', 'temperature', 29.5, 'flex', 1, 115),
(12347, 'DEV-12347', CURRENT_TIMESTAMP - INTERVAL '5 days' + INTERVAL '15 hours', 'pressure', 48.1, 'grip', 4, 250),
(12347, 'DEV-12347', CURRENT_TIMESTAMP - INTERVAL '5 days' + INTERVAL '15 hours 12 minutes', 'pressure', 46.7, 'release', 4, 255);

-- День 4
INSERT INTO sensor_telemetry (user_id, device_id, timestamp, sensor_type, sensor_value, movement_type, movement_count, usage_duration_seconds) VALUES
(12347, 'DEV-12347', CURRENT_TIMESTAMP - INTERVAL '4 days' + INTERVAL '6 hours 30 minutes', 'pressure', 42.7, 'grip', 2, 125),
(12347, 'DEV-12347', CURRENT_TIMESTAMP - INTERVAL '4 days' + INTERVAL '6 hours 35 minutes', 'pressure', 44.9, 'release', 2, 130),
(12347, 'DEV-12347', CURRENT_TIMESTAMP - INTERVAL '4 days' + INTERVAL '13 hours', 'temperature', 30.3, 'flex', 3, 180);

-- День 5
INSERT INTO sensor_telemetry (user_id, device_id, timestamp, sensor_type, sensor_value, movement_type, movement_count, usage_duration_seconds) VALUES
(12347, 'DEV-12347', CURRENT_TIMESTAMP - INTERVAL '3 days' + INTERVAL '7 hours 45 minutes', 'pressure', 41.5, 'grip', 1, 98),
(12347, 'DEV-12347', CURRENT_TIMESTAMP - INTERVAL '3 days' + INTERVAL '7 hours 50 minutes', 'pressure', 43.2, 'release', 1, 103),
(12347, 'DEV-12347', CURRENT_TIMESTAMP - INTERVAL '3 days' + INTERVAL '16 hours', 'pressure', 47.3, 'grip', 2, 170);

-- День 6
INSERT INTO sensor_telemetry (user_id, device_id, timestamp, sensor_type, sensor_value, movement_type, movement_count, usage_duration_seconds) VALUES
(12347, 'DEV-12347', CURRENT_TIMESTAMP - INTERVAL '2 days' + INTERVAL '8 hours 20 minutes', 'pressure', 42.1, 'grip', 1, 105),
(12347, 'DEV-12347', CURRENT_TIMESTAMP - INTERVAL '2 days' + INTERVAL '8 hours 25 minutes', 'pressure', 44.6, 'release', 1, 110),
(12347, 'DEV-12347', CURRENT_TIMESTAMP - INTERVAL '2 days' + INTERVAL '12 hours', 'temperature', 29.9, 'flex', 2, 145),
(12347, 'DEV-12347', CURRENT_TIMESTAMP - INTERVAL '2 days' + INTERVAL '17 hours', 'pressure', 48.9, 'grip', 5, 290);

-- День 7 (вчера)
INSERT INTO sensor_telemetry (user_id, device_id, timestamp, sensor_type, sensor_value, movement_type, movement_count, usage_duration_seconds) VALUES
(12347, 'DEV-12347', CURRENT_TIMESTAMP - INTERVAL '1 day' + INTERVAL '9 hours', 'pressure', 43.1, 'grip', 2, 132),
(12347, 'DEV-12347', CURRENT_TIMESTAMP - INTERVAL '1 day' + INTERVAL '9 hours 5 minutes', 'pressure', 45.7, 'release', 2, 137),
(12347, 'DEV-12347', CURRENT_TIMESTAMP - INTERVAL '1 day' + INTERVAL '14 hours', 'temperature', 30.6, 'flex', 4, 240),
(12347, 'DEV-12347', CURRENT_TIMESTAMP - INTERVAL '1 day' + INTERVAL '18 hours', 'pressure', 47.2, 'grip', 3, 200),
(12347, 'DEV-12347', CURRENT_TIMESTAMP - INTERVAL '1 day' + INTERVAL '18 hours 15 minutes', 'pressure', 46.4, 'release', 3, 205);

-- ============================================================================
-- Проверка количества вставленных записей
-- ============================================================================
SELECT 
    user_id,
    COUNT(*) as total_records,
    MIN(timestamp) as first_record,
    MAX(timestamp) as last_record,
    SUM(usage_duration_seconds) as total_usage_seconds,
    SUM(movement_count) as total_movements
FROM sensor_telemetry
WHERE user_id IN (12345, 12346, 12347)
GROUP BY user_id
ORDER BY user_id;
