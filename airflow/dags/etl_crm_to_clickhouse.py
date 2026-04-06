"""
ETL DAG для загрузки данных из CRM в ClickHouse
Извлекает данные о клиентах и протезах из PostgreSQL CRM,
преобразует их и загружает в ClickHouse для аналитики
"""
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from datetime import datetime, timedelta
import os

from clickhouse_driver import Client as ClickHouseClient

default_args = {
    'owner': 'bionicpro',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}


def extract_crm_clients(**context):
    """Извлечение данных о клиентах из CRM"""
    pg_hook = PostgresHook(postgres_conn_id='crm_postgres')
    
    sql = """
    SELECT 
        buyer_id,
        full_name,
        email,
        phone,
        registration_date,
        last_visit_date,
        status
    FROM crm_clients
    WHERE status = 'active'
    """
    
    connection = pg_hook.get_conn()
    cursor = connection.cursor()
    cursor.execute(sql)
    
    clients = cursor.fetchall()
    cursor.close()
    connection.close()
    
    # Сохраняем данные в XCom
    context['task_instance'].xcom_push(key='clients', value=clients)
    print(f"Извлечено {len(clients)} клиентов из CRM")


def extract_crm_prosthetics(**context):
    """Извлечение данных о протезах из CRM"""
    pg_hook = PostgresHook(postgres_conn_id='crm_postgres')
    
    sql = """
    SELECT 
        prosthetic_id,
        buyer_id,
        prosthetic_type,
        manufacture_date,
        delivery_date,
        serial_number,
        warranty_months,
        price
    FROM crm_prosthetics
    """
    
    connection = pg_hook.get_conn()
    cursor = connection.cursor()
    cursor.execute(sql)
    
    prosthetics = cursor.fetchall()
    cursor.close()
    connection.close()
    
    context['task_instance'].xcom_push(key='prosthetics', value=prosthetics)
    print(f"Извлечено {len(prosthetics)} протезов из CRM")


def load_clients_to_clickhouse(**context):
    """Загрузка данных о клиентах в ClickHouse"""
    clients = context['task_instance'].xcom_pull(task_ids='extract_clients', key='clients')
    
    if not clients:
        print("Нет данных для загрузки")
        return
    
    ch_host = os.getenv('CLICKHOUSE_HOST', 'clickhouse')
    ch_port = int(os.getenv('CLICKHOUSE_PORT', 9000))
    ch_user = os.getenv('CLICKHOUSE_USER', 'analytics_user')
    ch_password = os.getenv('CLICKHOUSE_PASSWORD', 'analytics_password')
    ch_db = os.getenv('CLICKHOUSE_DB', 'analytics_db')
    
    client = ClickHouseClient(
        host=ch_host,
        port=ch_port,
        user=ch_user,
        password=ch_password,
        database=ch_db
    )
    
    # Подготавливаем данные для вставки
    data_to_insert = [
        (
            int(row[0]),  # buyer_id
            str(row[1]),  # full_name
            str(row[2]),  # email
            str(row[3]) if row[3] else '',  # phone
            row[4],  # registration_date
            row[5] if row[5] else datetime.now(),  # last_visit_date
            str(row[6])  # status
        )
        for row in clients
    ]
    
    # Вставляем данные
    client.execute(
        'INSERT INTO client_dimension (buyer_id, full_name, email, phone, registration_date, last_visit_date, status) VALUES',
        data_to_insert
    )
    
    print(f"Загружено {len(data_to_insert)} клиентов в ClickHouse")


def load_prosthetics_to_clickhouse(**context):
    """Загрузка данных о протезах в ClickHouse"""
    prosthetics = context['task_instance'].xcom_pull(task_ids='extract_prosthetics', key='prosthetics')
    
    if not prosthetics:
        print("Нет данных для загрузки")
        return
    
    ch_host = os.getenv('CLICKHOUSE_HOST', 'clickhouse')
    ch_port = int(os.getenv('CLICKHOUSE_PORT', 9000))
    ch_user = os.getenv('CLICKHOUSE_USER', 'analytics_user')
    ch_password = os.getenv('CLICKHOUSE_PASSWORD', 'analytics_password')
    ch_db = os.getenv('CLICKHOUSE_DB', 'analytics_db')
    
    client = ClickHouseClient(
        host=ch_host,
        port=ch_port,
        user=ch_user,
        password=ch_password,
        database=ch_db
    )
    
    # Подготавливаем данные для вставки
    data_to_insert = [
        (
            int(row[0]),  # prosthetic_id
            int(row[1]),  # buyer_id
            str(row[2]),  # prosthetic_type
            row[3],  # manufacture_date
            row[4] if row[4] else datetime.now().date(),  # delivery_date
            str(row[5]),  # serial_number
            int(row[6]),  # warranty_months
            float(row[7])  # price
        )
        for row in prosthetics
    ]
    
    # Вставляем данные
    client.execute(
        'INSERT INTO prosthetic_dimension (prosthetic_id, buyer_id, prosthetic_type, manufacture_date, delivery_date, serial_number, warranty_months, price) VALUES',
        data_to_insert
    )
    
    print(f"Загружено {len(data_to_insert)} протезов в ClickHouse")


