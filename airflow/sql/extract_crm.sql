-- Источник: PostgreSQL CRM.
-- Достаём только то, что нужно для витрины. updated_at > data_interval_start,
-- чтобы инкрементально тянуть изменения.

SELECT
    u.id            AS user_id,
    u.email         AS user_email,
    u.first_name    AS user_first_name,
    u.last_name     AS user_last_name,
    u.country       AS user_country,
    p.id            AS prosthesis_id,
    p.model         AS prosthesis_model,
    p.serial_number AS prosthesis_serial,
    p.assigned_at   AS assigned_at
FROM users u
INNER JOIN prostheses p ON p.user_id = u.id
WHERE u.updated_at >= '{{ data_interval_start }}'
   OR p.updated_at >= '{{ data_interval_start }}';