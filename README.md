# BionicPRO — Проектная работа (Спринт 9)

## Структура проекта

```
architecture-bionicpro/
├── docker-compose.yaml                   Keycloak, OpenLDAP, Frontend, MinIO, Nginx CDN, Kafka, Debezium
├── diagrams/
│   ├── c4_container.puml                 C4-диаграмма: безопасность (Задание 1)
│   └── c4_reports.puml                   C4-диаграмма: сервис отчётов (Задание 2)
├── backend/
│   ├── app.py                            Reports API (GET /reports, S3/CDN)
│   ├── auth_service.py                   bionicpro-auth — BFF-сервис аутентификации
│   ├── requirements.txt                  Python-зависимости
│   └── start.sh                          Скрипт запуска uvicorn
├── frontend/
│   └── src/
│       ├── App.tsx                        PKCE flow + session cookie
│       └── components/ReportPage.tsx      Кнопка отчёта + таблица результатов
├── keycloak/
│   ├── realm-export.json                 Realm с PKCE, LDAP, MFA, Yandex IdP
│   └── keycloak-results-export.json      Финальный экспорт realm
├── ldap/
│   └── config.ldif                       LDIF: пользователи и роли OpenLDAP
├── airflow/
│   ├── docker-compose.airflow.yaml       ClickHouse + Postgres (CRM) + Airflow
│   ├── .env.example                      Шаблон переменных окружения
│   ├── requirements.txt                  Зависимости Airflow
│   └── dags/bionicpro_etl_dag.py         DAG: CRM → ClickHouse → витрина
├── nginx/
│   └── nginx-cdn.conf                    Nginx reverse proxy + кеширование
├── debezium/
│   └── register-connector.json           Конфигурация Debezium Postgres Connector
└── clickhouse/
    └── init-scripts/
        ├── create_kafka_engine.sql        KafkaEngine для приёма CDC-событий
        └── create_materialized_view.sql   MaterializedView для витрины
```

---

## Задание 1. Повышение безопасности системы

### Задача 1. C4-диаграмма архитектуры

**Файл:** `diagrams/c4_container.puml`

C4 Container-диаграмма в PlantUML отражает:
- **bionicpro-auth (BFF)** — новый сервис между фронтендом и Keycloak, управляющий сессиями.
- **Session Store** — хранилище привязки session_id к access/refresh токенам.
- **OpenLDAP** — внешний каталог пользователей представительства в другой стране.
- **Yandex ID** — внешний Identity Provider через Identity Brokering.
- Фронтенд взаимодействует с BFF через session cookie (HttpOnly, Secure), токены не попадают на клиент.

### Задача 2. PKCE flow

**Файл:** `keycloak/realm-export.json` — клиент `reports-frontend`

Настройки клиента:
- `"publicClient": true` — публичный клиент без client_secret.
- `"attributes": { "pkce.code.challenge.method": "S256" }` — обязательный PKCE.
- `"directAccessGrantsEnabled": false` — Resource Owner Password Grant отключён.
- `"standardFlowEnabled": true` — Authorization Code Flow включён.

Фронтенд (`frontend/src/App.tsx`) генерирует `code_verifier` и `code_challenge` (S256) и передаёт их в authorization request к Keycloak.

### Задача 3. bionicpro-auth (BFF-сервис)

**Файл:** `backend/auth_service.py`

Сервис на Python (FastAPI) реализует:

| Эндпоинт | Описание |
|---|---|
| `POST /auth/callback` | Принимает `{ code, code_verifier, redirect_uri }` от фронта, обменивает code на токены через Keycloak token endpoint. Создаёт серверную сессию, отдаёт HttpOnly cookie. |
| `POST /auth/logout` | Инвалидирует сессию на сервере, вызывает Keycloak logout endpoint, удаляет cookie. |
| `GET /auth/session` | Проверяет валидность сессии по cookie. Выполняет ротацию session_id. |
| `GET /auth/userinfo` | Проксирует запрос к Keycloak userinfo, используя серверный access_token. |

Ключевые механизмы:
- **Session store** — in-memory dict (`sessions: dict[str, dict]`). Привязка session_id к access_token и refresh_token.
- **HttpOnly / Secure cookie** — `SESSION_ID`, `SameSite=Lax`, `max_age=1800`.
- **Auto-refresh** — если access_token истёк (проверка `exp` из JWT payload), сервис обновляет его через refresh_token (`_refresh_access_token`).
- **Ротация сессии** — функция `rotate_session()` при каждом запросе к защищённому ресурсу генерирует новый session_id, перепривязывает токены и обновляет cookie. Предотвращает session fixation.
- **access_token TTL** — 120 секунд (`"accessTokenLifespan": 120` в realm). Время жизни сессии (1800 сек) больше TTL токена.

