# BionicPRO

## Задания

- **Задание 1. Повышение безопасности системы** — реализовано.
  Разбор и инструкция запуска: [`docs/ASSIGNMENT-1.md`](./docs/ASSIGNMENT-1.md).
  - BFF-сервис `bionicpro-auth` (Go): Authorization Code + PKCE, серверное
    хранение токенов, session-cookie, ротация сессии.
  - Keycloak: PKCE, `access_token` ≤ 2 мин, LDAP-федерация, обязательный OTP,
    Identity Brokering (Яндекс ID).
  - Фронтенд переведён на работу с сессиями (без токенов).
- **Задание 2. Разработка сервиса отчётов** — реализовано.
  Разбор: [`docs/ASSIGNMENT-2.md`](./docs/ASSIGNMENT-2.md).
  - ETL на Airflow (`reports_etl`): CRM + телеметрия → витрина ClickHouse.
  - `reports-api` (Go): `GET /reports` из OLAP, доступ только к своему отчёту.
  - Кнопка отчёта в UI (через BFF).
- **Задание 3. Снижение нагрузки на базу данных** — реализовано.
  Разбор: [`docs/ASSIGNMENT-3.md`](./docs/ASSIGNMENT-3.md).
  - Кэш готовых отчётов в S3 (Minio), раздача через CDN (Nginx `proxy_cache`).
  - Cache-aside в `reports-api`: на попадании в кеш запрос в OLAP не идёт;
    ключ версионируется watermark'ом ETL (авто-инвалидация).
- **Задание 4. Повышение оперативности и стабильности работы CRM** — реализовано.
  Разбор: [`docs/ASSIGNMENT-4.md`](./docs/ASSIGNMENT-4.md).
  - CDC: Debezium (CRM Postgres) → Kafka → ClickHouse `KafkaEngine`.
  - Витрина через `MaterializedView`; `reports-api` переведён на неё.
  - Массовые выгрузки ушли из OLTP CRM в потоковую репликацию.

| Сервис          | URL / порт                          |
|-----------------|-------------------------------------|
| Frontend (SPA)  | http://localhost:3000               |
| bionicpro-auth  | http://localhost:8000               |
| Keycloak        | http://localhost:8080 (admin/admin) |
| OpenLDAP        | ldap://localhost:389                |
| reports-api     | http://localhost:8081               |
| ClickHouse      | http://localhost:8123               |
| Airflow UI      | http://localhost:8088               |
| crm-db          | postgres://localhost:5434           |
| CDN (Nginx)     | http://localhost:8090               |
| MinIO console   | http://localhost:9001 (minioadmin)  |
| Kafka Connect   | http://localhost:8083               |

## Структура репозитория

```
bionicpro-auth/   BFF-сервис аутентификации (Go)
reports-api/      сервис отчётов (Go): /reports из ClickHouse
airflow/          DAG ETL (CRM+телеметрия → витрина ClickHouse)
analytics/        seed источника (crm), схема/пользователь ClickHouse, CDC-скрипты (KafkaEngine+MV)
debezium/         конфиг Debezium-коннектора (CRM CDC)
nginx/            конфиг CDN (reverse proxy к MinIO + proxy_cache)
frontend/         React SPA (сессии BFF + отчёт)
keycloak/         realm-export.json (импорт) + keycloak-results-export.json (экспорт)
ldap/             config.ldif — пользователи и роли представительства
docs/             диаграммы (draw.io) и разбор заданий
docker-compose.yaml
```
