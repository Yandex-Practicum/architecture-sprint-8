# BionicPRO — Отчёт о выполнении заданий

## Задание 1. Повышение безопасности системы

### Задача 1.1. Архитектура Federated Identity + BFF

**Цель:** Предложить архитектуру для унификации доступа с учётом локального хранения данных в разных странах.

**Изменённые файлы:**

- `BionicPRO_C4_model.drawio.xml` — добавлены контейнеры и связи:
  - **Keycloak (SSO Server)** — центральный IdP
  - **Token Proxy / BFF** — сервер-посредник для безопасного хранения токенов
  - **Federated Identity Provider** — внешние удостоверяющие службы
  - Связи: Federated IdP → Keycloak (SAML/OIDC) → BFF (Code + PKCE) → API (JWT)

#### Компоненты архитектуры

**1. Keycloak (центральный IdP)**

- Роль: единый провайдер аутентификации и авторизации (SSO)
- Протоколы: OpenID Connect, OAuth 2.0
- Хранение: локальная база PostgreSQL для конфигурации Realm
- Пользователи: федеративные — через User Federation (LDAP), внешние — через SAML/OIDC Identity Providers

**2. LDAP / Active Directory (User Federation)**

- Роль: локальное хранение учётных записей сотрудников в каждой стране
- Механизм: Keycloak подключает LDAP-каталог как User Federation провайдера
- Преимущества: пароли и атрибуты не покидают страну, проверка учётных данных — на стороне LDAP, поддержка OU (People, Groups)
- Конфигурация: `ldap/config.ldif` — тестовые пользователи и группы

**3. Federated Identity Provider (внешние IdP)**

- Роль: аутентификация пользователей через внешние удостоверяющие службы в разных странах
- Протоколы: SAML 2.0, OpenID Connect
- Сценарий: Keycloak выступает как Service Provider (SP), внешний IdP — как Identity Provider
- Data residency: токены и атрибуты подтверждаются внешним IdP, персональные данные хранятся локально

**4. Token Proxy / BFF (Backend-for-Frontend)**

- Роль: промежуточный сервис между SPA-фронтендом и Keycloak/API
- Безопасность: фронтенд никогда не получает access/refresh токены напрямую от IdP
- Протокол: SPA → BFF через httpOnly session cookie (недоступна JavaScript)
- Жизненный цикл токенов:
  - BFF выполняет Authorization Code + PKCE flow с Keycloak
  - Access/Refresh токены хранятся в серверной сессии BFF
  - BFF проксирует запросы к API, подставляя JWT из сессии
  - Refresh токена происходит прозрачно на стороне BFF

#### Потоки аутентификации

**Внутри страны (Local)**

```
Пользователь → SPA → BFF (session cookie)
                         ↓
                    Keycloak ←→ LDAP (User Federation)
                         ↓
                    BFF хранит токены в сессии (httpOnly)
                         ↓
                    BFF → API (JWT)
```

**Между странами (Federated)**

```
Пользователь (Страна A) → SPA → BFF
                                   ↓
                              Keycloak (SP)
                                   ↓
                   ╔══════════════════════╗
                   ║ Federated IdP        ║
                   ║ (Страна B)           ║
                   ║ SAML/OIDC            ║
                   ╚══════════════════════╝
                                   ↓
                              Keycloak получает атрибуты
                              Данные хранятся локально в Стране A
```

#### Data Residency (границы хранения данных)

| Тип данных | Где хранится | Обоснование |
|-----------|-------------|-------------|
| Персональные данные (ФИО, паспорт) | LDAP в стране пользователя | 152-ФЗ, GDPR |
| Медицинские данные телеметрии | PostgreSQL в стране пользователя | Медицинская тайна |
| Учётные данные (пароли) | LDAP / AD локально | Никогда не покидают страну |
| Метаданные сессии | BFF (сервер в стране пользователя) | Временные данные |
| Агрегированная аналитика | ClickHouse (OLAP) | Обезличенные данные |

#### Требования безопасности

1. PKCE — обязателен для всех публичных клиентов (SPA, мобильное приложение)
2. BFF — токены никогда не попадают в браузер пользователя
3. httpOnly session cookie — защита от XSS
4. CORS — строгая политика (не `*`)
5. LDAPS — шифрование трафика между Keycloak и LDAP
6. JWT Validation — проверка подписи RS256 на BFF при проксировании

---

### Задача 1.2. Переход с Code Grant на PKCE

**Цель:** Улучшить безопасность аутентификации для публичных клиентов (SPA).

**Изменённые файлы:**

- `keycloak/realm-export.json`:
  - Добавлен `"attributes": { "pkce.code.challenge.method": "S256" }` для клиента `reports-frontend`
  - `directAccessGrantsEnabled` оставлен `true` для dev-тестирования API через curl; в production отключается

**Обоснование:**

