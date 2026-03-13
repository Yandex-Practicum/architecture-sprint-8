-- CRM Database initialization
-- This simulates the BionicPRO CRM (Bitrix24) data

CREATE TABLE IF NOT EXISTS customers (
    id SERIAL PRIMARY KEY,
    keycloak_user_id VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    phone VARCHAR(50),
    country VARCHAR(100) DEFAULT 'Russia',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(id),
    product_name VARCHAR(255) NOT NULL,
    product_type VARCHAR(100) NOT NULL,
    order_date DATE NOT NULL,
    delivery_date DATE,
    status VARCHAR(50) DEFAULT 'pending',
    total_amount NUMERIC(10,2),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS telemetry (
    id SERIAL PRIMARY KEY,
    device_id VARCHAR(255) NOT NULL,
    customer_id INTEGER REFERENCES customers(id),
    signal_strength FLOAT,
    usage_hours FLOAT,
    active_movements INTEGER,
    battery_cycles INTEGER,
    error_count INTEGER DEFAULT 0,
    firmware_version VARCHAR(50),
    recorded_at TIMESTAMP DEFAULT NOW()
);

-- Create publication for Debezium CDC
CREATE PUBLICATION dbz_publication FOR TABLE customers, orders, telemetry;

-- Insert sample data matching Keycloak users (prothetic_user role)
INSERT INTO customers (keycloak_user_id, email, first_name, last_name, phone, country) VALUES
    ('prothetic1', 'prothetic1@example.com', 'Prothetic', 'One', '+7-900-111-0001', 'Russia'),
    ('prothetic2', 'prothetic2@example.com', 'Prothetic', 'Two', '+7-900-111-0002', 'Russia'),
    ('prothetic3', 'prothetic3@example.com', 'Prothetic', 'Three', '+7-900-111-0003', 'Russia');

INSERT INTO orders (customer_id, product_name, product_type, order_date, delivery_date, status, total_amount) VALUES
    (1, 'BionicHand Pro v3', 'hand_prosthesis', '2024-01-15', '2024-03-20', 'delivered', 850000.00),
    (1, 'BionicHand Pro v3 - Maintenance Kit', 'accessory', '2024-06-10', '2024-06-15', 'delivered', 15000.00),
    (2, 'BionicArm Elite v2', 'arm_prosthesis', '2024-02-20', '2024-04-25', 'delivered', 1200000.00),
    (3, 'BionicHand Lite v1', 'hand_prosthesis', '2024-03-10', '2024-05-15', 'delivered', 450000.00),
    (3, 'BionicHand Pro v3', 'hand_prosthesis', '2024-09-01', NULL, 'in_production', 850000.00);

INSERT INTO telemetry (device_id, customer_id, signal_strength, usage_hours, active_movements, battery_cycles, error_count, firmware_version, recorded_at) VALUES
    ('DEV-001-A', 1, 0.85, 6.5, 1250, 2, 0, '3.2.1', '2024-06-01 10:00:00'),
    ('DEV-001-A', 1, 0.82, 7.2, 1380, 2, 1, '3.2.1', '2024-06-02 10:00:00'),
    ('DEV-001-A', 1, 0.88, 5.1, 980, 1, 0, '3.2.1', '2024-06-03 10:00:00'),
    ('DEV-001-A', 1, 0.79, 8.0, 1520, 3, 2, '3.2.2', '2024-06-04 10:00:00'),
    ('DEV-001-A', 1, 0.91, 4.3, 870, 1, 0, '3.2.2', '2024-06-05 10:00:00'),
    ('DEV-002-B', 2, 0.76, 9.1, 1890, 3, 3, '2.8.0', '2024-06-01 10:00:00'),
    ('DEV-002-B', 2, 0.78, 8.5, 1720, 3, 1, '2.8.0', '2024-06-02 10:00:00'),
    ('DEV-002-B', 2, 0.81, 7.8, 1600, 2, 0, '2.8.1', '2024-06-03 10:00:00'),
    ('DEV-002-B', 2, 0.74, 10.2, 2100, 4, 5, '2.8.1', '2024-06-04 10:00:00'),
    ('DEV-003-C', 3, 0.92, 3.5, 650, 1, 0, '1.5.0', '2024-06-01 10:00:00'),
    ('DEV-003-C', 3, 0.89, 4.0, 720, 1, 0, '1.5.0', '2024-06-02 10:00:00'),
    ('DEV-003-C', 3, 0.87, 5.2, 950, 2, 1, '1.5.1', '2024-06-03 10:00:00');
