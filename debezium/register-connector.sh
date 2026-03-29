#!/bin/sh
set -eu

CONNECT_URL="${KAFKA_CONNECT_URL:-http://kafka-connect:8083}"
CONNECTOR_NAME="${DEBEZIUM_CONNECTOR_NAME:-crm-postgres-connector}"
CONFIG_PATH="${DEBEZIUM_CONNECTOR_CONFIG:-/debezium/crm-postgres-connector.json}"

until curl -fsS "${CONNECT_URL}/connectors" >/dev/null 2>&1; do
  echo "waiting for kafka-connect at ${CONNECT_URL}"
  sleep 5
done

echo "registering ${CONNECTOR_NAME}"
until curl -fsS \
  -X PUT \
  -H "Content-Type: application/json" \
  --data @"${CONFIG_PATH}" \
  "${CONNECT_URL}/connectors/${CONNECTOR_NAME}/config" >/dev/null 2>&1; do
  echo "connector registration is not accepted yet, retrying"
  sleep 5
done

echo "connector ${CONNECTOR_NAME} is ready"
