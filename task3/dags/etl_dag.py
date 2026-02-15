from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.operators.postgres import PostgresOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
import requests
import json
import boto3
import os

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
        {'client_id': 'john@example.com', 'name': 'John Doe', 'email': 'john@example.com'},
        {'client_id': 'alex@example.com', 'name': 'Alex Smith', 'email': 'alex@example.com'},
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
        DROP TABLE IF EXISTS crm_clients;
        CREATE TABLE crm_clients (
            client_id VARCHAR(255) PRIMARY KEY,
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
        {'client_id': 'john@example.com', 'event': 'login', 'timestamp': '2023-01-01 10:00:00'},
        {'client_id': 'john@example.com', 'event': 'view_page', 'timestamp': '2023-01-01 10:05:00'},
        {'client_id': 'alex@example.com', 'event': 'login', 'timestamp': '2023-01-01 11:00:00'},
    ]
    return telemetry_data

def load_telemetry_to_olap(**context):
    telemetry_data = context['ti'].xcom_pull(task_ids='extract_telemetry')
    hook = PostgresHook(postgres_conn_id='olap_conn')
    conn = hook.get_conn()
    cursor = conn.cursor()
    # Create table if not exists
    cursor.execute("""
        DROP TABLE IF EXISTS telemetry_events;
        CREATE TABLE telemetry_events (
            id SERIAL PRIMARY KEY,
            client_id VARCHAR(255),
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

def clear_s3_reports():
    """Clear all cached reports from S3 after data update"""
    s3_client = boto3.client(
        's3',
        endpoint_url=os.getenv('S3_ENDPOINT', 'http://minio:9000'),
        aws_access_key_id=os.getenv('S3_ACCESS_KEY', 'minioadmin'),
        aws_secret_access_key=os.getenv('S3_SECRET_KEY', 'minioadmin'),
        region_name='us-east-1'
    )
    bucket = os.getenv('S3_BUCKET', 'reports')
    try:
        # List all objects in reports/ prefix
        response = s3_client.list_objects_v2(Bucket=bucket, Prefix='reports/')
        if 'Contents' in response:
            for obj in response['Contents']:
                s3_client.delete_object(Bucket=bucket, Key=obj['Key'])
                print(f"Deleted {obj['Key']}")
    except Exception as e:
        print(f"Error clearing S3: {e}")

create_datamart = PostgresOperator(
    task_id='create_datamart',
    postgres_conn_id='olap_conn',
    sql="""
        DROP TABLE IF EXISTS client_datamart;
        CREATE TABLE client_datamart (
            client_id VARCHAR(255) PRIMARY KEY,
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

clear_s3 = PythonOperator(
    task_id='clear_s3_reports',
    python_callable=clear_s3_reports,
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
[load_crm, load_telemetry] >> create_datamart >> clear_s3