-- Замена контейнера "База данных" (PostgreSQL) с исходной C4-диаграммы:
-- сырая техническая телеметрия, отправляемая чипом протеза (качество
-- миосигнала, задержка распознавания, уровень заряда батареи).
CREATE TABLE telemetry_events (
    event_id            BIGSERIAL PRIMARY KEY,
    customer_id         VARCHAR(64) NOT NULL,
    device_id           VARCHAR(64) NOT NULL,
    event_ts            TIMESTAMP NOT NULL,
    myosignal_quality   NUMERIC(5, 2) NOT NULL,  -- 0..100
    recognition_latency_ms INTEGER NOT NULL,
    battery_level       INTEGER NOT NULL,        -- 0..100
    action_recognized   VARCHAR(64) NOT NULL
);

CREATE INDEX idx_telemetry_customer_ts ON telemetry_events (customer_id, event_ts);

INSERT INTO telemetry_events (customer_id, device_id, event_ts, myosignal_quality, recognition_latency_ms, battery_level, action_recognized) VALUES
    ('user1', 'dev-001', now() - interval '2 hours', 92.5, 78, 64, 'grip'),
    ('user1', 'dev-001', now() - interval '1 hours', 90.1, 82, 63, 'release'),
    ('user2', 'dev-002', now() - interval '3 hours', 88.4, 95, 41, 'pinch'),
    ('user2', 'dev-002', now() - interval '2 hours', 87.9, 99, 40, 'grip'),
    ('prothetic1', 'dev-003', now() - interval '5 hours', 95.2, 60, 77, 'grip'),
    ('prothetic1', 'dev-003', now() - interval '4 hours', 94.8, 63, 76, 'release'),
    ('prothetic2', 'dev-004', now() - interval '6 hours', 81.0, 110, 55, 'step'),
    ('prothetic2', 'dev-004', now() - interval '5 hours', 83.4, 105, 54, 'step'),
    ('prothetic3', 'dev-005', now() - interval '1 hours', 96.6, 55, 88, 'grip'),
    ('john.doe', 'dev-006', now() - interval '2 hours', 89.9, 84, 70, 'grip'),
    ('jane.smith', 'dev-007', now() - interval '3 hours', 91.4, 74, 66, 'step');
