#!/bin/sh
set -eu
CONNECT="${CONNECT_URL:-http://kafka-connect:8083}"
NAME="crm-connector"
CFG="/scripts/crm-connector.json"

echo "Waiting for Kafka Connect at ${CONNECT}..."
i=0
while ! curl -sf "${CONNECT}/" >/dev/null 2>&1; do
  i=$((i + 1))
  if [ "$i" -gt 90 ]; then
    echo "Kafka Connect not ready" >&2
    exit 1
  fi
  sleep 2
done

echo "Removing old connector if any..."
curl -sf -X DELETE "${CONNECT}/connectors/${NAME}" >/dev/null 2>&1 || true

echo "Registering Debezium PostgreSQL connector..."
curl -sf -X POST "${CONNECT}/connectors" \
  -H "Content-Type: application/json" \
  -d @"${CFG}"

echo ""
echo "Waiting for connector RUNNING..."
i=0
while [ "$i" -lt 120 ]; do
  if curl -sf "${CONNECT}/connectors/${NAME}/status" | grep -q '"state":"RUNNING"'; then
    echo "Connector RUNNING."
    exit 0
  fi
  i=$((i + 1))
  sleep 2
done

echo "Connector did not reach RUNNING in time" >&2
curl -sf "${CONNECT}/connectors/${NAME}/status" >&2 || true
exit 1
