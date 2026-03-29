CREATE TABLE IF NOT EXISTS customers (
    customer_id SERIAL PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL,
    full_name TEXT NOT NULL,
    country TEXT NOT NULL,
    city TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS prostheses (
    prosthesis_id TEXT PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
    prosthesis_model TEXT NOT NULL,
    support_tier TEXT NOT NULL,
    fitted_at DATE NOT NULL,
    last_service_date DATE NOT NULL
);

INSERT INTO customers (username, email, full_name, country, city) VALUES
    ('prothetic1', 'prothetic1@example.com', 'Prothetic One', 'Russia', 'Moscow'),
    ('prothetic2', 'prothetic2@example.com', 'Prothetic Two', 'Russia', 'Saint Petersburg'),
    ('prothetic3', 'prothetic3@example.com', 'Prothetic Three', 'Russia', 'Kazan'),
    ('john.doe', 'john.doe@example.com', 'John Doe', 'Armenia', 'Yerevan'),
    ('alex.johnson', 'alex.johnson@example.com', 'Alex Johnson', 'Kazakhstan', 'Almaty')
ON CONFLICT (username) DO NOTHING;

INSERT INTO prostheses (prosthesis_id, customer_id, prosthesis_model, support_tier, fitted_at, last_service_date)
SELECT 'BP-1001', customer_id, 'BionicPRO Hand X', 'premium', DATE '2025-11-20', DATE '2026-03-18'
FROM customers WHERE username = 'prothetic1'
ON CONFLICT (prosthesis_id) DO NOTHING;

INSERT INTO prostheses (prosthesis_id, customer_id, prosthesis_model, support_tier, fitted_at, last_service_date)
SELECT 'BP-1002', customer_id, 'BionicPRO Hand Lite', 'standard', DATE '2026-01-10', DATE '2026-03-16'
FROM customers WHERE username = 'prothetic1'
ON CONFLICT (prosthesis_id) DO NOTHING;

INSERT INTO prostheses (prosthesis_id, customer_id, prosthesis_model, support_tier, fitted_at, last_service_date)
SELECT 'BP-1003', customer_id, 'BionicPRO Arm X', 'premium', DATE '2025-12-05', DATE '2026-03-12'
FROM customers WHERE username = 'prothetic2'
ON CONFLICT (prosthesis_id) DO NOTHING;

INSERT INTO prostheses (prosthesis_id, customer_id, prosthesis_model, support_tier, fitted_at, last_service_date)
SELECT 'BP-1004', customer_id, 'BionicPRO Wrist', 'standard', DATE '2025-10-15', DATE '2026-03-20'
FROM customers WHERE username = 'prothetic3'
ON CONFLICT (prosthesis_id) DO NOTHING;

INSERT INTO prostheses (prosthesis_id, customer_id, prosthesis_model, support_tier, fitted_at, last_service_date)
SELECT 'INT-2001', customer_id, 'BionicPRO Hand Global', 'standard', DATE '2025-09-30', DATE '2026-03-14'
FROM customers WHERE username = 'john.doe'
ON CONFLICT (prosthesis_id) DO NOTHING;

INSERT INTO prostheses (prosthesis_id, customer_id, prosthesis_model, support_tier, fitted_at, last_service_date)
SELECT 'INT-2002', customer_id, 'BionicPRO Flex', 'premium', DATE '2025-08-22', DATE '2026-03-11'
FROM customers WHERE username = 'alex.johnson'
ON CONFLICT (prosthesis_id) DO NOTHING;