- **PKCE (S256)** — обязателен для публичных клиентов (SPA). Без него authorization code можно перехватить. В Keycloak 21.1 настраивается через `attributes` в JSON-экспорте.
- **Direct Access Grants** — оставлен для dev-режима, чтобы можно было тестировать API через curl с парольным grant_type. В production заменяется на PKCE + Authorization Code через BFF.
- **keycloak-js v21.1** — PKCE поддерживается нативно, фронтенд менять не пришлось.

**Проверка:** Keycloak запущен, realm `reports-realm` импортирован, PKCE S256 подтверждён через Admin API (`attributes.pkce.code.challenge.method: "S256"`).

---

## Задание 2. Разработка сервиса отчётов

### Задача 2.1. Архитектура ETL + витрина отчётности

**Цель:** Спроектировать ETL-процесс с Apache Airflow и витрину отчётности в ClickHouse.

**Источники данных:**
- **CRM (Битрикс24)** — данные о клиентах (ФИО, email, страна)
- **PostgreSQL (телеметрия)** — показания датчиков протезов (миосигналы, тип движения, уровень батареи)

**OLAP-база:** ClickHouse

**Схема «Звезда»:**
- `dim_customers` — пользователи (user_id, full_name, email, country)
- `fact_telemetry` — агрегированная телеметрия по дням (total_readings, avg_signals, movements по типам)
- `report_mart` — объединённая витрина для API

**ETL-процесс (Airflow DAG `prosthetic_reports_etl`):**
1. `extract_customers` — выгрузка клиентов из CRM
2. `extract_telemetry` — агрегация телеметрии за день из PostgreSQL
3. `load_to_clickhouse` — запись в ClickHouse (dim_customers, fact_telemetry, report_mart)

**Диаграмма C4:** обновлена — добавлены контейнеры Apache Airflow, ClickHouse, Reports API.

**Изменённые/созданные файлы:**
- `BionicPRO_C4_model.drawio.xml` — ClickHouse, Airflow, Reports API + связи
- `airflow/dags/prosthetic_reports_dag.py` — DAG с тремя задачами
- `airflow/sql/create_report_mart.sql` — DDL для ClickHouse
- `airflow/docker-compose-airflow.yaml` — инфраструктура Airflow
- `telemetry/init.sql` — тестовые данные (3 пользователя, телеметрия за январь 2025)
- `docker-compose.yaml` — добавлены telemetry_db, clickhouse, reports-api
- `reports-api/main.py` — FastAPI с `/reports`
- `reports-api/services/clickhouse_client.py` — клиент ClickHouse
- `reports-api/config.py` — конфигурация
- `reports-api/Dockerfile`
- `reports-api/requirements.txt`
- `frontend/src/components/ReportPage.tsx` — обработка ответа, скачивание JSON

### Задача 2.2. Airflow DAG

**Файл:** `airflow/dags/prosthetic_reports_dag.py`

**Расписание:** `0 2 * * *` (ежедневно в 2:00)

**Задачи:**
1. `extract_customers` — загружает данные клиентов из CRM (PostgreSQL `customers`) через PostgresHook
2. `extract_telemetry` — агрегирует телеметрию за дату выполнения по user_id, считает средние сигналы и количество движений по типам
3. `load_to_clickhouse` — загружает клиентов в `dim_customers`, телеметрию в `fact_telemetry`, формирует `report_mart` через JOIN

**Зависимости:** `[extract_customers, extract_telemetry] >> load_to_clickhouse`

### Задача 2.3. API /reports

**Файл:** `reports-api/main.py`

**Стек:** FastAPI + uvicorn, clickhouse-driver, PyJWT, requests

**Эндпоинт:** `GET /reports?period_from=YYYY-MM-DD&period_to=YYYY-MM-DD`

**Аутентификация:** Bearer JWT (HTTPBearer)

**Поток:**
1. Получение public key из Keycloak (`/.well-known/openid-configuration` → jwks_uri)
2. Верификация подписи токена (RS256)
3. Извлечение `preferred_username` из payload
4. Запрос в ClickHouse `report_mart` по user_id
5. Возврат JSON-отчёта

### Задача 2.4. Ограничение доступа

- **JWT-валидация** — проверка подписи RS256, срока действия, realm_access roles
- **RBAC** — проверяется наличие роли `prothetic_user` в `realm_access.roles` токена
- **user_id** извлекается из `preferred_username` — не из query-параметра
- Пользователь может запросить только свои данные. Чужой user_id подставить нельзя — он берётся из токена
- **401** — токен отсутствует / истёк / невалидный
- **403** — роль пользователя не `prothetic_user` (например, `user1` с ролью `user`)

### Задача 2.5. UI

**Файл:** `frontend/src/components/ReportPage.tsx`

**Изменения:**
- Добавлена обработка ответа от API: 401 → "перелогиньтесь", 403 → "нет доступа"
- Пустой отчёт → "данные ещё не готовы"
- При успехе отображается сводка (имя, email, количество дней)
- Кнопка «Save as JSON» — скачивание отчета в формате JSON
