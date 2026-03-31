"""
ETL: CRM (CSV) + телеметрия (CSV) -> витрина reporting.mart_user_prosthesis_daily.
Расписание: ежедневно после полуночи UTC.
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


def _dsn() -> str:
    dsn = os.environ.get("REPORTING_OLAP_DSN")
    if not dsn:
        raise RuntimeError("REPORTING_OLAP_DSN is not set")
    return dsn


def load_staging(**_):
    conn = psycopg2.connect(_dsn())
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE reporting.stg_crm, reporting.stg_telemetry;")
            with open(CRM_CSV, "r", encoding="utf-8") as f:
                cur.copy_expert(
                    """
                    COPY reporting.stg_crm (customer_id, email, keycloak_subject, prosthesis_model, region)
                    FROM STDIN WITH (FORMAT csv, HEADER true)
                    """,
                    f,
                )
            with open(TEL_CSV, "r", encoding="utf-8") as f:
                cur.copy_expert(
                    """
                    COPY reporting.stg_telemetry (user_subject, event_date, active_minutes, steps)
                    FROM STDIN WITH (FORMAT csv, HEADER true)
                    """,
                    f,
                )
        conn.commit()
    finally:
        conn.close()


def merge_mart(**_):
    conn = psycopg2.connect(_dsn())
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM reporting.mart_user_prosthesis_daily;")
            cur.execute(
                """
                INSERT INTO reporting.mart_user_prosthesis_daily (
                    user_subject, stat_date, active_hours, steps, prosthesis_model, crm_region
                )
                SELECT
                    t.user_subject,
                    t.event_date AS stat_date,
                    ROUND(SUM(t.active_minutes)::numeric / 60.0, 4) AS active_hours,
                    SUM(t.steps)::bigint AS steps,
                    MAX(c.prosthesis_model) AS prosthesis_model,
                    MAX(c.region) AS crm_region
                FROM reporting.stg_telemetry t
                LEFT JOIN reporting.stg_crm c ON c.keycloak_subject = t.user_subject
                GROUP BY t.user_subject, t.event_date
                """
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
    description="Загрузка CRM + телеметрии в витрину OLAP",
    schedule="0 6 * * *",
    start_date=datetime(2026, 3, 1),
    catchup=False,
    tags=["reporting", "olap", "crm", "telemetry"],
) as dag:
    t_load = PythonOperator(
        task_id="load_staging_from_sources",
        python_callable=load_staging,
    )
    t_mart = PythonOperator(
        task_id="rebuild_mart_aggregates",
        python_callable=merge_mart,
    )
    t_load >> t_mart
