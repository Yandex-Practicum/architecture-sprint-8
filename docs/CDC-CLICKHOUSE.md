# CDC: CRM → Kafka → ClickHouse

## Цель

Разделение потоков операций: запросы на выгрузку данных не нагружают OLTP-БД CRM. Данные из CRM попадают в OLAP (ClickHouse) через CDC и Kafka, reports-api читает из ClickHouse.

## Компоненты

| Компонент            | Порт                       | Описание                                    |
|----------------------|----------------------------|---------------------------------------------|
| **crm_db**           | 5435                       | PostgreSQL OLTP, `wal_level=logical`        |
| **Kafka**            | 9092                       | Брокер сообщений                            |
| **Debezium Connect** | 8083                       | CDC-коннектор (PostgreSQL → Kafka)          |
| **ClickHouse**       | 8123 (HTTP), 9009 (native) | OLAP, KafkaEngine + MaterializedView        |
| **reports-api**      | 9000                       | Читает из ClickHouse (при `CLICKHOUSE_DSN`) |

## Поток данных

1. **CRM** (`crm_db`): таблицы `users`, `telemetry_events`
2. **Debezium**: логирует изменения → Kafka топики `crm_db.public.telemetry_events`, `crm_db.public.users`
3. **ClickHouse KafkaEngine**: читает из топика `crm_db.public.telemetry_events`
4. **MV `mv_telemetry_to_events`**: парсит Debezium JSON (`after`, `op`) → таблица `telemetry_events`
5. **MV `mv_telemetry_to_datamart`**: агрегирует по `user_id` и неделе → витрина `datamart_reports`
6. **reports-api**: `SELECT ... FROM datamart_reports FINAL WHERE user_id = ?`

## Запуск

1. Поднять все сервисы:
   ```bash
   docker compose up -d --build
   ```

2. Дождаться старта Debezium Connect (~30 сек), зарегистрировать коннектор:
   ```bash
   chmod +x scripts/register-debezium-connector.sh
   ./scripts/register-debezium-connector.sh
   ```

3. Дождаться snapshot Debezium и прихода данных в ClickHouse (1–2 мин). Проверка:
   ```bash
   docker exec -it clickhouse clickhouse-client --query "SELECT count() FROM telemetry_events"
   ```

## Переменные окружения reports-api

- `CLICKHOUSE_DSN` — при задании используется ClickHouse вместо PostgreSQL OLAP (например: `clickhouse://clickhouse:9000/default`)
- `OLAP_DATABASE_URL` — используется, если `CLICKHOUSE_DSN` не задан (fallback на PostgreSQL)
