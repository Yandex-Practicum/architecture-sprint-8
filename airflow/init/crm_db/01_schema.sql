CREATE TABLE customer_plan (
    user_id TEXT PRIMARY KEY,
    plan_code TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
