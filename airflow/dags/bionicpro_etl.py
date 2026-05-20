import csv
import os
from datetime import date, datetime, timedelta

import clickhouse_driver
from airflow import DAG
from airflow.operators.python import PythonOperator

DATA_DIR = os.getenv("DATA_DIR", "/opt/airflow/data")

CLICKHOUSE = dict(
    host=os.getenv("CLICKHOUSE_HOST", "clickhouse"),
    port=int(os.getenv("CLICKHOUSE_PORT", "9000")),
    database=os.getenv("CLICKHOUSE_DB", "bionicpro"),
)


def extract_and_load_crm(**_ctx) -> None:
    path = os.path.join(DATA_DIR, "crm_clients.csv")
    rows = []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            rows.append({
                "user_id": row["user_id"],
                "device_id": row["device_id"],
                "client_name": row["client_name"],
                "client_email": row["client_email"],
                "prosthesis_model": row["prosthesis_model"],
                "purchase_date": date.fromisoformat(row["purchase_date"]),
            })

    ch = clickhouse_driver.Client(**CLICKHOUSE)
    ch.execute("TRUNCATE TABLE crm_clients")
    if rows:
        ch.execute(
            "INSERT INTO crm_clients "
            "(user_id, device_id, client_name, client_email, prosthesis_model, purchase_date) VALUES",
            rows,
        )


def extract_and_load_telemetry(**_ctx) -> None:
    path = os.path.join(DATA_DIR, "telemetry.csv")
    rows = []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            rows.append({
                "user_id": row["user_id"],
                "device_id": row["device_id"],
                "timestamp": datetime.fromisoformat(row["timestamp"]),
                "signal_type": row["signal_type"],
                "signal_value": float(row["signal_value"]),
                "movement_detected": row["movement_detected"],
            })

    if rows:
        ch = clickhouse_driver.Client(**CLICKHOUSE)
        ch.execute(
            "INSERT INTO telemetry "
            "(user_id, device_id, timestamp, signal_type, signal_value, movement_detected) VALUES",
            rows,
        )


def refresh_user_report_mart(**ctx) -> None:
    report_date = ctx["data_interval_start"].date()

    ch = clickhouse_driver.Client(**CLICKHOUSE)

    ch.execute(
        "ALTER TABLE user_report_mart DELETE WHERE report_date = %(d)s",
        {"d": str(report_date)},
    )

    ch.execute(
        f"""
        INSERT INTO user_report_mart
        SELECT
            c.user_id,
            c.device_id,
            c.client_name,
            c.client_email,
            c.prosthesis_model,
            c.purchase_date,
            count()                                      AS total_sessions,
            countIf(t.movement_detected = 'true')        AS total_movements,
            nullIf(max(t.timestamp), toDateTime(0))      AS last_activity,
            avgIfOrNull(t.signal_value, t.user_id != '') AS avg_signal_quality,
            toDate('{report_date}')                      AS report_date
        FROM crm_clients AS c
        LEFT JOIN (
            SELECT * FROM telemetry WHERE toDate(timestamp) = toDate('{report_date}')
        ) AS t ON c.user_id = t.user_id
        GROUP BY
            c.user_id, c.device_id, c.client_name,
            c.client_email, c.prosthesis_model, c.purchase_date
        """
    )


default_args = {
    "owner": "bionicpro",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
        "bionicpro_etl",
        default_args=default_args,
        schedule_interval="@once",
        start_date=datetime(2026, 1, 1),
        catchup=False,
) as dag:
    t_crm = PythonOperator(task_id="extract_and_load_crm", python_callable=extract_and_load_crm)
    t_tel = PythonOperator(task_id="extract_and_load_telemetry", python_callable=extract_and_load_telemetry)
    t_mart = PythonOperator(task_id="refresh_user_report_mart", python_callable=refresh_user_report_mart)

    [t_crm, t_tel] >> t_mart
