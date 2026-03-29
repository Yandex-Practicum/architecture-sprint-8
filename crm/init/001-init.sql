CREATE TABLE customers (
    id SERIAL PRIMARY KEY,
    keycloak_username VARCHAR(100) NOT NULL UNIQUE,
    full_name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    country_code VARCHAR(10) NOT NULL
);

CREATE TABLE prostheses (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    prosthesis_code VARCHAR(64) NOT NULL UNIQUE,
    model_name VARCHAR(255) NOT NULL,
    activated_at TIMESTAMP NOT NULL
);

INSERT INTO customers (keycloak_username, full_name, email, country_code) VALUES
    ('prothetic1', 'Ivan Petrov', 'prothetic1@example.com', 'RU'),
    ('prothetic2', 'Anna Smirnova', 'prothetic2@example.com', 'RU'),
    ('prothetic3', 'Pavel Sidorov', 'prothetic3@example.com', 'KZ');

INSERT INTO prostheses (customer_id, prosthesis_code, model_name, activated_at) VALUES
    (1, 'BP-RU-001', 'BionicPRO Arm X', NOW() - INTERVAL '180 days'),
    (2, 'BP-RU-002', 'BionicPRO Arm X', NOW() - INTERVAL '120 days'),
    (3, 'BP-KZ-003', 'BionicPRO Arm Lite', NOW() - INTERVAL '90 days');
