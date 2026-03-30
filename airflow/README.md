# Сервис отчётов BionicPRO (Airflow + ClickHouse)

В этом задании реализован DAG `bionicpro_reports_dag`, который по расписанию:
- извлекает данные о клиентах из CRM (Postgres),
- загружает их в OLAP (ClickHouse),
- генерирует витрину `user_daily_telemetry`, объединяющую телеметрию протезов и данные клиентов.

## Структура

- `airflow/docker-compose.airflow.yaml`
  Поднимает локальный стенд:
  - `clickhouse` - OLAP-база для витрин;
  - `postgres` - БД метаданных Airflow;
  - `airflow-webserver`, `airflow-scheduler` - сам Airflow.

- `airflow/dags/bionicpro_reports_dag.py`
  DAG `bionicpro_reports_dag`:
  - создаёт схемы и таблицы в ClickHouse (`crm_customers`, `telemetry_events`, `user_daily_telemetry`);
  - при первом запуске сидирует демо-данные CRM и телеметрии;
  - инкрементально переносит клиентов из Postgres (CRM) в ClickHouse;
  - пересчитывает витрину `user_daily_telemetry` (агрегация телеметрии по пользователям и протезам с полями `full_name`, `country`).

- `airflow/requirements.txt`
  Зависимости для Airflow-контейнеров (сам Airflow, Postgres-провайдер, ClickHouse driver и т.п.).

- `.env`
  Настройки Airflow, в т.ч.:
  - `AIRFLOW__CORE__FERNET_KEY` - ключ шифрования, необходимо создать корректный;
  - `AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION=True` - DAG создаётся в состоянии *paused*;
  - `AIRFLOW_CONN_CRM_POSTGRES=postgresql+psycopg2://airflow:airflow@postgres:5432/crm` - connection `crm_postgres` для `PostgresHook`; создается автоматически, в UI Airflow можно не создавать вручную. Креды и адреса должны совпадать с теми, что указаны в `airflow/docker-compose.airflow.yaml`;
  - `AIRFLOW__WEBSERVER__SECRET_KEY=...` - ключ web-сервера Airflow, необходимо создать корректный.

## Запуск локально

Из корня репозитория:

```bash
docker compose -f airflow/docker-compose.airflow.yaml up -d
````

После старта стенда:

1. Открыть UI Airflow: `http://localhost:8081`
   Логин/пароль создаются автоматически: `admin / admin`.

2. В списке DAG’ов найти `bionicpro_reports_dag` и включить (тумблер в состояние **On**).

3. Для проверки работы можно вручную запустить DAG через кнопку **Trigger DAG** в UI.
   Первый запуск:

   * создаст таблицы в ClickHouse,
   * сидирует демо-данные CRM и телеметрии,
   * построит витрину `bionicpro.user_daily_telemetry`.

## Проверка результата

В контейнере ClickHouse:

```bash
docker compose -f airflow/docker-compose.airflow.yaml exec clickhouse \
  clickhouse-client -d bionicpro -q "SELECT * FROM user_daily_telemetry LIMIT 10"
```

Ожидается, что в витрине будут агрегаты телеметрии по пользователям и протезам, а также поля клиента `full_name` и `country` из CRM.
