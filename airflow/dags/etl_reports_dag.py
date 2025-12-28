"""
ETL DAG для формирования витрины отчётов BionicPRO.

Процесс:
1. EXTRACT: Извлечение данных из CRM (клиенты) и PostgreSQL (телеметрия)
2. TRANSFORM: Объединение и агрегация данных по пользователям
3. LOAD: Запись в ClickHouse (витрина reports_mart)

Расписание: ежедневно в 02:00
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.providers.http.hooks.http import HttpHook
import clickhouse_connect
import json
import logging

logger = logging.getLogger(__name__)

# Конфигурация
CLICKHOUSE_HOST = 'clickhouse'
CLICKHOUSE_PORT = 8123
CLICKHOUSE_DB = 'bionicpro'

default_args = {
    'owner': 'bionicpro',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
}


def create_clickhouse_tables():
    """Создание таблиц в ClickHouse если не существуют."""
    client = clickhouse_connect.get_client(
        host=CLICKHOUSE_HOST,
        port=CLICKHOUSE_PORT,
        database=CLICKHOUSE_DB
    )
    
    # Витрина отчётов
    client.command('''
        CREATE TABLE IF NOT EXISTS reports_mart (
            user_id String,
            username String,
            email String,
            first_name String,
            last_name String,
            prosthetic_model String,
            report_date Date,
            total_usage_hours Float64,
            movement_count UInt32,
            avg_response_time_ms Float64,
            battery_cycles UInt32,
            calibration_count UInt32,
            last_sync_at DateTime,
            etl_processed_at DateTime DEFAULT now()
        ) ENGINE = MergeTree()
        ORDER BY (user_id, report_date)
    ''')
    
    # Staging таблица для данных CRM
    client.command('''
        CREATE TABLE IF NOT EXISTS stg_crm_customers (
            user_id String,
            username String,
            email String,
            first_name String,
            last_name String,
            prosthetic_model String,
            created_at DateTime,
            updated_at DateTime
        ) ENGINE = MergeTree()
        ORDER BY user_id
    ''')
    
    # Staging таблица для телеметрии
    client.command('''
        CREATE TABLE IF NOT EXISTS stg_telemetry (
            user_id String,
            event_date Date,
            usage_hours Float64,
            movement_count UInt32,
            response_time_ms Float64,
            battery_cycle UInt32,
            calibration_flag UInt8,
            sync_timestamp DateTime
        ) ENGINE = MergeTree()
        ORDER BY (user_id, event_date)
    ''')
    
    logger.info("ClickHouse tables created successfully")


def extract_crm_data(**context):
    """
    Извлечение данных о клиентах из CRM.
    В реальном проекте здесь будет запрос к API Битрикс24.
    Для демо используем mock данные.
    """
    execution_date = context['execution_date']
    
    # Mock данные клиентов (в реальности - запрос к CRM API)
    customers = [
        {
            'user_id': 'prothetic1',
            'username': 'prothetic1',
            'email': 'prothetic1@example.com',
            'first_name': 'Prothetic',
            'last_name': 'One',
            'prosthetic_model': 'BionicHand Pro v2',
            'created_at': '2024-01-15 10:00:00',
            'updated_at': '2024-06-01 12:00:00'
        },
        {
            'user_id': 'prothetic2',
            'username': 'prothetic2',
            'email': 'prothetic2@example.com',
            'first_name': 'Prothetic',
            'last_name': 'Two',
            'prosthetic_model': 'BionicArm Elite v1',
            'created_at': '2024-02-20 14:30:00',
            'updated_at': '2024-05-15 09:00:00'
        },
        {
            'user_id': 'prothetic3',
            'username': 'prothetic3',
            'email': 'prothetic3@example.com',
            'first_name': 'Prothetic',
            'last_name': 'Three',
            'prosthetic_model': 'BionicHand Pro v3',
            'created_at': '2024-03-10 11:00:00',
            'updated_at': '2024-06-10 16:00:00'
        }
    ]
    
    # Сохранение в XCom для следующего шага
    context['ti'].xcom_push(key='crm_customers', value=customers)
    logger.info(f"Extracted {len(customers)} customers from CRM")
    return customers


def extract_telemetry_data(**context):
    """
    Извлечение данных телеметрии из PostgreSQL.
    В реальном проекте здесь будет запрос к БД телеметрии.
    """
    execution_date = context['execution_date']
    report_date = execution_date.strftime('%Y-%m-%d')
    
    # Mock данные телеметрии (в реальности - запрос к PostgreSQL)
    # Генерируем данные за последние 7 дней
    telemetry = []
    
    users = ['prothetic1', 'prothetic2', 'prothetic3']
    
    for user_id in users:
        for day_offset in range(7):
            event_date = (execution_date - timedelta(days=day_offset)).strftime('%Y-%m-%d')
            telemetry.append({
                'user_id': user_id,
                'event_date': event_date,
                'usage_hours': round(2.5 + (hash(f"{user_id}{event_date}") % 50) / 10, 2),
                'movement_count': 100 + (hash(f"{user_id}{event_date}") % 500),
                'response_time_ms': round(50 + (hash(f"{user_id}{event_date}") % 100) / 2, 2),
                'battery_cycle': 1 if hash(f"{user_id}{event_date}") % 3 == 0 else 0,
                'calibration_flag': 1 if hash(f"{user_id}{event_date}") % 7 == 0 else 0,
                'sync_timestamp': f"{event_date} 23:59:00"
            })
    
    context['ti'].xcom_push(key='telemetry_data', value=telemetry)
    logger.info(f"Extracted {len(telemetry)} telemetry records")
    return telemetry


def load_staging_tables(**context):
    """Загрузка данных в staging таблицы ClickHouse."""
    customers = context['ti'].xcom_pull(key='crm_customers')
    telemetry = context['ti'].xcom_pull(key='telemetry_data')
    
    client = clickhouse_connect.get_client(
        host=CLICKHOUSE_HOST,
        port=CLICKHOUSE_PORT,
        database=CLICKHOUSE_DB
    )
    
    # Очистка staging таблиц
    client.command('TRUNCATE TABLE stg_crm_customers')
    client.command('TRUNCATE TABLE stg_telemetry')
    
    # Загрузка клиентов
    if customers:
        customer_rows = [
            [c['user_id'], c['username'], c['email'], c['first_name'], 
             c['last_name'], c['prosthetic_model'], c['created_at'], c['updated_at']]
            for c in customers
        ]
        client.insert('stg_crm_customers', customer_rows,
                     column_names=['user_id', 'username', 'email', 'first_name', 
                                  'last_name', 'prosthetic_model', 'created_at', 'updated_at'])
        logger.info(f"Loaded {len(customers)} customers to staging")
    
    # Загрузка телеметрии
    if telemetry:
        telemetry_rows = [
            [t['user_id'], t['event_date'], t['usage_hours'], t['movement_count'],
             t['response_time_ms'], t['battery_cycle'], t['calibration_flag'], t['sync_timestamp']]
            for t in telemetry
        ]
        client.insert('stg_telemetry', telemetry_rows,
                     column_names=['user_id', 'event_date', 'usage_hours', 'movement_count',
                                  'response_time_ms', 'battery_cycle', 'calibration_flag', 'sync_timestamp'])
        logger.info(f"Loaded {len(telemetry)} telemetry records to staging")


def transform_and_load_mart(**context):
    """
    Трансформация данных и загрузка в витрину reports_mart.
    Объединяет данные клиентов с агрегированной телеметрией.
    """
    execution_date = context['execution_date']
    report_date = execution_date.strftime('%Y-%m-%d')
    
    client = clickhouse_connect.get_client(
        host=CLICKHOUSE_HOST,
        port=CLICKHOUSE_PORT,
        database=CLICKHOUSE_DB
    )
    
    # Удаление данных за текущую дату (идемпотентность)
    client.command(f"ALTER TABLE reports_mart DELETE WHERE report_date = '{report_date}'")
    
    # Трансформация и загрузка в витрину
    # Объединяем данные клиентов с агрегированной телеметрией
    transform_query = f'''
        INSERT INTO reports_mart (
            user_id, username, email, first_name, last_name, prosthetic_model,
            report_date, total_usage_hours, movement_count, avg_response_time_ms,
            battery_cycles, calibration_count, last_sync_at
        )
        SELECT 
            c.user_id,
            c.username,
            c.email,
            c.first_name,
            c.last_name,
            c.prosthetic_model,
            toDate('{report_date}') as report_date,
            COALESCE(SUM(t.usage_hours), 0) as total_usage_hours,
            COALESCE(SUM(t.movement_count), 0) as movement_count,
            COALESCE(AVG(t.response_time_ms), 0) as avg_response_time_ms,
            COALESCE(SUM(t.battery_cycle), 0) as battery_cycles,
            COALESCE(SUM(t.calibration_flag), 0) as calibration_count,
            COALESCE(MAX(t.sync_timestamp), now()) as last_sync_at
        FROM stg_crm_customers c
        LEFT JOIN stg_telemetry t ON c.user_id = t.user_id
        GROUP BY 
            c.user_id, c.username, c.email, c.first_name, 
            c.last_name, c.prosthetic_model
    '''
    
    client.command(transform_query)
    
    # Проверка результата
    result = client.query(f"SELECT count(*) FROM reports_mart WHERE report_date = '{report_date}'")
    count = result.result_rows[0][0]
    logger.info(f"Loaded {count} records to reports_mart for {report_date}")


def validate_data(**context):
    """Валидация загруженных данных."""
    execution_date = context['execution_date']
    report_date = execution_date.strftime('%Y-%m-%d')
    
    client = clickhouse_connect.get_client(
        host=CLICKHOUSE_HOST,
        port=CLICKHOUSE_PORT,
        database=CLICKHOUSE_DB
    )
    
    # Проверка наличия данных
    result = client.query(f'''
        SELECT 
            count(*) as total_records,
            count(DISTINCT user_id) as unique_users
        FROM reports_mart 
        WHERE report_date = '{report_date}'
    ''')
    
    total_records, unique_users = result.result_rows[0]
    
    if total_records == 0:
        raise ValueError(f"No records loaded for {report_date}")
    
    logger.info(f"Validation passed: {total_records} records, {unique_users} unique users")
    
    return {
        'report_date': report_date,
        'total_records': total_records,
        'unique_users': unique_users
    }


# Определение DAG
with DAG(
    dag_id='etl_reports_bionicpro',
    default_args=default_args,
    description='ETL процесс для формирования витрины отчётов BionicPRO',
    schedule_interval='0 2 * * *',  # Ежедневно в 02:00
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['bionicpro', 'etl', 'reports'],
) as dag:
    
    # Задача 1: Создание таблиц
    task_create_tables = PythonOperator(
        task_id='create_clickhouse_tables',
        python_callable=create_clickhouse_tables,
    )
    
    # Задача 2: Извлечение данных из CRM
    task_extract_crm = PythonOperator(
        task_id='extract_crm_data',
        python_callable=extract_crm_data,
    )
    
    # Задача 3: Извлечение телеметрии
    task_extract_telemetry = PythonOperator(
        task_id='extract_telemetry_data',
        python_callable=extract_telemetry_data,
    )
    
    # Задача 4: Загрузка в staging
    task_load_staging = PythonOperator(
        task_id='load_staging_tables',
        python_callable=load_staging_tables,
    )
    
    # Задача 5: Трансформация и загрузка в витрину
    task_transform_load = PythonOperator(
        task_id='transform_and_load_mart',
        python_callable=transform_and_load_mart,
    )
    
    # Задача 6: Валидация
    task_validate = PythonOperator(
        task_id='validate_data',
        python_callable=validate_data,
    )
    
    # Определение зависимостей
    task_create_tables >> [task_extract_crm, task_extract_telemetry]
    [task_extract_crm, task_extract_telemetry] >> task_load_staging
    task_load_staging >> task_transform_load >> task_validate

