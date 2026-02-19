docker run --rm --network architecture-bionicpro_default \
  minio/mc:RELEASE.2025-08-13T08-35-41Z \
  sh -c 'mc alias set local http://minio:9000 minioadmin minioadmin && echo "--- buckets ---" && mc ls local && echo "--- reports ---" && mc ls local/reports || true'



docker exec -i $(docker compose ps -q crm_db) psql -U crm_user -d crm -c "
CREATE TABLE IF NOT EXISTS customers (
  customer_id  TEXT PRIMARY KEY,
  crm_user_id  TEXT NOT NULL,
  full_name    TEXT NOT NULL,
  email        TEXT,
  phone        TEXT,
  country      TEXT,
  city         TEXT,
  prosthesis_id TEXT,
  contract_id  TEXT,
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS \$\$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
\$\$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_customers_updated_at ON customers;
CREATE TRIGGER trg_customers_updated_at
BEFORE UPDATE ON customers
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();
"


---
docker exec -i $(docker compose ps -q crm_db) psql -U crm_user -d crm -c "
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'debezium') THEN
    CREATE ROLE debezium WITH LOGIN PASSWORD 'dbz';
  END IF;
END
\$\$;

ALTER ROLE debezium REPLICATION;
GRANT CONNECT ON DATABASE crm TO debezium;
GRANT USAGE ON SCHEMA public TO debezium;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO debezium;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO debezium;
"
---
docker exec -i $(docker compose ps -q crm_db) psql -U crm_user -d crm -c "
DROP PUBLICATION IF EXISTS dbz_publication;
CREATE PUBLICATION dbz_publication FOR TABLE customers;
"
---

docker exec -i $(docker compose ps -q crm_db) psql -U crm_user -d crm -c "
INSERT INTO customers(customer_id, crm_user_id, full_name, email, phone, country, city, prosthesis_id, contract_id)
VALUES
  ('cust-1', 'crm-1', 'Ivan Petrov', 'ivan@example.com', '+79990001122', 'RU', 'Moscow', 'prost-1', 'contract-1'),
  ('cust-2', 'crm-2', 'Petr Ivanov', 'petr@example.com', '+79990003344', 'RU', 'Samara', 'prost-2', 'contract-2')
ON CONFLICT (customer_id) DO UPDATE SET
  crm_user_id = EXCLUDED.crm_user_id,
  full_name = EXCLUDED.full_name,
  email = EXCLUDED.email,
  phone = EXCLUDED.phone,
  country = EXCLUDED.country,
  city = EXCLUDED.city,
  prosthesis_id = EXCLUDED.prosthesis_id,
  contract_id = EXCLUDED.contract_id;
"
---
docker exec -it $(docker compose ps -q crm_db) psql -U crm_user -d crm -c "\dRp+"
---
curl -s -X POST http://localhost:8083/connectors \
  -H "Content-Type: application/json" \
  -d '{
    "name": "crm-postgres-connector",
    "config": {
      "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
      "tasks.max": "1",

      "database.hostname": "crm_db",
      "database.port": "5432",
      "database.user": "debezium",
      "database.password": "dbz",
      "database.dbname": "crm",
      "database.server.name": "crm",

      "plugin.name": "pgoutput",
      "publication.name": "dbz_publication",
      "slot.name": "dbz_slot",

      "schema.include.list": "public",
      "table.include.list": "public.customers",

      "topic.prefix": "crm",
      "tombstones.on.delete": "false",

      "key.converter": "org.apache.kafka.connect.json.JsonConverter",
      "value.converter": "org.apache.kafka.connect.json.JsonConverter",
      "key.converter.schemas.enable": "false",
      "value.converter.schemas.enable": "false"
    }
  }'
---