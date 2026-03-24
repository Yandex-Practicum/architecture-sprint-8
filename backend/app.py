"""
BionicPRO Reports API — основной бэкенд-сервис.

Объединяет:
  - bionicpro-auth (BFF для аутентификации)
  - /reports endpoint (данные из ClickHouse → S3/CDN)
"""

import json
import os
import time

import httpx
from clickhouse_driver import Client as CHClient
from fastapi import FastAPI, Request, Response, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from auth_service import (
    app as auth_app,
    sessions,
    get_current_session,
    rotate_session,
    _decode_token_payload,
    FRONTEND_URL,
)

app = FastAPI(title="BionicPRO Reports API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/auth", auth_app)

# ---------------------------------------------------------------------------
# ClickHouse connection settings
# ---------------------------------------------------------------------------
CH_HOST = os.getenv("CLICKHOUSE_HOST", "localhost")
CH_PORT = int(os.getenv("CLICKHOUSE_PORT", "9000"))
CH_USER = os.getenv("CLICKHOUSE_USER", "airflow")
CH_PASSWORD = os.getenv("CLICKHOUSE_PASSWORD", "airflow")
CH_DATABASE = os.getenv("CLICKHOUSE_DB", "bionicpro")

# S3 / MinIO settings
S3_ENDPOINT = os.getenv("S3_ENDPOINT", "http://localhost:9002")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY", "minioadmin")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY", "minioadmin")
S3_BUCKET = os.getenv("S3_BUCKET", "reports")
CDN_BASE_URL = os.getenv("CDN_BASE_URL", "http://localhost:8888")

USERNAME_TO_CUSTOMER_ID = {
    "prothetic1": "c1",
    "prothetic2": "c2",
    "prothetic3": "c3",
}


def _get_ch_client() -> CHClient:
    return CHClient(
        host=CH_HOST,
        port=CH_PORT,
        user=CH_USER,
        password=CH_PASSWORD,
        database=CH_DATABASE,
    )


def _get_s3_client():
    import boto3
    return boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=S3_ACCESS_KEY,
        aws_secret_access_key=S3_SECRET_KEY,
    )


def _s3_key(customer_id: str) -> str:
    return f"reports/{customer_id}/latest.json"


# ---------------------------------------------------------------------------
# Reports endpoint
# ---------------------------------------------------------------------------

@app.get("/reports")
async def get_reports(
    request: Request,
    response: Response,
    session: dict = Depends(get_current_session),
):
    new_id = rotate_session(session, response)

    payload = _decode_token_payload(session["access_token"])
    username = payload.get("preferred_username")
    roles = payload.get("realm_access", {}).get("roles", [])

    if "prothetic_user" not in roles:
        raise HTTPException(status_code=403, detail="Role prothetic_user required")

    customer_id = USERNAME_TO_CUSTOMER_ID.get(username)
    if not customer_id:
        raise HTTPException(status_code=403, detail="No customer mapping for user")

    # --- Check S3 cache first ---
    try:
        s3 = _get_s3_client()
        obj = s3.get_object(Bucket=S3_BUCKET, Key=_s3_key(customer_id))
        cdn_url = f"{CDN_BASE_URL}/{S3_BUCKET}/{_s3_key(customer_id)}"
        return {
            "source": "cache",
            "cdn_url": cdn_url,
            "report": json.loads(obj["Body"].read().decode()),
        }
    except Exception:
        pass

    # --- Generate from ClickHouse ---
    REPORT_TABLE = os.getenv("REPORT_TABLE", "user_report_mv")
    try:
        ch = _get_ch_client()
        rows = ch.execute(
            f"""
            SELECT customer_id, full_name, email, report_date,
                   total_events, avg_signal_strength, active_hours,
                   movement_count
            FROM {REPORT_TABLE}
            WHERE customer_id = %(cid)s
            ORDER BY report_date DESC
            """,
            {"cid": customer_id},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ClickHouse error: {e}")

    if not rows:
        raise HTTPException(
            status_code=404,
            detail="No report data available yet. Data may not have been processed by Airflow.",
        )

    days = [
        {
            "customer_id": r[0],
            "full_name": r[1],
            "email": r[2],
            "date": str(r[3]),
            "total_events": r[4],
            "avg_signal_strength": float(r[5]),
            "active_hours": float(r[6]),
            "movement_count": r[7],
        }
        for r in rows
    ]

    report = {"customer_id": customer_id, "username": username, "days": days}

    # --- Store in S3 ---
    try:
        s3 = _get_s3_client()
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=_s3_key(customer_id),
            Body=json.dumps(report).encode(),
            ContentType="application/json",
        )
    except Exception:
        pass

    cdn_url = f"{CDN_BASE_URL}/{S3_BUCKET}/{_s3_key(customer_id)}"

    last_etl_run = None
    try:
        meta = ch.execute(
            "SELECT value FROM etl_metadata FINAL WHERE key = 'last_etl_run' LIMIT 1"
        )
        if meta:
            last_etl_run = meta[0][0]
    except Exception:
        pass

    return {
        "source": "generated",
        "cdn_url": cdn_url,
        "last_etl_run": last_etl_run,
        "report": report,
    }


@app.get("/health")
async def health():
    return {"status": "ok"}
