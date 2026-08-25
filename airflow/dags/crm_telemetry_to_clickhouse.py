import os
from datetime import date, datetime

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from clickhouse_driver import Client

CLICKHOUSE_HOST = os.environ['CLICKHOUSE_HOST']
CLICKHOUSE_DB = os.environ['CLICKHOUSE_DB']

default_args = {
    'owner': 'airflow',
    'start_date': datetime(2026, 8, 17),
}


def clickhouse_client():
    return Client(host=CLICKHOUSE_HOST)


def create_mart():
    client = clickhouse_client()
    client.execute(f'CREATE DATABASE IF NOT EXISTS {CLICKHOUSE_DB}')
    client.execute(f"""
        CREATE TABLE IF NOT EXISTS {CLICKHOUSE_DB}.user_reports (
            user_id String,
            report_date Date,
            full_name String,
            prosthesis_model String,
            signals_count UInt64,
            movements_count UInt64,
            avg_reaction_ms Float64,
            avg_battery_level Float64
        )
        ENGINE = MergeTree
        PARTITION BY report_date
        ORDER BY (user_id, report_date)
    """)


def extract_crm():
    hook = PostgresHook(postgres_conn_id='crm_db')
    return hook.get_records("""
        SELECT user_id, full_name, prosthesis_model
        FROM clients
    """)


def extract_telemetry(data_interval_start, data_interval_end):
    hook = PostgresHook(postgres_conn_id='telemetry_db')
    return hook.get_records("""
        SELECT user_id,
               SUM(signals_count),
               SUM(movements_count),
               AVG(reaction_ms)::float8,
               AVG(battery_level)::float8
        FROM prosthesis_telemetry
        WHERE recorded_at >= %s AND recorded_at < %s
        GROUP BY user_id
    """, parameters=(data_interval_start, data_interval_end))


def join_clients_telemetry(ti, data_interval_start):
    clients = {row[0]: row for row in ti.xcom_pull(task_ids='extract_crm')}
    report_date = data_interval_start.date().isoformat()

    rows = []
    for user_id, signals, movements, reaction_ms, battery_level in ti.xcom_pull(task_ids='extract_telemetry'):
        client = clients.get(user_id)
        if client is None:
            continue
        rows.append([
            user_id,
            report_date,
            client[1],
            client[2],
            signals,
            movements,
            reaction_ms,
            battery_level,
        ])
    return rows


def load_mart(ti, data_interval_start):
    rows = ti.xcom_pull(task_ids='join_clients_telemetry')
    client = clickhouse_client()

    client.execute(
        f'ALTER TABLE {CLICKHOUSE_DB}.user_reports DROP PARTITION %(report_date)s',
        params={'report_date': data_interval_start.date()},
    )

    if rows:
        client.execute(
            f'INSERT INTO {CLICKHOUSE_DB}.user_reports VALUES',
            [[row[0], date.fromisoformat(row[1])] + row[2:] for row in rows],
        )


with DAG(
    'crm_telemetry_to_clickhouse',
    default_args=default_args,
    schedule_interval='@daily',
    catchup=True,
    max_active_runs=1,
) as dag:

    create_mart_task = PythonOperator(
        task_id='create_mart',
        python_callable=create_mart,
    )

    extract_crm_task = PythonOperator(
        task_id='extract_crm',
        python_callable=extract_crm,
    )

    extract_telemetry_task = PythonOperator(
        task_id='extract_telemetry',
        python_callable=extract_telemetry,
    )

    join_task = PythonOperator(
        task_id='join_clients_telemetry',
        python_callable=join_clients_telemetry,
    )

    load_mart_task = PythonOperator(
        task_id='load_mart',
        python_callable=load_mart,
    )

    create_mart_task >> [extract_crm_task, extract_telemetry_task] >> join_task >> load_mart_task
