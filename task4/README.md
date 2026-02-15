# Task4 — CDC, Kafka, ClickHouse, Airflow

## Архитектура
- CRM OLTP: `crm_db` (Postgres, `wal_level=logical`), данные инициализируются из `init_crm.sql`.
- CDC: Debezium Connector (Postgres) -> Kafka (`crm.crm_clients`, `crm.telemetry_events`).
- OLAP: ClickHouse (Kafka Engine + Materialized Views) с портами `8123`, `9002` (внутри кластера 9000).
- Витрина: таблица `client_datamart` в ClickHouse (обновляется DAG-ом).
- Отчёты: `reports_api` читает из ClickHouse, складывает отчёты в MinIO, раздаёт через `nginx_cdn`.
- Airflow: DAG `etl_crm_telemetry` (имитация загрузки + агрегирование в витрину), пакеты `clickhouse-driver` ставятся в entrypoint.

## Запуск
```bash
cd task4
# поднять базовые сервисы
docker compose up -d zookeeper kafka clickhouse crm_db debezium
# зарегистрировать коннектор (при необходимости, если не поднят register_connector)
docker run --rm --network task4_default curlimages/curl \
  sh -c "curl -X POST http://debezium:8083/connectors -H 'Content-Type: application/json' -d '{\"name\": \"crm-connector\", \"config\": {\"connector.class\": \"io.debezium.connector.postgresql.PostgresConnector\", \"database.hostname\": \"crm_db\", \"database.port\": \"5432\", \"database.user\": \"crm_user\", \"database.password\": \"crm_password\", \"database.dbname\": \"crm\", \"database.server.name\": \"crm\", \"table.include.list\": \"public.crm_clients,public.telemetry_events\", \"plugin.name\": \"pgoutput\", \"slot.name\": \"debezium_slot\", \"publication.name\": \"debezium_pub\", \"topic.prefix\": \"crm.\", \"key.converter\": \"org.apache.kafka.connect.json.JsonConverter\", \"value.converter\": \"org.apache.kafka.connect.json.JsonConverter\"}}'"
# запустить остальное (Airflow, фронт, API, MinIO и т.д.)
docker compose up -d
```

## Порты
- ClickHouse HTTP: 8123, TCP: 9002 (внутри сети 9000)
- Kafka: 9092 (host), 29092 (internal)
- Debezium: 8085
- CRM DB: 5436 (host)
- Airflow Web: 8082 (admin/admin123)
- Reports API: 8083
- Keycloak: 8080
- Frontend: 3000
- MinIO: 9000 (S3), 9001 (console)
- CDN (nginx_cdn): 8084

## Проверки
- ClickHouse доступен: `docker exec -it task4-clickhouse-1 clickhouse-client --query "SELECT 1"`
- Kafka топики: `docker exec -it task4-kafka-1 kafka-topics --bootstrap-server kafka:29092 --list`
- Debezium коннектор: `curl http://localhost:8085/connectors`
- Airflow DAGs: http://localhost:8082
- Reports API тест: POST http://localhost:8083/reports (с Bearer-токеном Keycloak)

## Примечания
- Если порт 9000 занят (MinIO), ClickHouse вынесен на 9002 снаружи.
- Пакет `clickhouse-driver` ставится в entrypoint для `airflow_webserver` и `airflow_scheduler`.
- При ошибках mount вида `.Trash/...` убедитесь, что файлы не лежат в Корзине macOS.
