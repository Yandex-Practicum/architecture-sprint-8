"""
BionicPRO ETL Pipeline
======================
DAG для загрузки данных из источников (CRM, Telemetry) в ClickHouse OLAP

Архитектура:
1. Extract: Извлечение данных из PostgreSQL (CRM, Telemetry)
2. Transform: Агрегация телеметрии
3. Load: Загрузка в ClickHouse
"""

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.hooks.base import BaseHook
from datetime import datetime, timedelta
import psycopg2
import clickhouse_connect
import os
from typing import Dict, List, Any

# ============================================================================
# КОНФИГУРАЦИЯ ПОДКЛЮЧЕНИЙ
# ============================================================================

def get_crm_connection():
    """Получить подключение к CRM PostgreSQL"""
    try:
        conn = BaseHook.get_connection('CRM_DB')
        return f"postgresql://{conn.login}:{conn.password}@{conn.host}:{conn.port}/{conn.schema}"
    except:
        return os.getenv('CRM_DB_CONN', 'postgresql://crm_user:crm_password@crm_db:5432/crm_db')

def get_telemetry_connection():
    """Получить подключение к Telemetry PostgreSQL"""
    try:
        conn = BaseHook.get_connection('TELEMETRY_DB')
        return f"postgresql://{conn.login}:{conn.password}@{conn.host}:{conn.port}/{conn.schema}"
    except:
        return os.getenv('TELEMETRY_DB_CONN', 'postgresql://telemetry_user:telemetry_password@telemetry_db:5432/telemetry_db')

def get_clickhouse_client():
    """Получить клиент ClickHouse"""
    try:
        conn = BaseHook.get_connection('CLICKHOUSE_HTTP')
        return clickhouse_connect.get_client(
            host=conn.host,
            port=conn.port or 8123,
            username=conn.login or 'clickhouse_user',
            password=conn.password or 'clickhouse_pass',
            database=conn.schema or 'default'
        )
    except:
        return clickhouse_connect.get_client(
            host=os.getenv('CLICKHOUSE_HOST', 'clickhouse'),
            port=int(os.getenv('CLICKHOUSE_PORT', '8123')),
            username=os.getenv('CLICKHOUSE_USER', 'clickhouse_user'),
            password=os.getenv('CLICKHOUSE_PASSWORD', 'clickhouse_pass'),
            database=os.getenv('CLICKHOUSE_DB', 'default')
        )

# ============================================================================
# EXTRACT: ИЗВЛЕЧЕНИЕ ДАННЫХ ИЗ ИСТОЧНИКОВ
# ============================================================================

def extract_crm_customers(**context):
    """
    Извлечение клиентов из CRM
    Полная загрузка (Full Load) - все активные клиенты
    """
    print("==> Извлечение клиентов из CRM...")
    
    conn = psycopg2.connect(get_crm_connection())
    cursor = conn.cursor()
    
    query = """
        SELECT 
            customer_id,
            user_external_id,
            full_name,
            email,
            phone,
            country,
            created_at,
            updated_at
        FROM crm.customers
        ORDER BY customer_id
    """
    
    cursor.execute(query)
    rows = cursor.fetchall()
    
    customers = []
    for row in rows:
        customers.append({
            'customer_id': row[0],
            'user_external_id': row[1],
            'full_name': row[2],
            'email': row[3],
            'phone': row[4] or '',
            'country': row[5],
            'created_at': row[6],
            'updated_at': row[7]
        })
    
    cursor.close()
    conn.close()
    
    print(f"Извлечено {len(customers)} клиентов")
    context['ti'].xcom_push(key='customers', value=customers)

def extract_crm_prostheses(**context):
    """
    Извлечение протезов из CRM
    Полная загрузка активных протезов
    """
    print("==> Извлечение протезов из CRM...")
    
    conn = psycopg2.connect(get_crm_connection())
    cursor = conn.cursor()
    
    query = """
        SELECT 
            prosthesis_id,
            customer_id,
            model,
            activated_at,
            deactivated_at,
            updated_at
        FROM crm.prostheses
        WHERE deactivated_at IS NULL  -- Только активные
        ORDER BY prosthesis_id
    """
    
    cursor.execute(query)
    rows = cursor.fetchall()
    
    prostheses = []
    for row in rows:
        prostheses.append({
            'prosthesis_id': row[0],
            'customer_id': row[1],
            'model': row[2],
            'activated_at': row[3],
            'deactivated_at': row[4],
            'updated_at': row[5]
        })
    
    cursor.close()
    conn.close()
    
    print(f"Извлечено {len(prostheses)} активных протезов")
    context['ti'].xcom_push(key='prostheses', value=prostheses)

