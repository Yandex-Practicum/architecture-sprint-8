# BionicPRO - Архитектурный проект

Проект системы отчётов для компании BionicPRO, производящей бионические протезы.

## Структура проекта

```
.
├── docker-compose.yaml          # Единый docker-compose для всех сервисов
├── frontend/                     # React фронтенд
│   ├── src/
│   │   ├── App.tsx
│   │   └── components/
│   │       └── ReportPage.tsx
│   └── Dockerfile
├── task2/
│   ├── backend/                  # Java Spring Boot API
│   │   ├── src/
│   │   └── Dockerfile
│   └── airflow/                  # ETL-процесс Apache Airflow
│       ├── dags/
│       │   └── reports_etl_dag.py
│       └── scripts/
│           └── create_data_mart.sql
└── keycloak/                     # Конфигурация Keycloak
    └── realm-export.json
```

## Быстрый запуск

### Запуск всех сервисов одной командой:

```bash
docker-compose up -d
```

Это запустит:
- **Frontend** (React) - http://localhost:3000
- **Backend API** (Java Spring Boot) - http://localhost:8000
- **Keycloak** (Аутентификация) - http://localhost:8080
- **ClickHouse** (OLAP БД) - http://localhost:8123
- **PostgreSQL** (Телеметрия) - localhost:5432
- **Airflow Webserver** - http://localhost:8081
- **Airflow Scheduler** - автоматический запуск

### Остановка всех сервисов:

```bash
docker-compose down
```

### Просмотр логов:

```bash
# Все сервисы
docker-compose logs -f

# Конкретный сервис
docker-compose logs -f backend
docker-compose logs -f airflow-scheduler
```

## Доступ к сервисам

После запуска доступны:

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **Keycloak Admin**: http://localhost:8080 (admin/admin)
- **Airflow UI**: http://localhost:8081 (admin/admin)
- **ClickHouse**: http://localhost:8123

## Первоначальная настройка

### 1. Создание витрины в ClickHouse

После запуска ClickHouse выполните:

```bash
docker exec -i bionicpro-clickhouse clickhouse-client < task2/airflow/scripts/create_data_mart.sql
```

Или через веб-интерфейс ClickHouse на http://localhost:8123

### 2. Настройка Airflow подключений

В Airflow UI (http://localhost:8081) создайте подключения:

**PostgreSQL** (Connection Id: `postgres_default`):
- Type: `Postgres`
- Host: `postgres`
- Schema: `bionicpro`
- Login: `bionicpro_user`
- Password: `bionicpro_password`
- Port: `5432`

**ClickHouse** (через переменные окружения, уже настроено)

**CRM HTTP** (Connection Id: `crm_http`):
- Type: `HTTP`
- Host: ваш CRM API адрес

### 3. Активация DAG в Airflow

1. Откройте http://localhost:8081
2. Войдите (admin/admin)
3. Найдите DAG `reports_etl_dag`
4. Включите его (переключатель слева)

## Использование

### Получение отчёта через Frontend

1. Откройте http://localhost:3000
2. Войдите через Keycloak
3. Нажмите кнопку "Get Report"
4. Просмотрите данные в таблице
5. При необходимости экспортируйте в CSV

### API запросы

```bash
# Получить отчёты (требуется JWT токен)
curl -H "Authorization: Bearer <TOKEN>" \
     http://localhost:8000/api/reports

# С фильтром по датам
curl -H "Authorization: Bearer <TOKEN>" \
     "http://localhost:8000/api/reports?startDate=2024-01-01&endDate=2024-01-31"
```

## Компоненты системы

### Frontend
- React + TypeScript
- Интеграция с Keycloak (PKCE)
- Запрос отчётов через API
- Отображение данных в таблице
- Экспорт в CSV

### Backend
- Java Spring Boot 3.1.5
- REST API `/api/reports`
- JWT аутентификация
- RBAC: пользователь видит только свои данные
- Подключение к ClickHouse

### ETL-процесс
- Apache Airflow 2.7.0
- Извлечение данных из PostgreSQL и CRM
- Трансформация и объединение
- Загрузка в ClickHouse витрину
- Расписание: ежедневно в 2:00

### Базы данных
- **PostgreSQL**: телеметрия с протезов
- **ClickHouse**: витрина отчётности (OLAP)
- **PostgreSQL (Keycloak)**: данные Keycloak
- **PostgreSQL (Airflow)**: метаданные Airflow

## Переменные окружения

Основные настройки можно изменить через переменные окружения в `docker-compose.yaml`:

- `CLICKHOUSE_URL` - адрес ClickHouse
- `POSTGRES_*` - настройки PostgreSQL
- `REACT_APP_*` - настройки фронтенда

## Устранение проблем

### Backend не запускается
- Проверьте логи: `docker-compose logs backend`
- Убедитесь, что ClickHouse запущен
- Проверьте порт 8000 на занятость

### Frontend не подключается к API
- Проверьте `REACT_APP_API_URL` в docker-compose
- Убедитесь, что backend запущен и здоров

### Airflow DAG не запускается
- Проверьте подключения в Airflow UI
- Проверьте логи: `docker-compose logs airflow-scheduler`
- Убедитесь, что витрина создана в ClickHouse

## Разработка

### Локальная разработка Backend

```bash
cd task2/backend
mvn spring-boot:run
```

### Локальная разработка Frontend

```bash
cd frontend
npm install
npm start
```

## Лицензия

Проект создан в рамках учебного курса.
