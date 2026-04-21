sleep 10

curl -X DELETE http://debezium:8083/connectors/postgres-cdc-connector 2>/dev/null

curl -X POST http://debezium:8083/connectors \
  -H "Content-Type: application/json" \
  -d '{
    "name": "postgres-cdc-connector",
    "config": {
      "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
      "tasks.max": "1",
      "database.hostname": "postgres_crm",
      "database.port": "5432",
      "database.user": "debezium_user",
      "database.password": "strong_password",
      "database.dbname": "crm_db",
      "database.server.name": "cdc",
      "plugin.name": "pgoutput",
      "publication.name": "debezium_publication",
      "slot.name": "debezium_slot",
      "table.include.list": "crm.users,crm.prostheses",
      "topic.prefix": "cdc",
      "key.converter": "org.apache.kafka.connect.json.JsonConverter",
      "value.converter": "org.apache.kafka.connect.json.JsonConverter",
      "key.converter.schemas.enable": "false",
      "value.converter.schemas.enable": "false",
      "tombstones.on.delete": "false",
      "snapshot.mode": "initial",
      "decimal.handling.mode": "double"
    }
  }'

echo "Connector registered"