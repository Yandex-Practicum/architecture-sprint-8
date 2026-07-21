#!/bin/sh
set -e

echo "waiting for kafka-connect REST API..."
until curl -sf http://kafka-connect:8083/connectors > /dev/null; do
  sleep 3
done

echo "registering debezium connector..."
code=$(curl -s -o /tmp/resp -w '%{http_code}' \
  -X POST -H 'Content-Type: application/json' \
  --data @/config/register-postgres.json \
  http://kafka-connect:8083/connectors || true)
echo "connector register HTTP ${code}"
cat /tmp/resp 2>/dev/null || true
echo ""
echo "connector-init done"
