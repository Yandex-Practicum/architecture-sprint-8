#!/bin/bash
# Register the Debezium PostgreSQL connector for CRM CDC
# Run this script after all services are up:
#   docker compose exec debezium bash /scripts/register-debezium-connector.sh
# Or from host:
#   bash scripts/register-debezium-connector.sh

DEBEZIUM_URL="${DEBEZIUM_URL:-http://localhost:8083}"
CONNECTOR_CONFIG="$(dirname "$0")/../debezium/connector-config.json"

echo "Waiting for Debezium Connect to be ready..."
until curl -sf "${DEBEZIUM_URL}/connectors" > /dev/null 2>&1; do
  echo "  Debezium not ready, retrying in 5s..."
  sleep 5
done

echo "Debezium Connect is ready. Registering CRM connector..."

curl -X POST "${DEBEZIUM_URL}/connectors" \
  -H "Content-Type: application/json" \
  -d @"${CONNECTOR_CONFIG}"

echo ""
echo "Connector registered. Checking status..."
sleep 2

curl -sf "${DEBEZIUM_URL}/connectors/crm-connector/status" | python3 -m json.tool 2>/dev/null || \
  curl -sf "${DEBEZIUM_URL}/connectors/crm-connector/status"

echo ""
echo "Done. Kafka topics should now be receiving CDC events."
