CREATE ROLE cdc_user WITH
    LOGIN
    REPLICATION
    PASSWORD 'password';

GRANT CONNECT ON DATABASE crm TO cdc_user;
GRANT USAGE ON SCHEMA public TO cdc_user;
GRANT SELECT ON TABLE public.crm_users TO cdc_user;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
GRANT SELECT ON TABLES TO cdc_user;

CREATE PUBLICATION crm_publication FOR TABLE public.crm_users, public.orders;