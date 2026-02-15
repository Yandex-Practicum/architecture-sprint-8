CREATE TABLE IF NOT EXISTS crm_clients (
    client_id VARCHAR(255) PRIMARY KEY,
    name VARCHAR(255),
    email VARCHAR(255)
);
CREATE TABLE IF NOT EXISTS telemetry_events (
    id SERIAL PRIMARY KEY,
    client_id VARCHAR(255),
    event VARCHAR(255),
    timestamp TIMESTAMP
);
CREATE TABLE IF NOT EXISTS client_datamart (
    client_id VARCHAR(255) PRIMARY KEY,
    name VARCHAR(255),
    email VARCHAR(255),
    total_events INTEGER,
    last_event TIMESTAMP
);
INSERT INTO crm_clients (client_id, name, email) VALUES 
('21d74fdf-adad-4b60-b296-4e73569c942a', 'Client A', 'a@example.com'),
('another-uuid', 'Client B', 'b@example.com')
ON CONFLICT (client_id) DO NOTHING;
INSERT INTO telemetry_events (client_id, event, timestamp) VALUES 
('21d74fdf-adad-4b60-b296-4e73569c942a', 'login', '2023-01-01 10:00:00'),
('21d74fdf-adad-4b60-b296-4e73569c942a', 'view_page', '2023-01-01 10:05:00'),
('another-uuid', 'login', '2023-01-01 11:00:00')
ON CONFLICT DO NOTHING;
INSERT INTO client_datamart (client_id, name, email, total_events, last_event) VALUES 
('21d74fdf-adad-4b60-b296-4e73569c942a', 'Client A', 'a@example.com', 2, '2023-01-01 10:05:00'),
('another-uuid', 'Client B', 'b@example.com', 1, '2023-01-01 11:00:00')
ON CONFLICT (client_id) DO UPDATE SET
    total_events = EXCLUDED.total_events,
    last_event = EXCLUDED.last_event;