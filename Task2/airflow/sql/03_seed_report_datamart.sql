-- Тестовые данные для проверки UI: отчёт для пользователя user1 (логин Keycloak).
-- Выполнить после 01_schema_olap.sql на пустой витрине.
INSERT INTO report_datamart (
    user_id, device_id, customer_name, customer_email, contract_date,
    prosthesis_model, delivery_date, session_count, total_usage_seconds,
    event_count, error_count, calibration_count, period_start, period_end, last_activity_utc, updated_at
) VALUES (
    'user1',
    'device-001',
    'User One',
    'user1@example.com',
    '2024-01-15',
    'BionicPRO v2',
    '2024-02-01',
    42,
    36000,
    120,
    2,
    5,
    '2024-12-01 00:00:00+00',
    '2024-12-31 23:59:59+00',
    '2024-12-30 14:22:00+00',
    NOW() AT TIME ZONE 'UTC'
) ON CONFLICT (user_id) DO NOTHING;