### Задача 4. Обновление фронтенда

**Файлы:** `frontend/src/App.tsx`, `frontend/src/components/ReportPage.tsx`

Изменения по сравнению с исходным кодом:
- Удалена прямая работа с `keycloak-js` / `@react-keycloak/web` для получения токенов.
- Логин: фронтенд генерирует PKCE `code_verifier`/`code_challenge`, редиректит на Keycloak. После редиректа обратно — отправляет code на `POST /auth/callback` через BFF.
- Все API-запросы используют `credentials: 'include'` (session cookie) вместо `Authorization: Bearer`.
- `ReportPage` отображает отчёт в таблице с обработкой ошибок (401, 403, 404).

### Задача 5. LDAP

**Файлы:** `ldap/config.ldif`, `docker-compose.yaml`, `keycloak/realm-export.json`

- **OpenLDAP** развёрнут в `docker-compose.yaml` (образ `osixia/openldap:1.5.0`, порт 389).
- LDIF содержит OU `People` и `Groups`, пользователей (john.doe, jane.smith, alex) и группы-роли (user, prothetic_user).
- В realm настроен **User Federation** типа `ldap` (`components.org.keycloak.storage.UserStorageProvider`):
  - `connectionUrl: ldap://openldap:389`
  - `bindDn: cn=admin,dc=example,dc=com`
  - `usersDn: ou=People,dc=example,dc=com`
  - Маппинг атрибутов: uid → username, mail → email, cn → firstName, sn → lastName.
  - **Role mapper**: группы из `ou=Groups` синхронизируются как realm-роли Keycloak.

### Задача 6. MFA (OTP)

**Файл:** `keycloak/realm-export.json`

- OTP-политика: `"otpPolicyType": "totp"`, `"otpPolicyAlgorithm": "HmacSHA1"`, 6 цифр, период 30 сек.
- Кастомный authentication flow `browser-with-otp`:
  - `auth-username-password-form` — REQUIRED
  - `auth-otp-form` — REQUIRED
- `"browserFlow": "browser-with-otp"` — назначен как основной flow realm.
- Все пользователи имеют `"requiredActions": ["CONFIGURE_TOTP"]` — при первом входе обязательная настройка OTP (Google Authenticator / FreeOTP).

### Задача 7. OAuth 2.0 от Яндекс ID

**Файл:** `keycloak/realm-export.json`

- Identity Provider типа `oidc` с alias `yandex`:
  - `authorizationUrl: https://oauth.yandex.ru/authorize`
  - `tokenUrl: https://oauth.yandex.ru/token`
  - `userInfoUrl: https://login.yandex.ru/info`
  - `defaultScope: login:info login:email login:avatar`
  - `prompt: consent` — после аутентификации запрашивается разрешение пользователя.
  - `storeToken: true` — токен сохраняется для запроса данных профиля.
  - `firstBrokerLoginFlowAlias: "first broker login"` — при первом входе спрашивает consent.
- Identity Provider Mappers:
  - `default_email` → `email`
  - `first_name` → `firstName`
  - `last_name` → `lastName`
- Client ID / Secret — placeholder-значения (`YANDEX_CLIENT_ID_PLACEHOLDER`), заменяются при деплое.

### Финальный экспорт

**Файл:** `keycloak/keycloak-results-export.json` — копия realm-export.json со всеми настройками.

---

## Задание 2. Разработка сервиса отчётов

### Задача 1. C4-диаграмма архитектуры отчётов

**Файл:** `diagrams/c4_reports.puml`

C4 Container-диаграмма показывает поток данных:
- CRM DB (Postgres) → Apache Airflow (ETL) → ClickHouse (OLAP витрина `user_daily_telemetry`)
- ClickHouse → Reports API → S3 (кеш) → CDN (Nginx) → Frontend
- Chip Program → Основная БД (телеметрия) → Airflow

### Задача 2. Airflow DAG

**Файлы:** `airflow/dags/bionicpro_etl_dag.py`, `airflow/docker-compose.airflow.yaml`

DAG `bionicpro_reports_dag`:
- **Расписание:** `15 * * * *` (каждый час, минута 15), `catchup=False`.
- **Pipeline:** `ensure_schema` → `ensure_crm_db_and_table` → `seed_crm` → `extract_load_crm` → `seed_telemetry` → `refresh_mart` → `invalidate_s3_cache` → `done_marker`

