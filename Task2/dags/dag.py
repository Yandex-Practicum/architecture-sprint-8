from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.operators.postgres import PostgresOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from datetime import datetime, timedelta
import csv
import os

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2025, 1, 1),
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

def load_csv_to_postgres(table_name, csv_path, columns):
    """Загружает CSV в указанную таблицу PostgreSQL"""
    hook = PostgresHook(postgres_conn_id='reporting_db')
    conn = hook.get_conn()
    cursor = conn.cursor()
    
    # Очищаем таблицу перед загрузкой (для простоты)
    cursor.execute(f"TRUNCATE TABLE {table_name};")
    
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            placeholders = ', '.join(['%s'] * len(columns))
            col_names = ', '.join(columns)
            query = f"INSERT INTO {table_name} ({col_names}) VALUES ({placeholders})"
            values = [row[col] for col in columns]
            cursor.execute(query, values)
    
    conn.commit()
    cursor.close()
    conn.close()

def load_crm():
    load_csv_to_postgres('raw_crm', '/opt/airflow/dags/data/crm_data.csv', 
                         ['client_id', 'full_name', 'email', 'registration_date'])

def load_telemetry():
    load_csv_to_postgres('raw_telemetry', '/opt/airflow/dags/data/telemetry_data.csv', 
                         ['record_id', 'client_id', 'session_date', 'active_minutes', 
                          'steps', 'battery_usage', 'errors'])

def build_mart():
    """Агрегирует данные из сырых таблиц в витрину mart_report"""
    hook = PostgresHook(postgres_conn_id='reporting_db')
    conn = hook.get_conn()
    cursor = conn.cursor()
    
    # Очищаем витрину
    cursor.execute("TRUNCATE TABLE mart_report;")
    
    # Заполняем витрину агрегированными данными
    query = """
    INSERT INTO mart_report (client_id, full_name, email, total_sessions, 
                             total_active_minutes, total_steps, avg_battery_usage, last_session_date)
    SELECT 
        c.client_id,
        c.full_name,
        c.email,
        COUNT(t.record_id) AS total_sessions,
        SUM(t.active_minutes) AS total_active_minutes,
        SUM(t.steps) AS total_steps,
        ROUND(AVG(t.battery_usage), 2) AS avg_battery_usage,
        MAX(t.session_date) AS last_session_date
    FROM raw_crm c
    LEFT JOIN raw_telemetry t ON c.client_id = t.client_id
    GROUP BY c.client_id, c.full_name, c.email;
    """
    cursor.execute(query)
    conn.commit()
    cursor.close()
    conn.close()

with DAG(
    'report_etl_dag',
    default_args=default_args,
    description='ETL for building report mart',
    schedule_interval='0 2 * * *',  # ежедневно в 2:00
    catchup=False,
    tags=['reports'],
) as dag:

    # 1. Создание таблиц (если не существуют)
    create_tables = PostgresOperator(
        task_id='create_tables',
        postgres_conn_id='reporting_db',
        sql="""
        CREATE TABLE IF NOT EXISTS raw_crm (
            client_id UUID PRIMARY KEY,
            full_name VARCHAR(255),
            email VARCHAR(255),
            registration_date DATE
        );

        CREATE TABLE IF NOT EXISTS raw_telemetry (
            record_id INTEGER PRIMARY KEY,
            client_id UUID,
            session_date DATE,
            active_minutes INTEGER,
            steps INTEGER,
            battery_usage NUMERIC(5,2),
            errors INTEGER
        );

        CREATE TABLE IF NOT EXISTS mart_report (
            client_id UUID PRIMARY KEY,
            full_name VARCHAR(255),
            email VARCHAR(255),
            total_sessions INTEGER,
            total_active_minutes INTEGER,
            total_steps INTEGER,
            avg_battery_usage NUMERIC(5,2),
            last_session_date DATE,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    # 2. Загрузка CRM
    load_crm_task = PythonOperator(
        task_id='load_crm',
        python_callable=load_crm
    )

    # 3. Загрузка телеметрии
    load_telemetry_task = PythonOperator(
        task_id='load_telemetry',
        python_callable=load_telemetry
    )

    # 4. Построение витрины
    build_mart_task = PythonOperator(
        task_id='build_mart',
        python_callable=build_mart
    )

    # Определяем порядок выполнения
    create_tables >> [load_crm_task, load_telemetry_task] >> build_mart_task