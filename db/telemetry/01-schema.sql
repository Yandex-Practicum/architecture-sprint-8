-- ============================================================================
-- TELEMETRY DATABASE SCHEMA
-- Схема базы данных телеметрии для хранения событий от протезов
-- ============================================================================

-- Создание схемы для изоляции объектов телеметрии
CREATE SCHEMA IF NOT EXISTS telemetry;

-- ============================================================================
-- ТАБЛИЦА: telemetry.events
-- Описание: События телеметрии от бионических протезов
-- Данные поступают в реальном времени через 4G модуль из чипа ESP32
-- ============================================================================
CREATE TABLE IF NOT EXISTS telemetry.events (
    -- Первичный ключ (автоинкремент для больших объемов данных)
    event_id BIGSERIAL PRIMARY KEY,
    
    -- ID протеза (связь с crm.prostheses.prosthesis_id)
    prosthesis_id BIGINT NOT NULL,
    
    -- Временная метка события (время на протезе)
    event_time TIMESTAMP NOT NULL DEFAULT NOW(),
    
    -- Метрики производительности
    -- Время отклика протеза в миллисекундах (критично: должно быть < 100ms)
    response_ms DOUBLE PRECISION NOT NULL,
    
    -- Флаг ошибки выполнения команды
    is_error BOOLEAN NOT NULL DEFAULT FALSE,
    
    -- Уровень заряда батареи (0-100%)
    battery_level DOUBLE PRECISION NOT NULL,
    
    -- Временная метка записи в БД (для аудита)
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    
    -- Ограничения для валидации данных
    CONSTRAINT chk_response_ms_positive CHECK (response_ms >= 0),
    CONSTRAINT chk_response_ms_reasonable CHECK (response_ms <= 10000), -- Максимум 10 секунд
    CONSTRAINT chk_battery_level_range CHECK (battery_level >= 0 AND battery_level <= 100)
);

-- ============================================================================
-- ИНДЕКСЫ ДЛЯ ОПТИМИЗАЦИИ ЗАПРОСОВ
-- ============================================================================

-- Основной индекс для запросов по протезу и времени
CREATE INDEX IF NOT EXISTS idx_events_prosthesis_time 
    ON telemetry.events(prosthesis_id, event_time DESC);

-- Индекс для поиска ошибок
CREATE INDEX IF NOT EXISTS idx_events_errors 
    ON telemetry.events(prosthesis_id, event_time DESC) 
    WHERE is_error = TRUE;

-- Индекс для анализа производительности
CREATE INDEX IF NOT EXISTS idx_events_response_time 
    ON telemetry.events(event_time DESC, response_ms);

-- Индекс для мониторинга батареи
CREATE INDEX IF NOT EXISTS idx_events_battery 
    ON telemetry.events(prosthesis_id, event_time DESC) 
    WHERE battery_level < 20;

-- Индекс для партиционирования по дате
CREATE INDEX IF NOT EXISTS idx_events_date 
    ON telemetry.events(DATE(event_time), prosthesis_id);

-- ============================================================================
-- КОММЕНТАРИИ К ТАБЛИЦЕ И КОЛОНКАМ
-- ============================================================================

COMMENT ON TABLE telemetry.events IS 'События телеметрии от бионических протезов в реальном времени';
COMMENT ON COLUMN telemetry.events.event_id IS 'Уникальный идентификатор события';
COMMENT ON COLUMN telemetry.events.prosthesis_id IS 'ID протеза (связь с CRM)';
COMMENT ON COLUMN telemetry.events.event_time IS 'Время события на протезе';
COMMENT ON COLUMN telemetry.events.response_ms IS 'Время отклика протеза в миллисекундах (целевое значение < 100ms)';
COMMENT ON COLUMN telemetry.events.is_error IS 'Флаг ошибки выполнения команды';
COMMENT ON COLUMN telemetry.events.battery_level IS 'Уровень заряда батареи (0-100%)';
COMMENT ON COLUMN telemetry.events.created_at IS 'Время записи события в БД';

-- ============================================================================
-- ПРИМЕЧАНИЕ: АНАЛИТИКА И ВИТРИНЫ
-- ============================================================================
-- Все аналитические запросы и витрины данных находятся в ClickHouse OLAP
-- Эта база (telemetry_db) используется только для приема событий в реальном времени
-- ETL процесс (Airflow) переносит данные в ClickHouse для аналитики