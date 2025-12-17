-- Создание базы данных для отчётов
CREATE DATABASE IF NOT EXISTS bionicpro_reports;

USE bionicpro_reports;

-- Создание витрины данных для отчётов
-- Таблица оптимизирована для быстрого доступа к данным по пользователям
CREATE TABLE IF NOT EXISTS reports_data_mart (
    user_id UInt32 COMMENT 'ID пользователя',
    email String COMMENT 'Email пользователя',
    first_name String COMMENT 'Имя пользователя',
    last_name String COMMENT 'Фамилия пользователя',
    prosthesis_id String COMMENT 'ID протеза',
    report_date Date COMMENT 'Дата отчёта',
    
    -- Метрики использования
    total_actions UInt32 COMMENT 'Общее количество действий',
    avg_response_time Float32 COMMENT 'Среднее время отклика (мс)',
    max_response_time Float32 COMMENT 'Максимальное время отклика (мс)',
    min_response_time Float32 COMMENT 'Минимальное время отклика (мс)',
    
    -- Типы действий
    grasp_count UInt32 COMMENT 'Количество захватов',
    release_count UInt32 COMMENT 'Количество отпусканий',
    flex_count UInt32 COMMENT 'Количество сгибаний',
    
    -- Состояние батареи
    avg_battery_level Float32 COMMENT 'Средний уровень заряда батареи (%)',
    min_battery_level Float32 COMMENT 'Минимальный уровень заряда батареи (%)',
    
    -- Время использования
    total_usage_seconds UInt32 COMMENT 'Общее время использования (секунды)',
    usage_hours Float32 COMMENT 'Время использования (часы)',
    actions_per_hour Float32 COMMENT 'Количество действий в час',
    
    -- Вычисляемые метрики
    efficiency_score Float32 COMMENT 'Оценка эффективности (0-100)',
    
    -- Данные из CRM
    order_date Date COMMENT 'Дата заказа протеза',
    status String COMMENT 'Статус пользователя',
    
    -- Служебные поля
    created_at DateTime DEFAULT now() COMMENT 'Время создания записи',
    updated_at DateTime DEFAULT now() COMMENT 'Время обновления записи'
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(report_date)  -- Партиционирование по месяцам для оптимизации
ORDER BY (user_id, report_date, prosthesis_id)  -- Сортировка для быстрого поиска по пользователю
PRIMARY KEY (user_id, report_date)  -- Первичный ключ для быстрого доступа
SETTINGS index_granularity = 8192;

-- Создание материализованного представления для агрегированных данных по пользователям
CREATE MATERIALIZED VIEW IF NOT EXISTS user_reports_summary
ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(report_date)
ORDER BY (user_id, report_date)
AS SELECT
    user_id,
    email,
    first_name,
    last_name,
    report_date,
    sum(total_actions) as total_actions,
    avg(avg_response_time) as avg_response_time,
    max(max_response_time) as max_response_time,
    min(min_response_time) as min_response_time,
    sum(grasp_count) as total_grasps,
    sum(release_count) as total_releases,
    sum(flex_count) as total_flexes,
    avg(avg_battery_level) as avg_battery_level,
    min(min_battery_level) as min_battery_level,
    sum(total_usage_seconds) as total_usage_seconds,
    sum(usage_hours) as total_usage_hours,
    avg(efficiency_score) as avg_efficiency_score
FROM reports_data_mart
GROUP BY user_id, email, first_name, last_name, report_date;

-- Создание индекса для быстрого поиска по email
-- В ClickHouse индексы создаются через ORDER BY, поэтому email включён в сортировку

-- Комментарии к таблице
ALTER TABLE reports_data_mart COMMENT COLUMN user_id 'ID пользователя из системы';
ALTER TABLE reports_data_mart COMMENT COLUMN prosthesis_id 'Уникальный идентификатор протеза';

