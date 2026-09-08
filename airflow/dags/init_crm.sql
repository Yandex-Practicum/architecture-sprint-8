CREATE TABLE IF NOT EXISTS clients (
                                       id SERIAL PRIMARY KEY,
                                       username VARCHAR(100) UNIQUE NOT NULL,
    full_name VARCHAR(200),
    email VARCHAR(200),
    created_at TIMESTAMP DEFAULT NOW()
    );

CREATE TABLE IF NOT EXISTS prosthesis_telemetry (
                                                    id SERIAL PRIMARY KEY,
                                                    client_id INTEGER REFERENCES clients(id),
    prosthesis_id VARCHAR(50),
    usage_hours FLOAT,
    battery_cycles INTEGER,
    movements_count INTEGER,
    recorded_at TIMESTAMP DEFAULT NOW()
    );

INSERT INTO clients (username, full_name, email) VALUES
                                                     ('prothetic1', 'Prothetic One', 'prothetic1@example.com'),
                                                     ('prothetic2', 'Prothetic Two', 'prothetic2@example.com'),
                                                     ('prothetic3', 'Prothetic Three', 'prothetic3@example.com')
    ON CONFLICT (username) DO NOTHING;

INSERT INTO prosthesis_telemetry (client_id, prosthesis_id, usage_hours, battery_cycles, movements_count) VALUES
                                                                                                              (1, 'PROS-001', 120.5, 45, 15000),
                                                                                                              (1, 'PROS-001', 125.0, 47, 15500),
                                                                                                              (2, 'PROS-002', 80.0, 30, 10000),
                                                                                                              (3, 'PROS-003', 200.0, 75, 25000)
    ON CONFLICT DO NOTHING;