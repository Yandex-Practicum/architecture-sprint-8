# BionicPRO — Спринт 9: SSO + OLAP + CDC

> Проектная работа 9 спринта курса "Архитектор ПО PRO"

## Обзор

В этом спринте решаем четыре задачи:

| # | Задание | Суть | Статус |
|---|---------|------|--------|
| 1 | Повышение безопасности | BFF + PKCE + LDAP + MFA + Яндекс ID | ✅ Готово |
| 2 | Сервис отчётов | Airflow ETL → ClickHouse → Report API | ✅ Готово |
| 3 | Снижение нагрузки на БД | S3 + CDN (Nginx) кэширование отчётов | ✅ Готово |
| 4 | Оперативность CRM | CDC через Debezium → Kafka → ClickHouse | ✅ Готово |

## Структура репозитория

```
architecture-bionicpro/
├── bionicpro-auth/          ← Задание 1: BFF-сервис (Java 25, Javalin)
│   ├── pom.xml
│   ├── Dockerfile
│   └── src/main/java/bionicpro/auth/
│       ├── AuthServer.java              ← Точка входа, роутинг, конфиг из env
│       ├── handler/
│       │   ├── LoginHandler.java        ← GET /auth/login (PKCE + redirect)
│       │   ├── CallbackHandler.java     ← GET /auth/callback (token exchange)
│       │   ├── LogoutHandler.java       ← POST /auth/logout
│       │   └── ProxyHandler.java        ← GET/POST /api/** (session + proxy)
│       ├── session/
│       │   ├── SessionStore.java        ← Interface (→ Redis в проде)
│       │   ├── InMemorySessionStore.java← ConcurrentHashMap + cleanup
│       │   └── SessionData.java         ← Record: tokens + user info
│       ├── keycloak/
│       │   └── KeycloakClient.java      ← Token exchange, refresh, JWT parse
│       └── util/
│           ├── PkceUtil.java            ← code_verifier / code_challenge / SecureRandom ID
│           └── CookieUtil.java          ← HttpOnly + SameSite=Strict cookies
├── report-service/          ← Задание 2+3+4: Report API + S3 кэш + CDC витрина (Java 25, Javalin)
│   ├── pom.xml
│   ├── Dockerfile
│   └── src/main/java/bionicpro/reports/
│       ├── ReportServer.java            ← Точка входа, порт 8001, конфиг из env
│       ├── handler/
│       │   ├── ReportHandler.java       ← GET /reports/me + /reports/{userId} + S3 кэш
│       │   └── HealthHandler.java       ← GET /health (CH + S3 статус)
│       ├── clickhouse/
│       │   └── ClickHouseClient.java    ← HTTP-запросы к ClickHouse, витрина через env REPORT_VIEW
│       ├── s3/
│       │   └── S3ReportStore.java       ← MinIO: check/get/put отчётов, CDN URL
│       └── auth/
│           └── JwtUtil.java             ← Base64-декодер JWT payload
├── airflow/                 ← Задание 2: ETL-оркестрация
│   └── dags/
│       └── etl_reports.py               ← DAG: CRM + телеметрия → витрина ClickHouse
├── olap-db/                 ← ClickHouse: init-скрипты, данные
│   ├── 01-init.sql                      ← emg_sensor_data + user_reports (витрина batch)
│   ├── 02-init-cdc.sql                  ← KafkaEngine + MV + crm_customers + user_reports_cdc
│   ├── olap.csv                         ← Тестовые данные телеметрии (5000 записей)
│   └── users.xml                        ← Конфиг доступа (без пароля, dev)
├── crm-db/                  ← CRM: init-скрипт, данные
│   ├── init.sql                         ← Таблица customers
│   └── crm.csv                          ← Тестовые данные клиентов (1000 записей)
├── frontend/                ← Обновлённый фронтенд (без keycloak-js)
│   ├── src/
│   │   ├── App.tsx                      ← Убран ReactKeycloakProvider
│   │   └── components/
│   │       └── ReportPage.tsx           ← Кнопка «Получить отчёт», отображение данных
│   └── package.json                     ← Удалены keycloak-js, @react-keycloak/web
├── keycloak/
│   ├── realm-export.json                ← Исходный конфиг (не трогаем)
│   └── keycloak-results-export.json     ← Наш результат (BFF + PKCE + LDAP + MFA + Яндекс)
├── ldap/
│   └── config.ldif                      ← Исправлен баг uid=alex → uid=alex.johnson
├── diagrams/                ← PlantUML-диаграммы
│   ├── C4_BionicPRO_Target.puml / .png
│   ├── Auth_Login_Flow.puml / .png
│   ├── Auth_API_Request_Flow.puml / .png
│   ├── Auth_Logout_Flow.puml / .png
│   ├── ETL_Reports_Architecture.puml / .png
│   ├── Report_Request_Flow.puml / .png
│   ├── S3_CDN_Cache_Flow.puml / .png
│   └── CDC_CRM_Flow.puml / .png
├── nginx/                   ← Задание 3: CDN — Nginx reverse proxy + cache
│   └── nginx.conf                       ← proxy_cache → MinIO, TTL 24h, X-Cache-Status
├── debezium/                ← Задание 4: CDC connector config
│   ├── register-connector.json          ← Конфиг Debezium PostgreSQL connector
│   └── register-connector.sh            ← Скрипт регистрации через Kafka Connect REST API
├── docker-compose.yaml      ← Полная конфигурация развёртывания
├── reset.sh                 ← Полный сброс данных (для перезапуска с нуля)
├── screenshots/             ← Скриншоты smoke test
└── README.md                ← Этот файл
```

---

## Задание 1. Повышение безопасности системы

### Проблема

Исходная архитектура использовала OAuth 2.0 Code Grant напрямую из фронтенда (`keycloak-js`). Токены (`access_token`, `refresh_token`) хранились в браузере — в `localStorage` или памяти JavaScript. Это привело к взлому: XSS-атака позволила украсть токены и скачать персональные данные пользователей.

### Решение: BFF + PKCE

Внедряем **Backend for Frontend (BFF)** паттерн — новый сервис `bionicpro-auth`, который:

1. Реализует PKCE (Proof Key for Code Exchange) поверх Code Grant
2. Получает и хранит токены **на сервере** (фронтенд их никогда не видит)
3. Выдаёт фронтенду только сессионную cookie (`HttpOnly`, `Secure`, `SameSite=Strict`)
4. Проксирует запросы к API, подставляя `Authorization: Bearer <token>`
5. Автоматически обновляет `access_token` через `refresh_token`
6. Ротирует `session_id` при каждом запросе (защита от session fixation)

### Диаграммы

Все диаграммы — в формате PlantUML (исходники в `diagrams/`). Рендер: https://www.planttext.com/

#### C4 Container Diagram (Target Architecture)

Целевая архитектура после выполнения всех заданий спринта 9.

[Исходник PlantUML](diagrams/C4_BionicPRO_Target.puml)

![C4 Container Diagram](diagrams/C4_BionicPRO_Target.png)

