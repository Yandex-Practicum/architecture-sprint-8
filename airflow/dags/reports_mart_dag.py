import os
from datetime import date, datetime, timedelta
from typing import Any, List, Tuple

import boto3
import pandas as pd
from airflow import DAG
from airflow.hooks.base import BaseHook
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from clickhouse_driver import Client

CONN_API = "read_from_api_db"
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

SQL_REPORTS_MART_REBUILD = """
INSERT INTO bionicpro.reports_mart
    (user_id, period_date, avg_temperature, avg_pulse, plan_code, data_watermark_date)
SELECT
    t.user_id AS user_id,
    t.period_date AS period_date,
    t.avg_temperature AS avg_temperature,
    t.avg_pulse AS avg_pulse,
    coalesce(c.plan_code, '') AS plan_code,
    coalesce(
        (SELECT max(period_date) FROM bionicpro.telemetry_daily_agg),
        toDate('1970-01-01')
    ) AS data_watermark_date
FROM bionicpro.telemetry_daily_agg AS t
LEFT JOIN
(
    SELECT
        user_id,
        argMax(plan_code, updated_at) AS plan_code
    FROM bionicpro.crm_customer_plan
    GROUP BY user_id
) AS c ON t.user_id = c.user_id
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


def _load_telemetry_refresh_mart(ti: Any, **context: Any) -> None:
    telemetry_json = ti.xcom_pull(task_ids="extract_telemetry")
    tel = pd.read_json(telemetry_json) if telemetry_json else pd.DataFrame()

    rows: List[Tuple[Any, ...]] = []
    if not tel.empty:
        for _, r in tel.iterrows():
            rows.append(
                (
                    str(r["user_id"]),
                    _parse_period_date(r["period_date"]),
                    None if pd.isna(r["avg_temperature"]) else float(r["avg_temperature"]),
                    None if pd.isna(r["avg_pulse"]) else float(r["avg_pulse"]),
                )
            )

    client = _clickhouse_client()
    client.execute("TRUNCATE TABLE IF EXISTS bionicpro.telemetry_daily_agg")
    if rows:
        client.execute(
            """
            INSERT INTO bionicpro.telemetry_daily_agg
                (user_id, period_date, avg_temperature, avg_pulse)
            VALUES
            """,
            rows,
        )
    client.execute("TRUNCATE TABLE IF EXISTS bionicpro.reports_mart")
    client.execute(SQL_REPORTS_MART_REBUILD)


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
    description="Телеметрия api_db → ClickHouse; CRM через Kafka/CDC; витрина TRUNCATE+INSERT",
    schedule_interval="@daily",
    start_date=datetime(2026, 3, 1),
    catchup=False,
    tags=["clickhouse", "reports", "etl", "kafka", "cdc"],
) as dag:
    extract_telemetry = PythonOperator(
        task_id="extract_telemetry",
        python_callable=_extract_telemetry,
    )
    load_telemetry_refresh_mart = PythonOperator(
        task_id="load_telemetry_refresh_mart",
        python_callable=_load_telemetry_refresh_mart,
    )
    purge_reports_s3 = PythonOperator(
        task_id="purge_reports_s3",
        python_callable=_purge_reports_s3,
    )

    extract_telemetry >> load_telemetry_refresh_mart >> purge_reports_s3
