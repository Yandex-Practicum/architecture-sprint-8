#!/usr/bin/env bash
# Регистрация Debezium-коннектора CDC для CRM в Kafka Connect.
# Использование: ./register.sh [connect_url]  (по умолчанию http://localhost:8083)
set -euo pipefail

CONNECT_URL="${1:-http://localhost:8083}"
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# @<(...) передаёт в --data только секцию config из crm-connector.json
curl -sf -X PUT \
  -H "Content-Type: application/json" \
  --data @<(python3 -c "import json,sys; c=json.load(open('$DIR/crm-connector.json')); print(json.dumps(c['config']))") \
  "$CONNECT_URL/connectors/crm-connector/config" \
  && echo "OK: коннектор crm-connector зарегистрирован/обновлён"
