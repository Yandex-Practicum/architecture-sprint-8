from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta

DEFAULT_ARGS = {
    "owner": "bionicpro",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

def extract_crm():
    pass

def extract_telemetry():
    pass

def load_to_olap():
    pass

with DAG(
    dag_id="crm_telemetry_daily_report",
    default_args=DEFAULT_ARGS,
    start_date=datetime(2024, 1, 1),
    schedule_interval="0 3 * * *",
    catchup=False,
) as dag:

    extract_crm_task = PythonOperator(
        task_id="extract_crm",
        python_callable=extract_crm,
    )

    extract_telemetry_task = PythonOperator(
        task_id="extract_telemetry",
        python_callable=extract_telemetry,
    )

    load_to_olap_task = PythonOperator(
        task_id="load_to_olap",
        python_callable=load_to_olap,
    )

    [extract_crm_task, extract_telemetry_task] >> load_to_olap_task