#### Login Flow (BFF + PKCE + MFA)

Полный flow логина: PKCE → Keycloak (пароль + OTP) → BFF получает токены → создание сессии → HttpOnly cookie.

[Исходник PlantUML](diagrams/Auth_Login_Flow.puml)

![Login Flow](diagrams/Auth_Login_Flow.png)

#### API Request Flow (Session Rotation + Token Refresh)

Запрос к защищённому ресурсу: проверка сессии → ротация session_id → refresh токена → проксирование к API.

[Исходник PlantUML](diagrams/Auth_API_Request_Flow.puml)

![API Request Flow](diagrams/Auth_API_Request_Flow.png)

#### Logout Flow

Завершение сессии: удаление серверной сессии → Keycloak SSO logout → очистка куки.

[Исходник PlantUML](diagrams/Auth_Logout_Flow.puml)

![Logout Flow](diagrams/Auth_Logout_Flow.png)

### C4 Container Diagram: ключевые изменения

По сравнению с исходной архитектурой:

| Компонент | Было | Стало |
|-----------|------|-------|
| Аутентификация | `keycloak-js` на фронте, токены в браузере | `bionicpro-auth` (BFF), токены на сервере |
| Сессии | Нет серверных сессий | In-Memory `ConcurrentHashMap` (session_id → tokens). В проде → Redis |
| Identity | Keycloak standalone | Keycloak + LDAP (User Federation) + Яндекс ID (Brokering) |
| MFA | Нет | TOTP (Google Authenticator / FreeOTP) |
| Аналитика | PostgreSQL (перегружен) | ClickHouse (OLAP) + витрины |
| Данные | Batch-only | Airflow (batch) + Kafka/Debezium (CDC) |
| Отчёты | Нет | Report Service → S3 → Nginx (CDN cache) |

Все оригинальные компоненты (Программа в чипе протеза, Приложение для донастройки, Интернет-магазин, CRM, cli tool) **сохранены** на диаграмме.

---

### Задача 1.1 — Архитектурное решение

→ `diagrams/C4_BionicPRO_Target.puml`

Целевая C4 Container Diagram включает все существующие компоненты + новые: `bionicpro-auth` (BFF), Session Store, ClickHouse, Airflow, Kafka/Debezium, Report Service, S3/MinIO, Nginx, OpenLDAP, Яндекс ID.

---

### Задача 1.2 — PKCE

→ `diagrams/Auth_Login_Flow.puml` (шаги 4–19)
→ `bionicpro-auth/.../util/PkceUtil.java`
→ `bionicpro-auth/.../handler/LoginHandler.java` + `CallbackHandler.java`

Client `reports-frontend` в Keycloak переведён с `publicClient: true` на **confidential** + PKCE S256:

```json
{
  "clientId": "reports-frontend",
  "publicClient": false,
  "secret": "bff-client-secret-change-me",
  "redirectUris": ["http://localhost:8000/auth/callback"],
  "directAccessGrantsEnabled": false,
  "attributes": { "pkce.code.challenge.method": "S256" }
}
```

`redirect_uri` указывает на BFF (`localhost:8000/auth/callback`), **не** на фронтенд.

PKCE реализация (`PkceUtil.java`):
- `code_verifier` — 32 байта `SecureRandom` → Base64URL (43 символа)
- `code_challenge` — `BASE64URL(SHA-256(code_verifier))`
- `state` — 32 байта `SecureRandom` → hex (64 символа), CSRF-защита

Login flow: `LoginHandler` генерирует PKCE-пару, сохраняет `code_verifier` на сервере (привязанный к `state`), и редиректит пользователя на Keycloak с `code_challenge`. Callback: `CallbackHandler` обменивает `code + code_verifier + client_secret` на токены.

---

### Задача 1.3 — Безопасное хранение токенов (bionicpro-auth)

→ `bionicpro-auth/` — полный исходный код Java-сервиса
→ `diagrams/Auth_API_Request_Flow.puml` (session rotation + token refresh)

**Стек:** Java 25, Javalin 6.4, Jackson, Logback. Maven. Без Spring.

**Эндпоинты:**

| Метод | Путь | Handler | Описание |
|-------|------|---------|----------|
| GET | `/auth/login` | `LoginHandler` | Генерирует PKCE, редиректит на Keycloak |
| GET | `/auth/callback` | `CallbackHandler` | Обменивает code на токены, создаёт сессию, Set-Cookie |
| POST | `/auth/logout` | `LogoutHandler` | Удаляет сессию, Keycloak SSO logout |
| GET/POST | `/api/**` | `ProxyHandler` | Валидация + ротация + refresh + проксирование |
| GET | `/health` | inline | `{"status":"UP","sessions":N}` |

**Безопасность сессий:**
- Session ID — `SecureRandom(32 bytes)` → hex (256 бит энтропии). Не UUID.
- Cookie: `BIONIC_SESSION=<id>; HttpOnly; SameSite=Strict; Path=/; Max-Age=1800`
- Ротация: при каждом запросе `getAndRemove(oldId)` → обработка → `put(newId)`. Атомарно.
- Refresh: `ProxyHandler` проверяет `accessTokenExpiresAt`, вызывает Keycloak `/token` с `grant_type=refresh_token`
- Cleanup: фоновый поток каждые 5 минут удаляет истёкшие сессии

**Хранилище:** `InMemorySessionStore` (`ConcurrentHashMap`) реализует интерфейс `SessionStore`. Замена на Redis — одна имплементация, остальной код не меняется.

**Smoke-тест пройден:**

```bash
$ curl -s http://localhost:8000/health | jq .
{"sessions":0,"status":"UP"}

$ curl -v http://localhost:8000/auth/login 2>&1 | grep "Location"
< Location: http://localhost:8080/realms/reports-realm/.../auth?...&code_challenge=...&code_challenge_method=S256

$ curl -s http://localhost:8000/api/reports/me | jq .
{"error":"Not authenticated. Please login."}
```

---

### Задача 1.4 — LDAP

→ `ldap/config.ldif`
→ `keycloak/keycloak-results-export.json` (секция `components`)

**Исправлен баг** в исходном `config.ldif`: DN записи Alex'а был `uid=alex`, а атрибут `uid` — `alex.johnson`. Группа `prothetic_user` ссылалась на `uid=alex.johnson` → member не находился. Исправлено: `uid=alex.johnson` и в DN, и в атрибуте.

Добавлена группа `administrator` (отсутствовала в оригинале).

Keycloak User Federation настроен на `ldap://openldap:389`:
- Edit Mode: `READ_ONLY`
- Group-to-Role маппинг: LDAP-группы (`cn=prothetic_user,ou=Groups,...`) → Keycloak realm roles
- Attribute mappers: `uid→username`, `mail→email`, `cn→firstName`, `sn→lastName`

---

### Задача 1.5 — MFA (OTP)

→ `keycloak/keycloak-results-export.json` (секции `otpPolicy*`, `requiredActions`, `users[].requiredActions`)

