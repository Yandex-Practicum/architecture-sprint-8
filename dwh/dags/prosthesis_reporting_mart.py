"""
ETL: загрузка CSV в OLTP CRM (PostgreSQL). Дальше CDC (Debezium) → Kafka → ClickHouse → витрина mart.
Тяжёлая агрегация не выполняется в CRM OLTP — только INSERT/COPY из файлов по расписанию.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path

import psycopg2
from airflow import DAG
from airflow.operators.python import PythonOperator

DATA_DIR = Path(os.environ.get("AIRFLOW_DATA_DIR", "/opt/airflow/data"))
CRM_CSV = DATA_DIR / "crm_customers.csv"
TEL_CSV = DATA_DIR / "telemetry_events.csv"


def _crm_dsn() -> str:
    dsn = os.environ.get("REPORTING_CRM_DSN")
    if not dsn:
        raise RuntimeError("REPORTING_CRM_DSN is not set")
    return dsn


def load_crm_oltp(**_):
    """Массовая загрузка в CRM OLTP; онлайн-транзакции не блокируются длительной агрегацией в этом DAG."""
    conn = psycopg2.connect(_crm_dsn())
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE telemetry_events, customers RESTART IDENTITY CASCADE;")
            with open(CRM_CSV, "r", encoding="utf-8") as f:
                cur.copy_expert(
                    """
                    COPY customers (customer_id, email, keycloak_subject, prosthesis_model, region)
                    FROM STDIN WITH (FORMAT csv, HEADER true)
                    """,
                    f,
                )
            with open(TEL_CSV, "r", encoding="utf-8") as f:
                cur.copy_expert(
                    """
                    COPY telemetry_events (user_subject, event_date, active_minutes, steps)
                    FROM STDIN WITH (FORMAT csv, HEADER true)
                    """,
                    f,
                )
        conn.commit()
    finally:
        conn.close()


default_args = {
    "owner": "bionicpro",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="prosthesis_reporting_mart",
    default_args=default_args,
    description="Загрузка CSV в CRM OLTP → CDC в ClickHouse (без тяжёлой витрины в OLTP)",
    schedule="0 6 * * *",
    start_date=datetime(2026, 3, 1),
    catchup=False,
    tags=["reporting", "crm", "cdc", "clickhouse"],
) as dag:
    t_load = PythonOperator(
        task_id="load_crm_oltp_from_csv",
        python_callable=load_crm_oltp,
    )
