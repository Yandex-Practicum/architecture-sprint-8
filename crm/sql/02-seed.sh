#!/bin/bash
set -e
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
  TRUNCATE telemetry_events, customers RESTART IDENTITY;
EOSQL
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -c "\COPY customers (customer_id, email, keycloak_subject, prosthesis_model, region) FROM '/seed/crm_customers.csv' WITH (FORMAT csv, HEADER true)"
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -c "\COPY telemetry_events (user_subject, event_date, active_minutes, steps) FROM '/seed/telemetry_events.csv' WITH (FORMAT csv, HEADER true)"
