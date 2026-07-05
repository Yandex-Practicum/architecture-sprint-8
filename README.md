# BionicPRO

Кейс BionicPRO: усиление безопасности, сервис отчётов, снижение нагрузки на БД и
CDC для CRM. Все сервисы поднимаются через `docker compose` (проверено на
`podman compose`).

## Состав и порты

| Сервис          | Порт (host)      | Назначение                                    |
|-----------------|------------------|-----------------------------------------------|
| frontend        | 3000             | React SPA (кнопка получения отчёта)           |
| bionicpro-auth  | 8000             | BFF/auth: PKCE, сессии, ротация               |
| reports-api     | 8001             | API отчётов (S3-кеш + CDN, витрина CH)        |
| keycloak        | 8080             | IdP (realm `reports-realm`)                   |
| airflow         | 8082             | ETL CRM → ClickHouse (задание 2)              |
| clickhouse      | 8123 (HTTP)      | OLAP-витрины                                  |
| minio           | 9002 API / 9001  | S3-хранилище отчётов (console на 9001)        |
| cdn (nginx)     | 8090             | CDN перед Minio (proxy_cache)                 |
| kafka           | 9092             | Брокер (CDC)                                  |
| connect         | 8083             | Kafka Connect + Debezium                      |
| openldap        | 3389 / 3636      | LDAP-представительство                        |

## Запуск

```bash
docker compose up -d          # или: podman compose up -d
```

После старта выполнить один ручной шаг — зарегистрировать Debezium-коннектор
(задание 4):

```bash
./debezium/register.sh        # PUT конфига на Kafka Connect (:8083)
```

Витрины ClickHouse создаются init-скриптами `clickhouse/init/*.sql` при первом
старте; после регистрации коннектора Kafka Engine вычитывает снапшот CRM.

Яндекс ID (задание 1) — креды в репозитории не хранятся, задаются через окружение:

```bash
cp .env.example .env          # вписать YANDEX_CLIENT_ID / YANDEX_CLIENT_SECRET
./keycloak/setup-yandex.sh    # проставит их в Identity Provider из .env
```

Фронтенд: http://localhost:3000

## Тестовые пользователи

| Логин         | Пароль         | Источник | Роль            |
|---------------|----------------|----------|-----------------|
| prothetic1    | prothetic123   | Keycloak | prothetic_user  |
| user1         | password123    | Keycloak | user            |
| admin1        | admin123       | Keycloak | administrator   |
| john.doe      | password       | LDAP     | prothetic_user  |
| jane.smith    | password       | LDAP     | user            |
| alex.johnson  | password       | LDAP     | prothetic_user  |

При первом входе Keycloak потребует привязать OTP (Google Authenticator/FreeOTP) —
MFA обязателен для всех (задание 1).

## Реализация по заданиям

### Задание 1. Безопасность
- **PKCE Authorization Code Flow** — обмен кода/токенов на бэкенде
  (`bionicpro-auth`), фронт из OAuth-флоу убран.
- **Токены и сессии** — access/refresh в Redis, refresh шифруется (Fernet),
  наружу только HttpOnly+Secure cookie; `accessTokenLifespan=120`; авто-refresh;
  ротация `session_id` (anti-fixation).
- **LDAP** — OpenLDAP + federation в Keycloak (мапперы username/email/first/last +
  role-mapper из групп).
- **MFA** — обязательный TOTP.
- **Яндекс ID** — Identity Provider (Identity Brokering). Секретов в realm нет —
  креды задаются через `.env` + `keycloak/setup-yandex.sh`.
- Диаграмма: `diagrams/auth-architecture.drawio`.
- Экспорт realm после настройки: `keycloak/keycloak-results-export.json`.

### Задание 2. Сервис отчётов
- Airflow DAG `airflow/dags/crm_to_clickhouse.py`: CRM → витрина
  `reports.user_report` (ClickHouse).
- `reports-api` `GET /reports` — отчёт только по себе (username из сессии).
- Диаграмма: `diagrams/reporting-architecture.drawio`.

### Задание 3. Снижение нагрузки
- `reports-api` пишет готовый отчёт в Minio по ключу
  `reports/{username}/{version}.json` (version = версия витрины); повторный
  запрос отдаётся из S3 без обращения к OLAP.
- CDN (`nginx/cdn.conf`) — reverse proxy к Minio с `proxy_cache`.
- Инвалидация: новый прогон витрины → новая версия → новый ключ → cache-miss.
- Диаграмма: `diagrams/load-reduction-architecture.drawio`.

### Задание 4. CDC для CRM
- CRM на `wal_level=logical`; Debezium (`debezium/crm-connector.json`) →
  Kafka → ClickHouse Kafka Engine → MV → `telemetry_raw`/`clients_dim` →
  агрегирующая витрина `user_report_rt` (`clickhouse/init/02_realtime_mart.sql`).
- `reports-api` переключается на витрину через env `REPORT_MART=realtime|airflow`
  (по умолчанию `realtime`).
- Диаграмма: `diagrams/cdc-architecture.drawio`.
