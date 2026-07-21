# Задание 2. Разработка сервиса отчётов

Пользователь получает отчёт о работе своего протеза. Данные готовятся заранее
ETL-процессом (Airflow) и складываются в OLAP-витрину (ClickHouse); бэкенд
`reports-api` только читает готовую витрину — без тяжёлых вычислений в реалтайме.

## Архитектура

Диаграмма (draw.io): [`docs/Task 2 Reports Diagram.png`](./Task%202%20Reports%20Diagram.png).

Компоненты и порты:

| Компонент     | Технология            | Порт            |
|---------------|-----------------------|-----------------|
| `reports-api` | Go (stdlib)           | 8081            |
| `clickhouse`  | ClickHouse (OLAP)     | 8123 / 9000     |
| `crm-db`      | PostgreSQL (источник) | 5434            |
| `airflow`     | Apache Airflow 2.9    | 8088 (UI)       |

## Соответствие задачам

### Задача 1 — архитектура
Диаграмма `docs/Task 2 Reports Diagram.png`. ETL (Airflow) объединяет телеметрию с
датчиков и данные CRM и формирует витрину в ClickHouse; отчёт по пользователю
отдаёт backend-сервис `reports-api` (тот самый «API» на исходной C4-схеме),
доступный фронтенду через BFF.

### Задача 2 — Airflow DAG
[`airflow/dags/reports_etl_dag.py`](../airflow/dags/reports_etl_dag.py):
- `schedule="@daily"`, `catchup=False`;
- задача `ensure_clickhouse_schema` — идемпотентно создаёт БД и витрину;
- задача `load_report_mart` — извлекает из Postgres агрегат телеметрии
  **в разрезе клиентов** (`GROUP BY client, date`), джойнит с CRM и грузит в
  ClickHouse (`INSERT ... FORMAT JSONEachRow`);
- обрабатывается только завершённый период: `WHERE t.ts < data_interval_end`.

Витрина `reports.user_report_mart`
([DDL](../analytics/clickhouse/init/01_schema.sql)) —
`ReplacingMergeTree ORDER BY (username, report_date)`: денормализована и
упорядочена по пользователю → выборка истории пользователя за один диапазонный
скан по первичному ключу; повторный запуск ETL идемпотентен.

### Задача 3 — бэкенд API
[`reports-api`](../reports-api) (Go): `GET /reports` читает готовую витрину из
ClickHouse по HTTP с серверной привязкой параметров (`{user:String}` — защита от
SQL-инъекций). Тяжёлых вычислений в реалтайме нет — только чтение агрегата.
Поддерживает период `?from=&to=` (YYYY-MM-DD).

### Задача 4 — ограничение доступа
- Требуется валидный access_token Keycloak (RS256, проверка по JWKS) — иначе 401.
- Отчёт всегда строится для `preferred_username` из токена; параметр `user`,
  если передан и не совпадает с владельцем токена → **403**.
- Требуется роль `prothetic_user` (`REQUIRED_ROLE`) → иначе 403.

### Задача 5 — кнопка в UI
[`frontend/src/components/ReportPage.tsx`](../frontend/src/components/ReportPage.tsx):
кнопка «Get Report» + поля периода вызывают `GET /api/reports` через BFF
(`credentials: 'include'`), отображают таблицу по дням, сводку и границу
обработанных данных; есть выгрузка отчёта в файл.

## Проверки перед сдачей (все выполнены на живом стенде)

| Требование | Как проверено |
|---|---|
| UI вызывает API генерации | Кнопка → `GET /api/reports` (BFF → reports-api) |
| Нельзя без аутентификации | `/reports` без/с мусорным токеном → **401** |
| Только собственный отчёт | реальный токен `prothetic1`: свой отчёт → 200; `?user=prothetic2` → **403** |
| Генерация из OLAP | reports-api читает `reports.user_report_mart` из ClickHouse |
| Только обработанный период | `latest_processed_date=max(report_date)`; запрос за его пределы → отчёт + `notice` |

Дополнительно (unit + интеграционно):
- `reports-api`: `go test ./...` — JWT (валидный/подделанный/просроченный/чужой
  issuer/не-RS256) и контроль доступа (401/403/200/notice).
- ETL data-path: агрегат из `crm-db` → `INSERT ... FORMAT JSONEachRow` → ClickHouse,
  чтение витрины запросом `reports-api`; повторный запуск идемпотентен (65 строк).
- DAG импортируется в Airflow без ошибок (`DagBag import_errors = {}`).

## Артефакты сдачи

| Требование | Файл |
|---|---|
| Диаграмма (draw.io) | `docs/Task 2 Reports Diagram.png` |
| Код Airflow (отдельная папка) | `airflow/dags/reports_etl_dag.py` |
| API-имплементация сбора из ClickHouse | `reports-api/` |
