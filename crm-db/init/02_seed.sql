INSERT INTO customers (username, first_name, last_name, email, prosthetic_id, country) VALUES
    ('prothetic1',  'Prothetic', 'One',     'prothetic1@example.com',   'PRO-1001', 'Russia'),
    ('prothetic2',  'Prothetic', 'Two',     'prothetic2@example.com',   'PRO-1002', 'Russia'),
    ('prothetic3',  'Prothetic', 'Three',   'prothetic3@example.com',   'PRO-1003', 'Russia'),
    ('alex.johnson','Alex',      'Johnson', 'alex@example.com',         'PRO-2001', 'Kazakhstan'),
    ('john.doe',    'John',      'Doe',     'john@example.com',         'PRO-2002', 'Kazakhstan');

INSERT INTO telemetry_events (customer_username, prosthetic_id, event_time, action_type, latency_ms, signal_quality)
SELECT
    c.username,
    c.prosthetic_id,
    now() - (gs.n || ' minutes')::interval,
    (ARRAY['grip', 'release', 'rotate', 'pinch'])[1 + floor(random() * 4)::int],
    round((40 + random() * 90)::numeric, 2),
    round((0.7 + random() * 0.3)::numeric, 3)
FROM customers c
CROSS JOIN LATERAL generate_series(0, 3 * 24 * 60, 5 + floor(random() * 15)::int) AS gs(n);
