-- ============================================================================
-- CRM DATABASE SCHEMA
-- Схема базы данных CRM для хранения информации о клиентах и протезах
-- ============================================================================

-- Создание схемы для изоляции объектов CRM
CREATE SCHEMA IF NOT EXISTS crm;

-- ============================================================================
-- ТАБЛИЦА: crm.customers
-- Описание: Клиенты компании BionicPRO
-- ============================================================================
CREATE TABLE IF NOT EXISTS crm.customers (
    -- Первичный ключ
    customer_id SERIAL PRIMARY KEY,
    
    -- Внешний идентификатор пользователя из Keycloak (UUID)
    -- Используется для связи с системой аутентификации
    user_external_id VARCHAR(255) NOT NULL UNIQUE,
    
    -- Персональные данные
    full_name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    phone VARCHAR(50),
    
    -- Страна клиента (ISO 3166-1 alpha-2, например: RU, KZ, BY)
    country VARCHAR(2) NOT NULL,
    
    -- Временные метки
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    
    -- Ограничения
    CONSTRAINT chk_email_format CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'),
    CONSTRAINT chk_country_code CHECK (LENGTH(country) = 2)
);

-- Индексы для оптимизации запросов
CREATE INDEX IF NOT EXISTS idx_customers_user_external_id ON crm.customers(user_external_id);
CREATE INDEX IF NOT EXISTS idx_customers_email ON crm.customers(email);
CREATE INDEX IF NOT EXISTS idx_customers_country ON crm.customers(country);
CREATE INDEX IF NOT EXISTS idx_customers_created_at ON crm.customers(created_at);

-- Комментарии к таблице и колонкам
COMMENT ON TABLE crm.customers IS 'Клиенты компании BionicPRO';
COMMENT ON COLUMN crm.customers.customer_id IS 'Уникальный идентификатор клиента';
COMMENT ON COLUMN crm.customers.user_external_id IS 'Внешний ID из Keycloak (sub claim из JWT)';
COMMENT ON COLUMN crm.customers.full_name IS 'Полное имя клиента';
COMMENT ON COLUMN crm.customers.email IS 'Email адрес клиента';
COMMENT ON COLUMN crm.customers.phone IS 'Телефон клиента';
COMMENT ON COLUMN crm.customers.country IS 'Код страны (ISO 3166-1 alpha-2)';
COMMENT ON COLUMN crm.customers.created_at IS 'Дата и время создания записи';
COMMENT ON COLUMN crm.customers.updated_at IS 'Дата и время последнего обновления';

-- ============================================================================
-- ТАБЛИЦА: crm.prostheses
-- Описание: Бионические протезы, принадлежащие клиентам
-- ============================================================================
CREATE TABLE IF NOT EXISTS crm.prostheses (
    -- Первичный ключ (ID протеза из чипа)
    prosthesis_id BIGINT PRIMARY KEY,
    
    -- Внешний ключ на клиента
    customer_id INTEGER NOT NULL,
    
    -- Модель протеза (например: BP-ARM-X, BP-LEG-Z)
    model VARCHAR(50) NOT NULL,
    
    -- Временные метки жизненного цикла
    activated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    deactivated_at TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    
    -- Внешний ключ
    CONSTRAINT fk_prostheses_customer 
        FOREIGN KEY (customer_id) 
        REFERENCES crm.customers(customer_id) 
        ON DELETE CASCADE,
    
    -- Ограничения
    CONSTRAINT chk_activation_order 
        CHECK (deactivated_at IS NULL OR deactivated_at >= activated_at)
);

-- Индексы для оптимизации запросов
CREATE INDEX IF NOT EXISTS idx_prostheses_customer_id ON crm.prostheses(customer_id);
CREATE INDEX IF NOT EXISTS idx_prostheses_model ON crm.prostheses(model);
CREATE INDEX IF NOT EXISTS idx_prostheses_activated_at ON crm.prostheses(activated_at);
CREATE INDEX IF NOT EXISTS idx_prostheses_active 
    ON crm.prostheses(customer_id, prosthesis_id) 
    WHERE deactivated_at IS NULL;

-- Комментарии к таблице и колонкам
COMMENT ON TABLE crm.prostheses IS 'Бионические протезы клиентов';
COMMENT ON COLUMN crm.prostheses.prosthesis_id IS 'Уникальный ID протеза (из чипа ESP32)';
COMMENT ON COLUMN crm.prostheses.customer_id IS 'ID клиента-владельца протеза';
COMMENT ON COLUMN crm.prostheses.model IS 'Модель протеза';
COMMENT ON COLUMN crm.prostheses.activated_at IS 'Дата активации протеза';
COMMENT ON COLUMN crm.prostheses.deactivated_at IS 'Дата деактивации (NULL если активен)';
COMMENT ON COLUMN crm.prostheses.updated_at IS 'Дата последнего обновления записи';

-- ============================================================================
-- ТРИГГЕРЫ ДЛЯ АВТОМАТИЧЕСКОГО ОБНОВЛЕНИЯ updated_at
-- ============================================================================

-- Функция для обновления updated_at
CREATE OR REPLACE FUNCTION crm.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Триггер для customers
CREATE TRIGGER trg_customers_updated_at
    BEFORE UPDATE ON crm.customers
    FOR EACH ROW
    EXECUTE FUNCTION crm.update_updated_at_column();

-- Триггер для prostheses
CREATE TRIGGER trg_prostheses_updated_at
    BEFORE UPDATE ON crm.prostheses
    FOR EACH ROW
    EXECUTE FUNCTION crm.update_updated_at_column();

-- ============================================================================
-- ПРИМЕЧАНИЕ: АНАЛИТИКА И ОТЧЕТНОСТЬ
-- ============================================================================
-- Все аналитические витрины и отчеты находятся в ClickHouse OLAP
-- Эта база (crm_db) используется только для хранения мастер-данных
-- ETL процесс (Airflow) переносит данные в ClickHouse для аналитики
