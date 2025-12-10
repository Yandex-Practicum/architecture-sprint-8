import json
import os
import logging
import hashlib
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
import clickhouse_connect
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError


CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "localhost")
CLICKHOUSE_PORT = int(os.getenv("CLICKHOUSE_PORT", "8123"))
CLICKHOUSE_DB = os.getenv("CLICKHOUSE_DB", "default")
CLICKHOUSE_USER = os.getenv("CLICKHOUSE_USER", "default")
CLICKHOUSE_PASSWORD = os.getenv("CLICKHOUSE_PASSWORD", "")

S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL", "http://minio:9000")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY", "minioadmin")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY", "minioadmin")
S3_BUCKET = os.getenv("S3_BUCKET", "reports-bucket")
CDN_BASE_URL = os.getenv("CDN_BASE_URL", "http://localhost:8081")

logger = logging.getLogger("reports-api")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Reports API", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_clickhouse_client():
    return clickhouse_connect.get_client(
        host=CLICKHOUSE_HOST,
        port=CLICKHOUSE_PORT,
        username=CLICKHOUSE_USER,
        password=CLICKHOUSE_PASSWORD,
        database=CLICKHOUSE_DB,
    )


def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT_URL,
        aws_access_key_id=S3_ACCESS_KEY,
        aws_secret_access_key=S3_SECRET_KEY,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )


_bucket_ready = False


def ensure_bucket(client):
    global _bucket_ready
    if _bucket_ready:
        return
    try:
        client.head_bucket(Bucket=S3_BUCKET)
    except ClientError:
        client.create_bucket(Bucket=S3_BUCKET)
        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": ["s3:GetObject"],
                    "Resource": [f"arn:aws:s3:::{S3_BUCKET}/*"],
                }
            ],
        }
        client.put_bucket_policy(Bucket=S3_BUCKET, Policy=json.dumps(policy))
    _bucket_ready = True


def get_current_user_id(request: Request):
    """
    Получаем user_id из заголовка X-User-Id (прокинут бэкендом сессий bionicpro-auth).
    Если нет — 401. Если строковый UUID — хешируем в UInt64 так же, как в bionicpro-auth.
    """
    user_id = request.headers.get("X-User-Id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User not authenticated")
    try:
        return int(user_id)
    except ValueError:
        return int.from_bytes(hashlib.sha256(user_id.encode()).digest()[:8], "big")


@app.get("/reports")
def get_report(client=Depends(get_clickhouse_client), user_id: int = Depends(get_current_user_id)):
    s3 = get_s3_client()
    ensure_bucket(s3)
    key = f"{user_id}.json"
    cdn_url = f"{CDN_BASE_URL}/reports/{key}"

    # Если отчёт уже есть в S3 — отдаём ссылку на CDN
    try:
        s3.head_object(Bucket=S3_BUCKET, Key=key)
        return {"cdn_url": cdn_url, "cached": True}
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") not in ("404", "NoSuchKey", "Not Found"):
            raise HTTPException(status_code=500, detail=f"S3 head_object failed: {e}")

    # Читаем CDC-витрину users_mv из ClickHouse по user_id, ограничиваемся последним периодом
    try:
        rows = client.query(
            "SELECT user_id, email, plan, country, period_date, actions_total, errors_total, active_minutes_avg "
            "FROM users_mv WHERE user_id = %(uid)s ORDER BY period_date DESC LIMIT 1",
            parameters={"uid": user_id},
        ).result_rows
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"ClickHouse query failed: {exc}")

    if not rows:
        raise HTTPException(status_code=404, detail="No report for this user")

    row = rows[0]
    report = {
        "user_id": row[0],
        "email": row[1],
        "plan": row[2],
        "country": row[3],
        "period_date": str(row[4]),
        "actions_total": row[5],
        "errors_total": row[6],
        "active_minutes_avg": row[7],
    }

    try:
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=key,
            Body=json.dumps(report).encode(),
            ContentType="application/json",
        )
    except ClientError as e:
        logger.error("Failed to upload report to S3: %s", e)

    return {"report": report, "cdn_url": cdn_url, "cached": False}


@app.get("/health")
def health():
    return {"status": "ok"}

