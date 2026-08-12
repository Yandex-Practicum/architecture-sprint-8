from airflow import DAG
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import logging
import clickhouse_connect

default_args = {
    'owner': 'airflow',
    'start_date': datetime(2023, 1, 1),
    'retries': 1,
    'retry_delay': timedelta(minutes=2),
}

dag = DAG(
    'etl_prosthesis_reports_mart',
    default_args=default_args,
    description='ETL: Объединение телеметрии (PG) и CRM для отчетов',
    schedule_interval='@hourly',
    catchup=False,
    tags=['bionicpro', 'reporting'],
)

def extract_and_transform(**context):
    pg_hook = PostgresHook(postgres_conn_id='postgres_bionic')
    sql = "SELECT user_id, prosthesis_id, recorded_at, movement_type, battery_level FROM prosthesis_telemetry"
    try:
        telemetry_records = pg_hook.get_records(sql)
    except Exception as e:
        logging.warning(f"Ошибка при чтении из PG: {e}")
        telemetry_records = []

    crm_mock_data = {
        "user_123": {"name": "Иван Иванов", "region": "Москва"},
        "user_456": {"name": "Петр Петров", "region": "Новосибирск"},
    }

    transformed_data = []
    for row in telemetry_records:
        user_id, prosthesis_id, recorded_at, movement_type, battery_level = row
        user_info = crm_mock_data.get(str(user_id), {"name": "Unknown", "region": "Unknown"})
        
        transformed_data.append({
            'user_id': str(user_id),
            'prosthesis_id': str(prosthesis_id),
            'recorded_at': recorded_at,  # <-- ИСПРАВЛЕНО: не конвертируем в строку
            'movement_type': str(movement_type),
            'battery_level': float(battery_level) if battery_level else 0.0,
            'crm_user_name': user_info['name'],
            'crm_region': user_info['region']
        })
    
    context['ti'].xcom_push(key='transformed_data', value=transformed_data)
    logging.info(f"Подготовлено {len(transformed_data)} записей")

def load_to_clickhouse(**context):
    ti = context['ti']
    data_to_load = ti.xcom_pull(key='transformed_data', task_ids='extract_and_transform')
    
    if not data_to_load:
        logging.info("Нет данных для загрузки")
        return

    client = clickhouse_connect.get_client(
        host='clickhouse',
        port=8123,
        username='default',
        password='secret',
        database='bionicpro'
    )
    
    columns = ['user_id', 'prosthesis_id', 'recorded_at', 'movement_type', 'battery_level', 'crm_user_name', 'crm_region']
    data_tuples = [
        (
            row['user_id'],
            row['prosthesis_id'],
            row['recorded_at'],
            row['movement_type'],
            row['battery_level'],
            row['crm_user_name'],
            row['crm_region']
        )
        for row in data_to_load
    ]
    
    client.insert('prosthesis_reports_mart', data_tuples, column_names=columns)
    logging.info(f"Успешно загружено {len(data_tuples)} записей в ClickHouse")

task_extract_transform = PythonOperator(
    task_id='extract_and_transform',
    python_callable=extract_and_transform,
    dag=dag,
)

task_load = PythonOperator(
    task_id='load_to_clickhouse',
    python_callable=load_to_clickhouse,
    dag=dag,
)

task_extract_transform >> task_load