CREATE TABLE IF NOT EXISTS customers (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    phone VARCHAR(50),
    country VARCHAR(100) NOT NULL,
    registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS prosthetic_devices (
    id SERIAL PRIMARY KEY,
    device_id VARCHAR(50) UNIQUE NOT NULL,
    user_id INTEGER NOT NULL REFERENCES customers(id),
    device_type VARCHAR(50) NOT NULL,
    serial_number VARCHAR(100) UNIQUE NOT NULL,
    manufacture_date DATE NOT NULL,
    delivery_date DATE,
    warranty_until DATE,
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES customers(id),
    order_number VARCHAR(100) UNIQUE NOT NULL,
    order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total_amount DECIMAL(10, 2) NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    payment_status VARCHAR(50) DEFAULT 'unpaid',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_profiles (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES customers(id),
    date_of_birth DATE,
    amputation_type VARCHAR(100),
    amputation_date DATE,
    rehabilitation_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_customers_email ON customers(email);
CREATE INDEX idx_customers_country ON customers(country);
CREATE INDEX idx_devices_user_id ON prosthetic_devices(user_id);
CREATE INDEX idx_devices_device_id ON prosthetic_devices(device_id);
CREATE INDEX idx_orders_user_id ON orders(user_id);
CREATE INDEX idx_orders_order_date ON orders(order_date);
CREATE INDEX idx_profiles_user_id ON user_profiles(user_id);

INSERT INTO customers (id, email, full_name, phone, country)
VALUES 
    (1, 'ivan.petrov@example.com', 'Иван Петров', '+7-900-123-4567', 'Russia'),
    (2, 'maria.sidorova@example.com', 'Мария Сидорова', '+7-900-234-5678', 'Russia'),
    (3, 'john.smith@example.com', 'John Smith', '+1-555-123-4567', 'USA');

INSERT INTO prosthetic_devices (device_id, user_id, device_type, serial_number, manufacture_date, delivery_date, warranty_until)
VALUES 
    ('DEVICE-001', 1, 'hand', 'SN-2024-001', '2024-01-15', '2024-02-01', '2027-02-01'),
    ('DEVICE-002', 2, 'arm', 'SN-2024-002', '2024-02-10', '2024-03-01', '2027-03-01'),
    ('DEVICE-003', 3, 'hand', 'SN-2024-003', '2024-03-05', '2024-03-20', '2027-03-20');

INSERT INTO orders (user_id, order_number, order_date, total_amount, status, payment_status)
VALUES 
    (1, 'ORD-2024-001', '2024-01-01', 850000.00, 'delivered', 'paid'),
    (2, 'ORD-2024-002', '2024-01-20', 1200000.00, 'delivered', 'paid'),
    (3, 'ORD-2024-003', '2024-02-15', 950000.00, 'delivered', 'paid');

INSERT INTO user_profiles (user_id, date_of_birth, amputation_type, amputation_date)
VALUES 
    (1, '1985-05-15', 'Below elbow', '2020-03-10'),
    (2, '1990-08-22', 'Above elbow', '2019-11-05'),
    (3, '1978-12-30', 'Below elbow', '2021-07-18');

COMMENT ON TABLE customers IS 'Клиенты компании BionicPRO';
COMMENT ON TABLE prosthetic_devices IS 'Бионические протезы, проданные клиентам';
COMMENT ON TABLE orders IS 'Заказы на изготовление протезов';
COMMENT ON TABLE user_profiles IS 'Профили пользователей с медицинской информацией';

COMMENT ON COLUMN prosthetic_devices.device_id IS 'Идентификатор устройства, используется в телеметрии';
COMMENT ON COLUMN user_profiles.amputation_type IS 'Тип ампутации (Above elbow, Below elbow, и т.д.)';
