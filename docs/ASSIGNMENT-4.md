# Задание 4. Повышение оперативности и стабильности работы CRM

Массовые выгрузки из CRM нагружали OLTP. Решение — **CDC**: изменения CRM
захватываются из WAL через **Debezium**, уходят в **Kafka**, а ClickHouse
принимает их через **KafkaEngine** и строит витрину **MaterializedView**.
Транзакционная Б\Д CRM больше не участвует в аналитических выгрузках — потоки
разделены.

## Поток данных

```
Postgres CRM (WAL, logical)
   │  Debezium (Kafka Connect, pgoutput, unwrap SMT)
Kafka topics: crm.public.clients, crm.public.telemetry
   │  ClickHouse KafkaEngine (kafka_clients, kafka_telemetry)  MaterializedView
CDC state: cdc_clients (ReplacingMergeTree), cdc_telemetry (ReplacingMergeTree)
   │  MaterializedView (агрегация в разрезе клиентов)
telemetry_daily (AggregatingMergeTree)  ──JOIN clients──  VIEW user_report_mart_cdc
                                                                    │
                                                              reports-api
```

## Соответствие задачам

### CDC для отслеживания изменений (Debezium)
- `crm-db` запущен с `wal_level=logical`; таблицы имеют `REPLICA IDENTITY FULL`.
- Debezium Postgres-коннектор: [`debezium/register-postgres.json`](../debezium/register-postgres.json)
  (`plugin.name=pgoutput`, `table.include.list=public.clients,public.telemetry`).
- `ExtractNewRecordState` (unwrap) разворачивает конверт Debezium в плоскую
  строку + метаполя `__op/__ts_ms/__deleted`.

### Отправка в топик Kafka
- Kafka (KRaft) + Kafka Connect в [`docker-compose.yaml`](../docker-compose.yaml).
- Топики: `crm.public.clients`, `crm.public.telemetry` (префикс `topic.prefix=crm`).

### Приём в ClickHouse через KafkaEngine
- [`analytics/clickhouse/cdc/01_cdc.sql`](../analytics/clickhouse/cdc/01_cdc.sql):
  таблицы `kafka_clients`, `kafka_telemetry` (`ENGINE = Kafka`, `JSONEachRow`).
- `MaterializedView` `mv_cdc_clients` / `mv_cdc_telemetry` перекладывают строки в
  state-таблицы `ReplacingMergeTree`. `auto_offset_reset=earliest`
  ([`config.d/kafka.xml`](../analytics/clickhouse/config.d/kafka.xml)) — чтобы
  забрать initial snapshot с начала топика.

### Витрина через MaterializedView
- `mv_report_mart` агрегирует телеметрию в разрезе (client, date) в
  `telemetry_daily` (`AggregatingMergeTree`, `SimpleAggregateFunction`).
- `VIEW user_report_mart_cdc` джойнит агрегат с актуальным состоянием клиентов
  (`argMax` по `ts_ms`, фильтр `is_deleted=0`) и отдаёт те же колонки, что и
  батч-витрина.

### Перевод API на новую витрину
- `reports-api`: `CLICKHOUSE_TABLE=user_report_mart_cdc`, `CLICKHOUSE_USE_FINAL=false`
  (витрина — VIEW, `FINAL` неприменим). Логика доступа/кеша (Задания 2–3) не
  меняется.

## Замечания
- Демо: CRM DB и телеметрия в одном Postgres; CDC покрывает обе таблицы.
- `mv_report_mart` агрегирует поток вставок; при at-least-once доставке/апдейтах
  строк возможен двойной учёт — для строгой идемпотентности берут дедуп по `id`
  (`cdc_telemetry FINAL`) на этапе выборки. Для snapshot-данных демо — точный
  однократный учёт.
- Kafka без host-порта (внутренняя сеть); Connect REST — на `:8083`.
