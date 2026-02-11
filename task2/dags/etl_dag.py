from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.operators.postgres import PostgresOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
import requests
import json

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2023, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'etl_crm_telemetry',
    default_args=default_args,
    description='ETL process for CRM and telemetry data',
    schedule_interval='@daily',
    catchup=False,
)

def extract_crm_data():
    # Simulate extracting CRM data
    # In real scenario, this would be an API call or database query
    crm_data = [
        {'client_id': 1, 'name': 'Client A', 'email': 'a@example.com'},
        {'client_id': 2, 'name': 'Client B', 'email': 'b@example.com'},
    ]
    return crm_data

def load_crm_to_olap(**context):
    crm_data = context['ti'].xcom_pull(task_ids='extract_crm')
    print(f"CRM data: {crm_data}")
    hook = PostgresHook(postgres_conn_id='olap_conn')
    conn = hook.get_conn()
    cursor = conn.cursor()
    # Create table if not exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS crm_clients (
            client_id INTEGER PRIMARY KEY,
            name VARCHAR(255),
            email VARCHAR(255)
        );
    """)
    # Insert data
    for client in crm_data:
        cursor.execute("""
            INSERT INTO crm_clients (client_id, name, email)
            VALUES (%s, %s, %s)
            ON CONFLICT (client_id) DO NOTHING;
        """, (client['client_id'], client['name'], client['email']))
    conn.commit()
    cursor.close()
    conn.close()

def extract_telemetry_data():
    # Simulate extracting telemetry data from Redis or API
    # In real scenario, connect to Redis or telemetry service
    telemetry_data = [
        {'client_id': 1, 'event': 'login', 'timestamp': '2023-01-01 10:00:00'},
        {'client_id': 1, 'event': 'view_page', 'timestamp': '2023-01-01 10:05:00'},
        {'client_id': 2, 'event': 'login', 'timestamp': '2023-01-01 11:00:00'},
    ]
    return telemetry_data

def load_telemetry_to_olap(**context):
    telemetry_data = context['ti'].xcom_pull(task_ids='extract_telemetry')
    hook = PostgresHook(postgres_conn_id='olap_conn')
    conn = hook.get_conn()
    cursor = conn.cursor()
    # Create table if not exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS telemetry_events (
            id SERIAL PRIMARY KEY,
            client_id INTEGER,
            event VARCHAR(255),
            timestamp TIMESTAMP
        );
    """)
    # Insert data
    for event in telemetry_data:
        cursor.execute("""
            INSERT INTO telemetry_events (client_id, event, timestamp)
            VALUES (%s, %s, %s);
        """, (event['client_id'], event['event'], event['timestamp']))
    conn.commit()
    cursor.close()
    conn.close()

create_datamart = PostgresOperator(
    task_id='create_datamart',
    postgres_conn_id='olap_conn',
    sql="""
        CREATE TABLE IF NOT EXISTS client_datamart (
            client_id INTEGER PRIMARY KEY,
            name VARCHAR(255),
            email VARCHAR(255),
            total_events INTEGER,
            last_event TIMESTAMP
        );

        INSERT INTO client_datamart (client_id, name, email, total_events, last_event)
        SELECT
            c.client_id,
            c.name,
            c.email,
            COUNT(t.id) as total_events,
            MAX(t.timestamp) as last_event
        FROM crm_clients c
        LEFT JOIN telemetry_events t ON c.client_id = t.client_id
        GROUP BY c.client_id, c.name, c.email
        ON CONFLICT (client_id) DO UPDATE SET
            total_events = EXCLUDED.total_events,
            last_event = EXCLUDED.last_event;
    """,
    dag=dag,
)

extract_crm = PythonOperator(
    task_id='extract_crm',
    python_callable=extract_crm_data,
    dag=dag,
)

load_crm = PythonOperator(
    task_id='load_crm',
    python_callable=load_crm_to_olap,
    dag=dag,
)

extract_telemetry = PythonOperator(
    task_id='extract_telemetry',
    python_callable=extract_telemetry_data,
    dag=dag,
)

load_telemetry = PythonOperator(
    task_id='load_telemetry',
    python_callable=load_telemetry_to_olap,
    dag=dag,
)

# Set dependencies
extract_crm >> load_crm
extract_telemetry >> load_telemetry
[load_crm, load_telemetry] >> create_datamart