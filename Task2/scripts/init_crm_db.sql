CREATE SCHEMA IF NOT EXISTS crm;

CREATE TABLE IF NOT EXISTS crm.users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) NOT NULL UNIQUE,
    phone VARCHAR(50),
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    country VARCHAR(100),
    city VARCHAR(100),
    registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP NULL
);

CREATE TABLE IF NOT EXISTS crm.prostheses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES crm.users(id),
    prosthesis_type VARCHAR(50) NOT NULL,
    manufacture_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_tuning_date TIMESTAMP,
    tuning_count INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'active'
);

-- ====================.  TASK 4 =====================

CREATE USER debezium_user WITH REPLICATION LOGIN PASSWORD 'strong_password';

GRANT CONNECT ON DATABASE crm_db TO debezium_user;
GRANT USAGE ON SCHEMA crm TO debezium_user;
GRANT SELECT ON ALL TABLES IN SCHEMA crm TO debezium_user;

ALTER TABLE crm.users REPLICA IDENTITY FULL;
ALTER TABLE crm.prostheses REPLICA IDENTITY FULL;

CREATE PUBLICATION debezium_publication FOR TABLE 
    crm.users,
    crm.prostheses;

SELECT pg_sleep(5);

INSERT INTO crm.users (id, email, phone, first_name, last_name, country, city) VALUES
    ('0aca56c5-b960-4c50-9f1b-0451aea68fe3', 'ivan@example.com', '+79123456789', 'Ivan', 'Petrov', 'Russia', 'Moscow'),
    ('11b225b9-4fda-4ebd-b508-6c90cefd23a7', 'olga@example.com', '+79234567890', 'Olga', 'Sidorova', 'Russia', 'Saint Petersburg'),
    ('fcf7435c-1f54-4a1e-80cb-6214a733e84a', 'sergey@example.com', '+79345678901', 'Sergey', 'Ivanov', 'Russia', 'Novosibirsk'),
    ('44444444-4444-4444-4444-444444444444', 'elena@example.com', '+79456789012', 'Elena', 'Volkova', 'Germany', 'Berlin'),
    ('55555555-5555-5555-5555-555555555555', 'mikhail@example.com', '+79567890123', 'Mikhail', 'Smirnov', 'Russia', 'Kazan');

INSERT INTO crm.prostheses (id, user_id, prosthesis_type, manufacture_date, last_tuning_date, tuning_count) VALUES
    ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', '0aca56c5-b960-4c50-9f1b-0451aea68fe3', 'standard', '2024-01-15', '2024-12-15 10:30:00', 3),
    ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', '11b225b9-4fda-4ebd-b508-6c90cefd23a7', 'premium', '2024-02-20', '2024-12-20 14:20:00', 2),
    ('cccccccc-cccc-cccc-cccc-cccccccccccc', 'fcf7435c-1f54-4a1e-80cb-6214a733e84a', 'standard', '2024-03-10', '2025-01-05 09:15:00', 1),
    ('dddddddd-dddd-dddd-dddd-dddddddddddd', '44444444-4444-4444-4444-444444444444', 'premium', '2024-04-05', '2025-01-10 11:45:00', 4),
    ('eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee', '55555555-5555-5555-5555-555555555555', 'standard', '2024-05-12', '2025-01-08 16:30:00', 2);



