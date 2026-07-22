import logging
from datetime import datetime, timezone, timedelta
from random import random

from airflow import DAG
from airflow.models import TaskInstance
from airflow.operators.python import PythonOperator
from airflow.providers.common.sql.operators.sql import SQLExecuteQueryOperator, SQLInsertRowsOperator

default_args = {
    'owner': 'airflow',
    'start_date': datetime(2026, 7, 20),
}


def generate_telemetry(ti: TaskInstance):
    online_devices = ti.xcom_pull(task_ids='fetch_online_devices')
    logging.info(f"Result from SQL: {online_devices}")
    insert_data = []
    for username, device_id in online_devices:
        for type in ['tension', 'battery_level', 'impedance']:
            insert_data.append((
                datetime.now(tz=timezone.utc).isoformat(),
                username,
                str(device_id),
                type,
                str(random())
            ))
    return insert_data


with DAG('generate_telemetry',
         default_args=default_args,
         schedule_interval=timedelta(minutes=5), # Генерирует новые измерения каждые 5 минут
         is_paused_upon_creation=False,
         catchup=False) as dag:
    fetch_online_devices = SQLExecuteQueryOperator(
        task_id='fetch_online_devices',
        conn_id='telemetry_connection',
        sql="SELECT * FROM online_devices",
        return_last=True,
        do_xcom_push=True,
        autocommit=True
    )

    generate_for_online_devices = PythonOperator(
        task_id='generate_for_online_devices',
        python_callable=generate_telemetry,
        provide_context=True
    )

    insert_measurements = SQLInsertRowsOperator(
        task_id='insert_measurements',
        conn_id='telemetry_connection',
        table_name="measurements",
        columns=["timestamp", "username", "device_id", "type", "value"],
        rows=generate_for_online_devices.output,
        insert_args={
            "executemany": True
        }
    )

    fetch_online_devices >> generate_for_online_devices >> insert_measurements
