CREATE TABLE IF NOT EXISTS customers (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),
    email VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(id),
    prosthesis_id VARCHAR(255) NOT NULL,
    order_date DATE,
    prosthesis_type VARCHAR(255)
);

INSERT INTO customers (username, name, email) VALUES
('prothetic1', 'Prothetic One', 'prothetic1@example.com'),
('prothetic2', 'Prothetic Two', 'prothetic2@example.com'),
('prothetic3', 'Prothetic Three', 'prothetic3@example.com')
ON CONFLICT (username) DO NOTHING;

INSERT INTO orders (customer_id, prosthesis_id, order_date, prosthesis_type) VALUES
(1, 'prosthesis-001', '2024-01-15', 'Hand'),
(2, 'prosthesis-002', '2024-02-20', 'Arm'),
(3, 'prosthesis-003', '2024-03-10', 'Hand')
ON CONFLICT DO NOTHING;
