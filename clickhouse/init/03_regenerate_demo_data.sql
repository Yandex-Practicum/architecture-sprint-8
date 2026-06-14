-- ============================================================================
-- Скрипт регенерации демо-данных для отчётов
-- Запускать вручную для обновления тестовых данных:
--   docker-compose exec clickhouse clickhouse-client --queries-file /docker-entrypoint-initdb.d/03_regenerate_demo_data.sql
-- ============================================================================

-- Удаляем старые демо-данные
ALTER TABLE reports.user_prosthesis_stats DELETE WHERE user_id IN (
    'ivan.petrov', 'maria.sidorova', 'alexey.kozlov', 'john.mueller', 'anna.schmidt'
);

-- Ждём завершения мутации
SELECT sleepEachRow(0.1) FROM numbers(30) FORMAT Null;

-- ============================================================================
-- Вставка демо-данных для ivan.petrov (BionicArm Pro - prothetic_user)
-- ============================================================================
INSERT INTO reports.user_prosthesis_stats
SELECT
    'ivan.petrov' AS user_id,
    1 AS prosthesis_id,
    'ESP32-ARM-001-A1B2C3' AS chip_id,
    toDate(now() - toIntervalDay(day_offset)) AS report_date,
    hour AS report_hour,
    'Петров Иван Сергеевич' AS customer_name,
    'ivan.petrov@bionicpro.com' AS customer_email,
    'russia' AS customer_region,
    'Москва' AS customer_branch,
    'BionicArm Pro 2024' AS prosthesis_model,
    'arm' AS prosthesis_category,
    'BP-2024-ARM-001' AS prosthesis_serial,
    toUInt32(15 + rand() % 20) AS movements_count,
    toUInt32(14 + rand() % 18) AS successful_movements,
    94.5 + (rand() % 50) / 10.0 AS success_rate,
    75.0 + (rand() % 500) / 10.0 AS avg_response_time,
    toUInt32(50 + rand() % 30) AS min_response_time,
    toUInt32(150 + rand() % 50) AS max_response_time,
    75.0 + (rand() % 250) / 10.0 AS avg_battery_level,
    toUInt8(65 + rand() % 20) AS min_battery_level,
    toUInt8(90 + rand() % 10) AS max_battery_level,
    38.0 + (rand() % 50) / 10.0 AS avg_actuator_temp,
    42.0 + (rand() % 30) / 10.0 AS max_actuator_temp,
    toUInt32(rand() % 2) AS error_count,
    toUInt32(rand() % 3) AS warning_count,
    92.0 + (rand() % 80) / 10.0 AS avg_connection_quality,
    250.0 + (rand() % 1000) / 10.0 AS avg_myo_amplitude,
    now() AS etl_processed_at,
    now() - toIntervalMinute(rand() % 60) AS source_updated_at
FROM (SELECT number AS day_offset FROM system.numbers LIMIT 7) AS days
CROSS JOIN (SELECT number + 8 AS hour FROM system.numbers LIMIT 14) AS hours
WHERE hour <= 22;

-- ============================================================================
-- Вставка демо-данных для maria.sidorova (BionicArm Standard - user)
-- ============================================================================
INSERT INTO reports.user_prosthesis_stats
SELECT
    'maria.sidorova' AS user_id,
    2 AS prosthesis_id,
    'ESP32-ARM-002-D4E5F6' AS chip_id,
    toDate(now() - toIntervalDay(day_offset)) AS report_date,
    hour AS report_hour,
    'Сидорова Мария Александровна' AS customer_name,
    'maria.sidorova@bionicpro.com' AS customer_email,
    'russia' AS customer_region,
    'Санкт-Петербург' AS customer_branch,
    'BionicArm Standard 2024' AS prosthesis_model,
    'arm' AS prosthesis_category,
    'BP-2024-ARM-002' AS prosthesis_serial,
    toUInt32(12 + rand() % 18) AS movements_count,
    toUInt32(11 + rand() % 16) AS successful_movements,
    93.0 + (rand() % 60) / 10.0 AS success_rate,
    80.0 + (rand() % 400) / 10.0 AS avg_response_time,
    toUInt32(55 + rand() % 25) AS min_response_time,
    toUInt32(140 + rand() % 60) AS max_response_time,
    70.0 + (rand() % 280) / 10.0 AS avg_battery_level,
    toUInt8(60 + rand() % 25) AS min_battery_level,
    toUInt8(88 + rand() % 12) AS max_battery_level,
    37.5 + (rand() % 60) / 10.0 AS avg_actuator_temp,
    41.0 + (rand() % 40) / 10.0 AS max_actuator_temp,
    toUInt32(rand() % 2) AS error_count,
    toUInt32(rand() % 4) AS warning_count,
    90.0 + (rand() % 90) / 10.0 AS avg_connection_quality,
    230.0 + (rand() % 1200) / 10.0 AS avg_myo_amplitude,
    now() AS etl_processed_at,
    now() - toIntervalMinute(rand() % 60) AS source_updated_at
