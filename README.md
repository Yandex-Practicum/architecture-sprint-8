# BionicPRO — Архитектурный проект

## Содержание
1. [Структура проекта](#структура-проекта)
2. [Задание 1 — Повышение безопасности системы](#задание-1--повышение-безопасности-системы)
3. [Задание 2 — Сервис отчётов](#задание-2--сервис-отчётов)
4. [Задание 3 — Снижение нагрузки на базу данных (S3 + CDN)](#задание-3--снижение-нагрузки-на-базу-данных-s3--cdn)
5. [Задание 4 — Повышение оперативности CRM (CDC: Debezium → Kafka → ClickHouse)](#задание-4--повышение-оперативности-crm-cdc-debezium--kafka--clickhouse)
6. [Запуск](#запуск)

---

## Структура проекта

```
architecture-bionicpro/
├── bionicpro-auth/          # BFF-сервис (Spring Boot, Java 21)
│   ├── Dockerfile
│   ├── pom.xml
│   └── src/main/java/com/bionicpro/auth/
│       ├── config/SecurityConfig.java       # Spring Security (STATELESS, CORS)
│       ├── controller/
│       │   ├── AuthController.java          # /auth/login, /callback, /status, /logout
│       │   └── ApiProxyController.java      # GET /api/reports → проксирование в reports-api
│       ├── model/
│       │   ├── SessionData.java             # Хранение токенов + срок жизни
│       │   └── TokenResponse.java           # Ответ Keycloak на /token
│       └── service/
│           ├── KeycloakService.java         # PKCE S256, обмен кода на токены, рефреш
│           └── SessionService.java          # In-memory сессии, ротация, очистка
│
├── frontend/                # React 18 + TypeScript + Tailwind
│   ├── Dockerfile
│   ├── nginx.conf
│   ├── .env                 # REACT_APP_AUTH_URL=http://localhost:8000
│   └── src/
│       ├── App.tsx
│       └── components/
│           └── ReportPage.tsx               # Главная страница: вход / скачать отчёт / выход
│
├── keycloak/
│   └── realm-export.json    # Конфигурация realm reports-realm (клиент, роли, LDAP, Yandex ID)
│
├── ldap/
│   └── config.ldif          # Структура LDAP: OU=People/Groups, пользователи иностранного офиса
│
├── crm-db/
│   └── init.sql             # Схема CRM (patients, telemetry) + seed-данные
│
├── olap-db/
│   └── init.sql             # Схема OLAP-витрины (user_report_mart)
│
├── airflow/
│   ├── requirements.txt     # psycopg2-binary, apache-airflow extras
│   └── dags/
│       └── bionicpro_etl_dag.py   # DAG: Extract CRM → Transform → Load OLAP (ежедневно)
│
├── reports-api/             # REST API отчётов (Python 3.11 + FastAPI)
│   ├── Dockerfile
│   ├── requirements.txt
│   └── main.py              # GET /reports — валидация JWT → запрос витрины → CSV-ответ
│
├── clickhouse/
│   └── init.sql             # ClickHouse: KafkaEngine таблицы, MV, Dictionary, user_report_mart
│
├── debezium/
│   ├── connector-config.json  # Конфигурация Debezium PostgreSQL connector
│   └── register-connector.sh  # Скрипт регистрации коннектора в Kafka Connect REST API
│
├── nginx/
│   └── nginx.conf           # Nginx: reverse proxy + кеш статических файлов (CDN-эмуляция)
│
├── diagramm/
│   ├── c4-diagramm-sprint9.drawio    # C4-диаграмма (спринт 9, безопасность)
│   ├── c4-diagramm.png
│   └── reports-architecture.drawio   # Архитектура отчётов: ETL+S3/CDN (с.2-3) + CDC (с.4)
│
└── docker-compose.yaml      # Оркестрация всех сервисов
```

---

## Задание 1 — Повышение безопасности системы

### Задача 1. Архитектура управления учётными данными (C4)

Разработана архитектура на базе паттерна **Backend-for-Frontend (BFF)**:

- **Унификация доступа через LDAP**: Keycloak настроен на федерацию с сервером OpenLDAP, который хранит учётные данные пользователей зарубежного представительства. Персональные и медицинские данные остаются в локальной юрисдикции — LDAP хранит только учётные записи (username, e-mail, роли).
- **Мультистрановой IdP**: через механизм Identity Brokering Keycloak подключает внешние IdP (Yandex ID и другие), не нарушая единую точку входа.
- Диаграмма: `diagramm/c4-diagramm-sprint9.drawio`

### Задача 2. PKCE (Proof Key for Code Exchange)

Заменён классический Authorization Code Flow на **PKCE с S256**:

- `KeycloakService.java` генерирует `code_verifier` (32 случайных байта, Base64url) и `code_challenge` (SHA-256 от verifier).
- `code_challenge` + `code_challenge_method=S256` передаются в запросе авторизации.
- `code_verifier` хранится в памяти сервера и передаётся при обмене кода на токены.
- Frontend не участвует в этом процессе — всё реализовано на стороне BFF.

### Задача 3. BFF-сервис `bionicpro-auth` — безопасная работа с токенами

Сервис `bionicpro-auth` (Spring Boot 3.2, Java 21) реализует паттерн BFF:

| Аспект | Решение |
|--------|---------|
| Хранение токенов | `access_token` и `refresh_token` — только в памяти BFF (`SessionService`, `ConcurrentHashMap`) |
| Передача фронтенду | HTTP-only Secure cookie с `session_id` (без токенов) |
| Срок жизни `access_token` | 2 минуты (настроено в Keycloak) |
| Срок жизни сессии | 3600 секунд > времени жизни `access_token` |
| Обновление токена | BFF автоматически рефрешит `access_token` через `refresh_token` при истечении |
| Ротация сессии | При каждом запросе к `/api/reports` — новый `session_id`, новая cookie (защита от Session Fixation) |
| Проксирование | BFF подставляет `Authorization: Bearer {access_token}` при обращении к `reports-api` |

**Эндпоинты BFF:**
- `GET /auth/login` — редирект на Keycloak с PKCE
- `GET /auth/callback` — обмен кода на токены, создание сессии, редирект на фронтенд
- `GET /auth/status` — проверка сессии (возвращает `{"authenticated": true/false}`)
- `POST /auth/logout` — инвалидация сессии
- `GET /api/reports` — прокси в `reports-api` с инжектом Bearer-токена

### Задача 4. LDAP (OpenLDAP)

Развёрнут `osixia/openldap:1.5.0`:
- Структура: `ou=People,dc=example,dc=com` / `ou=Groups,dc=example,dc=com`
- Пользователи: `john.doe`, `jane.smith`, `alex.johnson`
- Роли: `user`, `prothetic_user`
- Keycloak настроен на User Federation с OpenLDAP + маппинг ролей через Group Mapper

### Задача 5. MFA (OTP)

В Keycloak настроена обязательная OTP-аутентификация:
- Authentication Flow: Browser flow → OTP Form обязателен
- Совместимость: Google Authenticator, FreeOTP
- Пользователь при первом входе сканирует QR-код и регистрирует устройство

### Задача 6. Yandex ID OAuth 2.0

Через механизм Identity Brokering подключён Yandex ID:
- Провайдер: `oidc` с endpoint-ами Яндекса
- Credentials: `YANDEX_CLIENT_ID` / `YANDEX_CLIENT_SECRET` (env vars)
- После аутентификации Keycloak запрашивает consent у пользователя
- Данные профиля (имя, email) синхронизируются и сохраняются в БД Keycloak

---

## Задание 2 — Сервис отчётов

### Задача 1. Архитектура ETL и отчётности

```
[CRM DB (PostgreSQL)]  ──────────────────────────────────────────┐
  patients, telemetry                                             │
                                                                  ▼
                                               [Apache Airflow — ежедневный DAG]
                                                  1. Extract: patients + telemetry
                                                  2. Transform: агрегация по пользователю и дате
                                                  3. Load: upsert → user_report_mart
                                                                  │
[OLAP DB (PostgreSQL)] ←────────────────────────────────────────┘
  user_report_mart
         │
         ▼
  [reports-api (FastAPI)] ← Authorization: Bearer {token}
    GET /reports
    1. Валидирует JWT (Keycloak JWKS)
    2. Извлекает username из claims
    3. Запрашивает только строки WHERE username = ?
    4. Возвращает CSV-отчёт
         │
         ▲
  [bionicpro-auth BFF]  ← session cookie
    /api/reports (прокси)
         ▲
  [Frontend (React)]
    Кнопка "Download Report"
```

**OLAP-витрина `user_report_mart`:**

| Поле | Тип | Описание |
|------|-----|----------|
| username | VARCHAR(100) | PK |
| report_date | DATE | PK — дата агрегации |
| full_name | VARCHAR(200) | Имя пользователя (из CRM) |
| device_serial | VARCHAR(50) | Серийный номер протеза |
| device_model | VARCHAR(100) | Модель протеза |
| total_active_hours | DECIMAL | Суммарные часы активности за день |
| avg_battery_level | DECIMAL | Среднее значение заряда за день |
| total_steps | BIGINT | Суммарное число шагов за день |
| event_count | INTEGER | Число событий телеметрии за день |
| etl_updated_at | TIMESTAMP | Время последнего обновления ETL |

### Задача 2. Airflow DAG

Файл: `airflow/dags/bionicpro_etl_dag.py`

- **Расписание**: ежедневно в 01:00 (`0 1 * * *`)
- **Задачи (tasks)**:
  1. `extract_patients` — выгрузка пациентов из CRM
  2. `extract_telemetry` — выгрузка телеметрии за предыдущие сутки
  3. `transform_and_load` — агрегация + upsert в `user_report_mart`
- Зависимость: `extract_patients >> extract_telemetry >> transform_and_load`
- При запросе данных, которых ещё нет в OLAP, reports-api возвращает пустой отчёт с пояснением

### Задача 3. reports-api (FastAPI)

Файл: `reports-api/main.py`

- **Язык**: Python 3.11
- **Фреймворк**: FastAPI + Uvicorn
- **Эндпоинт**: `GET /reports`
  - Принимает `Authorization: Bearer {access_token}` от BFF
  - Декодирует JWT, получает `preferred_username`
  - Делает SELECT из `user_report_mart WHERE username = :username`
  - Возвращает CSV (`Content-Disposition: attachment; filename=report_{username}.csv`)

### Задача 4. Ограничение доступа

- JWT обязателен — без него возвращается `401 Unauthorized`
- Подпись токена проверяется через JWKS endpoint Keycloak
- Username извлекается только из проверенного токена — пользователь **не может** запросить отчёт другого пользователя
- Expired токен → `401 Unauthorized`

### Задача 5. Кнопка в UI

Реализована в `frontend/src/components/ReportPage.tsx`:
- Кнопка **"Download Report"** — вызывает `GET /api/reports` через BFF (credentials: include)
- Если пользователь не аутентифицирован — показывается форма входа
- При успехе — скачивает CSV-файл с отчётом

---

## Задание 3 — Снижение нагрузки на базу данных (S3 + CDN)

### Проблема

После запуска сервиса отчётов пользователи стали часто запрашивать свои отчёты. Поскольку данные обновляются только раз в сутки Airflow-пайплайном, повторные запросы возвращают идентичный результат — OLAP-база получает лишнюю нагрузку.

### Решение: S3-кеш + Nginx CDN

```
                    ┌──────────────────────────────────────────────────┐
User → Frontend → BFF → reports-api                                    │
                            │                                           │
                    1. Запрос MAX(etl_updated_at) из OLAP (легковесный) │
                    2. Формирование S3-ключа:                           │
                       reports/{username}/{etl_date}/report.csv         │
                    3. HEAD-запрос в MinIO                              │
                       ├── HIT  → вернуть CDN URL (OLAP не трогаем)    │
                       └── MISS → SELECT из OLAP → CSV → PUT в MinIO   │
                                  → вернуть CDN URL                    │
                            │
              ┌─────────────┴──────────────────┐
         [MinIO S3]                        [Nginx CDN]
         bionicpro-reports                 Кеш на диске
         bucket (public)                  proxy_cache 1h
              │                                │
              └───────────────────────────────→ User скачивает файл напрямую
```

### Архитектурные решения

#### S3-структура ключей и стратегия инвалидации кеша

Ключ включает дату последнего ETL-запуска: `reports/{username}/{etl_date}/report.csv`

| Что происходит | Результат |
|----------------|-----------|
| Пользователь запрашивает отчёт (данные актуальные) | S3 HIT → CDN URL → файл из кеша Nginx |
| Airflow запустился, обновил витрину | `etl_date` изменилась → новый S3-ключ → новый CDN URL |
| Пользователь запрашивает отчёт после ETL | S3 MISS (новый ключ) → генерация → загрузка в S3 → CDN URL |
| Старый CDN URL | Больше не запрашивается браузером (другой URL), устаревает по `inactive=24h` |

**Ключевой принцип**: инвалидация происходит автоматически через смену URL — никакого активного purge не нужно.

#### MinIO lifecycle policy

Старые файлы в S3 автоматически удаляются через 7 дней (задаётся при инициализации бакета через `mc ilm rule add --expire-days 7`).

#### Nginx CDN (cdn/nginx.conf)

- `proxy_cache_path`: кеш на диске, 500 МБ, TTL 24 часа для неактивных объектов
- `proxy_cache_valid 200 1h`: успешные ответы кешируются на 1 час
- `proxy_cache_lock on`: конкурентные запросы к одному файлу объединяются (только один запрос уходит в MinIO)
- `X-Cache-Status` header: показывает HIT/MISS/BYPASS — удобно для отладки

### Изменённые файлы

| Файл | Что изменилось |
|------|----------------|
| `reports-api/main.py` | Добавлен S3-слой: check → generate → upload; эндпоинт возвращает JSON с CDN URL вместо CSV-потока |
| `reports-api/requirements.txt` | Добавлен `boto3` |
| `frontend/src/components/ReportPage.tsx` | Обрабатывает JSON-ответ с `report_url`; показывает дату ETL и статус (cached/fresh); кнопка Download ведёт на CDN URL |
| `cdn/nginx.conf` | Новый файл — конфиг Nginx CDN |
| `docker-compose.yaml` | Добавлены сервисы `minio`, `minio-init`, `cdn` |

### Новые сервисы

| Сервис | Образ | Порт | Назначение |
|--------|-------|------|-----------|
| `minio` | `minio/minio:latest` | 9000 (S3 API), 9001 (Console) | Объектное хранилище |
| `minio-init` | `minio/mc:latest` | — | Создаёт бакет, ставит public-read, lifecycle 7d |
| `cdn` | `nginx:1.25-alpine` | 8100 | Reverse proxy с кешированием |

### Формат ответа reports-api (v2)

```json
{
  "report_url": "http://localhost:8100/bionicpro-reports/reports/john.doe/2024-01-15/report.csv",
  "etl_date":   "2024-01-15",
  "cached":     true
}
```

Если ETL ещё не запускался:
```json
{
  "report_url": null,
  "message":    "No data processed yet. Please try again after the nightly ETL run."
}
```

---

## Задание 4 — Повышение оперативности CRM (CDC: Debezium → Kafka → ClickHouse)

### Проблема

Массовые выгрузки из CRM DB (PostgreSQL) нагружали OLTP-систему: SELECT по всем таблицам конкурировал с транзакционными запросами, вызывая деградацию производительности.

### Решение: Change Data Capture (CDC)

Вместо периодических bulk-запросов CRM DB теперь отправляет только изменения (INSERT/UPDATE/DELETE) через механизм logical replication PostgreSQL. Debezium читает WAL и стримит события в Kafka. ClickHouse потребляет топики через KafkaEngine и немедленно обновляет витрину — без единого SELECT к production CRM.

```
[CRM DB PostgreSQL]
    WAL (wal_level=logical)
          │
    [Debezium Connector]          ← Kafka Connect :8083
    plugin: pgoutput              ← слот: debezium_slot
    SMT: ExtractNewRecordState    ← flat JSON, без schema
          │
    [Apache Kafka :9092]  (KRaft, без ZooKeeper)
    ├── bionicpro.public.patients
    └── bionicpro.public.telemetry
          │
    [ClickHouse :8123]  (DB: bionicpro)
    ├── kafka_patients  (KafkaEngine) ──MV──► patients_local (ReplacingMergeTree)
    │                                             │
    │                                   patients_dict (Dictionary, HASHED, refresh 60-300s)
    │                                             │
    └── kafka_telemetry (KafkaEngine) ──MV──► telemetry_local (MergeTree)
                                    │   ──MV──► user_report_mart (SummingMergeTree)
                                    │           └─ dictGet(patients_dict) для обогащения
          │
    [reports-api]  ← clickhouse-connect
    SELECT ... FROM user_report_mart GROUP BY username, report_date
```

### Схема ClickHouse (bionicpro)

| Объект | Engine | Назначение |
|--------|--------|-----------|
| `kafka_patients` | KafkaEngine | CDC consumer топика patients |
| `kafka_telemetry` | KafkaEngine | CDC consumer топика telemetry |
| `patients_local` | ReplacingMergeTree | Дедупликация по username |
| `telemetry_local` | MergeTree, PARTITION BY month | Сырые события телеметрии |
| `patients_dict` | Dictionary (HASHED) | In-memory справочник пациентов, refresh 60-300s |
| `patients_mv` | MaterializedView | kafka_patients → patients_local |
| `telemetry_mv` | MaterializedView | kafka_telemetry → telemetry_local |
| `report_mart_mv` | MaterializedView | kafka_telemetry + dictGet → user_report_mart |
| `user_report_mart` | SummingMergeTree | Витрина: частичные агрегаты по (username, date) |

### Почему SummingMergeTree для витрины

Каждый Kafka poll batch вставляет **частичные агрегаты** за (username, date). SummingMergeTree в фоне суммирует их при merge. До merge отчёт читается с `GROUP BY + sum()` — результат всегда корректен.

`avg_battery_level` хранится как `total_battery_sum` + `event_count` → вычисляется при запросе: `sum(total_battery_sum) / sum(event_count)`.

### Debezium конфигурация

| Параметр | Значение | Пояснение |
|----------|----------|-----------|
| `plugin.name` | `pgoutput` | Стандартный плагин PostgreSQL (без установки) |
| `snapshot.mode` | `initial` | Снимок всех существующих данных при первом старте |
| `decimal.handling.mode` | `double` | DECIMAL → Float64 в JSON |
| `time.precision.mode` | `connect` | DATE → days since epoch (Int32), TIMESTAMP → ms since epoch (Int64) |
| `transforms.unwrap.type` | `ExtractNewRecordState` | Плоский JSON вместо вложенного `{before, after, op}` |
| `transforms.unwrap.add.fields` | `op,ts_ms` | Добавляет `__op` и `__ts_ms` в сообщение |

### Новые сервисы (Assignment 4)

| Сервис | Образ | Порт | Назначение |
|--------|-------|------|-----------|
| `kafka` | `bitnami/kafka:3.7` | 9094 (external) | Kafka KRaft (без ZooKeeper) |
| `kafka-connect` | `quay.io/debezium/connect:2.6` | 8083 | Kafka Connect + Debezium connector |
| `debezium-init` | `curlimages/curl` | — | Регистрация коннектора через REST API |
| `clickhouse` | `clickhouse/clickhouse-server:23.8` | 8123 (HTTP), 9009 (native) | OLAP база данных |

### Изменённые компоненты

| Компонент | Изменение |
|-----------|-----------|
| `crm-db` | Добавлены `-c wal_level=logical -c max_replication_slots=5` |
| `reports-api/main.py` | Заменён psycopg2 на `clickhouse-connect`; запрос к `user_report_mart` с GROUP BY |
| `reports-api/requirements.txt` | Убран psycopg2, добавлен `clickhouse-connect` |

### Диаграмма

`diagramm/reports-architecture.drawio` — два листа:
1. **Assignments 2 & 3**: ETL (Airflow) + S3/CDN flow
2. **Assignment 4**: CDC flow (Debezium → Kafka → ClickHouse)

---

## Запуск

### Предварительные требования

- Docker Desktop 24+
- Docker Compose v2

### Конфигурация Yandex ID

Перед запуском установите credentials в `docker-compose.yaml`:

```yaml
YANDEX_CLIENT_ID:     <ваш client_id>
YANDEX_CLIENT_SECRET: <ваш client_secret>
```

### Запуск всего стека

```bash
docker-compose up --build
```

### Адреса сервисов

| Сервис | URL |
|--------|-----|
| Frontend | http://localhost:3000 |
| BionicPRO Auth (BFF) | http://localhost:8000 |
| Keycloak Admin | http://localhost:8080 |
| Reports API | http://localhost:8001 |
| Airflow UI | http://localhost:8090 |
| MinIO S3 API | http://localhost:9000 |
| MinIO Console | http://localhost:9001 |
| CDN (Nginx) | http://localhost:8100 |
| Kafka Connect (Debezium) | http://localhost:8083 |
| ClickHouse HTTP | http://localhost:8123 |
| CRM DB (PostgreSQL) | localhost:5434 |
| OLAP DB (PostgreSQL, legacy) | localhost:5435 |
| OpenLDAP | localhost:389 |

### Тестовые пользователи LDAP

| Username | Password | Роль |
|----------|----------|------|
| john.doe | password | prothetic_user |
| jane.smith | password | user |
| alex.johnson | password | prothetic_user |

### Keycloak Admin

- URL: http://localhost:8080
- Login: `admin` / `admin`
- Realm: `reports-realm`

### Airflow

- URL: http://localhost:8090
- Login: `airflow` / `airflow`
- DAG: `bionicpro_etl_dag` (можно запустить вручную через Trigger DAG)