Настройка:
- OTP Policy: TOTP, HmacSHA1, 6 digits, 30 sec, Look Ahead Window = 1
- Required Action `CONFIGURE_TOTP` включён как Default Action
- У всех пользователей в `requiredActions` добавлен `CONFIGURE_TOTP`
- При первом логине Keycloak покажет QR-код для Google Authenticator / FreeOTP

---

### Задача 1.6 — Яндекс ID

→ `keycloak/keycloak-results-export.json` (секция `identityProviders`)

Identity Provider настроен как OpenID Connect:
- Authorization URL: `https://oauth.yandex.ru/authorize`
- Token URL: `https://oauth.yandex.ru/token`
- UserInfo URL: `https://login.yandex.ru/info`
- Scope: `login:email login:info`
- `clientId` / `clientSecret` — плейсхолдеры (`YANDEX_CLIENT_ID_PLACEHOLDER`). Для активации необходимо зарегистрировать приложение на https://oauth.yandex.ru/ и подставить реальные значения.

---

### Изменения во фронтенде

Из `package.json` удалены зависимости:
- `keycloak-js` (^21.1.0)
- `@react-keycloak/web` (^3.4.0)

`App.tsx` — убран `ReactKeycloakProvider`, чистый рендер без знания о Keycloak.

`ReportPage.tsx` — полностью переписан:

| Аспект | Было (keycloak-js) | Стало (BFF) |
|--------|---------------------|-------------|
| Логин | `keycloak.login()` | `window.location.href = '/auth/login'` |
| Токен | `keycloak.token` в `Authorization` header | `credentials: 'include'` (cookie автоматически) |
| Логаут | `keycloak.logout()` | `POST /auth/logout` (form submit) |
| Знание о Keycloak | Да (URL, realm, clientId) | Нет. Фронтенд знает только BFF URL |

---

### Изменения в docker-compose.yaml

- Добавлен сервис `bionicpro-auth` (build из `./bionicpro-auth`, порт 8000)
- Keycloak импортирует `keycloak-results-export.json` (вместо `realm-export.json`)
- Frontend: env vars `REACT_APP_KEYCLOAK_*` заменены на `REACT_APP_BFF_URL`

---

### Deliverables задания 1

- [x] C4 Container Diagram целевой архитектуры (`diagrams/C4_BionicPRO_Target.puml`)
- [x] Sequence Diagram: Login Flow с PKCE + MFA (`diagrams/Auth_Login_Flow.puml`)
- [x] Sequence Diagram: API Request с ротацией и refresh (`diagrams/Auth_API_Request_Flow.puml`)
- [x] Sequence Diagram: Logout Flow (`diagrams/Auth_Logout_Flow.puml`)
- [x] Код PKCE flow (`bionicpro-auth/.../PkceUtil.java`, `LoginHandler.java`, `CallbackHandler.java`)
- [x] Код BFF-сервиса: токены на сервере, HttpOnly cookie, ротация, refresh (`bionicpro-auth/`)
- [x] Обновлённый фронтенд без `keycloak-js` (`frontend/`)
- [x] Keycloak realm config: confidential client + PKCE + LDAP + MFA + Яндекс ID (`keycloak/keycloak-results-export.json`)
- [x] LDAP config с исправленным багом (`ldap/config.ldif`)
- [x] Обновлённый `docker-compose.yaml`
- [x] Интеграционный тест: полный auth flow (Keycloak + BFF + Frontend). См. раздел «Результаты интеграционного тестирования».
- [ ] Яндекс ID: требуется регистрация приложения на https://oauth.yandex.ru/ и подстановка реальных `clientId`/`clientSecret`.

---

## Задание 2. Разработка сервиса отчётов

### Проблема

Пользователи хотят получать данные о работе своих протезов в виде отчёта. Данные разбросаны по двум источникам: телеметрия с датчиков (ClickHouse) и информация о клиентах (CRM PostgreSQL). Нужен ETL-процесс для объединения данных и API для выдачи отчётов.

### Решение: Airflow ETL → ClickHouse витрина → Report Service API

Два потока данных:

**ETL (batch, @daily):**
```
CRM PostgreSQL ──┐
                 ├──→ Airflow DAG ──→ ClickHouse (витрина user_reports)
ClickHouse       ┘
(emg_sensor_data)
```

**Runtime (по запросу пользователя):**
```
Frontend → BFF (cookie → Bearer) → Report Service → ClickHouse витрина → JSON
```

### Диаграммы

#### ETL Reports Architecture (C4 Container Diagram)

Архитектура сервиса отчётов: источники данных, ETL через Airflow, витрина ClickHouse, Report Service API.

[Исходник PlantUML](diagrams/ETL_Reports_Architecture.puml)

![ETL Reports Architecture](diagrams/ETL_Reports_Architecture.png)

#### Report Request Flow (Sequence Diagram)

Полный поток запроса отчёта: от клика пользователя через BFF и Report Service до ClickHouse. Включает ETL-процесс Airflow.

[Исходник PlantUML](diagrams/Report_Request_Flow.puml)

![Report Request Flow](diagrams/Report_Request_Flow.png)

---

### Задача 2.1 — Архитектура решения

→ `diagrams/ETL_Reports_Architecture.puml`
→ `diagrams/Report_Request_Flow.puml`

Архитектура включает:
- **Источники:** CRM DB (PostgreSQL, клиенты) + ClickHouse (сырая телеметрия `emg_sensor_data`)
- **ETL:** Apache Airflow, DAG `etl_reports`, расписание `@daily`
- **Витрина:** таблица `user_reports` в ClickHouse (агрегаты по пользователям и типам протезов)
- **API:** Report Service (Java 25, Javalin) — `GET /reports/me`, `GET /reports/{userId}`
- **Авторизация:** BFF проксирует запросы с Bearer token, Report Service проверяет JWT sub == userId

Ключевое решение: Airflow не перекладывает данные через Python. Вместо этого ClickHouse сам читает из CRM PostgreSQL через табличную функцию `postgresql()`. Данные не проходят через промежуточные слои.

---

### Задача 2.2 — Airflow DAG

→ `airflow/dags/etl_reports.py`

**DAG `etl_reports`** — четыре задачи, линейная цепочка:

```
check_sources → truncate_view → build_report_view → verify_view
```

| Задача | Что делает |
|--------|-----------|
| `check_sources` | Проверяет доступность CRM и ClickHouse, считает строки |
| `truncate_view` | Очищает витрину (full refresh) |
| `build_report_view` | `INSERT INTO user_reports SELECT ... FROM emg_sensor_data JOIN postgresql(crm)` |
| `verify_view` | Проверяет, что витрина не пуста, логирует статистику |

**Конфигурация:**
- `schedule_interval='@daily'` — ежедневно в полночь UTC
- `catchup=False` — не запускать за прошлые даты
- `retries=2`, `retry_delay=5 мин`
- Зависимости Python: `clickhouse-driver`, `psycopg2-binary` (через `_PIP_ADDITIONAL_REQUIREMENTS`)

**Стратегия загрузки:** Full refresh (truncate + insert). Для учебного объёма данных это проще и надёжнее инкрементальной загрузки.

