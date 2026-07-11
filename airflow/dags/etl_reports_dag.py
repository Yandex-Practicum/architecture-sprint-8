import os
import logging
from datetime import datetime, timedelta

import psycopg2
import clickhouse_connect
from airflow import DAG
from airflow.operators.python import PythonOperator

log = logging.getLogger(__name__)

PG_HOST     = os.getenv("BIONICPRO_DB_HOST",     "bionicpro_db")
PG_DB       = os.getenv("BIONICPRO_DB_NAME",     "bionicpro")
PG_USER     = os.getenv("BIONICPRO_DB_USER",     "bionicpro_user")
PG_PASSWORD = os.getenv("BIONICPRO_DB_PASSWORD", "bionicpro_password")
CH_HOST     = os.getenv("CLICKHOUSE_HOST",       "clickhouse")


def create_clickhouse_table(**context):
    """Ensure the reports_mart table exists in ClickHouse."""
    client = clickhouse_connect.get_client(host=CH_HOST, port=8123)
    client.command("""
        CREATE TABLE IF NOT EXISTS reports_mart (
            user_id              String,
            username             String,
            email                String,
            first_name           String,
            last_name            String,
            prosthesis_id        String,
            prosthesis_type      String,
            report_date          Date,
            total_movements      UInt64,
            avg_signal_strength  Float32,
            avg_battery_level    Float32,
            avg_response_time_ms Float32,
            most_common_movement String,
            etl_updated_at       DateTime DEFAULT now()
        )
        ENGINE = MergeTree()
        PARTITION BY toYYYYMM(report_date)
        ORDER BY (user_id, report_date)
        SETTINGS index_granularity = 8192
    """)
    log.info("Table reports_mart is ready.")


def etl_reports(**context):
    """
    Extract telemetry + CRM data for the logical execution date,
    aggregate per (user, day), upsert into ClickHouse reports_mart.
    """
    execution_date = context["ds"]   # YYYY-MM-DD string
    log.info("Running ETL for date: %s", execution_date)

    pg_conn = psycopg2.connect(
        host=PG_HOST, dbname=PG_DB, user=PG_USER, password=PG_PASSWORD
    )
    try:
        with pg_conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    c.user_id,
                    c.username,
                    c.email,
                    c.first_name,
                    c.last_name,
                    c.prosthesis_id,
                    c.prosthesis_type,
                    %(execution_date)s::date                                     AS report_date,
                    COUNT(*)::bigint                                             AS total_movements,
                    ROUND(AVG(t.signal_strength)::numeric,  2)::float           AS avg_signal_strength,
                    ROUND(AVG(t.battery_level)::numeric,    2)::float           AS avg_battery_level,
                    ROUND(AVG(t.response_time_ms)::numeric, 2)::float           AS avg_response_time_ms,
                    MODE() WITHIN GROUP (ORDER BY t.movement_type)              AS most_common_movement
                FROM telemetry t
                JOIN crm_clients c ON c.user_id = t.user_id
                WHERE DATE(t.recorded_at) = %(execution_date)s::date
                GROUP BY
                    c.user_id, c.username, c.email,
                    c.first_name, c.last_name,
                    c.prosthesis_id, c.prosthesis_type
                """,
                {"execution_date": execution_date},
            )
            rows = cur.fetchall()
    finally:
        pg_conn.close()

    if not rows:
        log.info("No telemetry data for %s — skipping ClickHouse load.", execution_date)
        return

    log.info("Fetched %d user-day records from PostgreSQL.", len(rows))

    ch_client = clickhouse_connect.get_client(host=CH_HOST, port=8123)

    # Idempotency: remove stale data for this date before inserting
    ch_client.command(
        "ALTER TABLE reports_mart DELETE WHERE report_date = {date:String}",
        parameters={"date": execution_date},
    )

    column_names = [
        "user_id", "username", "email", "first_name", "last_name",
        "prosthesis_id", "prosthesis_type", "report_date",
        "total_movements", "avg_signal_strength", "avg_battery_level",
        "avg_response_time_ms", "most_common_movement",
    ]

    data = [list(row) for row in rows]

    ch_client.insert("reports_mart", data, column_names=column_names)
    log.info("Inserted %d rows into ClickHouse for %s.", len(data), execution_date)


default_args = {
    "owner": "bionicpro",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="reports_etl",
    default_args=default_args,
    description="ETL: PostgreSQL (telemetry + CRM) → ClickHouse reports_mart",
    schedule="0 2 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["bionicpro", "reports"],
) as dag:

    t_init = PythonOperator(
        task_id="create_clickhouse_table",
        python_callable=create_clickhouse_table,
    )

    t_etl = PythonOperator(
        task_id="etl_reports_mart",
        python_callable=etl_reports,
    )

    t_init >> t_etl
