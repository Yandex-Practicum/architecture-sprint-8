"""Строит телеметрическую часть витрины отчётов по клиентам.

Раньше этот DAG также при каждом запуске массово читал таблицу customers
из CRM, что конкурировало с собственной OLTP-нагрузкой CRM. Теперь измерение
с клиентами непрерывно поступает в ClickHouse через Debezium CDC (см. debezium/
и clickhouse/init/02_cdc_mart.sql), поэтому этот DAG обращается только к базе
телеметрии. reports.user_report_mart_v2_mv (ClickHouse) объединяет обе стороны
при вставке.

Параметры подключения к БД берутся из Airflow Variables (Admin -> Variables),
а не хардкодятся в коде DAG. Значения по умолчанию соответствуют сервисам
из docker-compose.yaml и используются, если переменная не задана. В этом
стеке переменные заведены через переменные окружения контейнера airflow
с префиксом AIRFLOW_VAR_* (см. docker-compose.yaml) - это официальный
механизм Airflow, который не требует обращения к базе метаданных.
"""
from datetime import datetime

import clickhouse_connect
import psycopg2
import psycopg2.extras
from airflow import DAG
from airflow.models import Variable
from airflow.operators.python import PythonOperator


def get_telemetry_dsn() -> dict:
    # Variable.get() намеренно вызывается здесь, внутри функции задачи, а не
    # на уровне модуля - обращение к Variables при разборе DAG на каждой
    # итерации scheduler'а является анти-паттерном Airflow.
    return {
        "host": Variable.get("telemetry_db_host", default_var="telemetry_db"),
        "port": int(Variable.get("telemetry_db_port", default_var="5432")),
        "dbname": Variable.get("telemetry_db_name", default_var="telemetry"),
        "user": Variable.get("telemetry_db_user", default_var="telemetry_user"),
        "password": Variable.get("telemetry_db_password", default_var="telemetry_password"),
    }


def get_clickhouse_params() -> dict:
    return {
        "host": Variable.get("clickhouse_host", default_var="clickhouse"),
        "username": Variable.get("clickhouse_user", default_var="reports"),
        "password": Variable.get("clickhouse_password", default_var="reports_password"),
    }


def extract_telemetry_aggregates():
    query = """
        SELECT
            customer_id,
            count(*) AS events_count,
            avg(myosignal_quality) AS avg_myosignal_quality,
            avg(recognition_latency_ms) AS avg_recognition_latency_ms,
            min(battery_level) AS min_battery_level,
            (array_agg(action_recognized ORDER BY event_ts DESC))[1] AS last_action_recognized
        FROM telemetry_events
        GROUP BY customer_id
    """
    with psycopg2.connect(**get_telemetry_dsn()) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query)
            return cur.fetchall()


def build_telemetry_agg(**_context):
    aggregates = extract_telemetry_aggregates()
    if not aggregates:
        return

    generated_at = datetime.utcnow()
    rows = [
        (
            row["customer_id"],
            generated_at,
            int(row["events_count"]),
            float(row["avg_myosignal_quality"]),
            float(row["avg_recognition_latency_ms"]),
            int(row["min_battery_level"]),
            row["last_action_recognized"],
        )
        for row in aggregates
    ]

    client = clickhouse_connect.get_client(**get_clickhouse_params())
    client.insert(
        "reports.telemetry_agg",
        rows,
        column_names=[
            "customer_id", "agg_generated_at", "events_count", "avg_myosignal_quality",
            "avg_recognition_latency_ms", "min_battery_level", "last_action_recognized",
        ],
    )


with DAG(
    dag_id="reports_etl",
    description="Aggregates prosthesis telemetry into the ClickHouse reporting mart",
    schedule="0 * * * *",  # ежечасно
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["bionicpro", "reports"],
) as dag:
    PythonOperator(
        task_id="build_telemetry_agg",
        python_callable=build_telemetry_agg,
    )
