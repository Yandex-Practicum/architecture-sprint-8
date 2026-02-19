from __future__ import annotations

import os
import io
import csv
from datetime import date, datetime
from typing import Optional

from fastapi import FastAPI, Query, HTTPException
from pydantic import BaseModel
import clickhouse_connect

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

CH_HOST = os.getenv("CH_HOST", "clickhouse")
CH_PORT = int(os.getenv("CH_PORT", "8123"))
CH_USER = os.getenv("CH_USER", "default")
CH_PASSWORD = os.getenv("CH_PASSWORD", "")
CH_DATABASE = os.getenv("CH_DATABASE", "trends")
CH_SECURE = os.getenv("CH_SECURE", "false").lower() == "true"

MART_TABLE = os.getenv("CH_MART_TABLE", "mart_user_daily_report")

S3_ENDPOINT = os.getenv("S3_ENDPOINT", "http://minio:9000")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY", "minioadmin")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY", "minioadmin")
S3_BUCKET = os.getenv("S3_BUCKET", "reports")

CDN_BASE_URL = os.getenv("CDN_BASE_URL", "http://localhost:8089/reports").rstrip("/")


app = FastAPI(title="BionicPRO Reports API", version="1.1.0")


def get_ch_client():
    return clickhouse_connect.get_client(
        host=CH_HOST,
        port=CH_PORT,
        username=CH_USER,
        password=CH_PASSWORD,
        database=CH_DATABASE,
        secure=CH_SECURE,
    )


def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=S3_ACCESS_KEY,
        aws_secret_access_key=S3_SECRET_KEY,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )


class ReportLinkResponse(BaseModel):
    customer_id: str
    date_from: date
    date_to: date
    url: str
    s3_key: str
    cached: bool


def make_report_key(customer_id: str, date_from: date, date_to: date, version: str) -> str:

    return f"customer/{customer_id}/{date_from.isoformat()}_{date_to.isoformat()}/v{version}.csv"


def get_mart_version(customer_id: str, date_from: date, date_to: date) -> str:
    """
    Версия отчёта для инвалидации кеша:
    берём max(loaded_at) из витрины за период.
    ETL обновил витрину -> loaded_at изменился -> ключ отчёта изменился.
    """
    ch = get_ch_client()

    q = f"""
    SELECT toString(max(loaded_at))
    FROM {MART_TABLE}
    WHERE customer_id = %(customer_id)s
      AND day >= toDate(%(date_from)s)
      AND day <= toDate(%(date_to)s)
    """

    v = ch.query(
        q,
        parameters={
            "customer_id": customer_id,
            "date_from": str(date_from),
            "date_to": str(date_to),
        },
    ).result_rows[0][0]

    if not v or v == "None":
        return datetime.utcnow().strftime("%Y%m%d%H%M%S")

    v = v.split(".")[0]
    return v.replace("-", "").replace(":", "").replace(" ", "")


def s3_head_exists(s3, bucket: str, key: str) -> bool:
    try:
        s3.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if code in ("404", "NoSuchKey", "NotFound"):
            return False
        # другие ошибки лучше не скрывать
        raise


def fetch_mart_rows_as_csv(customer_id: str, date_from: date, date_to: date) -> bytes:
    ch = get_ch_client()

    q = f"""
    SELECT
      day,
      customer_id,
      prosthesis_id,
      full_name,
      email,
      phone,
      country,
      city,
      contract_id,
      samples_count,
      active_seconds,
      movements_count,
      errors_count,
      avg_battery,
      max_load
    FROM {MART_TABLE}
    WHERE customer_id = %(customer_id)s
      AND day >= toDate(%(date_from)s)
      AND day <= toDate(%(date_to)s)
    ORDER BY day ASC
    """

    res = ch.query(
        q,
        parameters={
            "customer_id": customer_id,
            "date_from": str(date_from),
            "date_to": str(date_to),
        },
    )

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(res.column_names)
    for r in res.result_rows:
        w.writerow(r)

    return buf.getvalue().encode("utf-8")

@app.get("/reports", response_model=ReportLinkResponse)
def get_report_link(
    customer_id: str = Query(..., description="ID клиента (как в витрине mart_user_daily_report)"),
    date_from: date = Query(..., description="Начало периода (включительно)"),
    date_to: date = Query(..., description="Конец периода (включительно)"),
):
    if date_to < date_from:
        raise HTTPException(status_code=400, detail="date_to must be >= date_from")

    version = get_mart_version(customer_id, date_from, date_to)
    key = make_report_key(customer_id, date_from, date_to, version)

    s3 = get_s3_client()

    if s3_head_exists(s3, S3_BUCKET, key):
        return ReportLinkResponse(
            customer_id=customer_id,
            date_from=date_from,
            date_to=date_to,
            url=f"{CDN_BASE_URL}/{key}",
            s3_key=key,
            cached=True,
        )

    csv_bytes = fetch_mart_rows_as_csv(customer_id, date_from, date_to)

    s3.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=csv_bytes,
        ContentType="text/csv; charset=utf-8",
        CacheControl="public, max-age=3600",
    )

    return ReportLinkResponse(
        customer_id=customer_id,
        date_from=date_from,
        date_to=date_to,
        url=f"{CDN_BASE_URL}/{key}",
        s3_key=key,
        cached=False,
    )


@app.get("/health")
def health():
    status = {"clickhouse": False, "minio": False}
    try:
        ch = get_ch_client()
        status["clickhouse"] = (ch.query("SELECT 1").result_rows[0][0] == 1)
    except Exception:
        pass

    try:
        s3 = get_s3_client()
        s3.head_bucket(Bucket=S3_BUCKET)
        status["minio"] = True
    except Exception:
        pass

    return {"status": "ok" if all(status.values()) else "degraded", **status}
