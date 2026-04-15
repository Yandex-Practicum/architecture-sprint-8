#!/usr/bin/env sh
# Повторная регистрация коннектора (если контейнер register уже отработал и нужен ручной запуск)
set -e
BASE_URL="${KAFKA_CONNECT_URL:-http://127.0.0.1:8083}"
DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
curl -sf -X DELETE "$BASE_URL/connectors/crm-postgres-connector" || true
curl -sf -X POST -H "Content-Type: application/json" \
  --data @"$DIR/crm-postgres-connector.json" \
  "$BASE_URL/connectors"
