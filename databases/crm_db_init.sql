-- ============================================================================
-- CRM Database Schema (Source: PostgreSQL)
-- BionicPRO CRM - данные клиентов, заказов и протезов
-- ============================================================================

-- Создание схемы
CREATE SCHEMA IF NOT EXISTS crm;

-- ============================================================================
-- Таблица клиентов
-- ============================================================================
CREATE TABLE IF NOT EXISTS crm.customers (
    customer_id         SERIAL PRIMARY KEY,
    external_id         VARCHAR(64) UNIQUE NOT NULL,          -- ID из Keycloak/LDAP
    first_name          VARCHAR(100) NOT NULL,
    last_name           VARCHAR(100) NOT NULL,
    middle_name         VARCHAR(100),
    email               VARCHAR(255) UNIQUE NOT NULL,
    phone               VARCHAR(20),
    birth_date          DATE,
    region              VARCHAR(50) NOT NULL,                  -- russia, europe
    branch              VARCHAR(100),                          -- Филиал
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Индексы для быстрого поиска
CREATE INDEX IF NOT EXISTS idx_customers_external_id ON crm.customers(external_id);
CREATE INDEX IF NOT EXISTS idx_customers_region ON crm.customers(region);
CREATE INDEX IF NOT EXISTS idx_customers_updated_at ON crm.customers(updated_at);

-- ============================================================================
-- Таблица моделей протезов
-- ============================================================================
CREATE TABLE IF NOT EXISTS crm.prosthesis_models (
    model_id            SERIAL PRIMARY KEY,
    model_code          VARCHAR(50) UNIQUE NOT NULL,
    model_name          VARCHAR(200) NOT NULL,
    category            VARCHAR(50) NOT NULL,                  -- arm, leg, hand, finger
    description         TEXT,
    price               DECIMAL(12, 2) NOT NULL,
    warranty_months     INTEGER DEFAULT 24,
    is_active           BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================================
-- Таблица протезов (экземпляры)
-- ============================================================================
CREATE TABLE IF NOT EXISTS crm.prostheses (
    prosthesis_id       SERIAL PRIMARY KEY,
    serial_number       VARCHAR(50) UNIQUE NOT NULL,
    model_id            INTEGER NOT NULL REFERENCES crm.prosthesis_models(model_id),
    customer_id         INTEGER REFERENCES crm.customers(customer_id),
    chip_id             VARCHAR(64) UNIQUE,                    -- ID чипа ESP32
    status              VARCHAR(30) NOT NULL DEFAULT 'manufactured',  -- manufactured, sold, active, maintenance, retired
    manufactured_date   DATE NOT NULL,
    sold_date           DATE,
    warranty_end_date   DATE,
    firmware_version    VARCHAR(20),
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_prostheses_customer_id ON crm.prostheses(customer_id);
CREATE INDEX IF NOT EXISTS idx_prostheses_chip_id ON crm.prostheses(chip_id);
CREATE INDEX IF NOT EXISTS idx_prostheses_status ON crm.prostheses(status);
CREATE INDEX IF NOT EXISTS idx_prostheses_updated_at ON crm.prostheses(updated_at);

-- ============================================================================
-- Таблица заказов
-- ============================================================================
CREATE TABLE IF NOT EXISTS crm.orders (
    order_id            SERIAL PRIMARY KEY,
    order_number        VARCHAR(50) UNIQUE NOT NULL,
    customer_id         INTEGER NOT NULL REFERENCES crm.customers(customer_id),
    prosthesis_id       INTEGER REFERENCES crm.prostheses(prosthesis_id),
    model_id            INTEGER NOT NULL REFERENCES crm.prosthesis_models(model_id),
    status              VARCHAR(30) NOT NULL DEFAULT 'new',    -- new, confirmed, production, shipping, delivered, cancelled
    total_amount        DECIMAL(12, 2) NOT NULL,
    discount_amount     DECIMAL(12, 2) DEFAULT 0,
    payment_status      VARCHAR(30) DEFAULT 'pending',         -- pending, paid, refunded
    order_date          TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    delivery_date       DATE,
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_orders_customer_id ON crm.orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON crm.orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_updated_at ON crm.orders(updated_at);

-- ============================================================================
-- Таблица обращений в техподдержку
-- ============================================================================
CREATE TABLE IF NOT EXISTS crm.support_tickets (
    ticket_id           SERIAL PRIMARY KEY,
    ticket_number       VARCHAR(50) UNIQUE NOT NULL,
    customer_id         INTEGER NOT NULL REFERENCES crm.customers(customer_id),
    prosthesis_id       INTEGER REFERENCES crm.prostheses(prosthesis_id),
    category            VARCHAR(50) NOT NULL,                  -- technical, warranty, question, complaint
    priority            VARCHAR(20) DEFAULT 'normal',          -- low, normal, high, critical
    status              VARCHAR(30) DEFAULT 'open',            -- open, in_progress, resolved, closed
    subject             VARCHAR(255) NOT NULL,
    description         TEXT,
    resolution          TEXT,
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    resolved_at         TIMESTAMP WITH TIME ZONE,
    updated_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_support_tickets_customer_id ON crm.support_tickets(customer_id);
CREATE INDEX IF NOT EXISTS idx_support_tickets_prosthesis_id ON crm.support_tickets(prosthesis_id);

-- ============================================================================
-- Триггер для автоматического обновления updated_at
-- ============================================================================
CREATE OR REPLACE FUNCTION crm.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_customers_updated_at
    BEFORE UPDATE ON crm.customers
    FOR EACH ROW EXECUTE FUNCTION crm.update_updated_at_column();

CREATE TRIGGER update_prostheses_updated_at
    BEFORE UPDATE ON crm.prostheses
    FOR EACH ROW EXECUTE FUNCTION crm.update_updated_at_column();

CREATE TRIGGER update_orders_updated_at
    BEFORE UPDATE ON crm.orders
    FOR EACH ROW EXECUTE FUNCTION crm.update_updated_at_column();

CREATE TRIGGER update_support_tickets_updated_at
    BEFORE UPDATE ON crm.support_tickets
    FOR EACH ROW EXECUTE FUNCTION crm.update_updated_at_column();

-- ============================================================================
-- Тестовые данные
-- ============================================================================

-- Модели протезов
INSERT INTO crm.prosthesis_models (model_code, model_name, category, description, price, warranty_months) VALUES
    ('BP-ARM-PRO-2024', 'BionicArm Pro 2024', 'arm', 'Профессиональная бионическая рука с 16 степенями свободы', 850000.00, 36),
    ('BP-ARM-STD-2024', 'BionicArm Standard 2024', 'arm', 'Стандартная бионическая рука с 8 степенями свободы', 450000.00, 24),
    ('BP-HAND-PRO-2024', 'BionicHand Pro 2024', 'hand', 'Бионическая кисть с индивидуальным управлением пальцами', 380000.00, 24),
    ('BP-LEG-PRO-2024', 'BionicLeg Pro 2024', 'leg', 'Бионическая нога с адаптивной системой ходьбы', 920000.00, 36),
    ('BP-LEG-STD-2024', 'BionicLeg Standard 2024', 'leg', 'Стандартная бионическая нога', 520000.00, 24)
ON CONFLICT (model_code) DO NOTHING;

-- Клиенты (соответствуют LDAP пользователям)
INSERT INTO crm.customers (external_id, first_name, last_name, middle_name, email, phone, birth_date, region, branch) VALUES
    ('ivan.petrov', 'Иван', 'Петров', 'Сергеевич', 'ivan.petrov@bionicpro.com', '+7-999-123-4567', '1985-03-15', 'russia', 'Москва'),
    ('maria.sidorova', 'Мария', 'Сидорова', 'Александровна', 'maria.sidorova@bionicpro.com', '+7-999-234-5678', '1990-07-22', 'russia', 'Санкт-Петербург'),
    ('alexey.kozlov', 'Алексей', 'Козлов', 'Дмитриевич', 'alexey.kozlov@bionicpro.com', '+7-999-345-6789', '1978-11-08', 'russia', 'Новосибирск'),
    ('john.mueller', 'John', 'Mueller', NULL, 'john.mueller@bionicpro.eu', '+49-171-1234567', '1982-05-30', 'europe', 'Berlin'),
    ('anna.schmidt', 'Anna', 'Schmidt', NULL, 'anna.schmidt@bionicpro.eu', '+49-172-2345678', '1995-09-12', 'europe', 'Munich')
ON CONFLICT (external_id) DO NOTHING;

-- Протезы
INSERT INTO crm.prostheses (serial_number, model_id, customer_id, chip_id, status, manufactured_date, sold_date, warranty_end_date, firmware_version) VALUES
    ('BP-2024-ARM-001', 1, 1, 'ESP32-ARM-001-A1B2C3', 'active', '2024-01-15', '2024-02-01', '2027-02-01', 'v2.1.5'),
    ('BP-2024-ARM-002', 2, 2, 'ESP32-ARM-002-D4E5F6', 'active', '2024-02-20', '2024-03-10', '2026-03-10', 'v2.1.5'),
    ('BP-2024-HAND-001', 3, 3, 'ESP32-HAND-001-G7H8I9', 'active', '2024-03-05', '2024-03-25', '2026-03-25', 'v2.1.4'),
    ('BP-2024-LEG-001', 4, 4, 'ESP32-LEG-001-J0K1L2', 'active', '2024-01-10', '2024-01-28', '2027-01-28', 'v2.1.5'),
    ('BP-2024-LEG-002', 5, 5, 'ESP32-LEG-002-M3N4O5', 'active', '2024-04-12', '2024-05-01', '2026-05-01', 'v2.1.5')
ON CONFLICT (serial_number) DO NOTHING;

-- Заказы
INSERT INTO crm.orders (order_number, customer_id, prosthesis_id, model_id, status, total_amount, discount_amount, payment_status, delivery_date) VALUES
    ('ORD-2024-00001', 1, 1, 1, 'delivered', 850000.00, 50000.00, 'paid', '2024-02-01'),
    ('ORD-2024-00002', 2, 2, 2, 'delivered', 450000.00, 0.00, 'paid', '2024-03-10'),
    ('ORD-2024-00003', 3, 3, 3, 'delivered', 380000.00, 20000.00, 'paid', '2024-03-25'),
    ('ORD-2024-00004', 4, 4, 4, 'delivered', 920000.00, 100000.00, 'paid', '2024-01-28'),
    ('ORD-2024-00005', 5, 5, 5, 'delivered', 520000.00, 0.00, 'paid', '2024-05-01')
ON CONFLICT (order_number) DO NOTHING;

-- Представление для ETL - данные клиентов и протезов
CREATE OR REPLACE VIEW crm.v_customer_prosthesis AS
SELECT
    c.customer_id,
    c.external_id AS user_id,
    c.first_name,
    c.last_name,
    c.middle_name,
    CONCAT(c.last_name, ' ', c.first_name, COALESCE(' ' || c.middle_name, '')) AS customer_full_name,
    c.email,
    c.phone,
    c.region,
    c.branch,
    p.prosthesis_id,
    p.serial_number AS prosthesis_serial,
    p.chip_id,
    p.status AS prosthesis_status,
    p.firmware_version,
    pm.model_code,
    pm.model_name AS prosthesis_model,
    pm.category AS prosthesis_category,
    p.sold_date,
    p.warranty_end_date,
    c.updated_at AS customer_updated_at,
    p.updated_at AS prosthesis_updated_at,
    GREATEST(c.updated_at, p.updated_at) AS last_updated_at
FROM crm.customers c
JOIN crm.prostheses p ON c.customer_id = p.customer_id
JOIN crm.prosthesis_models pm ON p.model_id = pm.model_id
WHERE p.status = 'active';
