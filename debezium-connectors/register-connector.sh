#!/bin/sh
set -e

echo "Waiting for Kafka Connect to start..."
until curl -f http://debezium-connect:8083/connectors; do
  sleep 5
done

echo "Registering Debezium PostgreSQL connector..."
curl -i -X POST -H "Content-Type: application/json" --data @crm-connector.json http://debezium-connect:8083/connectors

echo "Connector registered."
