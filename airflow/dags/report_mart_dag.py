"""
Airflow DAG: ежедневный ETL CRM + телеметрия → витрина `reports_mart` в ClickHouse.
Этапы:
1) extract_crm: вытягиваем профиль пользователя (email/plan/country).
2) extract_telemetry: агрегируем сырые события по user_id + дате.
3) transform: соединяем CRM + агрегации телеметрии, готовим строки витрины.
4) load_to_clickhouse: вставляем в `reports_mart`.

Подключение к ClickHouse задаётся переменными окружения:
CLICKHOUSE_HOST, CLICKHOUSE_PORT, CLICKHOUSE_USER, CLICKHOUSE_PASSWORD, CLICKHOUSE_DB.
"""

import os
from datetime import datetime, timedelta
from collections import defaultdict

import clickhouse_connect
from airflow import DAG
from airflow.operators.python import PythonOperator

CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "clickhouse")
CLICKHOUSE_PORT = int(os.getenv("CLICKHOUSE_PORT", "8123"))
CLICKHOUSE_USER = os.getenv("CLICKHOUSE_USER", "default")
CLICKHOUSE_PASSWORD = os.getenv("CLICKHOUSE_PASSWORD", "")
CLICKHOUSE_DB = os.getenv("CLICKHOUSE_DB", "default")


def extract_crm(**context):
    # TODO: заменить на реальный CRM источник (API / БД).
    crm_rows = [
        {"user_id": 14115120676845086225, "email": "user@example.com", "plan": "pro", "country": "RU"},
        {"user_id": 2222222222, "email": "user2@example.com", "plan": "basic", "country": "RU"},
    ]
    context["ti"].xcom_push(key="crm_rows", value=crm_rows)


def extract_telemetry(**context):
    # TODO: заменить на источник телеметрии (сырые данные в ClickHouse/DB/объектное хранилище).
    telemetry_rows = [
        {"user_id": 14115120676845086225, "ts": "2025-12-09", "actions": 120, "errors": 3, "active_minutes": 45},
        {"user_id": 2222222222, "ts": "2025-12-09", "actions": 80, "errors": 1, "active_minutes": 35},
    ]
    context["ti"].xcom_push(key="telemetry_rows", value=telemetry_rows)


def transform(**context):
    crm_rows = context["ti"].xcom_pull(key="crm_rows", task_ids="extract_crm")
    telemetry_rows = context["ti"].xcom_pull(key="telemetry_rows", task_ids="extract_telemetry")

    # Агрегация телеметрии по (user_id, date)
    agg = defaultdict(lambda: {"actions": 0, "errors": 0, "active_minutes": 0, "days": 0, "last_date": None})
    for row in telemetry_rows:
        uid = row["user_id"]
        day = row["ts"]
        agg_key = (uid, day)
        entry = agg[agg_key]
        entry["actions"] += row["actions"]
        entry["errors"] += row["errors"]
        entry["active_minutes"] += row["active_minutes"]
        entry["days"] += 1
        entry["last_date"] = day

    mart_rows = []
    crm_map = {c["user_id"]: c for c in crm_rows}

    for (uid, day), met in agg.items():
        crm = crm_map.get(uid, {})
        mart_rows.append(
            {
                "user_id": uid,
                "email": crm.get("email", ""),
                "plan": crm.get("plan", ""),
                "country": crm.get("country", ""),
                "period_date": day,
                "actions_total": met["actions"],
                "errors_total": met["errors"],
                "active_minutes_avg": met["active_minutes"] / met["days"] if met["days"] else 0,
            }
        )

    context["ti"].xcom_push(key="mart_rows", value=mart_rows)


def load_to_clickhouse(**context):
    mart_rows = context["ti"].xcom_pull(key="mart_rows", task_ids="transform")
    if not mart_rows:
        return

    client = clickhouse_connect.get_client(
        host=CLICKHOUSE_HOST,
        port=CLICKHOUSE_PORT,
        username=CLICKHOUSE_USER,
        password=CLICKHOUSE_PASSWORD,
        database=CLICKHOUSE_DB,
    )

    # Убеждаемся, что таблица есть
    client.command(
        """
        CREATE TABLE IF NOT EXISTS reports_mart
        (
            user_id UInt64,
            email String,
            plan String,
            country String,
            period_date Date,
            actions_total UInt64,
            errors_total UInt64,
            active_minutes_avg Float64
        )
        ENGINE = MergeTree
        PARTITION BY toYYYYMM(period_date)
        ORDER BY (user_id, period_date)
        """
    )

    client.insert(
        "reports_mart",
        [
            (
                row["user_id"],
                row["email"],
                row["plan"],
                row["country"],
                row["period_date"],
                row["actions_total"],
                row["errors_total"],
                row["active_minutes_avg"],
            )
            for row in mart_rows
        ],
        column_names=[
            "user_id",
            "email",
            "plan",
            "country",
            "period_date",
            "actions_total",
            "errors_total",
            "active_minutes_avg",
        ],
    )


default_args = {
    "owner": "data-eng",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="reports_mart_dag",
    default_args=default_args,
    start_date=datetime(2025, 1, 1),
    schedule_interval="30 0 * * *",  # ежедневно 00:30
    catchup=False,
    max_active_runs=1,
    tags=["reports", "etl"],
) as dag:

    t1 = PythonOperator(task_id="extract_crm", python_callable=extract_crm)
    t2 = PythonOperator(task_id="extract_telemetry", python_callable=extract_telemetry)
    t3 = PythonOperator(task_id="transform", python_callable=transform)
    t4 = PythonOperator(task_id="load_to_clickhouse", python_callable=load_to_clickhouse)

    [t1, t2] >> t3 >> t4
