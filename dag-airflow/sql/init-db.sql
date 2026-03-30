-- ==========================================================================
-- Инициализация БД для ETL-пайплайна BionicPRO
-- Создаёт базы sensor_data и crm_data в одном PostgreSQL-инстансе
-- (Airflow metadata DB 'airflow' создаётся автоматически)
-- ==========================================================================

-- ===================== БД датчиков =======================================

CREATE DATABASE sensor_data;

\connect sensor_data;

CREATE TABLE IF NOT EXISTS sessions (
    session_id        SERIAL PRIMARY KEY,
    user_id           BIGINT       NOT NULL,
    session_start     TIMESTAMP    NOT NULL,
    session_end       TIMESTAMP    NOT NULL,
    gestures_count    INT          NOT NULL DEFAULT 0,
    avg_myosignal_quality DOUBLE PRECISION NOT NULL DEFAULT 0,
    prosthesis_model  VARCHAR(100)
);

CREATE INDEX idx_sessions_user_date ON sessions (user_id, session_start);

-- Тестовые данные (вчера)
INSERT INTO sessions (user_id, session_start, session_end, gestures_count, avg_myosignal_quality, prosthesis_model)
VALUES
    (1, CURRENT_DATE - INTERVAL '1 day' + INTERVAL '8 hours',  CURRENT_DATE - INTERVAL '1 day' + INTERVAL '10 hours', 45, 0.82, 'BionicHand Pro V3'),
    (1, CURRENT_DATE - INTERVAL '1 day' + INTERVAL '14 hours', CURRENT_DATE - INTERVAL '1 day' + INTERVAL '15 hours 30 minutes', 30, 0.78, 'BionicHand Pro V3'),
    (2, CURRENT_DATE - INTERVAL '1 day' + INTERVAL '9 hours',  CURRENT_DATE - INTERVAL '1 day' + INTERVAL '12 hours', 62, 0.91, 'BionicArm Lite V2'),
    (3, CURRENT_DATE - INTERVAL '1 day' + INTERVAL '7 hours',  CURRENT_DATE - INTERVAL '1 day' + INTERVAL '8 hours 45 minutes', 18, 0.65, 'BionicHand Pro V3'),
    (3, CURRENT_DATE - INTERVAL '1 day' + INTERVAL '13 hours', CURRENT_DATE - INTERVAL '1 day' + INTERVAL '16 hours', 55, 0.72, 'BionicHand Pro V3'),
    (3, CURRENT_DATE - INTERVAL '1 day' + INTERVAL '19 hours', CURRENT_DATE - INTERVAL '1 day' + INTERVAL '20 hours', 12, 0.69, 'BionicHand Pro V3');

-- ===================== CRM DB ============================================

\connect postgres;

CREATE DATABASE crm_data;

\connect crm_data;

CREATE TABLE IF NOT EXISTS clients (
    user_id           BIGINT PRIMARY KEY,
    full_name         VARCHAR(200) NOT NULL,
    email             VARCHAR(200),
    phone             VARCHAR(50),
    last_contact_date DATE
);

CREATE TABLE IF NOT EXISTS orders (
    order_id          SERIAL PRIMARY KEY,
    client_id         BIGINT       NOT NULL REFERENCES clients(user_id),
    order_status      VARCHAR(50)  NOT NULL,
    prosthesis_model  VARCHAR(100) NOT NULL,
    order_date        DATE         NOT NULL,
    is_latest         BOOLEAN      NOT NULL DEFAULT false
);

-- Тестовые данные
INSERT INTO clients (user_id, full_name, email, phone, last_contact_date)
VALUES
    (1, 'Иванов Пётр Сергеевич',   'ivanov@example.com',  '+79001234567', CURRENT_DATE - INTERVAL '3 days'),
    (2, 'Смирнова Анна Дмитриевна', 'smirnova@example.com', '+79007654321', CURRENT_DATE - INTERVAL '7 days'),
    (3, 'Козлов Дмитрий Алексеевич','kozlov@example.com',  '+79009876543', CURRENT_DATE - INTERVAL '1 day');

INSERT INTO orders (client_id, order_status, prosthesis_model, order_date, is_latest)
VALUES
    (1, 'delivered',   'BionicHand Pro V3', '2024-06-15', true),
    (2, 'in_progress', 'BionicArm Lite V2', '2025-01-10', true),
    (3, 'delivered',   'BionicHand Pro V3', '2024-09-20', false),
    (3, 'warranty',    'BionicHand Pro V3', '2025-02-01', true);

-- ===================== OLAP DB (витрина отчётности) ========================

\connect postgres;

CREATE DATABASE olap_data;

\connect olap_data;

CREATE TABLE IF NOT EXISTS fact_user_report (
    id                    SERIAL PRIMARY KEY,
    user_id               BIGINT           NOT NULL,
    report_date           DATE             NOT NULL,
    session_count         INT              NOT NULL DEFAULT 0,
    avg_wear_time_min     DOUBLE PRECISION NOT NULL DEFAULT 0,
    total_gestures        INT              NOT NULL DEFAULT 0,
    avg_myosignal_quality DOUBLE PRECISION NOT NULL DEFAULT 0,
    order_status          VARCHAR(50),
    prosthesis_model      VARCHAR(100),
    last_contact_date     DATE,
    loaded_at             TIMESTAMP        NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_fact_user_report_user_date ON fact_user_report (user_id, report_date DESC);