---

### Задача 2.2 — ClickHouse: схема данных

→ `olap-db/01-init.sql`

Две таблицы:

**`emg_sensor_data`** — сырая телеметрия:
```sql
CREATE TABLE emg_sensor_data (
    user_id UInt32, prosthesis_type String, muscle_group String,
    signal_frequency UInt32, signal_duration UInt32,
    signal_amplitude Decimal(5,2), signal_time DateTime
) ENGINE = MergeTree()
ORDER BY (user_id, prosthesis_type, signal_time);
```

**`user_reports`** — витрина (заполняется Airflow):
```sql
CREATE TABLE user_reports (
    user_id UInt32, customer_name String, customer_email String,
    prosthesis_type String, total_signals UInt64,
    avg_amplitude Float64, avg_frequency Float64, avg_duration Float64,
    min_signal_time DateTime, max_signal_time DateTime,
    report_updated DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY (user_id, prosthesis_type);
```

`ORDER BY` начинается с `user_id` — основной фильтр при запросе отчёта. Используется обычный `MergeTree` (не `SummingMergeTree`), потому что витрина содержит `avg`-агрегаты.

**Тестовые данные:**
- `olap.csv` — 5000 записей телеметрии, 995 уникальных user_id, период февраль–март 2025
- `crm.csv` — 1000 клиентов, id 1–1000

---

### Задача 2.3 — Report Service (API)

→ `report-service/` — полный исходный код Java-сервиса

**Стек:** Java 25, Javalin 6.4, Jackson, Logback. Maven. Без Spring. Идентичный стек с `bionicpro-auth`.

**Эндпоинты:**

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/reports/me` | Отчёт по текущему пользователю (userId из JWT sub) |
| GET | `/reports/{userId}` | Отчёт по конкретному userId (проверка: sub == userId) |
| GET | `/health` | `{"status":"UP","clickhouse":"connected"}` |

**ClickHouse-клиент:** Использует HTTP API (порт 8123) через встроенный `java.net.http.HttpClient`. Ноль дополнительных зависимостей сверх Javalin + Jackson.

**JWT:** `JwtUtil` декодирует payload из Base64 без криптографической верификации подписи. Это безопасно: Report Service доступен только из docker-сети, запросы приходят от BFF.

**Формат ответа:**
```json
{
  "userId": 512,
  "customerName": "Alexis Moore",
  "customerEmail": "alexis.moore@example.com",
  "reportUpdated": "2025-03-16 02:00:00",
  "prostheses": [
    {
      "prosthesisType": "arm",
      "totalSignals": 42,
      "avgAmplitude": 3.14,
      "avgFrequency": 256,
      "avgDuration": 2100,
      "minSignalTime": "2025-02-01 ...",
      "maxSignalTime": "2025-03-31 ..."
    }
  ]
}
```

---

### Задача 2.4 — Ограничение доступа

→ `report-service/.../handler/ReportHandler.java`

Реализовано в `ReportHandler`:
1. Извлечь JWT из `Authorization: Bearer ...`
2. Декодировать payload, взять claim `sub` (user_id)
3. Для `/reports/{userId}`: сравнить `sub` с `{userId}` — если не совпадает, вернуть `403 Forbidden`
4. Для `/reports/me`: userId берётся напрямую из JWT, проверка не нужна

BFF (`ProxyHandler`) подставляет `Authorization: Bearer <access_token>` при проксировании.

---

### Задача 2.5 — UI: кнопка получения отчёта

→ `frontend/src/components/ReportPage.tsx`

Обновлённый `ReportPage.tsx`:
- Кнопка «Получить отчёт» → `fetch('/api/reports/me', { credentials: 'include' })`
- Отображение: имя клиента, email, группировка по типам протезов, метрики (сигналы, амплитуда, частота, длительность, период)
- Состояния UI: загрузка, успех, «отчёт не найден» (ETL ещё не обработал), ошибка авторизации (кнопка «Войти»)
- Кнопка «Выйти» → `POST /auth/logout`

---

### Изменения в docker-compose.yaml (задание 2)

Добавлены сервисы:

| Сервис | Образ | Порт | Назначение |
|--------|-------|------|-----------|
| `report-service` | build `./report-service` | 8001 | API /reports |
| `airflow_db` | postgres:14 | 5435 | Метабаза Airflow |
| `airflow-init` | apache/airflow:2.8.1 | — | Инициализация БД + admin |
| `airflow-webserver` | apache/airflow:2.8.1 | 8085 | UI (8080 занят Keycloak) |
| `airflow-scheduler` | apache/airflow:2.8.1 | — | Парсинг DAG, запуск задач |

BFF `API_BASE_URL` обновлён на `http://report-service:8001`.

---

### Deliverables задания 2

- [x] Архитектура решения: C4 диаграмма (`diagrams/ETL_Reports_Architecture.puml`)
- [x] Sequence Diagram: Report Request Flow (`diagrams/Report_Request_Flow.puml`)
- [x] ClickHouse init-скрипты: сырые данные + витрина (`olap-db/01-init.sql`)
- [x] CRM init-скрипт + тестовые данные (`crm-db/init.sql`, `crm-db/crm.csv`)
- [x] Airflow DAG: ETL с расписанием (`airflow/dags/etl_reports.py`)
- [x] Report Service: API /reports с авторизацией (`report-service/`)
- [x] Обновлённый фронтенд: кнопка «Получить отчёт» (`frontend/.../ReportPage.tsx`)
- [x] Обновлённый `docker-compose.yaml` (report-service + Airflow)
- [ ] Интеграционный тест: полный поток (Airflow ETL → отчёт в UI). Требует `docker-compose up`.

---

## Задание 3. Снижение нагрузки на базу данных

### Проблема

После внедрения сервиса отчётов (задание 2) нагрузка на ClickHouse возросла. Пользователи часто запрашивают свои отчёты, но данные обновляются только раз в сутки (ETL @daily). Каждый запрос одного и того же отчёта генерирует повторный `SELECT` к OLAP-базе — впустую.

### Решение: S3 + CDN (Nginx)

Два уровня кэширования:

1. **S3 (MinIO)** — Report Service сохраняет сгенерированный отчёт как JSON-объект в MinIO. При повторном запросе — читает из S3 вместо ClickHouse.
2. **CDN (Nginx)** — Nginx проксирует запросы к MinIO с кэшированием на диске. Клиент получает отчёт из кэша Nginx, даже MinIO не затрагивается.

```
Первый запрос:   Frontend → BFF → Report Service → ClickHouse → S3 (PUT) → ответ
Повторный:       Frontend → BFF → Report Service → S3 (GET) → ответ  (ClickHouse не тронут)
CDN-запрос:      Frontend → Nginx → кэш (HIT) → ответ                (S3 не тронут)
```

### Диаграмма

#### S3 + CDN Cache Flow (Sequence Diagram)

Три сценария: первый запрос (генерация), повторный (S3), CDN-кэш (Nginx). Плюс инвалидация кэша через Airflow.

