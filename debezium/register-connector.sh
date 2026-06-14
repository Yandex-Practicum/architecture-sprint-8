#!/bin/sh
# ============================================================================
# Debezium Connector Registration Script
# BionicPRO - Задание 4: CDC для CRM Database
# ============================================================================

set -e

CONNECT_URL="http://debezium:8083"
CONNECTOR_CONFIG="/crm-connector.json"

echo "============================================"
echo "Debezium Connector Registration"
echo "============================================"

# Ждём пока Debezium Connect станет доступен
echo "Waiting for Debezium Connect to be ready..."
until curl -s -o /dev/null -w '%{http_code}' "$CONNECT_URL" | grep -q "200"; do
    echo "  Waiting..."
    sleep 5
done
echo "Debezium Connect is ready!"

# Проверяем существующие коннекторы
echo ""
echo "Current connectors:"
curl -s "$CONNECT_URL/connectors" | cat
echo ""

# Проверяем существует ли уже коннектор
if curl -s "$CONNECT_URL/connectors/crm-connector" | grep -q "crm-connector"; then
    echo "Connector 'crm-connector' already exists. Updating..."
    curl -i -X PUT \
        -H "Accept:application/json" \
        -H "Content-Type:application/json" \
        "$CONNECT_URL/connectors/crm-connector/config" \
        -d @"$CONNECTOR_CONFIG"
else
    echo "Creating new connector 'crm-connector'..."
    curl -i -X POST \
        -H "Accept:application/json" \
        -H "Content-Type:application/json" \
        "$CONNECT_URL/connectors/" \
        -d @"$CONNECTOR_CONFIG"
fi

echo ""
echo "============================================"
echo "Connector status:"
echo "============================================"
sleep 5
curl -s "$CONNECT_URL/connectors/crm-connector/status" | cat
echo ""

echo "============================================"
echo "Registration complete!"
echo "============================================"
