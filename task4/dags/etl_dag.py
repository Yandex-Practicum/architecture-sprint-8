from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from clickhouse_driver import Client
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
    client = Client(host='clickhouse', port=9000, database='default', user='default', password='')
    # Insert data
    for client_data in crm_data:
        client.execute("""
            INSERT INTO crm_clients (client_id, name, email)
            VALUES
        """, [client_data])
    client.disconnect()

def extract_telemetry_data():
    # Simulate extracting telemetry data from Redis or API
    # In real scenario, connect to Redis or telemetry service
    telemetry_data = [
        {'id': 1, 'client_id': 'john@example.com', 'event': 'login', 'timestamp': '2023-01-01 10:00:00'},
        {'id': 2, 'client_id': 'john@example.com', 'event': 'view_page', 'timestamp': '2023-01-01 10:05:00'},
        {'id': 3, 'client_id': 'alex@example.com', 'event': 'login', 'timestamp': '2023-01-01 11:00:00'},
    ]
    return telemetry_data

def load_telemetry_to_olap(**context):
    telemetry_data = context['ti'].xcom_pull(task_ids='extract_telemetry')
    client = Client(host='clickhouse', port=9000, database='default', user='default', password='')
    # Insert data
    for event in telemetry_data:
        client.execute("""
            INSERT INTO telemetry_events (id, client_id, event, timestamp)
            VALUES
        """, [(event['id'], event['client_id'], event['event'], event['timestamp'])])
    client.disconnect()

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

def create_datamart():
    client = Client(host='clickhouse', port=9000, database='default', user='default', password='')
    client.execute("""
        INSERT INTO client_datamart (client_id, name, email, total_events, last_event)
        SELECT
            c.client_id,
            c.name,
            c.email,
            count(t.id) as total_events,
            max(t.timestamp) as last_event
        FROM crm_clients c
        LEFT JOIN telemetry_events t ON c.client_id = t.client_id
        GROUP BY c.client_id, c.name, c.email
    """)
    client.disconnect()

create_datamart_task = PythonOperator(
    task_id='create_datamart',
    python_callable=create_datamart,
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
[load_crm, load_telemetry] >> create_datamart_task >> clear_s3