[Исходник PlantUML](diagrams/S3_CDN_Cache_Flow.puml)

![S3 CDN Cache Flow](diagrams/S3_CDN_Cache_Flow.png)

---

### Задача 3.1 — Запись отчётов в S3

→ `report-service/.../s3/S3ReportStore.java`
→ `report-service/.../handler/ReportHandler.java`

**S3ReportStore** — клиент для MinIO (библиотека `io.minio:minio:8.5.7`):

| Метод | Что делает | S3 операция |
|-------|-----------|-------------|
| `exists(userId)` | Проверяет наличие отчёта | `HEAD /reports/{userId}/report.json` |
| `get(userId)` | Читает отчёт | `GET /reports/{userId}/report.json` |
| `put(userId, json)` | Сохраняет отчёт | `PUT /reports/{userId}/report.json` |
| `cdnUrl(userId)` | Формирует CDN-ссылку | `/cdn/reports/{userId}/report.json` |

При старте сервиса `S3ReportStore` автоматически:
- Создаёт bucket `reports` (если не существует)
- Устанавливает anonymous read policy — чтобы Nginx мог проксировать GET без авторизации

**Обновлённый ReportHandler** — flow:
1. Извлечь userId из JWT (как в задании 2)
2. `s3.exists(userId)` → если есть → `s3.get(userId)` → вернуть с `cdnUrl`
3. Если нет → запросить ClickHouse → `s3.put(userId, json)` → вернуть с `cdnUrl`
4. В ответе: поле `"source": "s3"` или `"clickhouse"` — для отладки

S3 — кэширующий слой. Его недоступность не ломает основной flow: если MinIO недоступен, отчёт генерируется из ClickHouse напрямую (graceful degradation).

**Структура ключей в S3:**
```
reports/               ← bucket
├── 512/
│   └── report.json
├── 887/
│   └── report.json
└── ...
```

---

### Задача 3.2 — CDN (Nginx reverse proxy + cache)

→ `nginx/nginx.conf`

Nginx эмулирует CDN: проксирует `GET /cdn/reports/...` к MinIO и кэширует ответы на диске.

```nginx
proxy_cache_path /var/cache/nginx/s3
    levels=1:2 keys_zone=s3_cache:10m max_size=1g inactive=24h;

location /cdn/reports/ {
    rewrite ^/cdn/(.*)$ /$1 break;
    proxy_pass http://minio:9000;
    proxy_cache s3_cache;
    proxy_cache_valid 200 24h;
    proxy_cache_valid 404 1m;
    add_header X-Cache-Status $upstream_cache_status always;
}
```

| Параметр | Значение | Почему |
|----------|---------|--------|
| `proxy_cache_valid 200 24h` | TTL кэша для успешных ответов | Совпадает с периодом ETL |
| `proxy_cache_valid 404 1m` | TTL для 404 | Отчёт может появиться после генерации |
| `proxy_cache_key $uri` | Ключ кэша | Один URL = один кэш |
| `X-Cache-Status` | HIT / MISS / EXPIRED | Заголовок для отладки |
| `Authorization ""` | Убираем заголовок авторизации | Bucket с anonymous read |

Nginx на порту **8088** (наружу).

---

### Задача 3.3 — Механизм обновления кэша

→ `airflow/dags/etl_reports.py` (шаг `invalidate_s3_cache`)

Двухуровневая инвалидация:

**Уровень 1: S3 (активная очистка через Airflow).** После перестроения витрины Airflow DAG удаляет все объекты из bucket `reports`. При следующем запросе пользователя Report Service не найдёт отчёт в S3, сгенерирует свежий из обновлённой витрины и сохранит обратно.

Обновлённая цепочка задач:
```
check_sources → truncate_view → build_report_view → verify_view → invalidate_s3_cache
```

**Уровень 2: Nginx (TTL-based).** Кэш Nginx живёт 24 часа (`proxy_cache_valid 200 24h`). После удаления объектов из S3 Airflow'ом, Nginx при следующем запросе получит MISS → обратится к MinIO → получит 404 или свежий отчёт. Модуль `ngx_cache_purge` не требуется.

**Цепочка инвалидации:**
```
Airflow обновляет витрину
  → Airflow удаляет объекты из S3
    → Nginx кэш устаревает по TTL
      → Следующий запрос: Report Service → ClickHouse → свежий отчёт → S3 → Nginx
```

---

### Изменения в docker-compose.yaml (задание 3)

Добавлен сервис:

| Сервис | Образ | Порт | Назначение |
|--------|-------|------|-----------|
| `nginx` | nginx:1.25-alpine | 8088 | CDN — reverse proxy к MinIO с кэшированием |

Обновлённые сервисы:

| Сервис | Что изменилось |
|--------|---------------|
| `report-service` | Добавлены env: `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `CDN_BASE_URL`. depends_on: minio |
| `airflow-*` | `_PIP_ADDITIONAL_REQUIREMENTS` — добавлен пакет `minio` |

Volumes: добавлен `nginx_cache` для персистентного кэша Nginx.

---

### Deliverables задания 3

- [x] Sequence Diagram: S3 + CDN кэширование (`diagrams/S3_CDN_Cache_Flow.puml`)
- [x] Report Service: запись отчётов в S3, check→get/generate→put (`report-service/.../s3/S3ReportStore.java`)
- [x] Report Service: при запросе сначала S3, потом ClickHouse (`report-service/.../handler/ReportHandler.java`)
- [x] Nginx конфигурация: reverse proxy + cache (`nginx/nginx.conf`)
- [x] Airflow DAG: инвалидация S3 кэша после ETL (`airflow/dags/etl_reports.py`)
- [x] Обновлённый `docker-compose.yaml` (nginx + S3 env vars)
- [ ] Интеграционный тест: X-Cache-Status HIT/MISS. Требует `docker-compose up`.

---

## Задание 4. Повышение оперативности и стабильности работы CRM

### Проблема

CRM PostgreSQL перегружена массовыми выгрузками для отчётности (Airflow DAG из задания 2 делает `SELECT * FROM customers` при каждом запуске ETL). Это создаёт long-running транзакции, давит на MVCC, раздувает WAL. OLTP-запросы операторов CRM замедляются и падают по таймауту.

### Решение: CDC через Debezium → Kafka → ClickHouse

Вместо batch-выгрузки — потоковый CDC (Change Data Capture). Debezium читает WAL PostgreSQL через logical replication. CRM не испытывает дополнительной нагрузки: WAL пишется в любом случае, Debezium лишь подписывается на поток.

```
CRM PostgreSQL ──WAL──→ Debezium ──→ Kafka ──→ ClickHouse KafkaEngine
                (logical repl.)                      ↓
                                              MaterializedView
                                                     ↓
                                              crm_customers (ReplacingMergeTree)
                                                     +
                                              emg_sensor_data (batch, Airflow)
                                                     ↓
                                              user_reports_cdc (VIEW)
                                                     ↓
                                              Report Service API
