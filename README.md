# BionicPRO — архитектура и демо-стенд

Репозиторий содержит схемы (C4 / drawio), Docker Compose для приложения (Keycloak, фронт, API отчётов) и отдельный стек для **OLTP → Airflow → ClickHouse** (папка `dags/`).

## Структура

| Каталог | Назначение |
|---------|------------|
| `docker-compose.yaml` | Keycloak, Postgres под Keycloak, **reports-api**, **frontend** |
| `dags/docker-compose.yaml` | Postgres (Airflow + БД `sample`), ClickHouse, Airflow |
| `dags/` | DAG’и Airflow, SQL bootstrap OLTP, init ClickHouse |
| `frontend/` | React + Keycloak, экран отчёта по витрине |
| `reports-api/` | FastAPI: JWT Keycloak + чтение витрины ClickHouse |
| `keycloak/realm-export.json` | Realm `reports-realm`, пользователи и клиенты |
| `diagrams/` | Диаграммы (в т.ч. OLAP / отчётность) |

## Airflow DAG’и (`dags/`)

| DAG ID | Файл | Назначение |
|--------|------|------------|
| **`bionicpro_crm_telemetry_to_clickhouse`** | `dag_bionicpro_etl_to_clickhouse.py` | **ETL в витрину:** `ensure_oltp_schema` — идемпотентный DDL и демо-данные CRM/телеметрии в БД **`sample`** (`sql/oltp_bionicpro_bootstrap.sql`); **`build_mart_for_logical_day`** — чтение OLTP (заказы, телеметрия по дню из `ds`), загрузка в **`bionicpro.mart_user_prosthesis_report`** в ClickHouse по HTTP. Расписание: ежедневно **03:00** UTC (`0 3 * * *`), `catchup=False`. |
| **`csv_to_postgres_dag`** | `dag_sample.py` | **Учебный пример:** создаёт таблицу `sample_table`, генерирует `INSERT` из `data/sample.csv`, пишет в **`sample`**. Запуск **`@once`**. |

Для отчётов на фронте нужен успешный прогон **`bionicpro_crm_telemetry_to_clickhouse`** (хотя бы один раз вручную после поднятия стека).

## Порты (локально)

| Сервис | Порт | Compose |
|--------|------|---------|
| Frontend | 3000 | корень |
| Reports API | 8000 | корень |
| Keycloak | 8090 → 8080 в контейнере | корень |
| Postgres (Keycloak) | 5433 | корень |
| Airflow Web UI | 8080 | `dags/` |
| ClickHouse HTTP | 8123 | `dags/` |
| ClickHouse native | 9000 | `dags/` |

На одной машине **8080** занят Airflow из `dags/`, поэтому Keycloak снаружи проброшен на **8090**.

## Быстрый старт

### 1. OLAP: Postgres + ClickHouse + Airflow

```bash
cd dags
docker-compose up -d
```

Дождитесь healthy-сервисов. При необходимости включите DAG **`bionicpro_crm_telemetry_to_clickhouse`** и выполните задачи **`ensure_oltp_schema`** и **`build_mart_for_logical_day`** (или дождитесь расписания).

### 2. Приложение: Keycloak + API + фронт

Из **корня** репозитория:

```bash
docker-compose up -d --build
```

Переменные `REACT_APP_*` для фронта задаются **build args** в Compose (см. `frontend/Dockerfile`).

### 3. Вход и отчёт

1. Откройте **http://localhost:3000**.
2. Войдите через Keycloak (realm **`reports-realm`**).
3. Нажмите **«Загрузить отчёт»** — запрос к **http://localhost:8000/reports/mart** с Bearer-токеном.

API отфильтровывает витрину по **`sub`** из JWT: пользователь видит только свои строки.

## Демо-пользователи Keycloak

Пароли заданы в `keycloak/realm-export.json`.

| Пользователь | Пароль | Роль |
|--------------|--------|------|
| `prothetic1` | `prothetic123` | `prothetic_user` |
| `prothetic2` | `prothetic123` | `prothetic_user` |
| `user1` | `password123` | `user` |
| `admin1` | `admin123` | `administrator` |

У пользователей **prothetic1** и **prothetic2** в экспорте realm зафиксированы **`id`** (они же попадают в JWT как **`sub`**). Значения должны совпадать с **`crm_customer.keycloak_sub`** в БД **`sample`** (см. `dags/sql/oltp_bionicpro_bootstrap.sql` и `dags/db/02-sample-oltp.sql`).

## Витрина ClickHouse

- База: **`bionicpro`**
- Таблица: **`mart_user_prosthesis_report`**
- Схема: `dags/clickhouse/docker-entrypoint-initdb.d/01-schema.sql`

Проверка с хоста:

```bash
curl -sS -u 'default:bionicpro_local' \
  'http://127.0.0.1:8123/?database=bionicpro&query=SELECT%20count()%20FROM%20mart_user_prosthesis_report'
```

(Пароль по умолчанию в compose для демо: **`bionicpro_local`**.)

## Reports API

- Исходники: `reports-api/main.py`
- Проверка подписи JWT по JWKS Keycloak (внутри Docker: `http://keycloak:8080`)
- ClickHouse по HTTP: по умолчанию **`http://host.docker.internal:8123`** (нужен запущенный ClickHouse из `dags/`)

Переменные окружения см. в корневом `docker-compose.yaml` (сервис **`reports-api`**).
