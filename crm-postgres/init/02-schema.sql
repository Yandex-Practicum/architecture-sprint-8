CREATE TABLE IF NOT EXISTS public.crm_customers (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    customer_code VARCHAR(64) NOT NULL,
    orders_count INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Те же клиенты, что и в мок-CRM Airflow (Keycloak realm)
INSERT INTO public.crm_customers (email, customer_code, orders_count) VALUES
    ('user1@example.com', 'CRM-U1', 1),
    ('user2@example.com', 'CRM-U2', 0),
    ('admin1@example.com', 'CRM-ADM', 5),
    ('prothetic1@example.com', 'CRM-P1', 3),
    ('prothetic2@example.com', 'CRM-P2', 2),
    ('prothetic3@example.com', 'CRM-P3', 4)
ON CONFLICT (email) DO UPDATE SET
    customer_code = EXCLUDED.customer_code,
    orders_count = EXCLUDED.orders_count,
    updated_at = now();
