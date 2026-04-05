INSERT INTO telemetry (user_id, measured_at, temperature_c, pulse_bpm)
SELECT
    u.user_id,
    slots.measured_at,
    CASE
        WHEN u.has_temp THEN round((36.2 + random() * 1.0)::numeric, 2)
    END,
    CASE
        WHEN u.has_pulse THEN (58 + floor(random() * 38)::int)
    END
FROM (
    VALUES
        ('john.doe', true, true),
        ('jane.smith', false, true),
        ('alex.johnson', true, false)
) AS u(user_id, has_temp, has_pulse)
CROSS JOIN generate_series(
    TIMESTAMPTZ '2026-03-01 00:00:00+00',
    TIMESTAMPTZ '2026-03-31 23:00:00+00',
    INTERVAL '1 hour'
) AS slots(measured_at);
