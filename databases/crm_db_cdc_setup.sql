-- ============================================================================
-- CRM Database CDC Setup for Debezium
-- BionicPRO - Задание 4: Change Data Capture
-- ============================================================================
-- Этот скрипт настраивает PostgreSQL для работы с Debezium CDC

-- ============================================================================
-- Создание роли для репликации (Debezium)
-- ============================================================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'debezium') THEN
        CREATE ROLE debezium WITH REPLICATION LOGIN PASSWORD 'debezium_password';
    END IF;
END
$$;

-- Даём права на чтение схемы и таблиц
GRANT USAGE ON SCHEMA crm TO debezium;
GRANT SELECT ON ALL TABLES IN SCHEMA crm TO debezium;
ALTER DEFAULT PRIVILEGES IN SCHEMA crm GRANT SELECT ON TABLES TO debezium;

-- ============================================================================
-- Создание публикации для Debezium
-- ============================================================================
-- Публикация определяет какие таблицы будут отслеживаться CDC

-- Удаляем существующую публикацию если есть
DROP PUBLICATION IF EXISTS dbz_publication;

-- Создаём публикацию для таблиц CRM
CREATE PUBLICATION dbz_publication FOR TABLE
    crm.customers,
    crm.prostheses,
    crm.prosthesis_models;

-- ============================================================================
-- Альтернатива: публикация для всех таблиц в схеме
-- CREATE PUBLICATION dbz_publication FOR ALL TABLES;
-- ============================================================================

-- ============================================================================
-- Настройка REPLICA IDENTITY для таблиц
-- ============================================================================
-- REPLICA IDENTITY FULL позволяет Debezium получать полные данные строк при UPDATE/DELETE
-- Это важно для proper CDC event payload

ALTER TABLE crm.customers REPLICA IDENTITY FULL;
ALTER TABLE crm.prostheses REPLICA IDENTITY FULL;
ALTER TABLE crm.prosthesis_models REPLICA IDENTITY FULL;

-- ============================================================================
-- Проверка настроек
-- ============================================================================
-- Можно выполнить для проверки:
-- SELECT * FROM pg_publication;
-- SELECT * FROM pg_publication_tables;
-- SELECT relname, relreplident FROM pg_class WHERE relname IN ('customers', 'prostheses', 'prosthesis_models');

-- ============================================================================
-- Справка по уровням REPLICA IDENTITY:
-- ============================================================================
-- DEFAULT (d): Только primary key в old значениях
-- USING INDEX: Использует уникальный индекс
-- FULL (f): Полные old значения всех колонок (рекомендуется для CDC)
-- NOTHING (n): Никаких old значений (не рекомендуется)
