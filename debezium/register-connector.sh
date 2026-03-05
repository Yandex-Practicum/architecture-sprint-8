#!/bin/bash
# Регистрация Debezium-коннектора в Kafka Connect
# Запускать после того, как kafka-connect полностью стартовал

set -euo pipefail

CONNECT_URL="${CONNECT_URL:-http://localhost:8083}"
CONNECTOR_CONFIG="$(dirname "$0")/register-connector.json"

echo "⏳ Ожидание готовности Kafka Connect..."
until curl -s "${CONNECT_URL}/connectors" > /dev/null 2>&1; do
    sleep 2
done
echo "✅ Kafka Connect доступен"

echo "📦 Регистрация коннектора crm-connector..."
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST "${CONNECT_URL}/connectors" \
    -H "Content-Type: application/json" \
    -d @"${CONNECTOR_CONFIG}")

if [ "$RESPONSE" = "201" ]; then
    echo "✅ Коннектор зарегистрирован"
elif [ "$RESPONSE" = "409" ]; then
    echo "⚠️  Коннектор уже существует, обновляем конфиг..."
    curl -s -X PUT "${CONNECT_URL}/connectors/crm-connector/config" \
        -H "Content-Type: application/json" \
        -d "$(jq '.config' "${CONNECTOR_CONFIG}")"
    echo "✅ Конфиг обновлён"
else
    echo "❌ Ошибка: HTTP ${RESPONSE}"
    curl -s -X POST "${CONNECT_URL}/connectors" \
        -H "Content-Type: application/json" \
        -d @"${CONNECTOR_CONFIG}"
    exit 1
fi

echo ""
echo "📊 Статус коннектора:"
curl -s "${CONNECT_URL}/connectors/crm-connector/status" | jq .
