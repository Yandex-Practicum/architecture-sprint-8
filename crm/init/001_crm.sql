CREATE TABLE IF NOT EXISTS public.crm_customers
(
    user_id TEXT NOT NULL,
    user_name TEXT NOT NULL,
    email TEXT NOT NULL,
    prosthesis_id TEXT NOT NULL,
    country_code TEXT NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, prosthesis_id)
);

ALTER TABLE public.crm_customers REPLICA IDENTITY FULL;

INSERT INTO public.crm_customers
    (user_id, user_name, email, prosthesis_id, country_code, updated_at)
VALUES
    ('prothetic1', 'Alex Ivanov', 'alex.ivanov@example.com', 'prosthesis-1001', 'RU', '2026-06-18 08:00:00'),
    ('prothetic2', 'Maria Petrova', 'maria.petrova@example.com', 'prosthesis-1002', 'RU', '2026-06-18 08:10:00'),
    ('prothetic3', 'John Smith', 'john.smith@example.com', 'prosthesis-1003', 'US', '2026-06-18 08:20:00')
ON CONFLICT (user_id, prosthesis_id) DO UPDATE SET
    user_name = EXCLUDED.user_name,
    email = EXCLUDED.email,
    country_code = EXCLUDED.country_code,
    updated_at = EXCLUDED.updated_at;
