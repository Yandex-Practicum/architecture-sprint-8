-- =============================================================================
-- BionicPRO · CRM DB · Init Script
-- =============================================================================
-- Создаётся при первом запуске контейнера crm_db.
-- Таблица customers — данные клиентов из CRM (Битрикс24).
-- Используется:
--   - Airflow DAG (etl_reports): JOIN с телеметрией для витрины
--   - Задание 4 (CDC): Debezium отслеживает изменения
-- =============================================================================

CREATE TABLE IF NOT EXISTS customers (
    id      SERIAL PRIMARY KEY,
    name    VARCHAR(100),
    email   VARCHAR(100),
    age     NUMERIC,
    gender  VARCHAR(10),
    country VARCHAR(100),
    address VARCHAR(255),
    phone   VARCHAR(25)
);

-- Загрузка начальных данных из CSV
-- Файл crm.csv монтируется в /docker-entrypoint-initdb.d/ вместе с этим скриптом
COPY customers(id, name, email, age, gender, country, address, phone)
FROM '/docker-entrypoint-initdb.d/crm.csv'
DELIMITER ','
CSV HEADER;