```

**Параллельное существование:** Airflow DAG и batch-витрина `user_reports` (задание 2) сохранены. CDC-пайплайн — параллельный набор сервисов. Переключение Report Service на CDC-витрину — через env `REPORT_VIEW=user_reports_cdc`.

### Диаграмма

#### CDC CRM Data Flow (Sequence Diagram)

Полный CDC-pipeline: initial snapshot, штатная работа через WAL, KafkaEngine → MV → target, обработка UPDATE и DELETE.

[Исходник PlantUML](diagrams/CDC_CRM_Flow.puml)

![CDC CRM Flow](diagrams/CDC_CRM_Flow.png)

---

### Задача 4.1 — CDC через Debezium

→ `debezium/register-connector.json`
→ `debezium/register-connector.sh`

**Debezium PostgreSQL Connector** читает WAL через `pgoutput` (встроенный плагин PostgreSQL 10+, без дополнительных расширений).

Ключевые параметры конфигурации:

| Параметр | Значение | Почему |
|----------|---------|--------|
| `plugin.name` | `pgoutput` | Встроен в PostgreSQL, не нужно устанавливать `decoderbufs` |
| `topic.prefix` | `crm` | Топик: `crm.public.customers` |
| `table.include.list` | `public.customers` | Захватываем только нужную таблицу |
| `snapshot.mode` | `initial` | Первый запуск: полный snapshot, потом только WAL |
| `schemas.enable` | `false` | Упрощённый JSON (без встроенной JSON Schema) |
| `delete.handling.mode` | `rewrite` | При DELETE: полное событие с `__deleted=true` вместо tombstone |
| `heartbeat.interval.ms` | `10000` | Heartbeat каждые 10с — чтобы WAL slot не разрастался |

CRM PostgreSQL настроен с `wal_level=logical` (через `command` в docker-compose).

Регистрация коннектора — через REST API Kafka Connect:
```bash
./debezium/register-connector.sh
# Ждёт готовности Kafka Connect, затем POST /connectors
```

---

### Задача 4.2 — Kafka

→ `docker-compose.yaml` (сервисы `zookeeper`, `kafka`, `kafka-connect`)

Три новых сервиса:

| Сервис | Образ | Порт | Назначение |
|--------|-------|------|-----------|
| `zookeeper` | confluentinc/cp-zookeeper:7.5.3 | 2181 | Координация Kafka |
| `kafka` | confluentinc/cp-kafka:7.5.3 | 9092 (хост) / 29092 (docker) | Брокер сообщений |
| `kafka-connect` | debezium/connect:2.4 | 8083 | Платформа для Debezium connector |

Kafka с двумя listener'ами: `INTERNAL` (kafka:29092, для Docker-сети) и `EXTERNAL` (localhost:9092, для отладки с хоста). ClickHouse подключается к `kafka:29092`.

Образ `debezium/connect:2.4` уже содержит PostgreSQL-коннектор — ничего дополнительно устанавливать не нужно.

---

### Задача 4.3 — KafkaEngine в ClickHouse

→ `olap-db/02-init-cdc.sql`

Четыре объекта, выполняются после `01-init.sql` (алфавитный порядок):

**1. `crm_customers_queue`** (KafkaEngine) — виртуальная очередь, читает сырой JSON из топика `crm.public.customers`. Формат `JSONAsString` — каждое сообщение целиком как строка.

**2. `crm_customers`** (ReplacingMergeTree) — CDC-реплика таблицы CRM. `ORDER BY id`, дедупликация по `_ts` (timestamp события). Колонка `_is_deleted` для обработки DELETE.

**3. `crm_customers_mv`** (MaterializedView) — автоматический триггер: при появлении сообщений в KafkaEngine парсит Debezium JSON через `JSONExtract*`, вставляет в `crm_customers`. Обрабатывает все типы операций:

| op | Debezium | Что делает MV |
|----|----------|---------------|
| `r` | Snapshot (initial) | INSERT, `_is_deleted=0` |
| `c` | Create (INSERT) | INSERT, `_is_deleted=0` |
| `u` | Update (UPDATE) | INSERT новой версии, ReplacingMergeTree заменит старую |
| `d` | Delete (DELETE) | INSERT с `_is_deleted=1`, фильтруется при чтении |

---

### Задача 4.4 — Витрина MaterializedView

→ `olap-db/02-init-cdc.sql` (секция 4)

**`user_reports_cdc`** (VIEW) — параллельная витрина, объединяющая CDC-данные CRM с телеметрией:

```sql
SELECT ... FROM (SELECT * FROM crm_customers FINAL) AS c
INNER JOIN emg_sensor_data AS e ON c.id = e.user_id
WHERE c._is_deleted = 0
GROUP BY c.id, c.name, c.email, e.prosthesis_type
```

Ключевые решения:

- **`FINAL`** — заставляет ReplacingMergeTree дедуплицировать строки на лету (без ожидания фонового merge). В проде с большими объёмами → периодический `OPTIMIZE TABLE` или MV с предагрегацией.
- **VIEW, не MATERIALIZED VIEW** — CRM-данные обновляются через CDC в near real-time, телеметрия через Airflow batch. MV срабатывал бы только при INSERT в один источник. VIEW пересчитывает JOIN при каждом SELECT — для учебного проекта достаточно.
- **Структура колонок** совпадает с `user_reports` (задание 2): `user_id`, `customer_name`, `customer_email`, `prosthesis_type`, `total_signals`, `avg_amplitude`, `avg_frequency`, `avg_duration`, `min_signal_time`, `max_signal_time`, `report_updated`. Это позволяет переключаться между витринами без изменения Report Service.

---

### Задача 4.5 — Перевод API на новую витрину

→ `report-service/.../clickhouse/ClickHouseClient.java`

Изменение минимальное: `ClickHouseClient` принимает имя витрины через конструктор. SQL-запрос использует `FROM %s` вместо захардкоженного `FROM user_reports`.

```java
// ReportServer.java — одна строчка:
String reportView = System.getenv().getOrDefault("REPORT_VIEW", "user_reports");
new ClickHouseClient(chHost, chPort, reportView);
```

В `docker-compose.yaml` для `report-service`:
```yaml
REPORT_VIEW: user_reports_cdc
```

**ReportHandler.java не изменён.** Вся логика (S3 кэш, JWT, CDN URL) работает одинаково для обеих витрин.

---

### Сравнение batch vs CDC

| Аспект | Задание 2 (Airflow batch) | Задание 4 (CDC) |
|--------|--------------------------|-----------------|
| Источник CRM-данных | `SELECT * FROM customers` | WAL (logical replication) |
| Нагрузка на CRM | Высокая (full table scan) | Минимальная (чтение WAL) |
| Задержка данных | До 24ч (ETL @daily) | Секунды (near real-time) |
| Обработка UPDATE/DELETE | Перезапись всей витрины | ReplacingMergeTree + `_is_deleted` |
| Витрина | `user_reports` (MergeTree, Airflow fill) | `user_reports_cdc` (VIEW, JOIN on-the-fly) |
| Инфраструктура | Airflow | + Zookeeper + Kafka + Kafka Connect + Debezium |

---

### Изменения в docker-compose.yaml (задание 4)

Новые сервисы:

| Сервис | Образ | Порт | Назначение |
|--------|-------|------|-----------|
| `zookeeper` | confluentinc/cp-zookeeper:7.5.3 | 2181 | Координация Kafka |
| `kafka` | confluentinc/cp-kafka:7.5.3 | 9092 / 29092 | Брокер сообщений |
| `kafka-connect` | debezium/connect:2.4 | 8083 | Debezium PostgreSQL connector |

Изменённые сервисы:

| Сервис | Что изменилось |
|--------|---------------|
| `crm_db` | Добавлен `command: postgres -c wal_level=logical -c max_replication_slots=4 -c max_wal_senders=4` |
| `report-service` | Добавлена env `REPORT_VIEW: user_reports_cdc` |
| `olap_db` | Добавлен `depends_on: kafka: condition: service_healthy` (KafkaEngine нужен живой Kafka) |

---

### Deliverables задания 4

- [x] Sequence Diagram: CDC Data Flow (`diagrams/CDC_CRM_Flow.puml`)
- [x] Конфигурация Debezium connector (`debezium/register-connector.json`)
- [x] Скрипт регистрации коннектора (`debezium/register-connector.sh`)
- [x] KafkaEngine + MaterializedView + CDC-реплика CRM (`olap-db/02-init-cdc.sql`)
- [x] Витрина `user_reports_cdc` с JOIN CRM + телеметрия (`olap-db/02-init-cdc.sql`)
- [x] Report Service: параметризуемая витрина (`report-service/.../clickhouse/ClickHouseClient.java`)
- [x] Kafka + Zookeeper + Kafka Connect в `docker-compose.yaml`
- [x] CRM PostgreSQL: `wal_level=logical` в `docker-compose.yaml`
- [x] Интеграционный тест: full CDC pipeline — 1000 записей из CRM snapshot → ClickHouse. См. раздел «Результаты интеграционного тестирования».

---

## Запуск и проверка

### Требования

- Docker Engine 20.10+ и Docker Compose V2 (`docker compose`)
- 32 GB RAM (рекомендуется, 15 сервисов + Kafka + ClickHouse)
- Первый запуск: ~5 минут на скачивание образов, ~2-5 минут на сборку Java-сервисов

### Полный сброс (если что-то пошло не так)

```bash
./reset.sh
# Удаляет контейнеры, volumes, persistent data directories
# После этого — повторный запуск с Фазы 1
```

### Поэтапный запуск

Проект содержит 16 сервисов с зависимостями. Запускаем в 6 фаз, чтобы каждый сервис стартовал после своих зависимостей.

**Фаза 1: Инфраструктура (базы данных, брокеры, хранилища)**

```bash
docker compose up -d zookeeper
docker compose up -d kafka
docker compose up -d keycloak_db crm_db airflow_db openldap minio
docker compose ps  # Все должны быть Running/Healthy
```

**Фаза 2: ClickHouse + Kafka Connect**

```bash
docker compose up -d olap_db
docker compose up -d kafka-connect
# Проверка таблиц ClickHouse:
docker compose exec olap_db clickhouse-client --query "SHOW TABLES"
# Ожидаем: emg_sensor_data, user_reports, crm_customers_queue, crm_customers, crm_customers_mv, user_reports_cdc
```

**Фаза 3: Keycloak**

```bash
docker compose up -d keycloak
# Ждём ~30-60 сек (импорт realm), проверка:
curl -s http://localhost:8080/realms/reports-realm | python3 -m json.tool | head -3
```

**Фаза 4: Java-сервисы (первая сборка ~2-5 мин)**

```bash
docker compose up -d report-service
curl -s http://localhost:8001/health  # {"status":"UP","clickhouse":"connected","s3":"connected"}

