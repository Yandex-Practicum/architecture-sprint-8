curl -X POST http://localhost:8083/connectors \
  -H "Content-Type: application/json" \
  -d '{
    "name": "crm-postgres-cdc",
    "config": {
      "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
      "plugin.name": "pgoutput",

      "database.hostname": "crm_db",
      "database.port": "5432",
      "database.user": "cdc_user",
      "database.password": "password",
      "database.dbname": "crm",

      "topic.prefix": "crm",
      "slot.name": "crm_debezium_slot",
      "publication.name": "crm_publication",
      "publication.autocreate.mode": "disabled",

      "table.include.list": "public.crm_users,public.orders",

      "snapshot.mode": "initial",

      "key.converter": "org.apache.kafka.connect.json.JsonConverter",
      "value.converter": "org.apache.kafka.connect.json.JsonConverter",
      "key.converter.schemas.enable": "false",
      "value.converter.schemas.enable": "false",

      "transforms": "unwrap",
      "transforms.unwrap.type": "io.debezium.transforms.ExtractNewRecordState",
      "transforms.unwrap.delete.tombstone.handling.mode": "rewrite",
      "transforms.unwrap.add.fields": "op,source.ts_ms",

      "decimal.handling.mode": "string"
    }
  }'