FROM (SELECT number AS day_offset FROM system.numbers LIMIT 7) AS days
CROSS JOIN (SELECT number + 8 AS hour FROM system.numbers LIMIT 14) AS hours
WHERE hour <= 22;

-- ============================================================================
-- Вставка демо-данных для alexey.kozlov (BionicHand Pro - administrator)
-- ============================================================================
INSERT INTO reports.user_prosthesis_stats
SELECT
    'alexey.kozlov' AS user_id,
    3 AS prosthesis_id,
    'ESP32-HAND-001-G7H8I9' AS chip_id,
    toDate(now() - toIntervalDay(day_offset)) AS report_date,
    hour AS report_hour,
    'Козлов Алексей Дмитриевич' AS customer_name,
    'alexey.kozlov@bionicpro.com' AS customer_email,
    'russia' AS customer_region,
    'Новосибирск' AS customer_branch,
    'BionicHand Pro 2024' AS prosthesis_model,
    'hand' AS prosthesis_category,
    'BP-2024-HAND-001' AS prosthesis_serial,
    toUInt32(18 + rand() % 25) AS movements_count,
    toUInt32(17 + rand() % 22) AS successful_movements,
    95.0 + (rand() % 40) / 10.0 AS success_rate,
    70.0 + (rand() % 350) / 10.0 AS avg_response_time,
    toUInt32(45 + rand() % 25) AS min_response_time,
    toUInt32(130 + rand() % 50) AS max_response_time,
    78.0 + (rand() % 200) / 10.0 AS avg_battery_level,
    toUInt8(68 + rand() % 18) AS min_battery_level,
    toUInt8(92 + rand() % 8) AS max_battery_level,
    36.5 + (rand() % 55) / 10.0 AS avg_actuator_temp,
    40.0 + (rand() % 35) / 10.0 AS max_actuator_temp,
    toUInt32(rand() % 2) AS error_count,
    toUInt32(rand() % 2) AS warning_count,
    93.0 + (rand() % 70) / 10.0 AS avg_connection_quality,
    270.0 + (rand() % 800) / 10.0 AS avg_myo_amplitude,
    now() AS etl_processed_at,
    now() - toIntervalMinute(rand() % 60) AS source_updated_at
FROM (SELECT number AS day_offset FROM system.numbers LIMIT 7) AS days
CROSS JOIN (SELECT number + 8 AS hour FROM system.numbers LIMIT 14) AS hours
WHERE hour <= 22;

