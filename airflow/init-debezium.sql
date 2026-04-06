-- Пользователь и права для Debezium (logical replication + чтение CRM)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'debezium') THEN
        CREATE ROLE debezium WITH LOGIN PASSWORD 'debezium' REPLICATION;
    END IF;
END
$$;

GRANT CONNECT ON DATABASE crm_db TO debezium;
-- filtered publication (Debezium) требует CREATE на БД и владения таблицами в публикации
GRANT CREATE ON DATABASE crm_db TO debezium;
GRANT USAGE ON SCHEMA public TO debezium;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO debezium;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO debezium;

ALTER TABLE public.crm_clients OWNER TO debezium;
ALTER TABLE public.crm_prosthetics OWNER TO debezium;