def extract_telemetry_events(**context):
    """
    Извлечение событий телеметрии
    Инкрементальная загрузка - только за вчерашний день
    """
    execution_date = context['execution_date']
    target_date = (execution_date - timedelta(days=1)).date()
    
    print(f"==> Извлечение телеметрии за {target_date}...")
    
    conn = psycopg2.connect(get_telemetry_connection())
    cursor = conn.cursor()
    
    query = """
        SELECT 
            prosthesis_id,
            DATE(event_time) as event_date,
            COUNT(*) as events_cnt,
            AVG(response_ms) as avg_response_ms,
            MIN(response_ms) as min_response_ms,
            MAX(response_ms) as max_response_ms,
            PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY response_ms) as p95_response_ms,
            SUM(CASE WHEN is_error THEN 1 ELSE 0 END) as err_cnt,
            AVG(battery_level) as battery_avg,
            MIN(battery_level) as min_battery
        FROM telemetry.events
        WHERE DATE(event_time) = %s
        GROUP BY prosthesis_id, DATE(event_time)
    """
    
    cursor.execute(query, (target_date,))
    rows = cursor.fetchall()
    
    events = []
    for row in rows:
        events.append({
            'prosthesis_id': row[0],
            'event_date': row[1],
            'events_cnt': row[2],
            'avg_response_ms': float(row[3]),
            'min_response_ms': float(row[4]),
            'max_response_ms': float(row[5]),
            'p95_response_ms': float(row[6]),
            'err_cnt': row[7],
            'battery_avg': float(row[8]),
            'min_battery': float(row[9])
        })
    
    cursor.close()
    conn.close()
    
    print(f"Извлечено {len(events)} агрегированных записей за {target_date}")
    context['ti'].xcom_push(key='telemetry_events', value=events)

# ============================================================================
# LOAD: ЗАГРУЗКА В CLICKHOUSE
# ============================================================================

def load_staging_customers(**context):
    """
    Загрузка клиентов в staging таблицу ClickHouse
    Стратегия: Truncate & Load (полная перезагрузка)
    """
    customers = context['ti'].xcom_pull(task_ids='extract_crm_customers', key='customers')
    
    if not customers:
        print("Нет данных для загрузки")
        return
    
    print(f"==> Загрузка {len(customers)} клиентов в ClickHouse staging...")
    
    client = get_clickhouse_client()
    
    # Очистка staging таблицы
    client.command("TRUNCATE TABLE default.stg_crm_customers")
    
    # Подготовка данных для вставки
    data = []
    for c in customers:
        data.append([
            c['customer_id'],
            c['user_external_id'],
            c['full_name'],
            c['email'],
            c['phone'],
            c['country'],
            c['created_at'],
            c['updated_at']
        ])
    
    # Вставка данных
    client.insert(
        'default.stg_crm_customers',
        data,
        column_names=['customer_id', 'user_external_id', 'full_name', 'email', 
                     'phone', 'country', 'created_at', 'updated_at']
    )
    
    client.close()
    print(f"Загружено {len(customers)} клиентов в staging")

def load_staging_prostheses(**context):
    """
    Загрузка протезов в staging таблицу ClickHouse
    """
    prostheses = context['ti'].xcom_pull(task_ids='extract_crm_prostheses', key='prostheses')
    
    if not prostheses:
        print("Нет данных для загрузки")
        return
    
    print(f"==> Загрузка {len(prostheses)} протезов в ClickHouse staging...")
    
    client = get_clickhouse_client()
    
    # Очистка staging таблицы
    client.command("TRUNCATE TABLE default.stg_crm_prostheses")
    
    # Подготовка данных
    data = []
    for p in prostheses:
        data.append([
            p['prosthesis_id'],
            p['customer_id'],
            p['model'],
            p['activated_at'],
            p['deactivated_at'],
            p['updated_at']
        ])
    
    # Вставка данных
    client.insert(
        'default.stg_crm_prostheses',
        data,
        column_names=['prosthesis_id', 'customer_id', 'model', 
                     'activated_at', 'deactivated_at', 'updated_at']
    )
    
    client.close()
    print(f"Загружено {len(prostheses)} протезов в staging")

def update_dim_user(**context):
    """
    Обновление измерения пользователей из staging
    Стратегия: Upsert через ReplacingMergeTree
    """
    print("==> Обновление dim_user из staging...")
    
    client = get_clickhouse_client()
    
    # Вставка/обновление через INSERT SELECT
    query = """
        INSERT INTO default.dim_user
        SELECT 
            customer_id,
            user_external_id,
            full_name,
            email,
            country,
            updated_at
        FROM default.stg_crm_customers
    """
    
    client.command(query)
    
    # Получение статистики
    count = client.command("SELECT COUNT(*) FROM default.dim_user FINAL")
    
    client.close()
    print(f"Измерение dim_user обновлено. Всего записей: {count}")

