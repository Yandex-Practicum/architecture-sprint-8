# Быстрый старт BionicPRO

## 🚀 Запуск всех сервисов одной командой

```bash
docker-compose up -d
```

Это запустит все компоненты системы:
- Frontend (React) - http://localhost:3000
- Backend API (Java) - http://localhost:8000
- Keycloak - http://localhost:8080
- Airflow - http://localhost:8081
- ClickHouse - http://localhost:8123
- PostgreSQL - localhost:5432

## 📋 После запуска

### 1. Создание витрины в ClickHouse

```bash
docker exec -i bionicpro-clickhouse clickhouse-client < task2/airflow/scripts/create_data_mart.sql
```

### 2. Настройка Airflow подключений

Откройте http://localhost:8081 (admin/admin) и создайте подключения:

**PostgreSQL** (`postgres_default`):
- Host: `postgres`
- Database: `bionicpro`
- User: `bionicpro_user`
- Password: `bionicpro_password`

```bash
docker exec bionicpro-airflow-webserver airflow connections add 'postgres_default' \
  --conn-type 'postgres' \
  --conn-host 'postgres' \
  --conn-schema 'bionicpro' \
  --conn-login 'bionicpro_user' \
  --conn-password 'bionicpro_password' \
  --conn-port '5432'
```

### 3. Активация DAG

В Airflow UI включите DAG `reports_etl_dag`

## 🔍 Проверка работы

1. **Frontend**: http://localhost:3000
   - Войдите через Keycloak
   - Нажмите "Get Report"

2. **Backend API**: http://localhost:8000/api/reports
   - Требуется JWT токен

3. **Airflow**: http://localhost:8081
   - Логин: admin / admin

## 🛑 Остановка

```bash
docker-compose down
```

## 📊 Просмотр логов

```bash
# Все сервисы
docker-compose logs -f

# Конкретный сервис
docker-compose logs -f backend
docker-compose logs -f airflow-scheduler
```

