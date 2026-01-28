-- База данных CRM
CREATE TABLE IF NOT EXISTS clients (
    client_id SERIAL PRIMARY KEY,
    external_client_id VARCHAR(50) UNIQUE NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    phone VARCHAR(20),
    date_of_birth DATE,
    registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

COMMENT ON TABLE clients IS 'Клиенты - владельцы протезов';
COMMENT ON COLUMN clients.external_client_id IS 'Внешний ID для API доступа';

CREATE INDEX IF NOT EXISTS idx_clients_external_id ON clients(external_client_id);
CREATE INDEX IF NOT EXISTS idx_clients_email ON clients(email);

CREATE TABLE IF NOT EXISTS devices (
    device_id VARCHAR(50) PRIMARY KEY,
    client_id INTEGER NOT NULL,
    device_name VARCHAR(100),
    device_type VARCHAR(50) NOT NULL,
    serial_number VARCHAR(100) UNIQUE NOT NULL,
    manufacturing_date DATE,
    activation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    warranty_until DATE,
    is_active BOOLEAN DEFAULT TRUE,
    last_maintenance_date DATE,
    FOREIGN KEY (client_id) REFERENCES clients(client_id) ON DELETE CASCADE
);

COMMENT ON TABLE devices IS 'Протезы (устройства), привязанные к клиентам';
COMMENT ON COLUMN devices.device_type IS 'тип: верхняя_конечность, нижняя_конечность и т.д.';

CREATE INDEX IF NOT EXISTS idx_devices_client_id ON devices(client_id);
CREATE INDEX IF NOT EXISTS idx_devices_serial_number ON devices(serial_number);

-- Вставляем тестовые данные (опционально)
INSERT INTO clients (external_client_id, first_name, last_name, email, phone, date_of_birth) VALUES
('client_001', 'Иван', 'Петров', 'ivan.petrov@example.com', '+79161234567', '1985-05-15'),
('client_002', 'Мария', 'Сидорова', 'maria.sidorova@example.com', '+79167654321', '1990-08-22')
ON CONFLICT (email) DO NOTHING;

INSERT INTO devices (device_id, client_id, device_name, device_type, serial_number, manufacturing_date) VALUES
('device_001', 1, 'Мой протез руки', 'верхняя_конечность', 'SN-ARM-001', '2023-01-15'),
('device_002', 1, 'Запасной протез', 'верхняя_конечность', 'SN-ARM-002', '2023-06-20'),
('device_003', 2, 'Протез ноги', 'нижняя_конечность', 'SN-LEG-001', '2023-03-10')
ON CONFLICT (device_id) DO NOTHING;