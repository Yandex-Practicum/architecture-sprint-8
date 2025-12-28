# BionicPRO - Проектная работа 9 спринта

Проект включает улучшение архитектуры безопасности и разработку сервиса отчётов для компании BionicPRO — производителя бионических протезов.

## Структура проекта

```
├── diagrams/                    # Архитектурные диаграммы C4
│   ├── BionicPRO_C4_as-is.drawio           # Исходная архитектура
│   ├── BionicPRO_C4_task1_security.drawio  # Задание 1: Архитектура безопасности
│   └── BionicPRO_C4_task2_reports.drawio   # Задание 2: Сервис отчётов
├── airflow/                     # Apache Airflow DAG
├── backend/                     # Backend API (FastAPI)
├── frontend/                    # React-приложение
├── keycloak/                    # Конфигурация Keycloak
├── ldap/                        # Конфигурация LDAP
└── docker-compose.yaml          # Docker Compose для запуска
```

---

## Задание 1. Повышение безопасности системы

### Задача 1. Архитектурное решение для управления учётными данными

**Файл:** `diagrams/BionicPRO_C4_task1_security.drawio`

#### Требования и решения:

| Требование | Решение |
|------------|---------|
| Унификация доступа через внешний источник | Keycloak как Identity Broker — федерация с внешними IdP |
| Локальное хранение персональных данных | PostgreSQL хранит медицинские данные локально в стране пользователя |
| Токены НЕ передаются фронтенду | BFF (Backend For Frontend) хранит access/refresh токены, фронтенд получает только сессионную cookie |
| Поддержка разных IdP в разных странах | Identity Federation через OIDC/SAML для России, ЕС, других рынков |

#### Ключевые компоненты архитектуры:

1. **BFF (Backend For Frontend)** — хранит токены, выдаёт сессии, проксирует запросы к API
2. **Keycloak (Identity Broker)** — федерация идентификации с внешними провайдерами
3. **Внешние IdP** — провайдеры для разных стран (ЕСИА/AD для России, Azure AD для ЕС, Okta для других)
4. **Локальная БД** — персональные и медицинские данные остаются в стране пользователя

### Задача 2. Реализация PKCE

**Файлы:**
- `keycloak/realm-export.json` — настройка PKCE для клиента
- `frontend/src/App.tsx` — использование PKCE в приложении

#### Что было изменено:

**Keycloak (realm-export.json):**
```json
{
  "clientId": "reports-frontend",
  "directAccessGrantsEnabled": false,
  "standardFlowEnabled": true,
  "attributes": {
    "pkce.code.challenge.method": "S256"
  }
}
```

**Frontend (App.tsx):**
```typescript
const initOptions = {
  pkceMethod: 'S256' as const,
  onLoad: 'check-sso' as const,
  checkLoginIframe: false
};
```

#### Как работает PKCE:

1. Frontend генерирует случайный `code_verifier`
2. Создаёт `code_challenge` = SHA256(code_verifier)
3. Отправляет `code_challenge` при запросе авторизации
4. При обмене code на токен отправляет `code_verifier`
5. Keycloak проверяет: SHA256(code_verifier) == code_challenge

Это защищает от перехвата authorization code злоумышленником.

---

## Задание 2. Разработка сервиса отчётов

### Задача 1. Архитектура решения для подготовки и получения отчётов

**Файл:** `diagrams/BionicPRO_C4_task2_reports.drawio`

#### Компоненты архитектуры:

| Компонент | Технология | Назначение |
|-----------|------------|------------|
| CRM | Битрикс24 | Источник данных о клиентах |
| PostgreSQL | PostgreSQL | Телеметрия с протезов |
| Apache Airflow | Python DAG | ETL-процесс по расписанию |
| ClickHouse | ClickHouse | OLAP витрина для быстрых отчётов |
| Backend API | FastAPI | Endpoint /reports |
| Frontend | React | Кнопка "Скачать отчёт" |

#### ETL-процесс:

```
1. EXTRACT: данные из CRM (клиенты)
2. EXTRACT: данные из PostgreSQL (телеметрия)
3. TRANSFORM: объединение и агрегация по user_id
4. LOAD: запись в ClickHouse (витрина reports_mart)
```

**Расписание:** ежедневно в 02:00

### Задача 2. Airflow DAG

**Файлы:**
- `airflow/dags/etl_reports_dag.py` — DAG для ETL-процесса
- `airflow/init_db.sql` — SQL скрипт инициализации ClickHouse
- `airflow/Dockerfile` — Docker образ для Airflow
- `airflow/requirements.txt` — зависимости Python

