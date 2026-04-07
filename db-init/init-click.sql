CREATE DATABASE IF NOT EXISTS bionic;
USE bionic;

-- Создание единой таблицы для аналитики движений
CREATE TABLE IF NOT EXISTS prosthesis_events_datamart (
    -- Данные движения
    event_start_time DateTime,
    event_end_time DateTime,
    movement_type String,
    movements_count UInt32,
    
    -- Данные пользователя (денормализованные)
    user_id UInt32,
    user_first_name String,
    user_last_name String,
    user_email String
) 
ENGINE = MergeTree()
ORDER BY (event_start_time, user_id);