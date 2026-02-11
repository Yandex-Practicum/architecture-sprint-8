#!/bin/bash
# Регистрирует Debezium PostgreSQL connector для crm_db
# Конфигурация: debezium/crm-connector.json
# Запускать после старта debezium-connect (подождать ~30 сек)

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
CONNECT_URL="${DEBEZIUM_CONNECT_URL:-http://localhost:8083}"

curl -s -X POST -H "Content-Type: application/json" \
  "$CONNECT_URL/connectors" \
  -d @"$PROJECT_ROOT/debezium/crm-connector.json"

echo ""
echo "Connector registered. Check: curl $CONNECT_URL/connectors"
