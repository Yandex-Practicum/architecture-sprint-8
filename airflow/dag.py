from datetime import timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago

import psycopg2
from clickhouse_driver import Client


POSTGRES_CONFIG = {
    "host": "crm-postgres",
    "dbname": "crm",
    "user": "crm_user",
    "password": "crm_password",
}

CLICKHOUSE_HOST = "clickhouse"
CLICKHOUSE_DB = "backend"


def get_clickhouse():
    return Client(host=CLICKHOUSE_HOST, database=CLICKHOUSE_DB)


# ---------- CRM sync ----------

def sync_crm_users():
    conn = psycopg2.connect(**POSTGRES_CONFIG)
    cur = conn.cursor()

    crm_query = """
        SELECT
            u.id,
            u.country,
            u.segment,
            p.id,
            p.tariff
        FROM users u
        JOIN prostheses p ON p.user_id = u.id
    """

    cur.execute(crm_query)
    data = cur.fetchall()

    cur.close()
    conn.close()

    ch = get_clickhouse()

    ch.execute("""
        CREATE TABLE IF NOT EXISTS crm_users_stage (
            user_id UInt64,
            country String,
            segment String,
            prosthesis_id UInt64,
            tariff String
        )
        ENGINE = Memory
    """)

    ch.execute("TRUNCATE TABLE crm_users_stage")

    if data:
        ch.execute(
            """
            INSERT INTO crm_users_stage
            (user_id, country, segment, prosthesis_id, tariff)
            VALUES
            """,
            data
        )


# ---------- Telemetry aggregation ----------

def calculate_daily_metrics():

    ch = get_clickhouse()

    ch.execute("""
        CREATE TABLE IF NOT EXISTS telemetry_daily_metrics (
            user_id UInt64,
            prosthesis_id UInt64,
            report_date Date,
            active_seconds UInt32,
            avg_reaction_ms Float32,
            movements UInt32,
            errors UInt32,
            battery_avg Float32,
            last_event_ts DateTime
        )
        ENGINE = MergeTree
        PARTITION BY toYYYYMM(report_date)
        ORDER BY (user_id, prosthesis_id, report_date)
    """)

    ch.execute("TRUNCATE TABLE telemetry_daily_metrics")

    aggregation_query = """
        INSERT INTO telemetry_daily_metrics
        SELECT
            user_id,
            prosthesis_id,
            toDate(ts),
            sum(active_seconds),
            avg(reaction_ms),
            count(),
            sumIf(1, has_error),
            avg(battery_level_pct),
            max(ts)
        FROM telemetry_raw
        GROUP BY
            user_id,
            prosthesis_id,
            toDate(ts)
    """

    ch.execute(aggregation_query)


# ---------- Report mart ----------

def build_reports_dataset():

    ch = get_clickhouse()

    ch.execute("""
        CREATE TABLE IF NOT EXISTS report_user_daily (
            user_id UInt64,
            prosthesis_id UInt64,
            report_date Date,
            active_seconds UInt32,
            avg_reaction_ms Float32,
            movements UInt32,
            errors UInt32,
            battery_avg Float32,
            last_event_ts DateTime,
            country String,
            segment String,
            tariff String
        )
        ENGINE = MergeTree
        PARTITION BY toYYYYMM(report_date)
        ORDER BY (user_id, prosthesis_id, report_date)
    """)

    ch.execute("TRUNCATE TABLE report_user_daily")

    mart_query = """
        INSERT INTO report_user_daily
        SELECT
            t.user_id,
            t.prosthesis_id,
            t.report_date,
            t.active_seconds,
            t.avg_reaction_ms,
            t.movements,
            t.errors,
            t.battery_avg,
            t.last_event_ts,
            c.country,
            c.segment,
            c.tariff
        FROM telemetry_daily_metrics t
        LEFT JOIN crm_users_stage c
            ON c.user_id = t.user_id
            AND c.prosthesis_id = t.prosthesis_id
    """

    ch.execute(mart_query)


# ---------- DAG ----------

default_args = {
    "owner": "analytics",
    "retries": 2,
    "retry_delay": timedelta(minutes=3),
}

with DAG(
    dag_id="prosthesis_telemetry_pipeline",
    default_args=default_args,
    description="Pipeline for prosthesis telemetry reporting",
    start_date=days_ago(1),
    schedule_interval="0 * * * *",
    catchup=False,
    max_active_runs=1,
    tags=["telemetry", "analytics"],
) as dag:

    crm_sync = PythonOperator(
        task_id="sync_crm_data",
        python_callable=sync_crm_users,
    )

    telemetry_metrics = PythonOperator(
        task_id="calculate_daily_metrics",
        python_callable=calculate_daily_metrics,
    )

    build_reports = PythonOperator(
        task_id="build_reports_dataset",
        python_callable=build_reports_dataset,
    )

    [crm_sync, telemetry_metrics] >> build_reports