def build_reports_mart(**context):
    """Построение витрины данных для отчетов пользователей"""
    ch_host = os.getenv('CLICKHOUSE_HOST', 'clickhouse')
    ch_port = int(os.getenv('CLICKHOUSE_PORT', 9000))
    ch_user = os.getenv('CLICKHOUSE_USER', 'analytics_user')
    ch_password = os.getenv('CLICKHOUSE_PASSWORD', 'analytics_password')
    ch_db = os.getenv('CLICKHOUSE_DB', 'analytics_db')
    
    client = ClickHouseClient(
        host=ch_host,
        port=ch_port,
        user=ch_user,
        password=ch_password,
        database=ch_db
    )
    
    # SQL для построения витрины отчетов
    # Объединяем данные из телеметрии с информацией о клиентах и протезах
    sql = """
    INSERT INTO user_reports_mart 
    (buyer_id, full_name, email, prosthetic_type, serial_number, 
     total_usage_hours, total_movements, total_errors, avg_battery_level, 
     last_telemetry_date, report_period_start, report_period_end)
    SELECT 
        c.buyer_id,
        c.full_name,
        c.email,
        p.prosthetic_type,
        p.serial_number,
        sum(t.usage_hours) as total_usage_hours,
        sum(t.movement_count) as total_movements,
        sum(t.error_count) as total_errors,
        avg(t.battery_level) as avg_battery_level,
        max(t.event_timestamp) as last_telemetry_date,
        min(t.sync_date) as report_period_start,
        max(t.sync_date) as report_period_end
    FROM telemetry_facts t
    JOIN client_dimension c ON t.buyer_id = c.buyer_id
    JOIN prosthetic_dimension p ON t.buyer_id = p.buyer_id AND t.prosthetic_serial = p.serial_number
    WHERE t.sync_date >= today() - INTERVAL 30 DAY
    GROUP BY c.buyer_id, c.full_name, c.email, p.prosthetic_type, p.serial_number
    """
    
    client.execute(sql)
    print("Витрина отчетов успешно обновлена")


def invalidate_reports_s3_cache(**context):
    """После ETL сбрасываем кеш отчётов в S3 (и косвенно CDN после истечения TTL)."""
    url = os.getenv("REPORTS_WEBHOOK_URL")
    secret = os.getenv("REPORTS_WEBHOOK_SECRET")
    if not url or not secret:
        print("REPORTS_WEBHOOK_URL / REPORTS_WEBHOOK_SECRET не заданы, пропуск webhook")
        return
    import requests

    try:
        resp = requests.post(
            url,
            headers={"X-Webhook-Secret": secret},
            timeout=30,
        )
        resp.raise_for_status()
        print("Webhook инвалидации кеша отчётов:", resp.json())
    except Exception as e:
        print(f"Предупреждение: не удалось вызвать webhook инвалидации: {e}")


# Определяем DAG
with DAG(
    'etl_crm_to_clickhouse',
    default_args=default_args,
    description='ETL процесс для загрузки данных из CRM в ClickHouse',
    schedule_interval='0 2 * * *',  # Запускается ежедневно в 2:00
    catchup=False,
    tags=['etl', 'crm', 'clickhouse', 'bionicpro'],
) as dag:
    
    # Задача 1: Извлечение данных о клиентах
    extract_clients = PythonOperator(
        task_id='extract_clients',
        python_callable=extract_crm_clients,
        provide_context=True,
    )
    
    # Задача 2: Извлечение данных о протезах
    extract_prosthetics = PythonOperator(
        task_id='extract_prosthetics',
        python_callable=extract_crm_prosthetics,
        provide_context=True,
    )
    
    # Задача 3: Загрузка клиентов в ClickHouse
    load_clients = PythonOperator(
        task_id='load_clients',
        python_callable=load_clients_to_clickhouse,
        provide_context=True,
    )
    
    # Задача 4: Загрузка протезов в ClickHouse
    load_prosthetics = PythonOperator(
        task_id='load_prosthetics',
        python_callable=load_prosthetics_to_clickhouse,
        provide_context=True,
    )
    
    # Задача 5: Построение витрины отчетов
    build_mart = PythonOperator(
        task_id='build_reports_mart',
        python_callable=build_reports_mart,
        provide_context=True,
    )

    invalidate_reports_cache = PythonOperator(
        task_id='invalidate_reports_cache',
        python_callable=invalidate_reports_s3_cache,
        provide_context=True,
    )
    
    # Определяем зависимости задач
    # Сначала извлекаем данные параллельно
    extract_clients >> load_clients
    extract_prosthetics >> load_prosthetics
    
    # Затем после загрузки строим витрину отчетов и сбрасываем кеш отчётов в S3
    [load_clients, load_prosthetics] >> build_mart >> invalidate_reports_cache
