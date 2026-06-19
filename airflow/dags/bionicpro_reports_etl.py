from __future__ import annotations

from datetime import datetime, timedelta

import psycopg2
import clickhouse_connect

from airflow import DAG
from airflow.hooks.base import BaseHook
from airflow.operators.python import PythonOperator


CRM_CONN_ID = "crm_postgres"
CLICKHOUSE_CONN_ID = "clickhouse_reports"


def get_crm_connection():
    """
    Получаем параметры подключения к CRM из Airflow Connections.
    """
    conn = BaseHook.get_connection(CRM_CONN_ID)

    return psycopg2.connect(
        host=conn.host,
        port=conn.port,
        dbname=conn.schema,
        user=conn.login,
        password=conn.password,
    )


def get_clickhouse_client():
    """
    Получаем параметры подключения к ClickHouse из Airflow Connections.
    """
    conn = BaseHook.get_connection(CLICKHOUSE_CONN_ID)

    return clickhouse_connect.get_client(
        host=conn.host,
        port=conn.port,
        username=conn.login or "default",
        password=conn.password or "",
        database=conn.schema or "reports",
    )


def check_crm_connection():
    """
    Проверяем доступность CRM PostgreSQL.
    """
    connection = get_crm_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1;")
            result = cursor.fetchone()
            print(f"CRM connection is OK: {result}")
    finally:
        connection.close()


def check_clickhouse_connection():
    """
    Проверяем доступность ClickHouse.
    """
    client = get_clickhouse_client()
    result = client.query("SELECT 1").result_rows
    print(f"ClickHouse connection is OK: {result}")


def load_crm_snapshot_to_clickhouse():
    """
    Extract + Load:
    Забираем клиентов и протезы из CRM PostgreSQL
    и загружаем их в ClickHouse snapshot-таблицу.
    """
    crm_connection = get_crm_connection()

    try:
        with crm_connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    c.id AS user_id,
                    c.full_name AS user_full_name,
                    COALESCE(c.email, '') AS email,
                    p.id AS prosthetic_id,
                    p.model AS prosthetic_model,
                    COALESCE(p.serial_number, '') AS serial_number
                FROM clients c
                         JOIN prosthetics p ON p.client_id = c.id;
                """
            )
            rows = cursor.fetchall()
    finally:
        crm_connection.close()

    print(f"Rows extracted from CRM: {len(rows)}")

    client = get_clickhouse_client()

    client.command("TRUNCATE TABLE reports.crm_prosthetics_snapshot")

    prepared_rows = [
        (
            user_id,
            user_full_name,
            email,
            prosthetic_id,
            prosthetic_model,
            serial_number,
            datetime.utcnow(),
        )
        for (
            user_id,
            user_full_name,
            email,
            prosthetic_id,
            prosthetic_model,
            serial_number,
        ) in rows
    ]

    if prepared_rows:
        client.insert(
            "reports.crm_prosthetics_snapshot",
            prepared_rows,
            column_names=[
                "user_id",
                "user_full_name",
                "email",
                "prosthetic_id",
                "prosthetic_model",
                "serial_number",
                "loaded_at",
            ],
        )

    print("CRM snapshot loaded to ClickHouse")


def refresh_report_mart():
    """
    Transform + Load:
    Пересобираем готовую витрину отчётности.

    Здесь объединяются:
    - CRM snapshot: пользователь, протез, модель, серийный номер;
    - telemetry_events: события работы протеза.

    На выходе получаем готовую таблицу для backend API /reports.
    """
    client = get_clickhouse_client()

    client.command("TRUNCATE TABLE reports.user_prosthetic_report_mart")

    client.command(
        """
        INSERT INTO reports.user_prosthetic_report_mart
        SELECT
            crm.user_id,
            crm.prosthetic_id,
            toDate(t.event_time) AS report_date,

            crm.user_full_name,
            crm.prosthetic_model,
            crm.serial_number,

            count() AS total_events,
            avg(t.response_time_ms) AS avg_response_time_ms,
            max(t.response_time_ms) AS max_response_time_ms,
            avg(t.sensor_noise) AS avg_sensor_noise,
            countIf(t.battery_level < 20) AS low_battery_events,

            max(t.event_time) AS last_telemetry_at,
            now() AS updated_at
        FROM reports.crm_prosthetics_snapshot crm
                 INNER JOIN reports.telemetry_events t
                            ON t.prosthetic_id = crm.prosthetic_id
        GROUP BY
            crm.user_id,
            crm.prosthetic_id,
            toDate(t.event_time),
            crm.user_full_name,
            crm.prosthetic_model,
            crm.serial_number
        """
    )

    print("Report mart refreshed")


def validate_report_mart():
    """
    Проверяем, что витрина заполнилась.
    """
    client = get_clickhouse_client()

    result = client.query(
        """
        SELECT count()
        FROM reports.user_prosthetic_report_mart
        """
    ).result_rows

    row_count = result[0][0]
    print(f"Rows in report mart: {row_count}")

    if row_count == 0:
        raise ValueError("Report mart is empty after ETL")


default_args = {
    "owner": "bionicpro",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=1),
}


with DAG(
        dag_id="bionicpro_reports_etl",
        description="ETL для подготовки витрины отчётов по работе бионических протезов",
        default_args=default_args,
        start_date=datetime(2026, 1, 1),
        schedule="0 * * * *",
        catchup=False,
        tags=["bionicpro", "reports", "etl"],
) as dag:

    check_crm_connection_task = PythonOperator(
        task_id="check_crm_connection",
        python_callable=check_crm_connection,
    )

    check_clickhouse_connection_task = PythonOperator(
        task_id="check_clickhouse_connection",
        python_callable=check_clickhouse_connection,
    )


    load_crm_snapshot_task = PythonOperator(
        task_id="load_crm_snapshot_to_clickhouse",
        python_callable=load_crm_snapshot_to_clickhouse,
    )

    refresh_report_mart_task = PythonOperator(
        task_id="refresh_report_mart",
        python_callable=refresh_report_mart,
    )

    validate_report_mart_task = PythonOperator(
        task_id="validate_report_mart",
        python_callable=validate_report_mart,
    )

    (
            [check_crm_connection_task, check_clickhouse_connection_task]
            >> load_crm_snapshot_task
            >> refresh_report_mart_task
            >> validate_report_mart_task
    )