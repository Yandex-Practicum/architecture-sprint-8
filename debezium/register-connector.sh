#!/bin/sh
# Registers the Debezium PostgreSQL connector with Kafka Connect.
# Retries until Kafka Connect REST API is available.

KC_URL="${KAFKA_CONNECT_URL:-http://kafka-connect:8083}"
CONFIG_FILE="${CONFIG_FILE:-/connector-config.json}"

echo "Waiting for Kafka Connect at ${KC_URL} ..."
until curl -sf "${KC_URL}/connectors" > /dev/null; do
  echo "  Kafka Connect not ready, retrying in 5s..."
  sleep 5
done

echo "Kafka Connect is up. Registering connector..."

RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" \
  -X POST "${KC_URL}/connectors" \
  -H "Content-Type: application/json" \
  --data-binary "@${CONFIG_FILE}")

if [ "$RESPONSE" = "201" ] || [ "$RESPONSE" = "409" ]; then
  echo "Connector registered (HTTP ${RESPONSE}). Done."
else
  echo "ERROR: Unexpected response HTTP ${RESPONSE}"
  exit 1
fi
