-- Создание базы данных для витрины
CREATE DATABASE IF NOT EXISTS bionicpro;

-- Создание витрины отчётов
CREATE TABLE IF NOT EXISTS bionicpro.user_report_mart (
    -- Идентификаторы
    user_id String,
    user_email String,
    user_name String,
    country String,
    prosthesis_id String,
    prosthesis_type String,
    
    -- Временные метки
    report_date Date,
    first_signal_time DateTime,
    last_signal_time DateTime,
    
    -- Агрегированные метрики
    total_signals UInt32,
    avg_reaction_time_ms Float32,
    max_reaction_time_ms UInt32,
    min_reaction_time_ms UInt32,
    stddev_reaction_time_ms Float32,
    
    -- Качество работы
    successful_movements UInt32,
    failed_movements UInt32,
    success_rate Float32,
    misclassification_rate Float32,
    
    -- Состояние батареи
    avg_battery_level Float32,
    min_battery_level UInt8,
    avg_signal_quality Float32,
    
    -- Метрики качества
    quality_ok UInt8,
    needs_tuning UInt8,
    
    -- Информация о протезе
    tuning_count UInt32,
    last_tuning_date DateTime,
    prosthesis_age_days UInt32,
    
    -- Метаданные ETL
    etl_created_at DateTime DEFAULT now()
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(report_date)
ORDER BY (user_id, report_date)
SETTINGS index_granularity = 8192;

-- Создание индекса для быстрого поиска по пользователю
ALTER TABLE bionicpro.user_report_mart ADD INDEX idx_user_id user_id TYPE bloom_filter GRANULARITY 1;
ALTER TABLE bionicpro.user_report_mart ADD INDEX idx_email user_email TYPE bloom_filter GRANULARITY 1;