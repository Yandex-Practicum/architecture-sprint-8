from __future__ import annotations

import json
import logging
import os
import urllib.parse
import urllib.request

import pendulum
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook

log = logging.getLogger(__name__)

# --- connection settings (overridable via environment) ---------------------
CRM_CONN_ID = os.environ.get("CRM_CONN_ID", "crm_postgres")
CH_URL = os.environ.get("CLICKHOUSE_HTTP_URL", "http://clickhouse:8123")
CH_USER = os.environ.get("CLICKHOUSE_USER", "default")
CH_PASSWORD = os.environ.get("CLICKHOUSE_PASSWORD", "")
CH_DB = os.environ.get("CLICKHOUSE_DB", "reports")
CH_TABLE = "user_report_mart"

# Aggregate telemetry in the "разрез клиентов" (per client, per day), joined
# with CRM master data. Bind :process_before to only include finished periods.
AGG_SQL = """
    SELECT
        (t.ts)::date                AS report_date,
        c.client_id,
        c.username,
        c.full_name,
        c.prosthesis_serial,
        c.region,
        count(*)                    AS telemetry_events,
        avg(t.response_time_ms)     AS avg_response_ms,
        max(t.response_time_ms)     AS max_response_ms,
        avg(t.signal_quality)       AS avg_signal_quality,
        sum(t.movements)            AS total_movements,
        avg(t.battery_pct)          AS avg_battery_pct
    FROM telemetry t
    JOIN clients c ON c.client_id = t.client_id
    WHERE t.ts < %(process_before)s
    GROUP BY 1, 2, 3, 4, 5, 6
    ORDER BY 1, 2
"""

CREATE_TABLE_SQL = f"""
    CREATE TABLE IF NOT EXISTS {CH_DB}.{CH_TABLE}
    (
        report_date        Date,
        client_id          UInt64,
        username           String,
        full_name          String,
        prosthesis_serial  String,
        region             String,
        telemetry_events   UInt64,
        avg_response_ms    Float64,
        max_response_ms    Float64,
        avg_signal_quality Float64,
        total_movements    UInt64,
        avg_battery_pct    Float64,
        updated_at         DateTime DEFAULT now()
    )
    ENGINE = ReplacingMergeTree(updated_at)
    ORDER BY (username, report_date)
"""

INSERT_COLUMNS = (
    "report_date, client_id, username, full_name, prosthesis_serial, region, "
    "telemetry_events, avg_response_ms, max_response_ms, avg_signal_quality, "
    "total_movements, avg_battery_pct"
)


def _clickhouse(sql: str, data: bytes | None = None) -> str:
    """Execute a statement against ClickHouse over its HTTP interface."""
    url = CH_URL + "/?" + urllib.parse.urlencode({"query": sql})
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("X-ClickHouse-User", CH_USER)
    if CH_PASSWORD:
        req.add_header("X-ClickHouse-Key", CH_PASSWORD)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode()


def ensure_schema() -> None:
    _clickhouse(f"CREATE DATABASE IF NOT EXISTS {CH_DB}")
    _clickhouse(CREATE_TABLE_SQL)
    log.info("ClickHouse schema %s.%s is ready", CH_DB, CH_TABLE)


def load_mart(**context) -> None:
    process_before = context["data_interval_end"]
    log.info("loading telemetry with ts < %s", process_before)

    hook = PostgresHook(postgres_conn_id=CRM_CONN_ID)
    rows = hook.get_records(
        AGG_SQL, parameters={"process_before": process_before.to_datetime_string()}
    )
    if not rows:
        log.info("no telemetry to load for this interval")
        return

    lines = []
    for r in rows:
        lines.append(json.dumps({
            "report_date": str(r[0]),
            "client_id": int(r[1]),
            "username": r[2],
            "full_name": r[3],
            "prosthesis_serial": r[4],
            "region": r[5],
            "telemetry_events": int(r[6]),
            "avg_response_ms": float(r[7]),
            "max_response_ms": float(r[8]),
            "avg_signal_quality": float(r[9]),
            "total_movements": int(r[10]),
            "avg_battery_pct": float(r[11]),
        }))

    payload = ("\n".join(lines)).encode("utf-8")
    _clickhouse(
        f"INSERT INTO {CH_DB}.{CH_TABLE} ({INSERT_COLUMNS}) FORMAT JSONEachRow",
        data=payload,
    )
    log.info("loaded %d aggregated rows into %s.%s", len(lines), CH_DB, CH_TABLE)


with DAG(
    dag_id="reports_etl",
    description="CRM + telemetry → ClickHouse reporting mart",
    schedule="@daily",
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    catchup=False,
    tags=["bionicpro", "reports", "etl"],
    default_args={"retries": 1, "retry_delay": pendulum.duration(minutes=1)},
) as dag:
    ensure_clickhouse_schema = PythonOperator(
        task_id="ensure_clickhouse_schema",
        python_callable=ensure_schema,
    )
    load_report_mart = PythonOperator(
        task_id="load_report_mart",
        python_callable=load_mart,
    )

    ensure_clickhouse_schema >> load_report_mart
