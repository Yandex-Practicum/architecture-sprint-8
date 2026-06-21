# BionicPRO

## Что сделано в задании 1

Фронтенд больше не работает с Keycloak напрямую и не получает `access_token` или `refresh_token`.
Вход начинается через `bionicpro-auth`, а в браузер возвращается только session cookie

`bionicpro-auth` делает следующее:

- запускает OAuth 2.0 Authorization Code + PKCE
- сам обменивает `code` на токены Keycloak
- хранит `access_token` и `refresh_token` в памяти процесса
- привязывает токены к server-side session id
- отдаёт фронтенду cookie `bp_session`
- обновляет `access_token` через `refresh_token`
- ротирует session id при успешной проверке `/auth/me`

В Keycloak realm добавлены:

- `accessTokenLifespan: 120`, access token живёт 2 минуты
- PKCE S256 для `reports-frontend` и `bionicpro-auth`
- confidential client `bionicpro-auth`
- OpenLDAP federation и role mapper
- обязательная настройка OTP через `CONFIGURE_TOTP`
- включенный Identity Provider `yandex-id` с consent prompt и scope `login:email login:info`

При успешном OAuth callback `bionicpro-auth` сохраняет импортированный профиль пользователя в ClickHouse-таблицу `identity_profiles`.
Для Yandex ID используются переменные окружения `YANDEX_CLIENT_ID` и `YANDEX_CLIENT_SECRET`.

## Запуск

```bash
docker compose up --build
```

Для проверки реального входа через Yandex ID перед запуском надо передать OAuth credentials приложения:

```bash
YANDEX_CLIENT_ID=<client-id> YANDEX_CLIENT_SECRET=<client-secret> docker compose up --build
```

Если credentials не переданы, `yandex-id` остается включенным, но получает placeholder values из `docker-compose.yaml`; реальный внешний вход через Yandex ID в таком режиме не пройдет.

Сервисы:

- frontend: `http://127.0.0.1:8002`
- bionicpro-auth: `http://127.0.0.1:8000`
- reports-api: `http://127.0.0.1:8001`
- Keycloak: `http://127.0.0.1:8003`
- OpenLDAP: `ldap://localhost:389`
- Airflow UI: `http://127.0.0.1:8081`, логин и пароль `admin` / `admin`
- ClickHouse HTTP: `http://127.0.0.1:8123`
- Minio API: `http://127.0.0.1:9002`
- Minio Console: `http://127.0.0.1:9001`, логин и пароль `minioadmin` / `minioadmin`
- CDN proxy: `http://127.0.0.1:8082`
- Kafka: `localhost:9092`
- Kafka Connect: `http://127.0.0.1:8083`

Для локального запуска в `docker-compose.yaml` выставлено `AUTH_COOKIE_SECURE=false`, потому что проект поднимается по HTTP.
В боевом окружении этот параметр надо убрать или выставить `true`, тогда cookie будет отдаваться с флагом `Secure`

Важно: `--import-realm` не перезаписывает уже существующий realm в Keycloak.
Если `postgres-keycloak-data` уже создан, изменения из `keycloak/realm-export.json` могут не примениться автоматически.
Для чистой проверки нужен свежий volume Keycloak/PostgreSQL или ручной импорт `keycloak/keycloak-results-export.json`.

## Ручные проверки

MFA надо проверить руками: первый вход пользователя должен отправить на настройку OTP в Google Authenticator или FreeOTP

Проверенный сценарий:

- OTP пройден, после этого пользователь `prothetic1` попадает в UI.
- Первый запрос отчета возвращает `cacheStatus: miss`.
- Повторный запрос отчета возвращает `cacheStatus: hit`.
- CDN URL открывает JSON-отчет.

Yandex ID включен как OIDC provider. Полный внешний OAuth-сценарий можно пройти только с реальными `YANDEX_CLIENT_ID` и `YANDEX_CLIENT_SECRET`

Файл результата для сдачи лежит в `keycloak/keycloak-results-export.json`

Диаграммы:

- `diagrams/bionicpro-sso-c4.drawio`, C4 для задания 1: SSO, Keycloak, LDAP/Yandex ID, `bionicpro-auth`, server-side tokens и session cookie.
- `diagrams/bionicpro-reporting-data-c4.drawio`, схема данных для заданий 2-4: Airflow ETL, CDC через Debezium/Kafka/ClickHouse, `report_mart_cdc`, Minio/S3 и Nginx CDN.

## Что сделано в задании 2

Добавлен отдельный сервис `reports-api` с endpoint `GET /reports`.
Он не получает bearer token от фронтенда, а проверяет session cookie через внутренний endpoint `bionicpro-auth`

Доступ к отчёту ограничен текущим пользователем: API берёт `username` из server-side сессии и ищет в ClickHouse только строку этого пользователя.
Чужой `user_id` с клиента не принимается, поэтому пользователь не может запросить отчёт другого пациента через параметр запроса

Добавлен ClickHouse:

- `clickhouse/init/001_reports.sql`, базовые таблицы и готовая витрина `report_mart`
- `crm_customers`, staging-данные CRM
- `prosthesis_telemetry`, staging-данные телеметрии
- `report_mart`, готовая OLAP-витрина Airflow ETL
- `identity_profiles`, таблица импортированных профилей Identity Provider

Добавлен Airflow DAG:

- `airflow/dags/bionicpro_reports_dag.py`
- расписание: каждый час
- источник CRM: `airflow/dags/data/crm_customers.csv`
- источник телеметрии: `airflow/dags/data/prosthesis_telemetry.csv`
- результат: агрегированные отчёты в ClickHouse `report_mart`

