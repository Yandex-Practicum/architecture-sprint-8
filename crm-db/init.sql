CREATE TABLE IF NOT EXISTS customers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100),
    email VARCHAR(100),
    age INTEGER,
    gender VARCHAR(10),
    country VARCHAR(100),
    address VARCHAR(255),
    phone VARCHAR(25)
);

COPY customers(id, name, email, age, gender, country, address, phone)
FROM '/docker-entrypoint-initdb.d/crm.csv'
DELIMITER ','
CSV HEADER;


CREATE USER cdc_user WITH PASSWORD 'password' REPLICATION;

GRANT CONNECT ON DATABASE crm_db TO cdc_user;
GRANT SELECT ON public.customers TO cdc_user;

CREATE PUBLICATION crm_pub FOR TABLE customers;