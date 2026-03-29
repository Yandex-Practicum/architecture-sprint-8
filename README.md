## BionicPRO Security And Reporting Upgrade

Репозиторий объединяет результат заданий спринта:

- `bionicpro-auth` реализует OIDC Authorization Code + PKCE, серверную сессию и работу с Keycloak;
- `reports-api` сначала ищет версионированный отчёт в MinIO, а при cache miss читает OLAP, публикует объект в S3 и возвращает CDN-ссылку;
- `Apache Airflow` по расписанию агрегирует telemetry и загружает только staging-слой в ClickHouse;
- `Debezium + Kafka + Kafka Connect` реплицируют CRM-изменения в ClickHouse без массовых выгрузок из OLTP;
- `ClickHouse` собирает финальную витрину `user_daily_reports_cdc` через `KafkaEngine` и `MaterializedView`;
- UI работает только через `/api`, использует cookie-сессию и позволяет запросить отчёт только за уже обработанный период;
- `frontend` Nginx эмулирует CDN: проксирует `/cdn/*` в MinIO и кеширует статические объекты;
- добавлены draw.io и PlantUML диаграммы для security- и reporting-контуров.

## Диаграммы

- `BionicPRO_C4_security.drawio.xml`
- `BionicPRO_C4_reporting.drawio.xml`

## Состав

- `frontend` - React SPA за HTTPS на `https://localhost:3000`.
- `bionicpro-auth` - login, callback, session, logout, internal session validation.
- `reports-api` - API `/reports` и `/reports/availability`, управляет S3-объектами отчётов и читает ClickHouse только при cache miss.
- `airflow` - DAG `bionicpro_reporting_etl`, обновляет telemetry staging и metadata окна по расписанию.
- `crm-db` - PostgreSQL с клиентами, протезами и сервисной информацией.
- `telemetry-db` - PostgreSQL с телеметрией по протезам.
- `kafka` - транспорт для CDC-событий Debezium.
- `kafka-connect` - runtime для Debezium Postgres connector.
- `debezium-register` - one-shot сервис, который регистрирует connector из `debezium/crm-postgres-connector.json`.
- `clickhouse` - OLAP БД с CRM CDC-слоем, telemetry staging, витриной `user_daily_reports_cdc` и metadata processed window.
- `minio` - S3-compatible object storage для готовых отчётов.
- `keycloak` - realm, MFA, LDAP federation, Yandex broker.
- `ldap` - OpenLDAP с пользователями представительства.

## Запуск

1. При необходимости создайте `.env` на основе `.env.example`.
2. Поднимите стек:

```bash
docker compose up --build
```

3. Откройте:

- `https://localhost:3000` - UI
- `http://localhost:8080` - Keycloak
- `http://localhost:8081` - Airflow
- `http://localhost:8083` - Kafka Connect REST
- `http://localhost:9094` - Kafka bootstrap
- `http://localhost:9001` - MinIO S3 API
- `http://localhost:9002` - MinIO Console

Фронтенд использует self-signed сертификат, поэтому браузер попросит подтвердить исключение.

## CDC И Отчёты

- DAG: `bionicpro_reporting_etl`
- Расписание: каждые 15 минут
- Debezium connector config: `debezium/crm-postgres-connector.json`
- ClickHouse init schema: `clickhouse/init/01_reporting_cdc.sql`
- Финальная витрина: `reporting.user_daily_reports_cdc`
- Metadata по доступному периоду: `reporting.reporting_load_windows`

CRM больше не читается массовыми запросами из ETL. Изменения по `customers` и `prostheses` считывает Debezium, отправляет их в Kafka, а ClickHouse забирает события через `KafkaEngine` и обновляет текущий CRM-слой. Airflow читает только `telemetry-db`, вставляет агрегаты в `reporting.telemetry_daily_rollups`, а `MaterializedView` внутри ClickHouse автоматически собирает финальную витрину `reporting.user_daily_reports_cdc`.

UI сначала запрашивает `/api/reports/availability`, получает доступный обработанный диапазон и только потом вызывает `/api/reports`. Этот эндпоинт возвращает JSON с CDN-ссылкой на готовый объект.

Логика `/api/reports`:

- по `username + period + format + loadedAt` строится детерминированный object key;
- сервис сначала делает `HEAD` в MinIO;
- при cache hit возвращает уже готовую CDN-ссылку без повторного чтения OLAP;
- при cache miss читает ClickHouse, собирает файл, загружает его в MinIO и только потом возвращает CDN-ссылку.

CDN cache invalidation сделан через versioned URL: в object key включён `loadedAt` из `reporting.reporting_load_windows`. После нового ETL меняется путь объекта, поэтому старый CDN cache не используется без явного purge.

Структура хранения в S3:

```text
reports/<dataset>/v=<loadedAt>/u=<hmac(username)>/<date_from>_<date_to>.<format>
```

Это даёт быстрый deterministic lookup и не светит username в открытом URL.

Если нужен немедленный прогон DAG после старта, можно вручную триггернуть его:

```bash
docker compose exec airflow airflow dags trigger bionicpro_reporting_etl
```

`airflow standalone` создаёт пользователя `admin`, а пароль пишет в логи контейнера:

```bash
docker compose logs airflow
```

Локальные параметры object storage и CDN можно переопределить через `.env`:

- `S3_ACCESS_KEY`
- `S3_SECRET_KEY`
- `S3_BUCKET`
- `CDN_BASE_URL`
- `REPORT_OBJECT_PREFIX`
- `REPORT_OBJECT_KEY_SECRET`

## Тестовые Пользователи

Локальные пользователи Keycloak:

- `prothetic1 / prothetic123`
- `prothetic2 / prothetic123`
- `prothetic3 / prothetic123`
- `admin1 / admin123`
- `user1 / password123`
- `user2 / password123`

LDAP пользователи:

- `john.doe / password`
- `jane.smith / password`
- `alex.johnson / password`

Для всех локальных пользователей включено обязательное действие `CONFIGURE_TOTP`, поэтому на первом входе потребуется привязать OTP-приложение.

## Yandex ID

При старте Keycloak рендерит импорт realm из [keycloak-results-export.json](keycloak/keycloak-results-export.json) с учетом env-переменных:

- `KEYCLOAK_PUBLIC_BASE_URL`
- `FRONTEND_BASE_URL`
- `AUTH_EXTERNAL_BASE_URL`
- `YANDEX_CLIENT_ID`
- `YANDEX_CLIENT_SECRET`
- `YANDEX_DEFAULT_SCOPE`

Для провайдера `yandex` заранее настроены claim mappings из `userInfo` Yandex:

- `id -> userIDClaim`
- `login -> userNameClaim`
- `default_email -> emailClaim`
- `real_name -> fullNameClaim`
- `first_name -> givenNameClaim`
- `last_name -> familyNameClaim`

После входа через Yandex backend `bionicpro-auth` получает внешний токен из broker session Keycloak, запрашивает профиль у `login.yandex.ru/info` и сохраняет его в `Profile DB`.

Для реального Yandex ID `KEYCLOAK_PUBLIC_BASE_URL` должен указывать на публичный `https`-адрес Keycloak, а `Redirect URI` в приложении Yandex должен совпадать с:

```text
<KEYCLOAK_PUBLIC_BASE_URL>/realms/reports-realm/broker/yandex/endpoint
```

Если realm уже существует в текущей Keycloak DB, импорт будет пропущен. В этом случае новые mappers и broker-настройки нужно применить вручную или пересоздать БД Keycloak.
