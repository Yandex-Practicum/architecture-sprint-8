"""
BionicPRO ETL DAG
=================
Extracts patient and telemetry data from the CRM PostgreSQL database,
aggregates it by user and calendar day, and upserts the result into
the OLAP reporting mart (user_report_mart).

Schedule: daily at 01:00 UTC
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

import psycopg2
import psycopg2.extras
from airflow import DAG
from airflow.operators.python import PythonOperator

log = logging.getLogger(__name__)

# ── Connection parameters (injected via docker-compose env) ───────────────────
import os

CRM_DSN = {
    "host":     os.getenv("CRM_DB_HOST", "crm-db"),
    "port":     int(os.getenv("CRM_DB_PORT", "5432")),
    "dbname":   os.getenv("CRM_DB_NAME", "crm_db"),
    "user":     os.getenv("CRM_DB_USER", "crm_user"),
    "password": os.getenv("CRM_DB_PASSWORD", "crm_password"),
}

OLAP_DSN = {
    "host":     os.getenv("OLAP_DB_HOST", "olap-db"),
    "port":     int(os.getenv("OLAP_DB_PORT", "5432")),
    "dbname":   os.getenv("OLAP_DB_NAME", "olap_db"),
    "user":     os.getenv("OLAP_DB_USER", "olap_user"),
    "password": os.getenv("OLAP_DB_PASSWORD", "olap_password"),
}

# ── Default DAG args ──────────────────────────────────────────────────────────
default_args = {
    "owner": "bionicpro",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
    "email_on_failure": False,
}


# ── Task functions ─────────────────────────────────────────────────────────────

def extract_patients(**context) -> None:
    """Pull all patients from CRM and push to XCom."""
    with psycopg2.connect(**CRM_DSN) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT username, email, full_name, device_serial, device_model
                FROM patients
            """)
            rows = [dict(r) for r in cur.fetchall()]

    log.info("Extracted %d patients from CRM", len(rows))
    context["ti"].xcom_push(key="patients", value=rows)


def extract_telemetry(**context) -> None:
    """
    Pull telemetry for the previous calendar day from CRM.
    Uses the logical_date of the DAG run as the reference point.
    """
    logical_date: date = context["logical_date"].date()
    target_date = logical_date - timedelta(days=1)

    with psycopg2.connect(**CRM_DSN) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    patient_username,
                    DATE(recorded_at)         AS rec_date,
                    AVG(battery_level)        AS avg_battery,
                    SUM(active_hours)         AS total_hours,
                    SUM(steps_count)          AS total_steps,
                    COUNT(*)                  AS event_count
                FROM telemetry
                WHERE DATE(recorded_at) = %s
                GROUP BY patient_username, DATE(recorded_at)
            """, (target_date,))
            rows = [dict(r) for r in cur.fetchall()]

    log.info("Extracted telemetry for %s: %d rows", target_date, len(rows))
    context["ti"].xcom_push(key="telemetry", value=rows)
    context["ti"].xcom_push(key="target_date", value=str(target_date))


def transform_and_load(**context) -> None:
    """
    Join patients with telemetry aggregates and upsert into OLAP mart.
    Patients with no telemetry for the day still get a zero-row entry
    so the mart always has full coverage.
    """
    ti = context["ti"]
    patients: list[dict] = ti.xcom_pull(key="patients", task_ids="extract_patients")
    telemetry: list[dict] = ti.xcom_pull(key="telemetry", task_ids="extract_telemetry")
    target_date_str: str = ti.xcom_pull(key="target_date", task_ids="extract_telemetry")
    target_date = date.fromisoformat(target_date_str)

    # Build a lookup dict: username -> telemetry aggregate
    tele_map: dict[str, dict] = {r["patient_username"]: r for r in telemetry}

    rows_to_upsert = []
    for patient in patients:
        uname = patient["username"]
        tele = tele_map.get(uname, {})
        rows_to_upsert.append((
            uname,
            target_date,
            patient.get("full_name"),
            patient.get("device_serial"),
            patient.get("device_model"),
            float(tele.get("total_hours") or 0),
            float(tele.get("avg_battery") or 0),
            int(tele.get("total_steps") or 0),
            int(tele.get("event_count") or 0),
            datetime.utcnow(),
        ))

    if not rows_to_upsert:
        log.info("Nothing to upsert for %s", target_date)
        return

    upsert_sql = """
        INSERT INTO user_report_mart (
            username, report_date, full_name, device_serial, device_model,
            total_active_hours, avg_battery_level, total_steps, event_count, etl_updated_at
        ) VALUES %s
        ON CONFLICT (username, report_date) DO UPDATE SET
            full_name          = EXCLUDED.full_name,
            device_serial      = EXCLUDED.device_serial,
            device_model       = EXCLUDED.device_model,
            total_active_hours = EXCLUDED.total_active_hours,
            avg_battery_level  = EXCLUDED.avg_battery_level,
            total_steps        = EXCLUDED.total_steps,
            event_count        = EXCLUDED.event_count,
            etl_updated_at     = EXCLUDED.etl_updated_at
    """

    with psycopg2.connect(**OLAP_DSN) as conn:
        with conn.cursor() as cur:
            psycopg2.extras.execute_values(cur, upsert_sql, rows_to_upsert)
        conn.commit()

    log.info("Upserted %d rows into user_report_mart for %s", len(rows_to_upsert), target_date)


# ── DAG definition ─────────────────────────────────────────────────────────────
with DAG(
    dag_id="bionicpro_etl_dag",
    default_args=default_args,
    description="BionicPRO: Extract CRM data → aggregate → load OLAP mart",
    schedule_interval="0 1 * * *",   # daily at 01:00 UTC
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["bionicpro", "etl", "reports"],
) as dag:

    t1 = PythonOperator(
        task_id="extract_patients",
        python_callable=extract_patients,
    )

    t2 = PythonOperator(
        task_id="extract_telemetry",
        python_callable=extract_telemetry,
    )

    t3 = PythonOperator(
        task_id="transform_and_load",
        python_callable=transform_and_load,
    )

    t1 >> t2 >> t3
