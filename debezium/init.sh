#!/bin/bash
echo "Waiting for Kafka Connect to be ready..."
while ! curl -s http://localhost:8083/connectors; do
  sleep 5
done

echo "Registering CRM connector..."
curl -i -X POST -H "Accept:application/json" -H "Content-Type:application/json" \
  http://localhost:8083/connectors/ -d @/connectors/crm-connector.json

echo "Connector registered!"