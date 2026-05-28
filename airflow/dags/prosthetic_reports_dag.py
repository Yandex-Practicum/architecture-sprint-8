import re
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from clickhouse_driver import Client as ClickHouseClient
import os

CLICKHOUSE_HOST = os.getenv('CLICKHOUSE_HOST', 'localhost')
CLICKHOUSE_PORT = int(os.getenv('CLICKHOUSE_PORT', '9000'))
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
    description='ETL: telemetry + CRM → ClickHouse',
    schedule_interval='0 2 * * *',
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=['bionicpro', 'etl'],
)

def user_str_to_int(uid):
    match = re.search(r'\d+$', uid)
    return int(match.group()) if match else 0

def extract_customers(**context):
    pg_hook = PostgresHook(postgres_conn_id=POSTGRES_CONN_ID)
    sql = "SELECT user_id, full_name, email, country FROM customers;"
    records = pg_hook.get_records(sql)
    # Convert user_id from string to int
    records = [(user_str_to_int(r[0]), r[1], r[2], r[3]) for r in records]
    context['ti'].xcom_push(key='customers', value=records)

def extract_telemetry(**context):
    pg_hook = PostgresHook(postgres_conn_id=POSTGRES_CONN_ID)
    execution_date = context['ds']
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
        WHERE recorded_at::date = %(date)s::date
        GROUP BY user_id, date(recorded_at);
    """
    records = pg_hook.get_records(sql, parameters={'date': execution_date})
    # Convert user_id from string to int
    records = [(user_str_to_int(r[0]),) + r[1:] for r in records]
    context['ti'].xcom_push(key='telemetry', value=records)

def load_to_clickhouse(**context):
    ch = ClickHouseClient(host=CLICKHOUSE_HOST, port=CLICKHOUSE_PORT, database='prosthetic_reports')
    customers = context['ti'].xcom_pull(key='customers')
    telemetry = context['ti'].xcom_pull(key='telemetry')

    ch.execute('TRUNCATE TABLE IF EXISTS prosthetic_reports.dim_customers')
    for row in (customers or []):
        ch.execute(
            'INSERT INTO prosthetic_reports.dim_customers (user_id, full_name, email, country) VALUES',
            [{'user_id': row[0], 'full_name': row[1], 'email': row[2], 'country': row[3]}]
        )

    for row in (telemetry or []):
        ch.execute(
            '''INSERT INTO prosthetic_reports.fact_telemetry
               (user_id, date, total_readings, avg_signal_1, avg_signal_2, avg_signal_3, avg_signal_4,
                avg_battery_level, movement_grasp, movement_release, movement_flex, movement_extend, movement_rotate)
               VALUES''',
            [{
                'user_id': row[0], 'date': row[1], 'total_readings': row[2],
                'avg_signal_1': row[3], 'avg_signal_2': row[4], 'avg_signal_3': row[5],
                'avg_signal_4': row[6], 'avg_battery_level': row[7],
                'movement_grasp': row[8], 'movement_release': row[9],
                'movement_flex': row[10], 'movement_extend': row[11], 'movement_rotate': row[12]
            }]
        )

    ch.execute('''
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

[t_extract_customers, t_extract_telemetry] >> t_load
