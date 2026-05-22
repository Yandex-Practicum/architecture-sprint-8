CREATE TABLE IF NOT EXISTS crm_customers (
    customer_id VARCHAR(50) PRIMARY KEY,
    full_name VARCHAR(200) NOT NULL,
    email VARCHAR(200),
    phone VARCHAR(50),
    prosthesis_model VARCHAR(100),
    purchase_date DATE NOT NULL,
    warranty_end_date DATE,
    region VARCHAR(100),
    doctor_name VARCHAR(200),
    hospital_name VARCHAR(200),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS crm_orders (
    order_id VARCHAR(50) PRIMARY KEY,
    customer_id VARCHAR(50) NOT NULL REFERENCES crm_customers(customer_id),
    order_date TIMESTAMP NOT NULL,
    total_amount DECIMAL(12, 2),
    status VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO crm_customers (customer_id, full_name, email, phone, prosthesis_model, purchase_date, warranty_end_date, region, doctor_name, hospital_name) VALUES
('CUST-001', 'Иван Петров', 'ivan.petrov@example.com', '+7-912-555-01-01', 'BionicPRO-X1', '2024-01-15', '2027-01-15', 'Москва', 'Смирнов А.А.', 'ГКБ №1'),
('CUST-002', 'Мария Иванова', 'maria.ivanova@example.com', '+7-912-555-01-02', 'BionicPRO-X2', '2024-03-20', '2027-03-20', 'Санкт-Петербург', 'Кузнецов В.В.', 'ГБ №15'),
('CUST-003', 'Алексей Сидоров', 'aleksey.sidorov@example.com', '+7-912-555-01-03', 'BionicPRO-X1', '2024-06-10', '2027-06-10', 'Новосибирск', 'Попова Е.Е.', 'ГКБ №2'),
('CUST-004', 'Елена Козлова', 'elena.kozlova@example.com', '+7-912-555-01-04', 'BionicPRO-X3', '2024-09-05', '2027-09-05', 'Москва', 'Смирнов А.А.', 'ГКБ №1'),
('CUST-005', 'Дмитрий Новиков', 'dmitry.novikov@example.com', '+7-912-555-01-05', 'BionicPRO-X2', '2025-02-14', '2028-02-14', 'Екатеринбург', 'Лебедева Т.Т.', 'ЦГКБ №6'),
('CUST-006', 'Ольга Морозова', 'olga.morozova@example.com', '+7-912-555-01-06', 'BionicPRO-X1', '2025-04-01', '2028-04-01', 'Казань', 'Федоров М.М.', 'РКБ'),
('CUST-007', 'Сергей Волков', 'sergey.volkov@example.com', '+7-912-555-01-07', 'BionicPRO-X3', '2024-11-20', '2027-11-20', 'Самара', 'Гришин В.В.', 'ГБ №7'),
('CUST-008', 'Анна Белова', 'anna.belova@example.com', '+7-912-555-01-08', 'BionicPRO-X2', '2025-01-10', '2028-01-10', 'Ростов-на-Дону', 'Коваленко И.И.', 'ГКБ №3');

INSERT INTO crm_orders (order_id, customer_id, order_date, total_amount, status) VALUES
('ORD-001', 'CUST-001', '2024-01-10 10:30:00', 450000.00, 'completed'),
('ORD-002', 'CUST-002', '2024-03-15 14:00:00', 580000.00, 'completed'),
('ORD-003', 'CUST-003', '2024-06-05 11:20:00', 450000.00, 'completed'),
('ORD-004', 'CUST-004', '2024-09-01 09:45:00', 720000.00, 'completed'),
('ORD-005', 'CUST-005', '2025-02-10 16:30:00', 580000.00, 'completed'),
('ORD-006', 'CUST-006', '2025-03-28 12:00:00', 450000.00, 'completed'),
('ORD-007', 'CUST-007', '2024-11-15 08:15:00', 720000.00, 'completed'),
('ORD-008', 'CUST-008', '2025-01-05 13:45:00', 580000.00, 'completed');
