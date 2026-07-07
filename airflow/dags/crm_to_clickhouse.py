from __future__ import annotations

import os
from datetime import datetime, timedelta

import clickhouse_connect
import psycopg2
from airflow import DAG
from airflow.operators.python import PythonOperator

CRM_DSN = {
    "host": os.getenv("CRM_DB_HOST", "crm_db"),
    "port": int(os.getenv("CRM_DB_PORT", "5432")),
    "dbname": os.getenv("CRM_DB_NAME", "crm"),
    "user": os.getenv("CRM_DB_USER", "crm_user"),
    "password": os.getenv("CRM_DB_PASSWORD", "crm_password"),
}

CH_CONF = {
    "host": os.getenv("CLICKHOUSE_HOST", "clickhouse"),
    "port": int(os.getenv("CLICKHOUSE_PORT", "8123")),
    "username": os.getenv("CLICKHOUSE_USER", "default"),
    "password": os.getenv("CLICKHOUSE_PASSWORD", ""),
}

EXTRACT_SQL = """
    SELECT
        c.username,
        c.full_name,
        c.prosthesis_model,
        date_trunc('day', t.ts)::date          AS period_date,
        avg(t.response_time_ms)                 AS avg_response_time_ms,
        max(t.response_time_ms)                 AS max_response_time_ms,
        min(t.battery_level)                    AS min_battery_level,
        sum(t.movements_count)                  AS total_movements,
        count(*)                                AS samples_count
    FROM telemetry t
    JOIN clients c ON c.id = t.client_id
    GROUP BY c.username, c.full_name, c.prosthesis_model, date_trunc('day', t.ts)
"""


def build_report_mart(**_context) -> None:
    conn = psycopg2.connect(**CRM_DSN)
    try:
        with conn.cursor() as cur:
            cur.execute(EXTRACT_SQL)
            rows = cur.fetchall()
    finally:
        conn.close()

    if not rows:
        return

    processed_at = datetime.utcnow()
    data = [
        [
            r[0],
            r[1],
            r[2],
            r[3],
            float(r[4]),
            int(r[5]),
            int(r[6]),
            int(r[7]),
            int(r[8]),
            processed_at,
        ]
        for r in rows
    ]

    client = clickhouse_connect.get_client(**CH_CONF)
    client.insert(
        "reports.user_report",
        data,
        column_names=[
            "username",
            "full_name",
            "prosthesis_model",
            "period_date",
            "avg_response_time_ms",
            "max_response_time_ms",
            "min_battery_level",
            "total_movements",
            "samples_count",
            "processed_at",
        ],
    )


default_args = {
    "owner": "bionicpro",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="crm_to_clickhouse_report_mart",
    description="ETL CRM -> ClickHouse: витрина отчётности по пользователям",
    default_args=default_args,
    start_date=datetime(2024, 1, 1),
    schedule_interval="@hourly",
    catchup=False,
    tags=["bionicpro", "etl", "reports"],
) as dag:
    PythonOperator(
        task_id="build_report_mart",
        python_callable=build_report_mart,
    )
