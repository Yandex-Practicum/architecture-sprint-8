#!/usr/bin/env bash
set -euo pipefail

CONNECT_URL="http://debezium-connect:8083"
CONFIG_FILE="/config/debezium-connector.json"

echo "Waiting for Debezium Connect at $CONNECT_URL..."
for i in $(seq 1 60); do
  if curl -fsS "$CONNECT_URL/connectors" >/dev/null 2>&1; then
    echo "Debezium Connect is up"
    break
  fi
  sleep 2
  if [ "$i" -eq 60 ]; then
    echo "Debezium Connect not reachable"
    exit 1
  fi
done

echo "Creating publication dbz_publication in CRM DB..."
docker exec -i crm_db psql -U crm_user -d crm -c "DROP PUBLICATION IF EXISTS dbz_publication;" 2>/dev/null || true
docker exec -i crm_db psql -U crm_user -d crm -c "CREATE PUBLICATION dbz_publication FOR TABLE users, prostheses;"

echo "Registering Postgres connector..."
HTTP_CODE=$(curl -sS -o /tmp/connector_resp -w "%{http_code}" \
  -X POST -H "Content-Type: application/json" \
  --data @"$CONFIG_FILE" \
  "$CONNECT_URL/connectors")

echo "HTTP $HTTP_CODE"
cat /tmp/connector_resp
echo
exit 0