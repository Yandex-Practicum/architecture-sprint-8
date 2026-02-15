ALTER SYSTEM SET wal_level = logical;
SELECT pg_reload_conf();
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
INSERT INTO crm_clients (client_id, name, email) VALUES
('21d74fdf-adad-4b60-b296-4e73569c942a', 'Client A', 'a@example.com'),
('another-uuid', 'Client B', 'b@example.com')
ON CONFLICT (client_id) DO NOTHING;
INSERT INTO telemetry_events (client_id, event, timestamp) VALUES
('21d74fdf-adad-4b60-b296-4e73569c942a', 'login', '2023-01-01 10:00:00'),
('21d74fdf-adad-4b60-b296-4e73569c942a', 'view_page', '2023-01-01 10:05:00'),
('another-uuid', 'login', '2023-01-01 11:00:00')
ON CONFLICT DO NOTHING;