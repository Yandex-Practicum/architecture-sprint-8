from __future__ import annotations

import os
from contextlib import closing
from datetime import datetime

import clickhouse_connect
import psycopg2
from airflow import DAG
from airflow.operators.python import PythonOperator


def get_pg_connection(prefix: str):
    return psycopg2.connect(
        host=os.environ[f"{prefix}_HOST"],
        port=os.environ[f"{prefix}_PORT"],
        dbname=os.environ[f"{prefix}_NAME"],
        user=os.environ[f"{prefix}_USER"],
        password=os.environ[f"{prefix}_PASSWORD"],
    )


def get_clickhouse_client():
    return clickhouse_connect.get_client(
        host=os.environ["CLICKHOUSE_HOST"],
        port=int(os.environ["CLICKHOUSE_PORT"]),
        username=os.environ.get("CLICKHOUSE_USERNAME", "default"),
        password=os.environ.get("CLICKHOUSE_PASSWORD", ""),
        database=os.environ.get("CLICKHOUSE_DATABASE", "default"),
    )


def load_crm_data():
    with closing(get_pg_connection("CRM_DB")) as crm_conn, closing(crm_conn.cursor()) as cursor:
        cursor.execute(
            """
            SELECT id, keycloak_username, full_name, email, country_code
            FROM customers
            ORDER BY id
            """
        )
        customers = cursor.fetchall()

        cursor.execute(
            """
            SELECT id, customer_id, prosthesis_code, model_name, activated_at
            FROM prostheses
            ORDER BY id
            """
        )
        prostheses = cursor.fetchall()

    client = get_clickhouse_client()
    client.command("TRUNCATE TABLE crm_customers_staging")
    client.command("TRUNCATE TABLE crm_prostheses_staging")

    if customers:
        client.insert(
            "crm_customers_staging",
            customers,
            column_names=["customer_id", "keycloak_username", "full_name", "email", "country_code"],
        )

    if prostheses:
        client.insert(
            "crm_prostheses_staging",
            prostheses,
            column_names=["prosthesis_id", "customer_id", "prosthesis_code", "model_name", "activated_at"],
        )

    client.close()


def load_telemetry_aggregate():
    with closing(get_pg_connection("TELEMETRY_DB")) as telemetry_conn, closing(telemetry_conn.cursor()) as cursor:
        cursor.execute(
            """
            SELECT
                prosthesis_code,
                MIN(event_time) AS telemetry_from,
                MAX(event_time) AS telemetry_to,
                COUNT(*) AS total_events,
                SUM(active_minutes) AS total_active_minutes,
                SUM(grip_actions) AS total_grip_actions,
                AVG(avg_signal) AS avg_signal,
                AVG(battery_level) AS avg_battery_level
            FROM telemetry_events
            GROUP BY prosthesis_code
            ORDER BY prosthesis_code
            """
        )
        telemetry_rows = cursor.fetchall()

    client = get_clickhouse_client()
    client.command("TRUNCATE TABLE telemetry_daily_staging")

    if telemetry_rows:
        client.insert(
            "telemetry_daily_staging",
            telemetry_rows,
            column_names=[
                "prosthesis_code",
                "telemetry_from",
                "telemetry_to",
                "total_events",
                "total_active_minutes",
                "total_grip_actions",
                "avg_signal",
                "avg_battery_level",
            ],
        )

    client.close()


def build_report_mart():
    client = get_clickhouse_client()
    client.command("TRUNCATE TABLE reports_user_summary")
    client.command(
        """
        INSERT INTO reports_user_summary
        SELECT
            c.keycloak_username,
            c.customer_id,
            c.full_name,
            c.email,
            c.country_code,
            p.prosthesis_id,
            p.prosthesis_code,
            p.model_name,
            p.activated_at,
            t.telemetry_from,
            t.telemetry_to,
            t.total_events,
            t.total_active_minutes,
            t.total_grip_actions,
            t.avg_signal,
            t.avg_battery_level,
            now()
        FROM crm_customers_staging AS c
        INNER JOIN crm_prostheses_staging AS p ON c.customer_id = p.customer_id
        INNER JOIN telemetry_daily_staging AS t ON p.prosthesis_code = t.prosthesis_code
        """
    )
    client.close()


with DAG(
    dag_id="reports_etl",
    start_date=datetime(2026, 3, 29),
    schedule="0 * * * *",
    catchup=False,
    tags=["reports", "etl", "clickhouse"],
) as dag:
    load_crm = PythonOperator(
        task_id="load_crm_to_clickhouse",
        python_callable=load_crm_data,
    )

    load_telemetry = PythonOperator(
        task_id="aggregate_telemetry_to_clickhouse",
        python_callable=load_telemetry_aggregate,
    )

    build_mart = PythonOperator(
        task_id="build_reports_mart",
        python_callable=build_report_mart,
    )

    [load_crm, load_telemetry] >> build_mart
