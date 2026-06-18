import re
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
import os
import requests

CLICKHOUSE_HOST = os.getenv('CLICKHOUSE_HOST', 'localhost')
CLICKHOUSE_HTTP_PORT = int(os.getenv('CLICKHOUSE_HTTP_PORT', '8123'))
POSTGRES_CONN_ID = 'telemetry_db'

default_args = {
    'owner': 'bionicpro',
    'depends_on_past': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'prosthetic_reports_etl',
    default_args=default_args,
    description='ETL: telemetry + CRM -> ClickHouse',
    schedule_interval='0 2 * * *',
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=['bionicpro', 'etl'],
)

def user_str_to_int(uid):
    match = re.search(r'\d+$', uid)
    return int(match.group()) if match else 0

def ch_execute(sql):
    url = f'http://{CLICKHOUSE_HOST}:{CLICKHOUSE_HTTP_PORT}/'
    resp = requests.post(url, params={'query': sql}, timeout=30)
    resp.raise_for_status()
    return resp.text

def ch_execute_insert(sql, rows, columns):
    if not rows:
        return
    values = []
    for row in rows:
        parts = []
        for i, col in enumerate(columns):
            val = row[i]
            if val is None:
                parts.append('NULL')
            elif isinstance(val, int):
                parts.append(str(val))
            elif isinstance(val, float):
                parts.append(str(val))
            elif isinstance(val, datetime):
                parts.append(f"'{val.strftime('%Y-%m-%d %H:%M:%S')}'")
            else:
                parts.append(f"'{str(val)}'")
        values.append('(' + ','.join(parts) + ')')
    full_sql = sql + ' VALUES ' + ','.join(values)
    ch_execute(full_sql)

def create_tables(**context):
    statements = [
        "CREATE DATABASE IF NOT EXISTS prosthetic_reports",
        """CREATE TABLE IF NOT EXISTS prosthetic_reports.dim_customers (
            user_id UInt32, full_name String, email String, country String,
            loaded_at DateTime DEFAULT now()
        ) ENGINE = ReplacingMergeTree(loaded_at) ORDER BY user_id""",
        """CREATE TABLE IF NOT EXISTS prosthetic_reports.fact_telemetry (
            user_id UInt32, date Date, total_readings UInt64,
            avg_signal_1 Float64, avg_signal_2 Float64, avg_signal_3 Float64, avg_signal_4 Float64,
            avg_battery_level Float64,
            movement_grasp UInt64, movement_release UInt64, movement_flex UInt64,
            movement_extend UInt64, movement_rotate UInt64,
            loaded_at DateTime DEFAULT now()
        ) ENGINE = SummingMergeTree((total_readings, movement_grasp, movement_release, movement_flex, movement_extend, movement_rotate))
        ORDER BY (user_id, date)""",
        """CREATE TABLE IF NOT EXISTS prosthetic_reports.report_mart (
            user_id UInt32, full_name String, email String, country String,
            date Date, total_readings UInt64,
            avg_signal_1 Float64, avg_signal_2 Float64, avg_signal_3 Float64, avg_signal_4 Float64,
            avg_battery_level Float64,
            movement_grasp UInt64, movement_release UInt64, movement_flex UInt64,
            movement_extend UInt64, movement_rotate UInt64
        ) ENGINE = MergeTree() ORDER BY (user_id, date)""",
    ]
    for stmt in statements:
        ch_execute(stmt)

def extract_customers(**context):
    pg_hook = PostgresHook(postgres_conn_id=POSTGRES_CONN_ID)
    sql = "SELECT user_id, full_name, email, country FROM customers;"
    records = pg_hook.get_records(sql)
    records = [(user_str_to_int(r[0]), r[1], r[2], r[3]) for r in records]
    context['ti'].xcom_push(key='customers', value=records)

def extract_telemetry(**context):
    pg_hook = PostgresHook(postgres_conn_id=POSTGRES_CONN_ID)
    sql = """
        SELECT
            user_id,
            date(recorded_at) as date,
            count(*) as total_readings,
            avg(myo_signal_1) as avg_signal_1,
            avg(myo_signal_2) as avg_signal_2,
            avg(myo_signal_3) as avg_signal_3,
            avg(myo_signal_4) as avg_signal_4,
            avg(battery_level) as avg_battery_level,
            sum(case when movement_type = 'grasp' then 1 else 0 end) as movement_grasp,
            sum(case when movement_type = 'release' then 1 else 0 end) as movement_release,
            sum(case when movement_type = 'flex' then 1 else 0 end) as movement_flex,
            sum(case when movement_type = 'extend' then 1 else 0 end) as movement_extend,
            sum(case when movement_type = 'rotate' then 1 else 0 end) as movement_rotate
        FROM telemetry
        GROUP BY user_id, date(recorded_at)
        ORDER BY user_id, date;
    """
    records = pg_hook.get_records(sql)
    records = [(user_str_to_int(r[0]),) + r[1:] for r in records]
    context['ti'].xcom_push(key='telemetry', value=records)

def load_to_clickhouse(**context):
    customers = context['ti'].xcom_pull(key='customers')
    telemetry = context['ti'].xcom_pull(key='telemetry')

    ch_execute('TRUNCATE TABLE IF EXISTS prosthetic_reports.dim_customers')
    ch_execute('TRUNCATE TABLE IF EXISTS prosthetic_reports.fact_telemetry')
    ch_execute('TRUNCATE TABLE IF EXISTS prosthetic_reports.report_mart')

    ch_execute_insert(
        'INSERT INTO prosthetic_reports.dim_customers (user_id, full_name, email, country)',
        customers or [],
        ['user_id', 'full_name', 'email', 'country']
    )

    tel_columns = ['user_id', 'date', 'total_readings', 'avg_signal_1', 'avg_signal_2',
                   'avg_signal_3', 'avg_signal_4', 'avg_battery_level',
                   'movement_grasp', 'movement_release', 'movement_flex',
                   'movement_extend', 'movement_rotate']
    ch_execute_insert(
        '''INSERT INTO prosthetic_reports.fact_telemetry
           (user_id, date, total_readings, avg_signal_1, avg_signal_2, avg_signal_3, avg_signal_4,
            avg_battery_level, movement_grasp, movement_release, movement_flex, movement_extend, movement_rotate)''',
        telemetry or [],
        tel_columns
    )

    ch_execute('''
        INSERT INTO prosthetic_reports.report_mart
        SELECT
            f.user_id,
            d.full_name,
            d.email,
            d.country,
            f.date,
            f.total_readings,
            f.avg_signal_1,
            f.avg_signal_2,
            f.avg_signal_3,
            f.avg_signal_4,
            f.avg_battery_level,
            f.movement_grasp,
            f.movement_release,
            f.movement_flex,
            f.movement_extend,
            f.movement_rotate
        FROM prosthetic_reports.fact_telemetry f
        LEFT JOIN prosthetic_reports.dim_customers d ON f.user_id = d.user_id
    ''')

t_create_tables = PythonOperator(
    task_id='create_tables',
    python_callable=create_tables,
    provide_context=True,
    dag=dag,
)

t_extract_customers = PythonOperator(
    task_id='extract_customers',
    python_callable=extract_customers,
    provide_context=True,
    dag=dag,
)

t_extract_telemetry = PythonOperator(
    task_id='extract_telemetry',
    python_callable=extract_telemetry,
    provide_context=True,
    dag=dag,
)

t_load = PythonOperator(
    task_id='load_to_clickhouse',
    python_callable=load_to_clickhouse,
    provide_context=True,
    dag=dag,
)

t_create_tables >> [t_extract_customers, t_extract_telemetry] >> t_load
