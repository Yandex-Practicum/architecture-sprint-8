# Задача 2: Airflow ETL DAG

Эта задача реализует ETL-процесс с использованием Apache Airflow для извлечения данных из CRM-системы, загрузки их в OLAP базу данных и создания витрины данных, объединяющей данные CRM и телеметрии.

## Архитектура

- **Данные CRM**: Симулированные данные клиентов (client_id, name, email)
- **Данные телеметрии**: Симулированные события пользователей (client_id, event, timestamp)
- **OLAP база данных**: Экземпляр PostgreSQL для хранения сырых данных и витрины
- **Витрина данных**: Таблица `client_datamart` с агрегированной телеметрией по клиентам

## Сервисы

- `airflow_db`: PostgreSQL для метаданных Airflow
- `olap_db`: PostgreSQL для OLAP данных
- `airflow_webserver`: Интерфейс Airflow на порту 8082
- `airflow_scheduler`: Планировщик Airflow

## Детали DAG

- **ID DAG**: `etl_crm_telemetry`
- **Расписание**: Ежедневно (@daily)
- **Задачи**:
  1. `extract_crm`: Извлечение данных CRM
  2. `load_crm`: Загрузка данных CRM в OLAP
  3. `extract_telemetry`: Извлечение данных телеметрии
  4. `load_telemetry`: Загрузка данных телеметрии в OLAP
  5. `create_datamart`: Создание/обновление витрины данных

## Схема витрины данных

```sql
CREATE TABLE client_datamart (
    client_id INTEGER PRIMARY KEY,
    name VARCHAR(255),
    email VARCHAR(255),
    total_events INTEGER,
    last_event TIMESTAMP
);
```

## Запуск системы

1. Запустите сервисы: `docker-compose up -d`
2. Доступ к интерфейсу Airflow: http://localhost:8082
3. DAG будет запускаться ежедневно автоматически
4. Для ручного запуска используйте интерфейс Airflow

## Примечания

- Извлечение CRM и телеметрии симулировано
- В продакшене замените на реальные подключения к API/базам данных
- OLAP база данных доступна на порту 5435


# Reports API Backend

Эта задача реализует бэкенд-сервис на Python с API для получения отчётов по пользователям из OLAP базы данных.

## Архитектура

- **Фреймворк**: FastAPI
- **База данных**: PostgreSQL (OLAP) с витриной `client_datamart`
- **API**: `/reports` — POST эндпоинт для получения отчёта по `client_id`

## Сервисы

- `reports_api`: FastAPI приложение на порту 8083
- `olap_db`: PostgreSQL с данными витрины

## API Эндпоинты

### POST /reports
- **Описание**: Возвращает отчёт по пользователю из витрины.
- **Тело запроса**:
  ```json
  {
    "client_id": 1
  }
  ```
- **Ответ**:
  ```json
  {
    "client_id": 1,
    "name": "Client A",
    "email": "a@example.com",
    "total_events": 2,
    "last_event": "2023-01-01T10:05:00"
  }
  ```
- **Ошибки**: 404 если клиент не найден, 500 при ошибке БД.

## Запуск

1. Перейдите в папку `task3`.
2. Запустите: `docker-compose up -d`
3. API доступно на http://localhost:8083
4. Документация API: http://localhost:8083/docs

## Тестирование

Используйте curl или Postman:

```bash
curl -X POST "http://localhost:8083/reports" \
     -H "Content-Type: application/json" \
     -d '{"client_id": 1}'
```

## Примечания

- Данные берутся из витрины `client_datamart`, созданной в задаче 2.
- Нет сложных вычислений — только быстрый запрос из готовой таблицы.