# ETL-процесс для витрины отчётности BionicPRO

## Описание

Этот проект содержит Airflow DAG для автоматизации ETL-процесса подготовки витрины отчётности. Процесс объединяет данные телеметрии из PostgreSQL и данные клиентов из CRM-системы, загружая результат в OLAP базу данных ClickHouse.

## Структура проекта

```
task2/airflow/
├── dags/
│   └── reports_etl_dag.py      # Основной DAG для ETL-процесса
├── scripts/
│   └── create_data_mart.sql     # SQL скрипт для создания витрины
├── requirements.txt             # Зависимости Python
└── README.md                    # Документация
```

## Компоненты ETL-процесса

### 1. Extract (Извлечение)

- **extract_telemetry**: Извлекает агрегированные данные телеметрии из PostgreSQL за последние 24 часа
- **extract_crm_data**: Получает данные клиентов из CRM-системы через HTTP API

### 2. Transform (Трансформация)

- **transform_data**: Объединяет данные телеметрии и CRM, вычисляет дополнительные метрики:
  - `usage_hours`: Время использования в часах
  - `actions_per_hour`: Количество действий в час
  - `efficiency_score`: Оценка эффективности использования протеза

### 3. Load (Загрузка)

- **create_data_mart_table**: Создаёт таблицу витрины в ClickHouse (если не существует)
- **load_to_clickhouse**: Загружает подготовленные данные в витрину

## Структура витрины данных

Витрина `reports_data_mart` содержит следующие данные:

### Метрики использования
- `total_actions`: Общее количество действий
- `avg_response_time`, `max_response_time`, `min_response_time`: Время отклика протеза
- `grasp_count`, `release_count`, `flex_count`: Количество действий по типам

### Состояние устройства
- `avg_battery_level`, `min_battery_level`: Уровень заряда батареи

### Время использования
- `total_usage_seconds`: Общее время использования
- `usage_hours`: Время использования в часах
- `actions_per_hour`: Плотность использования

### Данные пользователя
- `user_id`, `email`, `first_name`, `last_name`: Информация о пользователе
- `prosthesis_id`: Идентификатор протеза
- `order_date`, `status`: Данные из CRM

### Оптимизация

Таблица оптимизирована для быстрого доступа:
- **Партиционирование**: По месяцам (`toYYYYMM(report_date)`)
- **Сортировка**: По `user_id`, `report_date`, `prosthesis_id`
- **Первичный ключ**: `(user_id, report_date)` для быстрого поиска по пользователю

## Настройка Airflow

### 1. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 2. Настройка подключений

В Airflow UI создайте следующие подключения:

#### PostgreSQL
- **Connection Id**: `postgres_default`
- **Connection Type**: `Postgres`
- **Host**: `postgres_host`
- **Schema**: `bionicpro`
- **Login**: `postgres_user`
- **Password**: `postgres_password`
- **Port**: `5432`

#### CRM API
- **Connection Id**: `crm_http`
- **Connection Type**: `HTTP`
- **Host**: `crm.bionicpro.local`
- **Port**: `80` или `443`
- **Login**: `crm_user` (если требуется)
- **Password**: `crm_password` (если требуется)

#### ClickHouse
- **Connection Id**: `clickhouse_default`
- **Connection Type**: `Generic`
- **Host**: `clickhouse`
- **Port**: `9000`
- **Login**: `default`
- **Password**: `` (пусто)

### 3. Создание витрины в ClickHouse

Выполните SQL скрипт для создания витрины:

```bash
clickhouse-client < scripts/create_data_mart.sql
```

Или через Airflow:

```bash
airflow tasks test reports_etl_dag create_data_mart_table 2024-01-01
```

## Расписание запуска

DAG настроен на ежедневный запуск в **2:00 ночи**:

```python
schedule_interval='0 2 * * *'
```

Это позволяет:
- Обработать все данные за предыдущий день
- Подготовить витрину до начала рабочего дня
- Избежать нагрузки на систему в пиковые часы

### Изменение расписания

Для изменения расписания отредактируйте параметр `schedule_interval` в DAG:

```python
# Ежедневно в 3:00
schedule_interval='0 3 * * *'

# Каждые 6 часов
schedule_interval='0 */6 * * *'

# Еженедельно по понедельникам в 1:00
schedule_interval='0 1 * * 1'
```

## Мониторинг и логирование

Все задачи логируют свою работу:
- Количество извлечённых записей
- Ошибки при подключении к источникам данных
- Статус загрузки данных

Логи доступны в Airflow UI в разделе "Logs" для каждой задачи.

## Обработка ошибок

DAG настроен с:
- **retries**: 2 попытки повтора
- **retry_delay**: 5 минут между попытками
- **email_on_failure**: Отключено (можно включить при необходимости)

## Тестирование

### Тестирование отдельных задач

```bash
# Тест извлечения телеметрии
airflow tasks test reports_etl_dag extract_telemetry 2024-01-01

# Тест извлечения CRM данных
airflow tasks test reports_etl_dag extract_crm_data 2024-01-01

# Тест трансформации
airflow tasks test reports_etl_dag transform_data 2024-01-01

# Тест загрузки
airflow tasks test reports_etl_dag load_to_clickhouse 2024-01-01
```

### Запуск всего DAG

```bash
airflow dags trigger reports_etl_dag
```

## Примеры запросов к витрине

### Получить отчёт по пользователю за период

```sql
SELECT *
FROM bionicpro_reports.reports_data_mart
WHERE user_id = 123
  AND report_date BETWEEN '2024-01-01' AND '2024-01-31'
ORDER BY report_date DESC;
```

### Статистика использования по всем пользователям

```sql
SELECT
    user_id,
    email,
    sum(total_actions) as total_actions,
    avg(avg_response_time) as avg_response_time,
    sum(usage_hours) as total_hours,
    avg(efficiency_score) as avg_efficiency
FROM bionicpro_reports.reports_data_mart
WHERE report_date >= today() - 30
GROUP BY user_id, email
ORDER BY total_actions DESC;
```

### Топ пользователей по эффективности

```sql
SELECT
    user_id,
    email,
    avg(efficiency_score) as efficiency,
    sum(total_actions) as actions,
    sum(usage_hours) as hours
FROM bionicpro_reports.reports_data_mart
WHERE report_date >= today() - 7
GROUP BY user_id, email
ORDER BY efficiency DESC
LIMIT 10;
```

## Дальнейшее развитие

Возможные улучшения:
1. Добавление инкрементальной загрузки (только новые данные)
2. Реализация обработки ошибок с уведомлениями
3. Добавление метрик качества данных
4. Создание дополнительных материализованных представлений
5. Оптимизация запросов для больших объёмов данных

