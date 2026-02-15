#!/bin/sh

# Wait for Debezium to be ready
sleep 30

# Register PostgreSQL connector for crm_clients
curl -X POST http://debezium:8083/connectors -H "Content-Type: application/json" -d '{
  "name": "crm-connector",
  "config": {
    "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
    "database.hostname": "crm_db",
    "database.port": "5432",
    "database.user": "crm_user",
    "database.password": "crm_password",
    "database.dbname": "crm",
    "database.server.name": "crm",
    "table.include.list": "public.crm_clients,public.telemetry_events",
    "plugin.name": "pgoutput",
    "slot.name": "debezium_slot",
    "publication.name": "debezium_pub",
    "topic.prefix": "crm.",
    "key.converter": "org.apache.kafka.connect.json.JsonConverter",
    "key.converter.schemas.enable": false,
    "value.converter": "org.apache.kafka.connect.json.JsonConverter",
    "value.converter.schemas.enable": false
  }
}'