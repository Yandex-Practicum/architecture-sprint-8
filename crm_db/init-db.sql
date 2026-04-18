CREATE TABLE IF NOT EXISTS crm_customers (
    id SERIAL PRIMARY KEY,
    full_name TEXT NOT NULL,
    email TEXT NOT NULL,
    country TEXT NOT NULL,
    age INT NOT NULL
);

COPY crm_customers(id, full_name, email, country, age)
FROM '/docker-entrypoint-initdb.d/crm.csv'
DELIMITER ','
CSV HEADER;