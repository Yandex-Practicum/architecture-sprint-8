CREATE TABLE IF NOT EXISTS crm_users (
                                         user_id SERIAL PRIMARY KEY,
                                         username VARCHAR(50) NOT NULL,
    email VARCHAR(100) NOT NULL,
    full_name VARCHAR(150)
    );

INSERT INTO crm_users (username, email, full_name) VALUES
                                                       ('john.doe', 'john@example.com', 'John Doe'),
                                                       ('jane.smith', 'jane@example.com', 'Jane Smith'),
                                                       ('alex.johnson', 'alex@example.com', 'Alex Johnson');


CREATE TABLE IF NOT EXISTS public.orders (
                                             order_id SERIAL PRIMARY KEY,
                                             user_id INTEGER NOT NULL REFERENCES public.crm_users(user_id),
    order_number VARCHAR(64) NOT NULL UNIQUE,
    product_name VARCHAR(255) NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    amount NUMERIC(12, 2) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'created',
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    updated_at TIMESTAMP NOT NULL DEFAULT now()
    );

ALTER TABLE public.orders REPLICA IDENTITY FULL;

CREATE INDEX IF NOT EXISTS idx_orders_user_id ON public.orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON public.orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_created_at ON public.orders(created_at);