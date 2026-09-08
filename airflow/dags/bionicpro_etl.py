from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
import psycopg2
import clickhouse_connect

default_args = {
    'owner': 'bionicpro',
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

def extract_from_crm():
    conn = psycopg2.connect(
        host='crm_db',
        port=5432,
        database='crm_db',
        user='crm_user',
        password='crm_password'
    )
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            c.username,
            c.full_name,
            c.email,
            t.prosthesis_id,
            SUM(t.usage_hours) as total_usage_hours,
            SUM(t.battery_cycles) as total_battery_cycles,
            SUM(t.movements_count) as total_movements,
            MAX(t.recorded_at) as last_recorded_at
        FROM clients c
        JOIN prosthesis_telemetry t ON c.id = t.client_id
        GROUP BY c.username, c.full_name, c.email, t.prosthesis_id
    """)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows

def load_to_clickhouse(**context):
    rows = context['ti'].xcom_pull(task_ids='extract_from_crm')
    
    client = clickhouse_connect.get_client(
        host='clickhouse',
        port=8123,
        database='bionicpro'
    )

    client.command("""
        CREATE TABLE IF NOT EXISTS prosthesis_report (
            username String,
            full_name String,
            email String,
            prosthesis_id String,
            total_usage_hours Float64,
            total_battery_cycles Int64,
            total_movements Int64,
            last_recorded_at DateTime,
            updated_at DateTime DEFAULT now()
        ) ENGINE = ReplacingMergeTree(updated_at)
        ORDER BY (username, prosthesis_id)
    """)

    data = [
        [
            row[0], row[1], row[2], row[3],
            float(row[4]), int(row[5]), int(row[6]),
            row[7]
        ]
        for row in rows
    ]

    client.insert(
        'prosthesis_report',
        data,
        column_names=[
            'username', 'full_name', 'email', 'prosthesis_id',
            'total_usage_hours', 'total_battery_cycles',
            'total_movements', 'last_recorded_at'
        ]
    )
    print(f"Inserted {len(data)} rows into ClickHouse")

with DAG(
    dag_id='bionicpro_etl',
    default_args=default_args,
    description='ETL from CRM to ClickHouse',
    schedule_interval='0 6 * * *',
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=['bionicpro']
) as dag:

    extract = PythonOperator(
        task_id='extract_from_crm',
        python_callable=extract_from_crm
    )

    load = PythonOperator(
        task_id='load_to_clickhouse',
        python_callable=load_to_clickhouse,
        provide_context=True
    )

    extract >> load