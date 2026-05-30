-- Создание базы данных
CREATE DATABASE IF NOT EXISTS reports_db;

USE reports_db;

-- Полная таблица для отчётов с движком TinyLog (без проблем с правами)
CREATE TABLE IF NOT EXISTS user_report_mart (
    -- Данные из CRM
                                                user_id String,
                                                user_name String,
                                                email String,
                                                phone String,
                                                prosthesis_model String,
                                                serial_number String,
                                                registration_date Date,

    -- Агрегированные данные телеметрии
                                                total_movements UInt32 DEFAULT 0,
                                                avg_reaction_time Float32 DEFAULT 0,
                                                median_reaction_time Float32 DEFAULT 0,
                                                min_reaction_time UInt16 DEFAULT 0,
                                                max_reaction_time UInt16 DEFAULT 0,
                                                avg_signal_quality Float32 DEFAULT 0,
                                                min_signal_quality Float32 DEFAULT 0,
                                                avg_battery_level UInt8 DEFAULT 0,

    -- Вычисляемые метрики
                                                performance_score Float32 DEFAULT 0,
                                                needs_calibration Bool DEFAULT false,

    -- Временные метки
                                                last_activity_date Date,
                                                report_date Date DEFAULT today(),
    updated_at DateTime DEFAULT now()
    ) ENGINE = TinyLog();