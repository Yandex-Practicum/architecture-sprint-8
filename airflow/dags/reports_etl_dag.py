"""
ETL DAG: запуск Go 1.24 ETL (reports-etl) — извлечение CRM/телеметрии и формирование витрины в OLAP.
Расписание: ежедневно. Нужны connection olap_db и образ reports-etl:latest (docker build -t reports-etl:latest ./reports-etl).
"""
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.hooks.base import BaseHook

OLAP_CONN_ID = "olap_db"

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
}


def _run_go_etl(**context):
    """Запускает контейнер reports-etl:latest с OLAP_DATABASE_URL из connection olap_db."""
    import subprocess
    conn = BaseHook.get_connection(OLAP_CONN_ID)
    port = conn.port or 5432
    schema = conn.schema or "olap_db"
    url = f"postgresql://{conn.login}:{conn.password}@{conn.host}:{port}/{schema}?sslmode=disable"
    cmd = [
        "docker", "run", "--rm",
        "-e", f"OLAP_DATABASE_URL={url}",
        "reports-etl:latest",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise RuntimeError(f"reports-etl failed: {result.stderr or result.stdout}")
    return result.stdout


with DAG(
    dag_id="reports_etl",
    default_args=default_args,
    description="ETL (Go 1.24): CRM + телеметрия → витрина OLAP",
    schedule_interval=timedelta(days=1),
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["reports", "etl"],
) as dag:
    run_etl = PythonOperator(
        task_id="run_reports_etl",
        python_callable=_run_go_etl,
    )
