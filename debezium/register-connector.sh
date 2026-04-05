#!/bin/sh
set -e

CONNECT_URL="${KAFKA_CONNECT_URL:-http://kafka-connect:8083}"
CONNECTOR_NAME="crm-connector"
CONFIG_FILE="/debezium/postgres-crm-connector.json"

attempt=0
until curl -sf "${CONNECT_URL}/connectors" >/dev/null; do
  attempt=$((attempt + 1))
  if [ "$attempt" -gt 90 ]; then
    echo "kafka-connect not ready"
    exit 1
  fi
  sleep 2
done

if curl -sf "${CONNECT_URL}/connectors/${CONNECTOR_NAME}" >/dev/null; then
  echo "Debezium connector ${CONNECTOR_NAME} already registered"
else
  curl -sf -X POST -H "Content-Type: application/json" \
    -d @"${CONFIG_FILE}" \
    "${CONNECT_URL}/connectors"
  echo "Registered ${CONNECTOR_NAME}"
fi