| Task | Описание |
|---|---|
| `ensure_schema` | Создаёт БД `bionicpro` и таблицы в ClickHouse: `crm_customers`, `telemetry_events`, `user_daily_telemetry` |
| `ensure_crm_db_and_table` | Создаёт БД `crm` и таблицу `customers` в Postgres |
| `seed_crm` | Заполняет CRM тестовыми данными (3 пользователя: c1, c2, c3). Однократно через Airflow Variable |
| `extract_load_crm` | Инкрементальная выгрузка из CRM в ClickHouse через watermark (`CRM_WATERMARK`) |
| `seed_telemetry` | Генерирует тестовые данные телеметрии (90 дней, 20-100 событий/день на пользователя) |
| `refresh_mart` | Агрегирует данные в витрину `user_daily_telemetry`: total_events, avg_signal_strength, active_hours, movement_count в разрезе customer_id + report_date |
| `invalidate_s3_cache` | Удаляет кешированные отчёты `reports/*/latest.json` из MinIO (S3), чтобы при следующем запросе API сгенерировал отчёт из обновлённых данных |
| `done_marker` | Записывает метку времени последнего успешного ETL в таблицу `etl_metadata` в ClickHouse |

Стек: ClickHouse 24.8, Postgres 15, Apache Airflow 2.9.3.

### Задача 3. Backend API /reports

**Файл:** `backend/app.py`

Эндпоинт `GET /reports`:
1. Проверяет сессию (session cookie) через `get_current_session` из auth_service.
2. Выполняет ротацию session_id.
3. Извлекает `preferred_username` из access_token, проверяет роль `prothetic_user`.
4. Маппит username → customer_id (`prothetic1` → `c1`, `prothetic2` → `c2`, `prothetic3` → `c3`).
5. Запрашивает данные из ClickHouse витрины `bionicpro.user_report_mv` (или `user_daily_telemetry` через env `REPORT_TABLE`) по customer_id.
6. Возвращает JSON с массивом `days` (дневная телеметрия).
7. Если данных нет — 404 с сообщением о том, что данные ещё не обработаны Airflow.

### Задача 4. Ограничение доступа

Реализовано в `backend/app.py`:
- Без session cookie → HTTP 401.
- Без роли `prothetic_user` → HTTP 403.
- Пользователь получает **только свои данные**: маппинг `username → customer_id` исключает доступ к чужим отчётам.

### Задача 5. Кнопка в UI

**Файл:** `frontend/src/components/ReportPage.tsx`

- Кнопка "Download Report" вызывает `GET /reports` с `credentials: 'include'`.
- Результат отображается в таблице (Date, Events, Avg Signal, Active Hours, Movements).
- Обработка ошибок: 401 (сессия истекла), 403 (нет доступа), 404 (нет данных).
- Раскрываемый блок "Raw JSON" с полным ответом API.

---

## Задание 3. Снижение нагрузки на базу данных

### 1. S3 (MinIO)

**Файл:** `docker-compose.yaml` — сервисы `minio`, `minio-init`

- MinIO (S3-совместимое хранилище), порты: 9002 (API), 9001 (console).
- `minio-init` автоматически создаёт bucket `reports` и устанавливает публичный доступ на чтение.
- Логика в `backend/app.py`: при запросе отчёта сервис сначала проверяет наличие в S3 (`reports/{customer_id}/latest.json`). Если есть — возвращает `source: "cache"` и CDN-ссылку. Если нет — генерирует из ClickHouse, сохраняет в S3 и возвращает `source: "generated"`.

### 2. Nginx CDN (reverse proxy)

**Файлы:** `nginx/nginx-cdn.conf`, `docker-compose.yaml` — сервис `nginx-cdn`

- Nginx работает как reverse proxy к MinIO на порту 8888.
- `proxy_cache` включён: зона `s3_cache`, 10 MB ключей, max 1 GB, инактивность 60 мин.
- `proxy_cache_valid 200 30m` — кеширование успешных ответов на 30 минут.
- Заголовок `X-Cache-Status` позволяет проверить попадание в кеш (HIT/MISS).
- `Cache-Control: public, max-age=1800`.
- `Access-Control-Allow-Origin: http://localhost:3000` — ограниченный CORS.

### 3. Механизм обновления кеша

- Структура ключей S3: `reports/{customer_id}/latest.json` — один файл на пользователя.
- Airflow DAG содержит задачу `invalidate_s3_cache`, которая после `refresh_mart` удаляет все `reports/*/latest.json` из MinIO через boto3. При следующем запросе API сгенерирует отчёт заново из обновлённой витрины.
- CDN-кеш (Nginx) истекает через 30 минут (`proxy_cache_valid`), что соответствует периодичности ETL (1 час).
- API также записывает метку времени последнего ETL-прогона (`last_etl_run`) из таблицы `etl_metadata` в ClickHouse и возвращает её в ответе `/reports`.

---

## Задание 4. Повышение оперативности и стабильности работы CRM

### 1. Kafka + Kafka Connect (Debezium)

