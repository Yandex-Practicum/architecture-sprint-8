CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE telemetry_events (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_time     TIMESTAMPTZ NOT NULL,
    serial_number  TEXT NOT NULL,
    load_value     NUMERIC(10,2) NOT NULL,
    duration_sec   INT NOT NULL
);

INSERT INTO telemetry_events (event_time, serial_number, load_value, duration_sec) VALUES
  (NOW() - INTERVAL '2 hours', 'P-USER1-001', 10.5, 120),
  (NOW() - INTERVAL '1 hour',  'P-USER1-001', 12.0, 180),
  (NOW() - INTERVAL '3 hours', 'P-USER1-002', 8.0,  60),
  (NOW() - INTERVAL '30 mins', 'P-USER1-002', 9.5,  240),
  (NOW() - INTERVAL '1 day',   'P-USER2-001', 7.0,  300),
  (NOW() - INTERVAL '20 mins', 'P-USER2-001', 15.0, 120),
  (NOW() - INTERVAL '5 hours', 'P-USER2-002', 5.0,  90),
  (NOW() - INTERVAL '10 mins', 'P-USER2-002', 11.5, 60);
