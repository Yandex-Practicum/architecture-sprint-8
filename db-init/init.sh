#!/bin/bash
set -e

# 1. Создание ролей и баз данных (от имени суперпользователя postgres)
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "postgres" <<-EOSQL
    -- Создание ролей
    CREATE ROLE keycloak NOSUPERUSER CREATEDB NOCREATEROLE NOINHERIT LOGIN NOREPLICATION NOBYPASSRLS PASSWORD 'keycloak';
    CREATE ROLE airflow NOSUPERUSER CREATEDB NOCREATEROLE NOINHERIT LOGIN NOREPLICATION NOBYPASSRLS PASSWORD 'airflow';
    CREATE ROLE prosthesis NOSUPERUSER CREATEDB NOCREATEROLE NOINHERIT LOGIN NOREPLICATION NOBYPASSRLS PASSWORD 'prosthesis';
    CREATE ROLE bionic_crm NOSUPERUSER CREATEDB NOCREATEROLE NOINHERIT LOGIN NOREPLICATION NOBYPASSRLS PASSWORD 'bionic_crm';

    -- Создание баз данных
    CREATE DATABASE keycloak WITH OWNER = keycloak ENCODING = 'UTF8';
    CREATE DATABASE airflow WITH OWNER = airflow ENCODING = 'UTF8';
    CREATE DATABASE prosthesis WITH OWNER = prosthesis ENCODING = 'UTF8';
    CREATE DATABASE bionic_crm WITH OWNER = bionic_crm ENCODING = 'UTF8';
EOSQL

# 2. Наполнение базы PROSTHESIS
echo "Initializing prosthesis database..."
export PGPASSWORD='prosthesis'
psql -v ON_ERROR_STOP=1 --username "prosthesis" --dbname "prosthesis" <<-EOSQL
    CREATE TABLE IF NOT EXISTS prosthesis_usage (
        id SERIAL PRIMARY KEY,
        user_id INTEGER,
        start_time TIMESTAMP,
        end_time TIMESTAMP,
        movement_type VARCHAR(50),
        movements_count INTEGER
    );

    INSERT INTO prosthesis_usage (user_id, start_time, end_time, movement_type, movements_count)
    SELECT 
        floor(random() * 10 + 1)::int AS user_id,
        ts AS start_time,
        ts + (random() * interval '30 minutes') AS end_time,
        (ARRAY['Сжатие кисти', 'Разжатие кисти', 'Вращение', 'Указательный жест', 'Хват щепотью'])[floor(random() * 5 + 1)] AS movement_type,
        floor(random() * 20 + 1)::int AS movements_count
    FROM (
        SELECT NOW() - (random() * interval '30 days') AS ts
        FROM generate_series(1, 1000)
    ) AS random_times
    ORDER BY ts;
EOSQL

# 3. Наполнение базы BIONIC_CRM
echo "Initializing bionic_crm database..."
export PGPASSWORD='bionic_crm'
psql -v ON_ERROR_STOP=1 --username "bionic_crm" --dbname "bionic_crm" <<-EOSQL
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        first_name VARCHAR(50),
        last_name VARCHAR(50),
        email VARCHAR(100) UNIQUE,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP 
    );

    INSERT INTO users (first_name, last_name, email, updated_at)
    SELECT 
        (ARRAY['Иван', 'Анна', 'Сергей', 'Мария', 'Дмитрий', 'Елена', 'Алексей', 'Ольга', 'Игорь', 'Наталья'])[i] AS first_name,
        (ARRAY['Иванов', 'Петрова', 'Сидоров', 'Кузнецова', 'Попов', 'Васильева', 'Соколов', 'Михайлова', 'Новиков', 'Фёдорова'])[i] AS last_name,
        'prothetic' || i || '@example.com' AS email,
        NOW() - (random() * interval '10 days')
    FROM generate_series(1, 10) AS i;
EOSQL

unset PGPASSWORD
echo "All databases initialized successfully!"