**Файл:** `docker-compose.yaml` — сервисы `zookeeper`, `kafka`, `kafka-connect`

- Zookeeper + Kafka (Confluent 7.5.0) — брокер сообщений.
- Kafka Connect с плагином Debezium (образ `debezium/connect:2.4`), порт 8083.
- Регистрация коннектора:
  ```bash
  curl -X POST http://localhost:8083/connectors \
    -H "Content-Type: application/json" \
    -d @debezium/register-connector.json
  ```

### 2. Debezium Connector

**Файл:** `debezium/register-connector.json`

- Класс: `io.debezium.connector.postgresql.PostgresConnector`
- Подключение к CRM Postgres (`crm` database).
- Отслеживание: `public.customers`.
- Топик Kafka: `crm.public.customers` (формируется из `topic.prefix` + имя таблицы).
- Плагин: `pgoutput`, формат: JSON без схемы.
- Snapshot mode: `initial` — при первом запуске выгружает все существующие данные.

### 3. ClickHouse KafkaEngine

**Файл:** `clickhouse/init-scripts/create_kafka_engine.sql`

- Таблица `bionicpro.crm_customers_kafka` с движком Kafka:
  - Подключение к `kafka:29092`, топик `crm.public.customers`.
  - Формат `JSONEachRow`, consumer group `clickhouse-crm-consumer`.
- Целевая таблица `bionicpro.crm_customers_cdc` с движком `ReplacingMergeTree` — хранит актуальные CRM-данные.

### 4. MaterializedView для витрины

**Файл:** `clickhouse/init-scripts/create_materialized_view.sql`

- `bionicpro.crm_customers_mv` — MV, автоматически переносит данные из Kafka-таблицы в `crm_customers_cdc`.
- `bionicpro.user_report_mv` — витрина отчётности:
  - JOIN `telemetry_events` с `crm_customers_cdc` по customer_id.
  - Агрегация: total_events, avg_signal_strength, active_hours, movement_count по (customer_id, report_date).
  - Движок: `ReplacingMergeTree`.

### 5. Переключение API

В `backend/app.py` эндпоинт `GET /reports` по умолчанию выполняет SELECT из витрины `user_report_mv` (CDC-витрина, построенная на основе данных Debezium → Kafka → ClickHouse). Витрина объединяет CRM-данные (full_name, email) с телеметрией без прямой нагрузки на CRM. Имя таблицы настраивается через переменную окружения `REPORT_TABLE`.

---

## Запуск

Все сервисы, которые должны взаимодействовать между двумя compose-файлами, подключены к общей Docker-сети `bionicpro-net`. Её необходимо создать перед запуском.

### 0. Создать общую Docker-сеть

```bash
docker network create bionicpro-net
```

### 1. Основной стек (Keycloak, LDAP, Frontend, MinIO, Nginx, Kafka, Debezium)

```bash
docker compose up -d
```

### 2. Airflow стек (ClickHouse, Postgres CRM, Airflow)

```bash
cd airflow
cp .env.example .env
# Сгенерировать FERNET_KEY и заполнить .env
docker compose -f docker-compose.airflow.yaml up -d
```

Airflow UI: http://localhost:8081 (admin / admin)

### 3. Backend API

```bash
cd backend
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Запуск ETL и регистрация Debezium

После того как Airflow запустился:

1. Откройте Airflow UI (http://localhost:8081), включите DAG `bionicpro_reports_dag` и запустите его вручную (или дождитесь расписания). DAG создаст базу данных `crm` в Postgres и наполнит её тестовыми данными.
2. **После** успешного выполнения DAG зарегистрируйте Debezium connector:
   ```bash
   curl -X POST http://localhost:8083/connectors \
     -H "Content-Type: application/json" \
     -d @debezium/register-connector.json
   ```
   Debezium требует, чтобы БД `crm` и таблица `customers` уже существовали.

### Порты

| Сервис | Порт |
|---|---|
| Keycloak | 8080 |
| Frontend | 3000 |
| Backend API | 8000 |
| Airflow UI | 8081 |
| ClickHouse (native) | 9000 |
| ClickHouse (HTTP) | 8123 |
| MinIO API | 9002 |
| MinIO Console | 9001 |
| Nginx CDN | 8888 |
| Kafka | 9092 |
| Kafka Connect | 8083 |
| OpenLDAP | 389 |

### Тестовые пользователи

| Username | Password | Роль |
|---|---|---|
| prothetic1 | prothetic123 | prothetic_user (отчёты доступны) |
| prothetic2 | prothetic123 | prothetic_user |
| prothetic3 | prothetic123 | prothetic_user |
| admin1 | admin123 | administrator |
| user1 | password123 | user |
