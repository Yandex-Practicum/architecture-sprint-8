-- Подключаемся к keycloak_db
-- \c keycloak_db;

-- Создаём схему для CRM данных
CREATE SCHEMA IF NOT EXISTS crm;

-- Таблица пользователей
CREATE TABLE IF NOT EXISTS crm.users (
                                         user_id VARCHAR(100) PRIMARY KEY,
    email VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    phone VARCHAR(50),
    date_of_birth DATE,
    gender VARCHAR(10),
    address TEXT,
    prosthesis_model VARCHAR(100),
    serial_number VARCHAR(100),
    firmware_version VARCHAR(50),
    manufactured_date DATE,
    warranty_end_date DATE,
    registration_date DATE,
    last_active_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

-- Создаём индексы
CREATE INDEX idx_users_email ON crm.users(email);
CREATE INDEX idx_users_updated_at ON crm.users(updated_at);

-- Функция для обновления updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
RETURN NEW;
END;
$$ language 'plpgsql';

-- Триггер для автоматического обновления updated_at
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON crm.users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();