-- ============================================================================
-- Вставка демо-данных для john.mueller (BionicLeg Pro - prothetic_user)
-- ============================================================================
INSERT INTO reports.user_prosthesis_stats
SELECT
    'john.mueller' AS user_id,
    4 AS prosthesis_id,
    'ESP32-LEG-001-J0K1L2' AS chip_id,
    toDate(now() - toIntervalDay(day_offset)) AS report_date,
    hour AS report_hour,
    'John Mueller' AS customer_name,
    'john.mueller@bionicpro.eu' AS customer_email,
    'europe' AS customer_region,
    'Berlin' AS customer_branch,
    'BionicLeg Pro 2024' AS prosthesis_model,
    'leg' AS prosthesis_category,
    'BP-2024-LEG-001' AS prosthesis_serial,
    toUInt32(20 + rand() % 30) AS movements_count,
    toUInt32(19 + rand() % 27) AS successful_movements,
    96.0 + (rand() % 35) / 10.0 AS success_rate,
    65.0 + (rand() % 300) / 10.0 AS avg_response_time,
    toUInt32(40 + rand() % 20) AS min_response_time,
    toUInt32(120 + rand() % 45) AS max_response_time,
    80.0 + (rand() % 180) / 10.0 AS avg_battery_level,
    toUInt8(70 + rand() % 15) AS min_battery_level,
    toUInt8(93 + rand() % 7) AS max_battery_level,
    37.0 + (rand() % 45) / 10.0 AS avg_actuator_temp,
    41.5 + (rand() % 30) / 10.0 AS max_actuator_temp,
    toUInt32(rand() % 2) AS error_count,
    toUInt32(rand() % 3) AS warning_count,
    94.0 + (rand() % 60) / 10.0 AS avg_connection_quality,
    280.0 + (rand() % 700) / 10.0 AS avg_myo_amplitude,
    now() AS etl_processed_at,
    now() - toIntervalMinute(rand() % 60) AS source_updated_at
FROM (SELECT number AS day_offset FROM system.numbers LIMIT 7) AS days
CROSS JOIN (SELECT number + 8 AS hour FROM system.numbers LIMIT 14) AS hours
WHERE hour <= 22;

-- ============================================================================
-- Вставка демо-данных для anna.schmidt (BionicLeg Standard - user)
-- ============================================================================
INSERT INTO reports.user_prosthesis_stats
SELECT
    'anna.schmidt' AS user_id,
    5 AS prosthesis_id,
    'ESP32-LEG-002-M3N4O5' AS chip_id,
    toDate(now() - toIntervalDay(day_offset)) AS report_date,
    hour AS report_hour,
    'Anna Schmidt' AS customer_name,
    'anna.schmidt@bionicpro.eu' AS customer_email,
    'europe' AS customer_region,
    'Munich' AS customer_branch,
    'BionicLeg Standard 2024' AS prosthesis_model,
    'leg' AS prosthesis_category,
    'BP-2024-LEG-002' AS prosthesis_serial,
    toUInt32(14 + rand() % 22) AS movements_count,
    toUInt32(13 + rand() % 20) AS successful_movements,
    94.0 + (rand() % 50) / 10.0 AS success_rate,
    78.0 + (rand() % 380) / 10.0 AS avg_response_time,
    toUInt32(52 + rand() % 28) AS min_response_time,
    toUInt32(138 + rand() % 55) AS max_response_time,
    73.0 + (rand() % 240) / 10.0 AS avg_battery_level,
    toUInt8(63 + rand() % 22) AS min_battery_level,
    toUInt8(89 + rand() % 11) AS max_battery_level,
    37.8 + (rand() % 52) / 10.0 AS avg_actuator_temp,
    42.0 + (rand() % 32) / 10.0 AS max_actuator_temp,
    toUInt32(rand() % 2) AS error_count,
    toUInt32(rand() % 4) AS warning_count,
    91.0 + (rand() % 85) / 10.0 AS avg_connection_quality,
    245.0 + (rand() % 900) / 10.0 AS avg_myo_amplitude,
    now() AS etl_processed_at,
    now() - toIntervalMinute(rand() % 60) AS source_updated_at
FROM (SELECT number AS day_offset FROM system.numbers LIMIT 7) AS days
CROSS JOIN (SELECT number + 8 AS hour FROM system.numbers LIMIT 14) AS hours
WHERE hour <= 22;

-- Проверяем результат
SELECT
    user_id,
    count() AS total_records,
    min(report_date) AS first_date,
    max(report_date) AS last_date
FROM reports.user_prosthesis_stats
WHERE user_id IN ('ivan.petrov', 'maria.sidorova', 'alexey.kozlov', 'john.mueller', 'anna.schmidt')
GROUP BY user_id
ORDER BY user_id;
