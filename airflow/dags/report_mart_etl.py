"""
Задание 4: CRM → OLAP только через CDC (Debezium → Kafka → ClickHouse KafkaEngine + MV).
Airflow больше не читает CRM из OLTP: DAG только обновляет телеметрию (мок DB/датчиков) и watermark.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

CH_URL = "http://clickhouse:8123/"
PIPELINE = "prosthetics_mart"

MOCK_USERS = [
    "user1@example.com",
    "user2@example.com",
    "admin1@example.com",
    "prothetic1@example.com",
    "prothetic2@example.com",
    "prothetic3@example.com",
]


def ch_exec(sql: str) -> None:
    req = urllib.request.Request(
        CH_URL,
        data=sql.encode("utf-8"),
        headers={"Content-Type": "text/plain; charset=utf-8"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=120).read()
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"ClickHouse HTTP {e.code}: {body}") from e


def init_schema(**_context):
    """Минимальная схема для DAG (основное в clickhouse/schema/001_cdc.sql)."""
    ch_exec("CREATE DATABASE IF NOT EXISTS reports")


def load_telemetry_and_watermark(**_context):
    """Телеметрия без обращения к PostgreSQL CRM — нагрузка OLTP CRM не растёт."""
    yesterday = date.today() - timedelta(days=1)
    rows = []
    for email in MOCK_USERS:
        samples = 1000 + (hash(email) % 5000)
        amplitude = 0.35 + (hash(email) % 100) / 200.0
        rows.append(
            {
                "user_email": email,
                "report_bucket": yesterday.isoformat(),
                "telemetry_samples": samples,
                "telemetry_avg_amplitude": round(amplitude, 4),
            }
        )
    payload = "\n".join(json.dumps(r, ensure_ascii=False) for r in rows)
    ch_exec(
        "INSERT INTO reports.telemetry_by_user "
        "(user_email, report_bucket, telemetry_samples, telemetry_avg_amplitude) FORMAT JSONEachRow\n"
        + payload
    )
    ch_exec(
        f"""
        INSERT INTO reports.etl_watermark (pipeline, data_through_date, last_success_at)
        VALUES ('{PIPELINE}', toDate('{yesterday.isoformat()}'), now())
        """
    )


default_args = {
    "owner": "bionicpro",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
}

with DAG(
    dag_id="prosthetics_report_mart_etl",
    default_args=default_args,
    description="Телеметрия + watermark; CRM приходит через Debezium→Kafka→CH",
    schedule=timedelta(hours=6),
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["bionicpro", "reports", "clickhouse", "cdc"],
) as dag:
    t_init = PythonOperator(task_id="init_clickhouse_schema", python_callable=init_schema)
    t_load = PythonOperator(task_id="load_telemetry_watermark", python_callable=load_telemetry_and_watermark)
    t_init >> t_load