docker compose up -d bionicpro-auth
curl -s http://localhost:8000/health  # {"status":"UP","sessions":0}
```

**Фаза 5: Frontend + CDN + Airflow**

```bash
docker compose up -d frontend nginx
docker compose up -d airflow-init
# Ждём завершения airflow-init (Exited 0):
docker compose ps -a | grep airflow-init
docker compose up -d airflow-webserver airflow-scheduler
```

**Фаза 6: Debezium connector (CDC)**

```bash
./debezium/register-connector.sh
# Ожидаем: connector RUNNING, task RUNNING

# Проверка CDC-данных (через ~15 сек):
docker compose exec olap_db clickhouse-client --query "SELECT count() FROM crm_customers"
# Ожидаем: 1000 (initial snapshot из CRM)
```

### Остановка и продолжение работы

```bash
# Остановить с сохранением данных (для продолжения завтра):
docker compose stop

# Возобновить:
docker compose start
# Если frontend не стартовал (nginx resolve error):
docker compose restart frontend
```

### Порты сервисов

| Порт | Сервис | Назначение |
|------|--------|-----------|
| 3000 | Frontend | React UI |
| 8000 | bionicpro-auth | BFF (login, proxy, logout) |
| 8001 | report-service | API /reports |
| 8080 | Keycloak | Identity Provider |
| 8083 | Kafka Connect | Debezium REST API |
| 8085 | Airflow | Webserver UI |
| 8088 | Nginx | CDN (reverse proxy к MinIO) |
| 8123 | ClickHouse | HTTP interface |
| 9000 | MinIO | S3 API |
| 9001 | MinIO | Console UI |
| 9092 | Kafka | External listener (хост) |

### Тестовые пользователи

| Username | Пароль | Роль | CRM user_id |
|----------|--------|------|-------------|
| prothetic1 | prothetic123 | prothetic_user | 1 |
| prothetic2 | prothetic123 | prothetic_user | 2 |
| prothetic3 | prothetic123 | prothetic_user | 3 |
| user1 | password123 | user | — |
| user2 | password123 | user | — |
| admin1 | admin123 | administrator | — |

При первом входе каждому пользователю предлагается настроить TOTP (Google Authenticator / FreeOTP / AndOTP).

---

## Результаты интеграционного тестирования

### Smoke test: полный E2E flow

Тестирование проводилось на Manjaro Linux, i7, 32 GB RAM.

**Пройденный сценарий:**

1. Открыть `http://localhost:3000` → отображается страница BionicPRO (`screenshots/screen1.png`)
2. Нажать «Получить отчёт» → BFF возвращает 401, предлагает войти (`screenshots/screen2.png`)
3. Нажать «Войти» → редирект на Keycloak (`localhost:8080`) с PKCE (`code_challenge`, `code_challenge_method=S256`) (`screenshots/screen3.png`)
4. Ввести `prothetic1` / `prothetic123` → Keycloak предлагает настроить TOTP (`screenshots/screen4.png`)
5. Отсканировать QR-код → ввести одноразовый код (`screenshots/screen5.png`)
6. Keycloak → callback → BFF создаёт сессию → redirect на фронтенд (`screenshots/screen6.png`)
7. Нажать «Получить отчёт» → отображается отчёт из CDC-витрины (`screenshots/screen7.png`, `screenshots/screen8.png`)

