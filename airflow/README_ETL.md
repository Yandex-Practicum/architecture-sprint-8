# BionicPRO ETL Pipeline

## Обзор

ETL-процесс для подготовки витрины отчётности BionicPRO. Объединяет данные телеметрии с протезов и данные о клиентах из CRM-системы.

## Архитектура

```
┌─────────────────┐     ┌─────────────────┐
│    CRM DB       │     │  Telemetry DB   │
│  (PostgreSQL)   │     │  (PostgreSQL)   │
└────────┬────────┘     └────────┬────────┘
         │                       │
         │    ┌─────────────┐    │
         └────┤   Airflow   ├────┘
              │     DAG     │
              └──────┬──────┘
                     │
              ┌──────▼──────┐
              │  ClickHouse │
              │    (OLAP)   │
              └─────────────┘
```

## Запуск

### 1. Запуск всех сервисов
```bash
docker-compose up -d
```

### 2. Проверка статуса
```bash
docker-compose ps
```

### 3. Доступ к Airflow UI
- URL: http://localhost:8081
- Логин: admin
- Пароль: admin

### 4. Проверка DAG
В Airflow UI перейдите в раздел DAGs и найдите `bionicpro_reports_etl`.
DAG запускается автоматически каждые 15 минут.

## DAG: bionicpro_reports_etl

### Расписание
- **Cron**: `*/15 * * * *` (каждые 15 минут)
- **Catchup**: Отключен (обрабатываются только новые данные)

### Задачи

| Task ID                | Описание                              | Источник     |
|------------------------|---------------------------------------|--------------|
| extract_crm_data       | Извлечение данных клиентов и протезов | CRM DB       |
| extract_telemetry_data | Извлечение почасовой телеметрии       | Telemetry DB |
| transform_and_join     | JOIN данных по chip_id                | In-memory    |
| load_to_clickhouse     | Загрузка в витрину                    | ClickHouse   |

### Граф зависимостей
```
extract_crm_data ──┐
                   ├──> transform_and_join ──> load_to_clickhouse
extract_telemetry_data
```

## Схема данных

### Источник: CRM DB

**Таблица crm.customers**
- customer_id, external_id, first_name, last_name
- email, phone, region, branch

**Таблица crm.prostheses**
- prosthesis_id, serial_number, chip_id
- model_id, customer_id, status

**Представление crm.v_customer_prosthesis**
- Денормализованные данные клиент + протез

### Источник: Telemetry DB

**Таблица telemetry.raw_telemetry**
- Сырые данные телеметрии с частотой ~1 сек

**Таблица telemetry.hourly_stats**
- Агрегированная статистика по часам

**Представление telemetry.v_hourly_telemetry**
- Почасовая телеметрия для ETL

### Целевая витрина: ClickHouse

**Таблица reports.user_prosthesis_stats**
```sql
user_id             String,           -- ID пользователя
prosthesis_id       UInt32,           -- ID протеза
chip_id             String,           -- ID чипа
report_date         Date,             -- Дата
report_hour         UInt8,            -- Час (0-23)
customer_name       String,           -- ФИО клиента
prosthesis_model    String,           -- Модель протеза
movements_count     UInt32,           -- Количество движений
successful_movements UInt32,          -- Успешные движения
avg_response_time   Float32,          -- Среднее время отклика (мс)
avg_battery_level   Float32,          -- Средний уровень заряда (%)
error_count         UInt32,           -- Количество ошибок
etl_processed_at    DateTime          -- Время обработки ETL
```

## Мониторинг

### Airflow UI
- Статус DAG runs
- Логи задач
- График выполнения

### ClickHouse
```sql
-- Проверка последних данных
SELECT
    user_id,
    report_date,
    count() as hours,
    sum(movements_count) as total_movements
FROM reports.user_prosthesis_stats
WHERE report_date = today()
GROUP BY user_id, report_date
ORDER BY total_movements DESC;

-- Статистика по дням
SELECT
    report_date,
    count(DISTINCT user_id) as users,
    sum(movements_count) as total_movements,
    avg(avg_response_time) as avg_response
FROM reports.user_prosthesis_stats
GROUP BY report_date
ORDER BY report_date DESC
LIMIT 7;
```

## Troubleshooting

### DAG не запускается
1. Проверьте, что DAG включен в UI (toggle = ON)
2. Проверьте логи scheduler: `docker-compose logs airflow-scheduler`
3. Проверьте connections в Admin -> Connections

### Ошибки извлечения данных
1. Проверьте доступность БД: `docker-compose ps`
2. Проверьте connections в Airflow
3. Смотрите логи конкретной задачи в UI

### Ошибки загрузки в ClickHouse
1. Проверьте доступность ClickHouse: `docker-compose logs clickhouse`
2. Проверьте, что схема создана: `clickhouse-client --query "SHOW TABLES FROM reports"`

## Конфигурация

### Airflow Connections

| ID                     | Type     | Host         | Port | DB           |
|------------------------|----------|--------------|------|--------------|
| bionicpro_crm_db       | postgres | crm_db       | 5432 | crm_db       |
| bionicpro_telemetry_db | postgres | telemetry_db | 5432 | telemetry_db |
| bionicpro_clickhouse   | generic  | clickhouse   | 9000 | reports      |

### Параметры ETL
- `ETL_LOOKBACK_HOURS = 2` - Период обработки данных
- `ETL_BATCH_SIZE = 10000` - Размер пакета для вставки
