import os
from datetime import date, datetime, timedelta, timezone
from typing import Any, List, Tuple

import boto3
import pandas as pd
from airflow import DAG
from airflow.hooks.base import BaseHook
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from clickhouse_driver import Client

CONN_API = "read_from_api_db"
CONN_CRM = "read_from_crm_db"
CONN_CLICKHOUSE = "clickhouse_bionicpro"

SQL_TELEMETRY_AGG = """
SELECT
    user_id,
    (measured_at AT TIME ZONE 'UTC')::date AS period_date,
    AVG(temperature_c)::double precision AS avg_temperature,
    AVG(pulse_bpm)::double precision AS avg_pulse
FROM telemetry
GROUP BY user_id, (measured_at AT TIME ZONE 'UTC')::date
ORDER BY user_id, period_date
"""

SQL_TELEMETRY_WATERMARK = """
SELECT (MAX(measured_at) AT TIME ZONE 'UTC')::date
FROM telemetry
"""

SQL_CRM = """
SELECT user_id, plan_code
FROM customer_plan
"""


def _parse_period_date(value: Any) -> date:
    if isinstance(value, pd.Timestamp):
        return value.date()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return pd.to_datetime(value).date()
    raise TypeError(f"Unsupported period_date type: {type(value)!r}")


def _extract_telemetry(**context: Any) -> str:
    hook = PostgresHook(postgres_conn_id=CONN_API)
    df = hook.get_pandas_df(SQL_TELEMETRY_AGG)
    return df.to_json(date_format="iso")


def _extract_crm(**context: Any) -> str:
    hook = PostgresHook(postgres_conn_id=CONN_CRM)
    df = hook.get_pandas_df(SQL_CRM)
    return df.to_json(date_format="iso")


def _clickhouse_client() -> Client:
    c = BaseHook.get_connection(CONN_CLICKHOUSE)
    extra = c.extra_dejson or {}
    database = extra.get("database", "bionicpro")
    port = c.port or 9000
    return Client(
        host=c.host,
        port=int(port),
        user=c.login or "default",
        password=c.password or "",
        database=database,
    )


def _build_rows(
    telemetry_json: str, crm_json: str, watermark_date_str: str
) -> List[Tuple[Any, ...]]:
    tel = pd.read_json(telemetry_json)
    crm = pd.read_json(crm_json)
    if tel.empty:
        return []

    merged = tel.merge(crm, on="user_id", how="left")
    merged["plan_code"] = merged["plan_code"].fillna("").astype(str)
    wm = pd.to_datetime(watermark_date_str).date()
    merged["data_watermark_date"] = wm

    rows: List[Tuple[Any, ...]] = []
    for _, r in merged.iterrows():
        rows.append(
            (
                str(r["user_id"]),
                _parse_period_date(r["period_date"]),
                None if pd.isna(r["avg_temperature"]) else float(r["avg_temperature"]),
                None if pd.isna(r["avg_pulse"]) else float(r["avg_pulse"]),
                str(r["plan_code"]),
                r["data_watermark_date"],
            )
        )
    return rows


def _load_mart(ti: Any, **context: Any) -> None:
    telemetry_json = ti.xcom_pull(task_ids="extract_telemetry")
    crm_json = ti.xcom_pull(task_ids="extract_crm")

    hook = PostgresHook(postgres_conn_id=CONN_API)
    wm_row = hook.get_first(SQL_TELEMETRY_WATERMARK)
    if wm_row and wm_row[0] is not None:
        watermark_date = wm_row[0]
        watermark_date_str = (
            watermark_date.isoformat()
            if hasattr(watermark_date, "isoformat")
            else str(watermark_date)
        )
    else:
        watermark_date_str = datetime.now(timezone.utc).date().isoformat()

    rows = _build_rows(telemetry_json, crm_json, watermark_date_str)
    client = _clickhouse_client()
    client.execute("TRUNCATE TABLE IF EXISTS bionicpro.reports_mart")
    if rows:
        client.execute(
            """
            INSERT INTO bionicpro.reports_mart
                (user_id, period_date, avg_temperature, avg_pulse, plan_code, data_watermark_date)
            VALUES
            """,
            rows,
        )


def _purge_reports_s3(**context: Any) -> None:
    endpoint = os.environ.get("REPORTS_S3_ENDPOINT_URL", "http://minio:9000")
    bucket = os.environ.get("REPORTS_S3_BUCKET", "bionicpro-reports")
    prefix = os.environ.get("REPORTS_S3_PREFIX", "reports/")
    access = os.environ.get("REPORTS_S3_ACCESS_KEY", "minioadmin")
    secret = os.environ.get("REPORTS_S3_SECRET_KEY", "minioadmin123")
    region = os.environ.get("REPORTS_S3_REGION", "us-east-1")

    s3 = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access,
        aws_secret_access_key=secret,
        region_name=region,
    )

    paginator = s3.get_paginator("list_objects_v2")
    keys: List[str] = []
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []) or []:
            keys.append(obj["Key"])

    if not keys:
        return

    for i in range(0, len(keys), 1000):
        batch = keys[i : i + 1000]
        s3.delete_objects(
            Bucket=bucket,
            Delete={"Objects": [{"Key": k} for k in batch]},
        )


default_args = {
    "owner": "bionicpro",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="reports_mart_daily",
    default_args=default_args,
    description="ETL телеметрии и CRM в витрину ClickHouse",
    schedule_interval="@daily",
    start_date=datetime(2026, 3, 1),
    catchup=False,
    tags=["clickhouse", "reports", "etl"],
) as dag:
    extract_telemetry = PythonOperator(
        task_id="extract_telemetry",
        python_callable=_extract_telemetry,
    )
    extract_crm = PythonOperator(
        task_id="extract_crm",
        python_callable=_extract_crm,
    )
    load_mart = PythonOperator(
        task_id="load_mart",
        python_callable=_load_mart,
    )
    purge_reports_s3 = PythonOperator(
        task_id="purge_reports_s3",
        python_callable=_purge_reports_s3,
    )

    [extract_telemetry, extract_crm] >> load_mart >> purge_reports_s3
