"""
DAG: загрузка тестовых данных отчётов из CSV в ClickHouse datamart_reports.
Запускается вручную (@once) или по расписанию. Нужен connection clickhouse.
"""
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.hooks.base import BaseHook

CLICKHOUSE_CONN_ID = "clickhouse"
CSV_PATH = "/opt/airflow/sample_files/reports_seed.csv"
MAIN_NETWORK = "architecture-bionicpro_default"


def _load_reports_csv_to_clickhouse(**context):
    """Читает reports_seed.csv и вставляет в ClickHouse datamart_reports."""
    import subprocess
    import csv

    conn = BaseHook.get_connection(CLICKHOUSE_CONN_ID)
    host = conn.host or "clickhouse"
    port = conn.port or 9000
    password = conn.password or "clickhouse"

    rows = []
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            user_id = row.get("user_id", "").strip()
            usage_hours = float(row.get("usage_hours", 0))
            steps = float(row.get("steps", 0))
            events_count = int(row.get("events_count", 0))
            if not user_id:
                continue
            rows.append((user_id, usage_hours, steps, events_count))

    if not rows:
        return "No rows to insert"

    # Формируем INSERT с VALUES
    values = []
    for uid, uh, st, ec in rows:
        values.append(f"('{uid}',toMonday(today()),toMonday(today())+6,{uh},{st},{ec},now64(3))")
    sql = "INSERT INTO datamart_reports (user_id, period_from, period_to, usage_hours, steps, events_count, report_generated_at) VALUES " + ",".join(values)

    cmd = [
        "docker", "run", "--rm",
        "--network", MAIN_NETWORK,
        "-e", f"CLICKHOUSE_PASSWORD={password}",
        "clickhouse/clickhouse-client:24.3",
        "--host", host,
        "--password", password,
        "--query", sql,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise RuntimeError(f"ClickHouse insert failed: {result.stderr or result.stdout}")
    return f"Inserted {len(rows)} row(s)"


with DAG(
    dag_id="load_reports_seed",
    default_args={
        "owner": "airflow",
        "retries": 1,
        "retry_delay": timedelta(minutes=1),
    },
    description="Загрузка reports_seed.csv в ClickHouse datamart_reports",
    schedule_interval="@once",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["reports", "seed"],
) as dag:
    load_task = PythonOperator(
        task_id="load_reports_to_clickhouse",
        python_callable=_load_reports_csv_to_clickhouse,
    )