**Результат:** Svetlana Lopez, два протеза (arm + hand), данные из `user_reports_cdc` (CDC pipeline, near real-time). Отчёт кэширован в S3, CDN URL доступен.

### Проблемы, найденные при запуске, и их решения

За два вечера тестирования было обнаружено и исправлено 12 проблем. Все фиксы внесены в репозиторий.

#### Критические (блокировали запуск)

| # | Проблема | Симптом | Причина | Фикс |
|---|----------|---------|---------|------|
| 1 | Порядок init-скриптов ClickHouse | `02-init-cdc.sql` ссылается на несуществующую таблицу | ClickHouse выполняет скрипты из `/docker-entrypoint-initdb.d/` в алфавитном порядке. `init-cdc.sql` < `init.sql` | Переименование: `init.sql` → `01-init.sql`, `init-cdc.sql` → `02-init-cdc.sql` |
| 2 | Перепутаны nginx-конфиги | Frontend контейнер получал CDN-конфиг вместо конфига раздачи React | CDN-конфиг ошибочно лежал в `frontend/nginx.conf` | Создана директория `nginx/`, конфиги разделены. В `frontend/nginx.conf` добавлен reverse proxy к BFF |
| 3 | Keycloak: пустые массивы в realm import | `Index 0 out of bounds for length 0` при старте Keycloak | LDAP mapper: `"groups.ldap.filter": []`, `"mapped.group.attributes": []`. Keycloak делает `array[0]` | Заменены `[]` → `[""]` |
| 4 | JAR signature conflict | `SecurityException: Invalid signature file digest for Manifest main attributes` | `maven-shade-plugin` без фильтра подписей. MinIO SDK тянёт подписанные JAR'ы (Bouncy Castle) | Добавлен `<filter>` исключающий `META-INF/*.SF`, `*.DSA`, `*.RSA` |
| 5 | Debezium JSON без обёртки `payload` | CDC MV парсит все поля как нули (0, пустые строки) | `schemas.enable=false` — Debezium отправляет `{"before":...,"after":...}` без `{"payload":{...}}`. MV искал `JSONExtract(raw, 'payload', 'after', ...)` | Убран уровень `'payload'` из всех `JSONExtract`. Поле `age` (Debezium decimal → base64) заменено на `toUInt8(0)` |
| 6 | Keycloak URL в браузере | Браузер пытается открыть `http://keycloak:8080/...` (внутренний Docker-хостнейм) | BFF использовал один `KEYCLOAK_URL` и для server-side token exchange, и для browser redirect | Разделение: `KEYCLOAK_URL` (internal) + `KEYCLOAK_EXTERNAL_URL` (browser). `KeycloakClient` принимает оба URL |
| 7 | BFF проксирует `/api/reports/me` → 404 | Report Service не находит endpoint | BFF проксировал путь как есть (`/api/reports/me`), а Report Service слушает на `/reports/me` | `ProxyHandler`: `path.startsWith("/api") ? path.substring(4) : path` |

#### Некритические (мешали, но не блокировали)

| # | Проблема | Фикс |
|---|----------|------|
| 8 | Zookeeper healthcheck не проходит | `cp-zookeeper:7.5.3` не содержит `nc`. Заменено на `curl -sf http://localhost:8080/commands/ruok` |
| 9 | CRM init.sql: Permission denied | Права файла `crm-db/init.sql` не позволяли postgres читать внутри контейнера. `chmod 644` |
| 10 | ClickHouse 24.8: `FROM table FINAL AS c` — syntax error | ClickHouse 24.8 не поддерживает `FINAL AS alias`. Обёрнуто в подзапрос: `FROM (SELECT * FROM crm_customers FINAL) AS c` |
| 11 | Java 25: `unsupported URI` с подчёркиванием в hostname | `http://olap_db:8123` невалидный по RFC. Добавлен сетевой alias `olapdb` в docker-compose |
| 12 | Frontend стартует раньше BFF | nginx не может зарезолвить upstream `bionicpro-auth`. Добавлен `depends_on: bionicpro-auth` |

#### Косметические

| # | Проблема | Фикс |
|---|----------|------|
| 13 | `version: '3.8'` deprecated | Удалено (Docker Compose V2 игнорирует) |
| 14 | `clickhouse/clickhouse-server:latest` | Зафиксировано: `clickhouse/clickhouse-server:24.8` (LTS) |
| 15 | PostgreSQL без healthcheck | Добавлены healthcheck для `keycloak_db`, `crm_db`, `airflow_db` + `condition: service_healthy` в depends_on |
| 16 | Airflow init YAML parsing | `command: >` складывал аргументы. Заменено на `command: - -c - |` (block scalar) |

### Известные ограничения и рекомендации для production

#### Маппинг Keycloak UUID → CRM user_id

**Текущее решение (demo):** BFF извлекает числовой ID из username регулярным выражением (`prothetic1` → `1`) и передаёт в заголовке `X-CRM-User-Id`. Report Service использует этот заголовок для запроса к ClickHouse.

**Production-решение:** В Keycloak добавить User Attribute `crm_user_id` (числовой ID пользователя в CRM). Через Protocol Mapper (тип `User Attribute`) включить его как claim в `id_token` и `access_token`. BFF и Report Service читают `crm_user_id` напрямую из JWT — никаких хаков с парсингом username.

```
Keycloak Admin → Users → prothetic1 → Attributes → crm_user_id = 1
Keycloak Admin → Clients → reports-frontend → Client Scopes → Mappers → Add:
  Name: crm-user-id
  Mapper Type: User Attribute
  User Attribute: crm_user_id
  Token Claim Name: crm_user_id
  Claim JSON Type: int
  Add to ID token: ON
  Add to access token: ON
```

#### Другие production-рекомендации

- **Session Store:** Заменить `InMemorySessionStore` (ConcurrentHashMap) на Redis. Интерфейс `SessionStore` уже абстрагирован — одна реализация
- **HTTPS:** Все URL сейчас HTTP. В production: TLS termination на reverse proxy (nginx/traefik), `Secure` флаг cookie
- **Яндекс ID:** Заменить плейсхолдеры `YANDEX_CLIENT_ID_PLACEHOLDER` на реальные credentials из https://oauth.yandex.ru/
- **ClickHouse FINAL:** В `user_reports_cdc` используется подзапрос с `FINAL` — на больших объёмах это дорого. В production: периодический `OPTIMIZE TABLE crm_customers FINAL` + убрать `FINAL` из VIEW
- **Kafka consumer group:** При `reset.sh` нужно инкрементировать `kafka_group_name` в `02-init-cdc.sql` (offset хранится в Kafka, не в ClickHouse)
- **Debezium `age` field:** Поле `age` типа `NUMERIC` кодируется Debezium как base64 (`{"scale":0,"value":"Ew=="}`). Текущий workaround: `toUInt8(0)`. Production: кастомный SMT (Single Message Transform) в Kafka Connect или обработка на стороне ClickHouse MV