Airflow UI доступен на `http://localhost:8081`, логин и пароль `admin` / `admin`

`report_mart` используется как базовая ETL-витрина.
Текущий endpoint `/reports` читает оперативную CDC-витрину `report_mart_cdc`.

## Что сделано в задании 3

Добавлено S3-compatible хранилище Minio и CDN-эмуляция через Nginx

Сервисы:

- Minio API: `http://localhost:9002`
- Minio Console: `http://localhost:9001`, логин и пароль `minioadmin` / `minioadmin`
- CDN proxy: `http://localhost:8082`

`reports-api` теперь работает так:

- проверяет сессию пользователя через `bionicpro-auth`
- получает готовый отчёт из ClickHouse `report_mart_cdc`
- строит ключ S3 в формате `{user_id}/{prosthesis_id}/{period}.json`
- проверяет, есть ли такой отчёт в S3
- если отчёт уже есть, возвращает CDN-ссылку и `cacheStatus: hit`
- если отчёта нет, сохраняет JSON в Minio и возвращает CDN-ссылку с `cacheStatus: miss`

Nginx CDN конфиг лежит в `nginx/nginx.conf`.
Он проксирует `/reports/...` в Minio bucket `bionicpro-reports` и кеширует успешные ответы на 1 час

Обновление кеша завязано на ключ отчёта. Когда Airflow подготовит витрину за новый период, `reports-api` сформирует новый S3 key, поэтому CDN начнёт отдавать новый объект без ручной инвалидации старого кеша

## Что сделано в задании 4

Добавлен CDC-контур для оперативного обновления CRM-данных в ClickHouse:

- `crm-db`, отдельная PostgreSQL CRM база с включенным `wal_level=logical`
- `zookeeper` и `kafka`
- `kafka-connect` на базе Debezium Connect
- `debezium/crm-postgres-connector.json`, connector для таблицы `public.crm_customers`
- `clickhouse/init/002_crm_cdc.sql`, прием Debezium-событий через `KafkaEngine`
- `crm_customers_cdc_raw`, raw-таблица событий Debezium
- `crm_customers_cdc`, нормализованная CRM-таблица из CDC-потока
- `report_mart_cdc`, отчетная витрина, которая объединяет CRM CDC и телеметрию через `MaterializedView`

Debezium пишет изменения CRM в Kafka topic `crm.public.crm_customers`.
ClickHouse читает этот topic через `KafkaEngine`, сохраняет raw-события и перекладывает их в нормализованную таблицу через materialized view.

Регистрация Debezium connector:

```bash
curl -X POST http://localhost:8083/connectors \
  -H 'Content-Type: application/json' \
  --data @debezium/crm-postgres-connector.json
```

Если connector уже существует:

```bash
curl http://localhost:8083/connectors/crm-postgres-connector/status
```

Проверка CDC:

```bash
docker compose exec -T crm-db psql -U crm_user -d crm \
  -c "UPDATE public.crm_customers SET user_name = 'Alex CDC' WHERE user_id = 'prothetic1';"

docker compose exec -T clickhouse clickhouse-client \
  --query "SELECT user_id, user_name, prosthesis_id, op FROM bionicpro.crm_customers_cdc FINAL ORDER BY event_ts DESC LIMIT 5"

docker compose exec -T clickhouse clickhouse-client \
  --query "SELECT user_id, user_name, prosthesis_id, events_count FROM bionicpro.report_mart_cdc FINAL ORDER BY user_id"
```

`reports-api` читает отчеты из `report_mart_cdc`.
`report_mart` из задания 2 остается базовой Airflow-витриной и контрольной таблицей для проверки ETL.
Новая `report_mart_cdc` используется API, чтобы изменения CRM попадали в отчеты без ожидания следующего Airflow-запуска.

## Автоматические проверки

Базовая проверка конфигурации:

```bash
docker compose config --quiet
docker compose ps
```

Проверка health endpoint и инфраструктуры:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8001/health
curl http://127.0.0.1:8082/health
curl http://127.0.0.1:8083/connectors/crm-postgres-connector/status
docker compose exec -T clickhouse clickhouse-client --query "SELECT 1"
docker compose exec -T kafka kafka-topics --bootstrap-server kafka:29092 --list
```

Проверка Airflow и основной витрины отчетов:

```bash
docker compose exec -T airflow airflow dags list-import-errors
docker compose exec -T airflow airflow dags test bionicpro_reports_etl 2026-06-20
docker compose exec -T clickhouse clickhouse-client \
  --query "SELECT user_id, prosthesis_id, events_count, avg_reaction_ms FROM bionicpro.report_mart ORDER BY user_id"
```

Проверка таблицы импортированных профилей:

```bash
docker compose exec -T clickhouse clickhouse-client \
  --query "SELECT subject, username, email, identity_provider FROM bionicpro.identity_profiles ORDER BY saved_at DESC LIMIT 5"
```

Проверка CDC-витрины:

```bash
docker compose exec -T crm-db psql -U crm_user -d crm \
  -c "UPDATE public.crm_customers SET user_name = 'Alex CDC Check', updated_at = now() WHERE user_id = 'prothetic1' AND prosthesis_id = 'prosthesis-1001';"

docker compose exec -T clickhouse clickhouse-client \
  --query "SELECT user_id, user_name, prosthesis_id, op FROM bionicpro.crm_customers_cdc FINAL WHERE user_id = 'prothetic1'"

docker compose exec -T clickhouse clickhouse-client \
  --query "SELECT user_id, user_name, prosthesis_id, events_count FROM bionicpro.report_mart_cdc FINAL WHERE user_id = 'prothetic1'"
```
