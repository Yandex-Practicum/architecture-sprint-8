-- Initialize Bionic Databases

-- Create database if it doesn't exist
-- Note: This is handled by Docker Compose and Kubernetes configs

-- Connect to the database
\c postgres;

CREATE ROLE keycloak NOSUPERUSER CREATEDB NOCREATEROLE NOINHERIT LOGIN NOREPLICATION NOBYPASSRLS PASSWORD 'keycloak';
CREATE ROLE airflow NOSUPERUSER CREATEDB NOCREATEROLE NOINHERIT LOGIN NOREPLICATION NOBYPASSRLS PASSWORD 'airflow';
CREATE ROLE prosthesis NOSUPERUSER CREATEDB NOCREATEROLE NOINHERIT LOGIN NOREPLICATION NOBYPASSRLS PASSWORD 'prosthesis';
CREATE ROLE bionic_crm NOSUPERUSER CREATEDB NOCREATEROLE NOINHERIT LOGIN NOREPLICATION NOBYPASSRLS PASSWORD 'bionic_crm';


CREATE DATABASE keycloak WITH OWNER = keycloak ENCODING = 'UTF8';
CREATE DATABASE airflow WITH OWNER = airflow ENCODING = 'UTF8';
CREATE DATABASE prosthesis WITH OWNER = prosthesis ENCODING = 'UTF8';
CREATE DATABASE bionic_crm WITH OWNER = bionic_crm ENCODING = 'UTF8';

-- Fill the Prosthesis DB with user and report data 
\c "host=localhost port=5432 dbname=prosthesis user=prosthesis password=prosthesis";

-- Создание таблицы движений протеза
CREATE TABLE IF NOT EXISTS prosthesis_usage (
    id SERIAL PRIMARY KEY,
    user_id INTEGER,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    movement_type VARCHAR(50),
    movements_count INTEGER
);

-- Наполнение данными о движениях (1000 строк)
INSERT INTO prosthesis_usage (user_id, start_time, end_time, movement_type, movements_count)
SELECT 
    floor(random() * 10 + 1)::int AS user_id,
    ts AS start_time,
    ts + (random() * interval '30 minutes') AS end_time,
    (ARRAY['Сжатие кисти', 'Разжатие кисти', 'Вращение', 'Указательный жест', 'Хват щепотью'])[floor(random() * 5 + 1)] AS movement_type,
    floor(random() * 20 + 1)::int AS movements_count
FROM (
    SELECT '2023-10-01 08:00:00'::timestamp + (random() * interval '30 days') AS ts
    FROM generate_series(1, 1000)
) AS random_times
ORDER BY ts;

-- Fill the Prosthesis DB with user and report data 
\c "host=localhost port=5432 dbname=bionic_crm user=bionic_crm password=bionic_crm";

-- Создание таблицы пользователей
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    first_name VARCHAR(50),
    last_name VARCHAR(50),
    email VARCHAR(100) UNIQUE
);

-- Наполнение пользователями (10 человек)
INSERT INTO users (first_name, last_name, email)
SELECT 
    (ARRAY['Иван', 'Анна', 'Сергей', 'Мария', 'Дмитрий', 'Елена', 'Алексей', 'Ольга', 'Игорь', 'Наталья'])[i] AS first_name,
    (ARRAY['Иванов', 'Петрова', 'Сидоров', 'Кузнецова', 'Попов', 'Васильева', 'Соколов', 'Михайлова', 'Новиков', 'Фёдорова'])[i] AS last_name,
    'user' || i || '@example.com' AS email
FROM generate_series(1, 10) AS i;