def load_fact_telemetry(**context):
    """
    Загрузка агрегированной телеметрии в факт-таблицу
    Стратегия: Upsert через ReplacingMergeTree
    """
    events = context['ti'].xcom_pull(task_ids='extract_telemetry_events', key='telemetry_events')
    prostheses = context['ti'].xcom_pull(task_ids='extract_crm_prostheses', key='prostheses')
    
    if not events:
        print("Нет событий телеметрии для загрузки")
        return
    
    # Создаем маппинг prosthesis_id -> customer_id
    prosthesis_to_customer = {p['prosthesis_id']: p['customer_id'] for p in prostheses}
    
    print(f"==> Загрузка {len(events)} записей телеметрии в fact таблицу...")
    
    client = get_clickhouse_client()
    
    # Подготовка данных с добавлением customer_id
    data = []
    for e in events:
        customer_id = prosthesis_to_customer.get(e['prosthesis_id'])
        if customer_id:
            data.append([
                e['event_date'],
                customer_id,
                e['prosthesis_id'],
                e['events_cnt'],
                e['avg_response_ms'],
                e['err_cnt'],
                e['battery_avg'],
                e['min_response_ms'],
                e['max_response_ms'],
                e['p95_response_ms'],
                e['min_battery'],
                datetime.now()  # updated_at
            ])
    
    if data:
        # Вставка данных (ReplacingMergeTree автоматически обновит дубликаты)
        client.insert(
            'default.fact_telemetry_daily',
            data,
            column_names=['event_date', 'customer_id', 'prosthesis_id', 'events_cnt',
                         'avg_response_ms', 'err_cnt', 'battery_avg', 'min_response_ms',
                         'max_response_ms', 'p95_response_ms', 'min_battery', 'updated_at']
        )
        
        print(f"Загружено {len(data)} записей в fact_telemetry_daily")
    else:
        print("Нет данных для загрузки (протезы не найдены в CRM)")
    
    client.close()

def optimize_tables(**context):
    """
    Оптимизация таблиц ClickHouse
    Принудительное слияние партиций для применения ReplacingMergeTree
    """
    print("==> Оптимизация таблиц ClickHouse...")
    
    client = get_clickhouse_client()
    
    # Оптимизация измерений
    client.command("OPTIMIZE TABLE default.dim_user FINAL")
    
    # Оптимизация фактов (только последняя партиция)
    execution_date = context['execution_date']
    target_date = (execution_date - timedelta(days=1)).date()
    partition = target_date.strftime('%Y%m')
    
    client.command(f"OPTIMIZE TABLE default.fact_telemetry_daily PARTITION {partition} FINAL")
    
    client.close()
    print("Оптимизация завершена")

# ============================================================================
# ОПРЕДЕЛЕНИЕ DAG
# ============================================================================

default_args = {
    'owner': 'bionicpro',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'etl_bionicpro_reports',
    default_args=default_args,
    description='ETL pipeline: PostgreSQL (CRM, Telemetry) → ClickHouse (OLAP)',
    schedule_interval='0 2 * * *',  # Ежедневно в 02:00
    catchup=False,
    max_active_runs=1,
    tags=['bionicpro', 'etl', 'clickhouse', 'olap'],
)

# ============================================================================
# ЗАДАЧИ DAG
# ============================================================================

# Extract задачи (параллельно)
task_extract_customers = PythonOperator(
    task_id='extract_crm_customers',
    python_callable=extract_crm_customers,
    dag=dag,
)

task_extract_prostheses = PythonOperator(
    task_id='extract_crm_prostheses',
    python_callable=extract_crm_prostheses,
    dag=dag,
)

task_extract_telemetry = PythonOperator(
    task_id='extract_telemetry_events',
    python_callable=extract_telemetry_events,
    dag=dag,
)

# Load staging задачи (параллельно после extract)
task_load_staging_customers = PythonOperator(
    task_id='load_staging_customers',
    python_callable=load_staging_customers,
    dag=dag,
)

task_load_staging_prostheses = PythonOperator(
    task_id='load_staging_prostheses',
    python_callable=load_staging_prostheses,
    dag=dag,
)

# Update dimensions (после staging)
task_update_dim_user = PythonOperator(
    task_id='update_dim_user',
    python_callable=update_dim_user,
    dag=dag,
)

# Load facts (после всех extract и prostheses)
task_load_fact_telemetry = PythonOperator(
    task_id='load_fact_telemetry',
    python_callable=load_fact_telemetry,
    dag=dag,
)

# Optimize (финальная задача)
task_optimize = PythonOperator(
    task_id='optimize_tables',
    python_callable=optimize_tables,
    dag=dag,
)

# ============================================================================
# ЗАВИСИМОСТИ ЗАДАЧ
# ============================================================================

# Extract фаза (параллельно)
[task_extract_customers, task_extract_prostheses, task_extract_telemetry]

# Load staging (после extract)
task_extract_customers >> task_load_staging_customers
task_extract_prostheses >> task_load_staging_prostheses

# Update dimensions (после staging)
task_load_staging_customers >> task_update_dim_user

# Load facts (после extract telemetry и prostheses)
[task_extract_telemetry, task_extract_prostheses] >> task_load_fact_telemetry

# Optimize (после всех загрузок)
[task_update_dim_user, task_load_fact_telemetry] >> task_optimize
