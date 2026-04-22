"""
Сервис отчётов: витрина в ClickHouse (OLAP). Задание 3 — кэш отчётов в S3 + CDN.
Задание 4 — витрина из CDC (KafkaEngine + MaterializedView), таблица из CLICKHOUSE_MART_TABLE.

Ключи S3: v1/<sha256(email)[:16]>/<data_through_date>.json — смена watermark даёт новый URL для CDN.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from typing import Any

import boto3
import clickhouse_connect
from botocore.exceptions import ClientError
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse

CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "localhost")
CLICKHOUSE_PORT = int(os.getenv("CLICKHOUSE_PORT", "9000"))
INTERNAL_TOKEN = os.getenv("INTERNAL_SERVICE_TOKEN", "change-me-internal")

S3_BUCKET = os.getenv("S3_BUCKET", "").strip()
S3_ENABLED = os.getenv("ENABLE_S3_CACHE", "true").lower() in ("1", "true", "yes")
CDN_PUBLIC_BASE = os.getenv("CDN_PUBLIC_BASE", "http://localhost:8090").rstrip("/")

_mart = os.getenv("CLICKHOUSE_MART_TABLE", "prosthetics_usage_mart_cdc")
if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", _mart):
    _mart = "prosthetics_usage_mart_cdc"
MART_FROM = f"reports.{_mart}"

app = FastAPI(title="BionicPRO Reports", version="1.1")


def ch_client():
    return clickhouse_connect.get_client(
        host=CLICKHOUSE_HOST,
        port=CLICKHOUSE_PORT,
        username=os.getenv("CLICKHOUSE_USER", "default"),
        password=os.getenv("CLICKHOUSE_PASSWORD", ""),
    )


def _s3():
    return boto3.client(
        "s3",
        endpoint_url=os.getenv("S3_ENDPOINT_URL", "http://localhost:9000"),
        aws_access_key_id=os.getenv("S3_ACCESS_KEY", "minioadmin"),
        aws_secret_access_key=os.getenv("S3_SECRET_KEY", "minioadmin"),
        region_name=os.getenv("S3_REGION", "us-east-1"),
    )


def s3_object_key(email: str, data_through) -> str:
    h = hashlib.sha256(email.encode("utf-8")).hexdigest()[:16]
    if hasattr(data_through, "isoformat"):
        d = data_through.isoformat()
    else:
        d = str(data_through)
    return f"v1/{h}/{d}.json"


def cdn_url_for_object_key(key: str) -> str:
    return f"{CDN_PUBLIC_BASE}/reports/{key}"


def s3_object_exists(key: str) -> bool:
    if not S3_BUCKET:
        return False
    try:
        _s3().head_object(Bucket=S3_BUCKET, Key=key)
        return True
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if code in ("404", "NoSuchKey", "NotFound"):
            return False
        raise


def put_report_json(key: str, body: bytes) -> None:
    _s3().put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=body,
        ContentType="application/json",
    )


def fetch_mart_rows(client, email: str, data_through, user_sub: str) -> list[dict[str, Any]]:
    params: dict[str, Any] = {
        "email": email,
        "through": data_through,
        "sub": user_sub,
    }
    q = f"""
    SELECT
      user_sub,
      user_email,
      report_bucket,
      telemetry_samples,
      telemetry_avg_amplitude,
      crm_customer_code,
      crm_orders_count,
      etl_batch_id,
      loaded_at
    FROM {MART_FROM} FINAL
    WHERE report_bucket <= {{through:Date}}
      AND user_email = {{email:String}}
    ORDER BY report_bucket DESC
    LIMIT 500
    """
    result = client.query(q, parameters=params)
    columns = list(result.column_names)
    return [dict(zip(columns, row)) for row in result.result_rows]


def build_report_payload(
    *,
    user_sub: str | None,
    user_email: str,
    data_through,
    rows: list[dict[str, Any]],
) -> bytes:
    d = str(data_through) if not hasattr(data_through, "isoformat") else data_through.isoformat()
    doc = {
        "user_sub": user_sub,
        "user_email": user_email,
        "data_through_date": d,
        "rows": rows,
        "count": len(rows),
    }
    return json.dumps(doc, default=str, ensure_ascii=False).encode("utf-8")


@app.get("/health")
def health():
    return {"status": "ok", "s3_cache": bool(S3_ENABLED and S3_BUCKET)}


@app.get("/reports")
def get_report(
    x_internal_token: str | None = Header(default=None, alias="X-Internal-Token"),
    x_user_sub: str | None = Header(default=None, alias="X-User-Sub"),
    x_user_email: str | None = Header(default=None, alias="X-User-Email"),
):
    if not x_internal_token or x_internal_token != INTERNAL_TOKEN:
        raise HTTPException(status_code=403, detail="forbidden")
    email = (x_user_email or "").strip()
    if not email:
        raise HTTPException(status_code=400, detail="missing user email")
    sub = (x_user_sub or "").strip() or None

    client = ch_client()
    wm = client.query(
        "SELECT max(data_through_date) FROM reports.etl_watermark WHERE pipeline = {p:String}",
        parameters={"p": "prosthetics_mart"},
    )
    if not wm.result_rows or wm.result_rows[0][0] is None:
        raise HTTPException(
            status_code=503,
            detail="Витрина ещё не подготовлена (запустите Airflow DAG или дождитесь первой загрузки).",
        )
    data_through = wm.result_rows[0][0]
    key = s3_object_key(email, data_through)

    use_s3 = S3_ENABLED and bool(S3_BUCKET)
    if use_s3 and s3_object_exists(key):
        return JSONResponse(
            {
                "source": "s3",
                "user_sub": sub,
                "user_email": email,
                "data_through_date": str(data_through),
                "cdn_url": cdn_url_for_object_key(key),
                "s3_key": key,
                "rows": None,
                "count": None,
            }
        )

    rows = fetch_mart_rows(client, email, data_through, sub or "")
    body = build_report_payload(
        user_sub=sub,
        user_email=email,
        data_through=data_through,
        rows=rows,
    )
    if use_s3:
        put_report_json(key, body)
        cdn = cdn_url_for_object_key(key)
    else:
        cdn = None

    return JSONResponse(
        {
            "source": "olap",
            "user_sub": sub,
            "user_email": email,
            "data_through_date": str(data_through),
            "cdn_url": cdn,
            "s3_key": key if use_s3 else None,
            "rows": rows,
            "count": len(rows),
        }
    )
