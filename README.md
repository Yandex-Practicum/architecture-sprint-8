J# BionicPRO Analytics Platform

Аналитическая платформа для мониторинга и отчетности бионических протезов.

## Компоненты системы

### 1. Источники данных (OLTP)

#### CRM Database (PostgreSQL)
- **Назначение**: Хранение мастер-данных о клиентах и протезах
- **Таблицы**:
  - `crm.customers` - клиенты компании
  - `crm.prostheses` - бионические протезы
- **Хранение**: Постоянное

#### Telemetry Database (PostgreSQL)
- **Назначение**: Прием событий телеметрии в реальном времени
- **Таблицы**:
  - `telemetry.events` - события от протезов (4G модуль → ESP32)
- **Хранение**: 30-90 дней (затем архивация)
- **Объем**: ~1-10 млн событий/день

### 2. ETL Pipeline (Apache Airflow)

#### DAG: `etl_bionicpro_reports`
- **Расписание**: Ежедневно в 02:00 MSK
- **Стратегия**: Инкрементальная загрузка (вчерашний день)

**Этапы:**
1. **Extract** (параллельно):
   - Клиенты из CRM
   - Протезы из CRM
   - Агрегированная телеметрия за вчера

2. **Load Staging**:
   - Truncate & Load для CRM данных
   - Staging таблицы в ClickHouse

3. **Update Dimensions**:
   - Upsert в `dim_user` через ReplacingMergeTree

4. **Load Facts**:
   - Upsert агрегированной телеметрии в `fact_telemetry_daily`

5. **Optimize**:
   - Принудительное слияние партиций (OPTIMIZE FINAL)

### 3. Аналитическое хранилище (ClickHouse)

#### Слои данных:

**Staging Layer** (временные данные)
- `stg_crm_customers` - клиенты из CRM
- `stg_crm_prostheses` - протезы из CRM
- TTL: 7 дней

**Dimensional Layer** (измерения)
- `dim_user` - пользователи (SCD Type 1)
- Engine: ReplacingMergeTree

**Fact Layer** (факты)
- `fact_telemetry_daily` - дневная агрегация телеметрии
- Партиционирование: по месяцам
- Engine: ReplacingMergeTree
- TTL: 2 года

**Reporting Layer** (витрины)
- `vw_user_telemetry_daily` - основная витрина для API
- `vw_prosthesis_performance` - производительность протезов
- `vw_critical_performance` - критические показатели

### 4. Reports API (FastAPI)

- **Эндпоинты**:
  - `GET /reports` - получение отчетов пользователя
  - `GET /healthz` - проверка здоровья
- **Аутентификация**: Keycloak JWT
- **Авторизация**: Доступ только к своим данным
- **Источник данных**: ClickHouse `vw_user_telemetry_daily`

### 5. Frontend (React)

- **Аутентификация**: Keycloak OAuth2.0 + PKCE
- **Функционал**: Просмотр отчетов по телеметрии
- **Фильтры**: Дата, ID протеза

## Запуск системы

### Предварительные требования
- Docker & Docker Compose
- 8GB RAM минимум
- Порты: 3000, 8000, 8080, 8081, 8123, 9000

### Запуск

```bash
# Запуск всех сервисов
docker compose up -d

# Проверка статуса
docker compose ps

# Логи
docker compose logs -f
```

### Доступ к сервисам

- **Frontend**: http://localhost:3000
- **Reports API**: http://localhost:8000
- **Keycloak**: http://localhost:8080 (admin/admin)
- **Airflow**: http://localhost:8081 (admin/admin)
- **ClickHouse HTTP**: http://localhost:8123

### Заполнение тестовыми данными

```bash
# Сделать скрипт исполняемым
chmod +x seed-user-data.sh

# Заполнить данные для пользователя
./seed-user-data.sh <keycloak_user_id>

# Пример
./seed-user-data.sh cbbbd1f1-ab80-4661-9be6-e9659d9fb277
```

### Запуск ETL

1. Открыть Airflow UI: http://localhost:8081
2. Найти DAG `etl_bionicpro_reports`
3. Включить DAG (toggle)
4. Trigger DAG вручную или дождаться расписания (02:00)

## Мониторинг

### Проверка данных в ClickHouse

```bash
# Подключение к ClickHouse
docker exec -it clickhouse clickhouse-client \
  --user clickhouse_user \
  --password clickhouse_pass

# Проверка данных
SELECT COUNT(*) FROM default.dim_user;
SELECT COUNT(*) FROM default.fact_telemetry_daily;
SELECT * FROM default.vw_user_telemetry_daily LIMIT 10;
```

### Проверка источников

```bash
# CRM
docker exec -it crm_db psql -U crm_user -d crm_db \
  -c "SELECT COUNT(*) FROM crm.customers;"

# Telemetry
docker exec -it telemetry_db psql -U telemetry_user -d telemetry_db \
  -c "SELECT COUNT(*) FROM telemetry.events;"
```

## Производительность

### Метрики

- **Время отклика протеза**: < 100ms (целевое)
- **Объем телеметрии**: ~1-10 млн событий/день
- **Время ETL**: ~5-15 минут
- **Время запроса API**: < 500ms

### Оптимизация
- **ClickHouse**: Партиционирование по месяцам
- **PostgreSQL**: Индексы на часто используемые поля
- **Airflow**: Параллельное выполнение задач
- **API**: Кэширование JWKS (1 час)

## Безопасность
- Аутентификация через Keycloak (OAuth2.0 + PKCE)
- JWT валидация (RS256, signature, exp, iss)
- Авторизация: доступ только к своим данным
- CORS настроен для фронтенда
- Все credentials через environment variables
