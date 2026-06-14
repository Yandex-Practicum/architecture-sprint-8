-- ============================================================================
-- Telemetry Database Schema (Source: PostgreSQL)
-- BionicPRO Telemetry - данные телеметрии с протезов
-- ============================================================================

-- Создание схемы
CREATE SCHEMA IF NOT EXISTS telemetry;

-- ============================================================================
-- Таблица сырых данных телеметрии (основная таблица)
-- ============================================================================
CREATE TABLE IF NOT EXISTS telemetry.raw_telemetry (
    telemetry_id        BIGSERIAL PRIMARY KEY,
    chip_id             VARCHAR(64) NOT NULL,                  -- ID чипа ESP32 протеза
    timestamp           TIMESTAMP WITH TIME ZONE NOT NULL,

    -- Миосигналы (данные с электродов)
    myo_channel_1       FLOAT,                                 -- Канал 1 миосигнала (мкВ)
    myo_channel_2       FLOAT,                                 -- Канал 2 миосигнала (мкВ)
    myo_channel_3       FLOAT,                                 -- Канал 3 миосигнала (мкВ)
    myo_channel_4       FLOAT,                                 -- Канал 4 миосигнала (мкВ)

    -- Данные движения
    movement_type       VARCHAR(50),                           -- grip, release, rotate_left, rotate_right, flex, extend
    movement_intensity  FLOAT,                                 -- Интенсивность 0-100%
    response_time_ms    INTEGER,                               -- Время отклика в мс
    movement_success    BOOLEAN DEFAULT TRUE,                  -- Успешность выполнения

    -- Данные датчиков
    accelerometer_x     FLOAT,
    accelerometer_y     FLOAT,
    accelerometer_z     FLOAT,
    gyroscope_x         FLOAT,
    gyroscope_y         FLOAT,
    gyroscope_z         FLOAT,

    -- Температура и давление
    actuator_temp       FLOAT,                                 -- Температура актуатора (°C)
    grip_pressure       FLOAT,                                 -- Давление захвата (Н)

    -- Состояние устройства
    battery_level       SMALLINT,                              -- Уровень заряда 0-100%
    battery_voltage     FLOAT,                                 -- Напряжение батареи (В)
    connection_quality  SMALLINT,                              -- Качество связи 0-100%

    -- Ошибки и предупреждения
    error_code          VARCHAR(20),                           -- Код ошибки (если есть)
    warning_flags       INTEGER DEFAULT 0,                     -- Битовая маска предупреждений

    -- Служебные поля
    firmware_version    VARCHAR(20),
    session_id          UUID,                                  -- ID сессии использования
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Партиционирование по времени для оптимизации (в реальности создавались бы партиции)
CREATE INDEX IF NOT EXISTS idx_raw_telemetry_chip_timestamp ON telemetry.raw_telemetry(chip_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_raw_telemetry_timestamp ON telemetry.raw_telemetry(timestamp);
CREATE INDEX IF NOT EXISTS idx_raw_telemetry_chip_id ON telemetry.raw_telemetry(chip_id);
CREATE INDEX IF NOT EXISTS idx_raw_telemetry_created_at ON telemetry.raw_telemetry(created_at);

-- ============================================================================
-- Таблица сессий использования протеза
-- ============================================================================
CREATE TABLE IF NOT EXISTS telemetry.usage_sessions (
    session_id          UUID PRIMARY KEY,
    chip_id             VARCHAR(64) NOT NULL,
    started_at          TIMESTAMP WITH TIME ZONE NOT NULL,
    ended_at            TIMESTAMP WITH TIME ZONE,
    duration_seconds    INTEGER,
    total_movements     INTEGER DEFAULT 0,
    successful_movements INTEGER DEFAULT 0,
    avg_response_time_ms FLOAT,
    min_battery_level   SMALLINT,
    max_actuator_temp   FLOAT,
    error_count         INTEGER DEFAULT 0,
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_usage_sessions_chip_id ON telemetry.usage_sessions(chip_id);
CREATE INDEX IF NOT EXISTS idx_usage_sessions_started_at ON telemetry.usage_sessions(started_at);

-- ============================================================================
-- Таблица агрегированных данных за час (для ускорения ETL)
-- ============================================================================
CREATE TABLE IF NOT EXISTS telemetry.hourly_stats (
    id                  BIGSERIAL PRIMARY KEY,
    chip_id             VARCHAR(64) NOT NULL,
    hour_start          TIMESTAMP WITH TIME ZONE NOT NULL,

    -- Агрегированные метрики
    movements_count     INTEGER DEFAULT 0,
    successful_movements INTEGER DEFAULT 0,
    avg_response_time   FLOAT,
    min_response_time   INTEGER,
    max_response_time   INTEGER,

    -- Статистика батареи
    avg_battery_level   FLOAT,
    min_battery_level   SMALLINT,
    max_battery_level   SMALLINT,

    -- Статистика температуры
    avg_actuator_temp   FLOAT,
    max_actuator_temp   FLOAT,

    -- Ошибки
    error_count         INTEGER DEFAULT 0,
    warning_count       INTEGER DEFAULT 0,

    -- Миосигналы (средние)
    avg_myo_amplitude   FLOAT,

    -- Качество связи
    avg_connection_quality FLOAT,

    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE(chip_id, hour_start)
);

CREATE INDEX IF NOT EXISTS idx_hourly_stats_chip_hour ON telemetry.hourly_stats(chip_id, hour_start);
CREATE INDEX IF NOT EXISTS idx_hourly_stats_hour_start ON telemetry.hourly_stats(hour_start);

-- ============================================================================
-- Функция для агрегации данных за час
-- ============================================================================
CREATE OR REPLACE FUNCTION telemetry.aggregate_hourly_stats(
    p_hour_start TIMESTAMP WITH TIME ZONE
)
RETURNS INTEGER AS $$
DECLARE
    rows_affected INTEGER;
BEGIN
    INSERT INTO telemetry.hourly_stats (
        chip_id,
        hour_start,
        movements_count,
        successful_movements,
        avg_response_time,
        min_response_time,
        max_response_time,
        avg_battery_level,
        min_battery_level,
        max_battery_level,
        avg_actuator_temp,
        max_actuator_temp,
        error_count,
        warning_count,
        avg_myo_amplitude,
        avg_connection_quality
    )
    SELECT
        chip_id,
        date_trunc('hour', timestamp) AS hour_start,
        COUNT(*) FILTER (WHERE movement_type IS NOT NULL) AS movements_count,
        COUNT(*) FILTER (WHERE movement_type IS NOT NULL AND movement_success = TRUE) AS successful_movements,
        AVG(response_time_ms) FILTER (WHERE response_time_ms IS NOT NULL) AS avg_response_time,
        MIN(response_time_ms) FILTER (WHERE response_time_ms IS NOT NULL) AS min_response_time,
        MAX(response_time_ms) FILTER (WHERE response_time_ms IS NOT NULL) AS max_response_time,
        AVG(battery_level) AS avg_battery_level,
        MIN(battery_level) AS min_battery_level,
        MAX(battery_level) AS max_battery_level,
        AVG(actuator_temp) AS avg_actuator_temp,
        MAX(actuator_temp) AS max_actuator_temp,
        COUNT(*) FILTER (WHERE error_code IS NOT NULL) AS error_count,
        COUNT(*) FILTER (WHERE warning_flags > 0) AS warning_count,
        AVG(SQRT(POWER(COALESCE(myo_channel_1, 0), 2) + POWER(COALESCE(myo_channel_2, 0), 2) +
                 POWER(COALESCE(myo_channel_3, 0), 2) + POWER(COALESCE(myo_channel_4, 0), 2))) AS avg_myo_amplitude,
        AVG(connection_quality) AS avg_connection_quality
    FROM telemetry.raw_telemetry
    WHERE timestamp >= p_hour_start
      AND timestamp < p_hour_start + INTERVAL '1 hour'
    GROUP BY chip_id, date_trunc('hour', timestamp)
    ON CONFLICT (chip_id, hour_start) DO UPDATE SET
        movements_count = EXCLUDED.movements_count,
        successful_movements = EXCLUDED.successful_movements,
        avg_response_time = EXCLUDED.avg_response_time,
        min_response_time = EXCLUDED.min_response_time,
        max_response_time = EXCLUDED.max_response_time,
        avg_battery_level = EXCLUDED.avg_battery_level,
        min_battery_level = EXCLUDED.min_battery_level,
        max_battery_level = EXCLUDED.max_battery_level,
        avg_actuator_temp = EXCLUDED.avg_actuator_temp,
        max_actuator_temp = EXCLUDED.max_actuator_temp,
        error_count = EXCLUDED.error_count,
        warning_count = EXCLUDED.warning_count,
        avg_myo_amplitude = EXCLUDED.avg_myo_amplitude,
        avg_connection_quality = EXCLUDED.avg_connection_quality,
        updated_at = NOW();

    GET DIAGNOSTICS rows_affected = ROW_COUNT;
    RETURN rows_affected;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- Представление для ETL - почасовая телеметрия
-- ============================================================================
CREATE OR REPLACE VIEW telemetry.v_hourly_telemetry AS
SELECT
    chip_id,
    hour_start,
    DATE(hour_start) AS report_date,
    EXTRACT(HOUR FROM hour_start) AS report_hour,
    movements_count,
    successful_movements,
    CASE WHEN movements_count > 0
         THEN ROUND((successful_movements::FLOAT / movements_count * 100)::NUMERIC, 2)
         ELSE 0 END AS success_rate,
    ROUND(avg_response_time::NUMERIC, 2) AS avg_response_time,
    min_response_time,
    max_response_time,
    ROUND(avg_battery_level::NUMERIC, 2) AS avg_battery_level,
    min_battery_level,
    max_battery_level,
    ROUND(avg_actuator_temp::NUMERIC, 2) AS avg_actuator_temp,
    max_actuator_temp,
    error_count,
    warning_count,
    ROUND(avg_myo_amplitude::NUMERIC, 2) AS avg_myo_amplitude,
    ROUND(avg_connection_quality::NUMERIC, 2) AS avg_connection_quality,
    updated_at
FROM telemetry.hourly_stats;

-- ============================================================================
-- Генерация тестовых данных телеметрии
-- ============================================================================
-- Функция для генерации случайного движения
CREATE OR REPLACE FUNCTION telemetry.random_movement_type()
RETURNS VARCHAR(50) AS $$
DECLARE
    movements VARCHAR(50)[] := ARRAY['grip', 'release', 'rotate_left', 'rotate_right', 'flex', 'extend'];
BEGIN
    RETURN movements[1 + floor(random() * 6)::INTEGER];
END;
$$ LANGUAGE plpgsql;

-- Генерация тестовых данных за последние 7 дней
DO $$
DECLARE
    chip_ids VARCHAR(64)[] := ARRAY[
        'ESP32-ARM-001-A1B2C3',
        'ESP32-ARM-002-D4E5F6',
        'ESP32-HAND-001-G7H8I9',
        'ESP32-LEG-001-J0K1L2',
        'ESP32-LEG-002-M3N4O5'
    ];
    chip VARCHAR(64);
    current_ts TIMESTAMP WITH TIME ZONE;
    end_ts TIMESTAMP WITH TIME ZONE;
    session_uuid UUID;
    i INTEGER;
BEGIN
    end_ts := NOW();

    FOREACH chip IN ARRAY chip_ids LOOP
        current_ts := end_ts - INTERVAL '7 days';

        WHILE current_ts < end_ts LOOP
            -- Генерируем данные только в "активные" часы (8:00 - 22:00)
            IF EXTRACT(HOUR FROM current_ts) BETWEEN 8 AND 22 THEN
                session_uuid := gen_random_uuid();

                -- Генерируем 10-30 записей телеметрии за час
                FOR i IN 1..floor(random() * 20 + 10)::INTEGER LOOP
                    INSERT INTO telemetry.raw_telemetry (
                        chip_id,
                        timestamp,
                        myo_channel_1,
                        myo_channel_2,
                        myo_channel_3,
                        myo_channel_4,
                        movement_type,
                        movement_intensity,
                        response_time_ms,
                        movement_success,
                        accelerometer_x,
                        accelerometer_y,
                        accelerometer_z,
                        gyroscope_x,
                        gyroscope_y,
                        gyroscope_z,
                        actuator_temp,
                        grip_pressure,
                        battery_level,
                        battery_voltage,
                        connection_quality,
                        error_code,
                        warning_flags,
                        firmware_version,
                        session_id
                    ) VALUES (
                        chip,
                        current_ts + (random() * INTERVAL '1 hour'),
                        random() * 500,                                    -- myo_channel_1
                        random() * 500,                                    -- myo_channel_2
                        random() * 450,                                    -- myo_channel_3
                        random() * 450,                                    -- myo_channel_4
                        telemetry.random_movement_type(),                  -- movement_type
                        random() * 100,                                    -- movement_intensity
                        50 + floor(random() * 150)::INTEGER,               -- response_time_ms (50-200ms)
                        random() > 0.05,                                   -- 95% успешность
                        (random() - 0.5) * 2,                              -- accelerometer_x
                        (random() - 0.5) * 2,                              -- accelerometer_y
                        9.8 + (random() - 0.5) * 0.2,                      -- accelerometer_z
                        (random() - 0.5) * 50,                             -- gyroscope_x
                        (random() - 0.5) * 50,                             -- gyroscope_y
                        (random() - 0.5) * 50,                             -- gyroscope_z
                        35 + random() * 10,                                -- actuator_temp (35-45°C)
                        random() * 50,                                     -- grip_pressure
                        60 + floor(random() * 40)::INTEGER,                -- battery_level (60-100%)
                        3.7 + random() * 0.5,                              -- battery_voltage (3.7-4.2V)
                        80 + floor(random() * 20)::INTEGER,                -- connection_quality (80-100%)
                        CASE WHEN random() > 0.98 THEN 'ERR_SENSOR' ELSE NULL END,  -- 2% ошибок
                        CASE WHEN random() > 0.95 THEN 1 ELSE 0 END,       -- 5% предупреждений
                        'v2.1.5',
                        session_uuid
                    );
                END LOOP;
            END IF;

            current_ts := current_ts + INTERVAL '1 hour';
        END LOOP;
    END LOOP;
END $$;

-- Агрегируем данные за все часы
DO $$
DECLARE
    hour_cursor TIMESTAMP WITH TIME ZONE;
BEGIN
    FOR hour_cursor IN
        SELECT DISTINCT date_trunc('hour', timestamp) AS hour_start
        FROM telemetry.raw_telemetry
        ORDER BY hour_start
    LOOP
        PERFORM telemetry.aggregate_hourly_stats(hour_cursor);
    END LOOP;
END $$;
