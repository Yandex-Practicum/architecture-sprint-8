"""
BionicPRO ETL Reporting DAG

ETL-процесс:
1. Extract телеметрии из PostgreSQL → Load в ClickHouse raw_telemetry
2. Extract данных CRM из PostgreSQL (симуляция Oracle) → Load в ClickHouse raw_crm_clients
3. Transform: построение витрины report_user_prosthesis в ClickHouse
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

import psycopg2
from clickhouse_driver import Client as CHClient

# =============================================
# Конфигурация подключений
# =============================================

PG_CONFIG = {
    "host": "data_db",
    "port": 5432,
    "dbname": "bionicpro",
    "user": "bionicpro",
    "password": "bionicpro",
}

CH_CONFIG = {
    "host": "clickhouse",
    "port": 9000,
}

# =============================================
# ETL-функции
# =============================================


def extract_load_telemetry(**kwargs):
    """Extract телеметрии из PostgreSQL и загрузка в ClickHouse."""
    pg_conn = psycopg2.connect(**PG_CONFIG)
    pg_cursor = pg_conn.cursor()

    pg_cursor.execute("""
        SELECT prosthesis_id, timestamp, signal_strength,
               response_time_ms, battery_level, movement_type,
               anomaly_detected::int
        FROM telemetry
    """)
    rows = pg_cursor.fetchall()
    pg_cursor.close()
    pg_conn.close()

    if not rows:
        print("No telemetry data to load")
        return

    ch = CHClient(**CH_CONFIG)
    # Очищаем raw-таблицу перед загрузкой (full refresh)
    ch.execute("TRUNCATE TABLE IF EXISTS raw_telemetry")
    ch.execute(
        "INSERT INTO raw_telemetry VALUES",
        rows,
    )
    print(f"Loaded {len(rows)} telemetry records into ClickHouse")


def extract_load_crm(**kwargs):
    """Extract данных клиентов и протезов из CRM и загрузка в ClickHouse."""
    pg_conn = psycopg2.connect(**PG_CONFIG)
    pg_cursor = pg_conn.cursor()

    pg_cursor.execute("""
        SELECT c.external_id, c.first_name, c.last_name, c.email,
               p.prosthesis_id, p.model, p.installation_date
        FROM crm_clients c
        JOIN crm_prostheses p ON p.client_id = c.id
        WHERE p.status = 'active'
    """)
    rows = pg_cursor.fetchall()
    pg_cursor.close()
    pg_conn.close()

    if not rows:
        print("No CRM data to load")
        return

    ch = CHClient(**CH_CONFIG)
    ch.execute("TRUNCATE TABLE IF EXISTS raw_crm_clients")
    ch.execute(
        "INSERT INTO raw_crm_clients VALUES",
        rows,
    )
    print(f"Loaded {len(rows)} CRM client records into ClickHouse")


def build_report_mart(**kwargs):
    """Построение витрины отчётности: агрегация телеметрии по клиентам."""
    ch = CHClient(**CH_CONFIG)

    # Очищаем витрину перед перестроением (full refresh)
    ch.execute("TRUNCATE TABLE IF EXISTS report_user_prosthesis")

    ch.execute("""
        INSERT INTO report_user_prosthesis
        SELECT
            c.client_id,
            concat(c.first_name, ' ', c.last_name) AS client_name,
            c.email,
            t.prosthesis_id,
            c.prosthesis_model,
            toDate(t.timestamp) AS report_date,
            count() AS total_movements,
            round(avg(t.response_time_ms), 2) AS avg_response_time_ms,
            round(avg(t.signal_strength), 4) AS avg_signal_strength,
            round(avg(t.battery_level), 2) AS avg_battery_level,
            toUInt64(
                dateDiff('minute', min(t.timestamp), max(t.timestamp))
            ) AS active_minutes,
            countIf(t.anomaly_detected = 1) AS anomaly_count
        FROM raw_telemetry t
        JOIN raw_crm_clients c ON t.prosthesis_id = c.prosthesis_id
        GROUP BY
            c.client_id,
            client_name,
            c.email,
            t.prosthesis_id,
            c.prosthesis_model,
            report_date
        ORDER BY client_id, prosthesis_id, report_date
    """)

    result = ch.execute("SELECT count() FROM report_user_prosthesis")
    print(f"Report mart built: {result[0][0]} rows")


# =============================================
# DAG
# =============================================

default_args = {
    "owner": "bionicpro",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="bionicpro_etl_reporting",
    default_args=default_args,
    description="ETL: PostgreSQL + CRM → ClickHouse → витрина отчётности",
    schedule="0 2 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["bionicpro", "etl", "reporting"],
) as dag:

    task_telemetry = PythonOperator(
        task_id="extract_load_telemetry",
        python_callable=extract_load_telemetry,
    )

    task_crm = PythonOperator(
        task_id="extract_load_crm",
        python_callable=extract_load_crm,
    )

    task_mart = PythonOperator(
        task_id="build_report_mart",
        python_callable=build_report_mart,
    )

    # Extract-задачи выполняются параллельно, затем строится витрина
    [task_telemetry, task_crm] >> task_mart
