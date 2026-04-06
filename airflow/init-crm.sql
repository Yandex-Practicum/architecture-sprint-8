-- Инициализация CRM базы данных
-- Создаем таблицу с информацией о клиентах
CREATE TABLE IF NOT EXISTS crm_clients (
    client_id BIGSERIAL PRIMARY KEY,
    buyer_id BIGINT UNIQUE NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    phone VARCHAR(50),
    registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_visit_date TIMESTAMP,
    status VARCHAR(50) DEFAULT 'active'
);

-- Создаем таблицу с информацией о протезах
CREATE TABLE IF NOT EXISTS crm_prosthetics (
    prosthetic_id BIGSERIAL PRIMARY KEY,
    buyer_id BIGINT NOT NULL REFERENCES crm_clients(buyer_id),
    prosthetic_type VARCHAR(100) NOT NULL,
    manufacture_date DATE NOT NULL,
    delivery_date DATE,
    serial_number VARCHAR(100) UNIQUE NOT NULL,
    warranty_months INTEGER DEFAULT 12,
    price DECIMAL(10,2) NOT NULL
);

-- Создаем таблицу заказов из CRM
CREATE TABLE IF NOT EXISTS crm_orders (
    order_id BIGSERIAL PRIMARY KEY,
    order_number BIGINT UNIQUE NOT NULL,
    buyer_id BIGINT NOT NULL REFERENCES crm_clients(buyer_id),
    prosthetic_id BIGINT REFERENCES crm_prosthetics(prosthetic_id),
    order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total DECIMAL(10,2) NOT NULL,
    discount DECIMAL(10,2) DEFAULT 0,
    status VARCHAR(50) DEFAULT 'pending'
);

-- Вставляем тестовых клиентов
INSERT INTO crm_clients (buyer_id, full_name, email, phone, registration_date, last_visit_date, status) VALUES
(648821, 'Иван Петров', 'ivan.petrov@example.com', '+79161234567', '2023-01-15 10:00:00', '2024-03-20 14:30:00', 'active'),
(6488214, 'Мария Сидорова', 'maria.sidorova@example.com', '+79162345678', '2023-02-20 11:00:00', '2024-03-18 09:15:00', 'active'),
(6488211, 'Алексей Иванов', 'alex.ivanov@example.com', '+79163456789', '2023-03-10 12:00:00', '2024-03-22 16:45:00', 'active'),
(6488219, 'Елена Смирнова', 'elena.smirnova@example.com', '+79164567890', '2023-04-05 13:00:00', '2024-03-19 11:20:00', 'active'),
(648801, 'Дмитрий Козлов', 'dmitry.kozlov@example.com', '+79165678901', '2023-05-12 14:00:00', '2024-03-21 15:10:00', 'active')
ON CONFLICT (buyer_id) DO NOTHING;

-- Вставляем информацию о протезах
INSERT INTO crm_prosthetics (buyer_id, prosthetic_type, manufacture_date, delivery_date, serial_number, warranty_months, price) VALUES
(648821, 'Бионическая рука', '2023-02-01', '2023-02-15', 'BP-ARM-2023-001', 24, 450000.00),
(6488214, 'Бионическая кисть', '2023-03-01', '2023-03-10', 'BP-HAND-2023-001', 18, 280000.00),
(6488211, 'Бионическая рука Pro', '2023-04-01', '2023-04-12', 'BP-ARM-PRO-2023-001', 36, 650000.00),
(6488219, 'Бионическая кисть', '2023-05-01', '2023-05-08', 'BP-HAND-2023-002', 18, 280000.00),
(648801, 'Бионическая рука Premium', '2023-06-01', '2023-06-15', 'BP-ARM-PREM-2023-001', 48, 890000.00)
ON CONFLICT (serial_number) DO NOTHING;

-- Вставляем тестовые заказы
INSERT INTO crm_orders (order_number, buyer_id, prosthetic_id, order_date, total, discount, status) VALUES
(12345, 648821, 1, '2023-01-20 10:30:00', 450000, 45000, 'completed'),
(123456, 6488214, 2, '2023-02-25 11:20:00', 280000, 14000, 'completed'),
(123457, 6488211, 3, '2023-03-15 12:45:00', 650000, 32500, 'completed'),
(123458, 6488219, 4, '2023-04-10 13:15:00', 280000, 0, 'completed'),
(123459, 648801, 5, '2023-05-18 14:50:00', 890000, 44500, 'completed')
ON CONFLICT (order_number) DO NOTHING;

-- Создаем индексы для оптимизации запросов
CREATE INDEX IF NOT EXISTS idx_crm_orders_buyer_id ON crm_orders(buyer_id);
CREATE INDEX IF NOT EXISTS idx_crm_prosthetics_buyer_id ON crm_prosthetics(buyer_id);
CREATE INDEX IF NOT EXISTS idx_crm_orders_order_date ON crm_orders(order_date);