#### Структура DAG:

```
create_clickhouse_tables
         │
    ┌────┴────┐
    ▼         ▼
extract_crm  extract_telemetry
    │         │
    └────┬────┘
         ▼
  load_staging_tables
         │
         ▼
 transform_and_load_mart
         │
         ▼
    validate_data
```

#### Витрина `reports_mart`:

| Поле | Тип | Описание |
|------|-----|----------|
| user_id | String | ID пользователя |
| username | String | Логин |
| email | String | Email |
| first_name, last_name | String | ФИО |
| prosthetic_model | String | Модель протеза |
| report_date | Date | Дата отчёта |
| total_usage_hours | Float64 | Общее время использования |
| movement_count | UInt32 | Количество движений |
| avg_response_time_ms | Float64 | Среднее время отклика |
| battery_cycles | UInt32 | Циклы батареи |
| calibration_count | UInt32 | Калибровки |
| last_sync_at | DateTime | Последняя синхронизация |
| etl_processed_at | DateTime | Время обработки ETL |

**Расписание:** `0 2 * * *` (ежедневно в 02:00)

### Задача 3. Backend API

**Файлы:**
- `backend/app/main.py` — FastAPI приложение
- `backend/app/routers/reports.py` — роутер `/reports`
- `backend/app/services/clickhouse_service.py` — сервис для ClickHouse
- `backend/app/models/report.py` — модели данных
- `backend/Dockerfile` — Docker образ
- `backend/requirements.txt` — зависимости Python

#### API Endpoints:

| Метод | Endpoint | Описание |
|-------|----------|----------|
| GET | `/reports?user_id=...` | Получить отчёт по пользователю |
| GET | `/reports/status` | Статус данных и дата последнего ETL |
| GET | `/health` | Проверка здоровья сервиса |

#### Пример запроса:

```bash
GET /reports?user_id=prothetic1&date_from=2024-01-01&limit=30
```

#### Пример ответа:

```json
{
  "success": true,
  "user_id": "prothetic1",
  "reports": [
    {
      "user_id": "prothetic1",
      "username": "prothetic1",
      "prosthetic_model": "BionicHand Pro v2",
      "report_date": "2024-06-01",
      "total_usage_hours": 42.5,
      "movement_count": 3500,
      "avg_response_time_ms": 65.3,
      "battery_cycles": 7,
      "calibration_count": 2
    }
  ],
  "total_count": 1
}
```

### Задача 4. Ограничение доступа

**Файлы:**
- `backend/app/auth/keycloak.py` — валидация JWT токена
- `backend/app/routers/reports.py` — авторизация на endpoint

#### Как работает ограничение доступа:

1. Пользователь отправляет запрос с JWT токеном:
   ```
   Authorization: Bearer <access_token>
   ```

2. Backend валидирует токен через JWKS Keycloak

3. User ID извлекается из claim `sub` токена

4. Запрос к ClickHouse фильтруется по этому user_id:
   ```sql
   SELECT * FROM reports_mart WHERE user_id = :current_user
   ```

#### Ключевой принцип:

```python
# User ID берётся из токена, НЕ из параметров запроса!
user_id = current_user.username  # Из JWT токена

# Невозможно запросить чужой отчёт
reports = clickhouse_service.get_reports_by_user(user_id=user_id)
```

#### Защита:

- ❌ Без токена — 401 Unauthorized
- ❌ С чужим токеном — получит только свои данные
- ❌ Подделка user_id в параметрах — игнорируется
- ✅ Доступ только к собственным отчётам

### Задача 5. UI кнопка получения отчёта

**Файл:** `frontend/src/components/ReportPage.tsx`

#### Функциональность:

- ✅ Кнопка "Получить отчёт" для вызова API
- ✅ Фильтры по датам (дата с / дата по)
- ✅ Отображение данных в таблице
- ✅ Кнопка "Скачать JSON" для экспорта
- ✅ Отображение ошибок
- ✅ Информация о пользователе из токена
- ✅ Кнопки входа/выхода

#### Проверки:

- ❌ Без аутентификации — показывается кнопка "Войти"
- ✅ После входа — доступна кнопка "Получить отчёт"
- ✅ JWT токен автоматически добавляется к запросу

---

## Запуск проекта

```bash
docker-compose up -d
```

- Frontend: http://localhost:3000
- Keycloak: http://localhost:8080 (admin/admin)
