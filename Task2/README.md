# BionicPRO — ETL и отчётность

## Быстрый старт

### 1. Запуск инфраструктуры

```bash
cd Task2
docker-compose up -d
```

Это поднимет:
- **Airflow Webserver** — http://localhost:8080 (логин: `admin` / пароль: `admin`)
- **Airflow Scheduler** — запуск DAG по расписанию
- **Airflow Metadata DB** — PostgreSQL на порту 5433
- **ClickHouse (OLAP)** — HTTP API на порту 8123, native на порту 9000

### 2. Настройка подключений

Подключения к источникам данных задаются через переменные окружения в `docker-compose.yml`:

| Connection ID | Назначение                  | Переменная окружения                  |
|---------------|-----------------------------|---------------------------------------|
| `sensor_db`   | БД датчиков (PostgreSQL)    | `AIRFLOW__CONNECTIONS__SENSOR_DB`     |
| `crm_db`      | CRM DB (Битрикс24)         | `AIRFLOW__CONNECTIONS__CRM_DB`        |
| `olap_db`     | ClickHouse (OLAP)           | `AIRFLOW__CONNECTIONS__OLAP_DB`       |

Замените значения на реальные строки подключения к вашим базам.

### 3. DAG — bionic_etl_reporting

**Расписание:** ежедневно в 03:00 UTC (`0 3 * * *`)

```
extract_sensor_data ─┐
                     ├──► transform_data ──► load_to_olap
extract_crm_data ────┘
```

| Таск                  | Описание                                                        |
|-----------------------|-----------------------------------------------------------------|
| `extract_sensor_data` | Извлечение телеметрии из PostgreSQL (инкрементально за день)    |
| `extract_crm_data`    | Извлечение справочника клиентов из CRM DB                      |
| `transform_data`      | Объединение по `user_id`, агрегация метрик телеметрии           |
| `load_to_olap`        | Загрузка витрины `fact_user_report` в ClickHouse                |

### 4. Витрина fact_user_report

DDL: `sql/create_fact_user_report.sql` (автоматически применяется при старте ClickHouse).

| Поле                    | Тип       | Описание                              |
|-------------------------|-----------|---------------------------------------|
| `user_id`               | UInt64    | ID пользователя (FK к CRM)           |
| `report_date`           | Date      | Дата отчёта                           |
| `session_count`         | UInt32    | Кол-во сессий за день                 |
| `avg_wear_time_min`     | Float64   | Среднее время ношения (мин)           |
| `total_gestures`        | UInt32    | Кол-во распознанных жестов            |
| `avg_myosignal_quality` | Float64   | Среднее качество миосигнала           |
| `order_status`          | String    | Статус заказа из CRM                  |
| `prosthesis_model`      | String    | Модель протеза                        |
| `last_contact_date`     | Date      | Дата последнего обращения             |

**Оптимизация доступа:**
- `ORDER BY (user_id, report_date)` — быстрые запросы по пользователю
- `PARTITION BY toYYYYMM(report_date)` — партиционирование по месяцам

## Структура файлов

```
Task2/
├── docker-compose.yml                        # Инфраструктура Airflow + ClickHouse
├── dags/
│   └── bionic_etl_reporting.py               # Airflow DAG (ETL-пайплайн)
├── sql/
│   └── create_fact_user_report.sql           # DDL витрины в ClickHouse
├── BionicPRO_C4_with_reporting.drawio.xml    # C4-схема с отчётностью
└── BionicPRO_ETL_reporting.drawio.xml        # Детальная схема ETL
```
