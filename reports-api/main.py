"""
Reports API Service для BionicPRO
Предоставляет эндпоинт для получения отчетов о работе протезов
с авторизацией через Keycloak и кешированием в S3 + раздачей через CDN (Nginx)
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import os
import logging
import json

from clickhouse_driver import Client as ClickHouseClient
from jose import jwt, JWTError
import requests
import boto3
from botocore.exceptions import ClientError
from botocore.config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

S3_ENDPOINT = os.getenv("S3_ENDPOINT", "http://minio:9000")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY", "minio")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY", "minio123")
S3_BUCKET = os.getenv("S3_BUCKET", "bionicpro-reports")
S3_REGION = os.getenv("S3_REGION", "us-east-1")
CDN_BASE_URL = os.getenv("CDN_BASE_URL", "http://127.0.0.1:8090").rstrip("/")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "bionicpro-webhook-secret-2024")

CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "clickhouse")
CLICKHOUSE_PORT = int(os.getenv("CLICKHOUSE_PORT", 9000))
CLICKHOUSE_USER = os.getenv("CLICKHOUSE_USER", "analytics_user")
CLICKHOUSE_PASSWORD = os.getenv("CLICKHOUSE_PASSWORD", "analytics_password")
CLICKHOUSE_DB = os.getenv("CLICKHOUSE_DB", "analytics_db")

KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://keycloak:8080")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "reports-realm")

_s3_client = None


def get_s3_client():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client(
            "s3",
            endpoint_url=S3_ENDPOINT,
            aws_access_key_id=S3_ACCESS_KEY,
            aws_secret_access_key=S3_SECRET_KEY,
            region_name=S3_REGION,
            config=Config(
                s3={"addressing_style": "path"},
                signature_version="s3v4",
            ),
        )
    return _s3_client


def report_object_key(buyer_id: int, period_days: int) -> str:
    return f"reports/{buyer_id}/{period_days}days/report.json"


def cdn_url_for_report(buyer_id: int, period_days: int) -> str:
    return f"{CDN_BASE_URL}/reports/{buyer_id}/{period_days}days/report.json"


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        get_s3_client().head_bucket(Bucket=S3_BUCKET)
        logger.info("S3 bucket %s доступен", S3_BUCKET)
    except ClientError as e:
        logger.warning("Бакет S3 при старте недоступен (нужен minio-init): %s", e)
    yield


app = FastAPI(
    title="BionicPRO Reports API",
    description="API для получения отчетов о работе протезов (S3 + CDN)",
    version="1.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:3000", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()


class ProstheticReport(BaseModel):
    buyer_id: int
    full_name: str
    email: str
    prosthetic_type: str
    serial_number: str
    total_usage_hours: float
    total_movements: int
    total_errors: int
    avg_battery_level: float
    last_telemetry_date: datetime
    report_period_start: datetime
    report_period_end: datetime


class ReportResponse(BaseModel):
    reports: List[ProstheticReport]
    cdn_url: str
    generated_at: datetime
    cached: bool
    cache_key: str


class UserInfo(BaseModel):
    sub: str
    email: Optional[str] = None
    preferred_username: Optional[str] = None
    buyer_id: Optional[int] = None


def get_clickhouse_client() -> ClickHouseClient:
    try:
        return ClickHouseClient(
            host=CLICKHOUSE_HOST,
            port=CLICKHOUSE_PORT,
            user=CLICKHOUSE_USER,
            password=CLICKHOUSE_PASSWORD,
            database=CLICKHOUSE_DB,
        )
    except Exception as e:
        logger.error("Ошибка подключения к ClickHouse: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Сервис аналитики временно недоступен",
        )


def get_keycloak_public_key() -> str:
    try:
        url = f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        realm_info = response.json()
        public_key = realm_info.get("public_key")
        if not public_key:
            raise ValueError("Public key not found in realm info")
        return f"-----BEGIN PUBLIC KEY-----\n{public_key}\n-----END PUBLIC KEY-----"
    except Exception as e:
        logger.error("Ошибка получения публичного ключа Keycloak: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Сервис аутентификации недоступен",
        )


def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> UserInfo:
    token = credentials.credentials
    try:
        public_key = get_keycloak_public_key()
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience="account",
            options={"verify_aud": False},
        )
        buyer_id = payload.get("buyer_id")
        if not buyer_id:
            preferred_username = payload.get("preferred_username", "")
            user_buyer_mapping = {
                "prothetic1": 648821,
                "prothetic2": 6488214,
                "admin1": 648801,
            }
            buyer_id = user_buyer_mapping.get(preferred_username)
        return UserInfo(
            sub=payload.get("sub"),
            email=payload.get("email"),
            preferred_username=payload.get("preferred_username"),
            buyer_id=buyer_id,
        )
    except JWTError as e:
        logger.error("Ошибка проверки токена: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Невалидный токен аутентификации",
            headers={"WWW-Authenticate": "Bearer"},
        )


def fetch_reports_from_clickhouse(buyer_id: int, period_days: int) -> List[ProstheticReport]:
    client = get_clickhouse_client()
    query = """
        SELECT
            buyer_id,
            full_name,
            email,
            prosthetic_type,
            serial_number,
            total_usage_hours,
            total_movements,
            total_errors,
            avg_battery_level,
            last_telemetry_date,
            report_period_start,
            report_period_end
        FROM user_reports_mart
        WHERE buyer_id = %(buyer_id)s
          AND report_period_end >= today() - INTERVAL %(period_days)s DAY
        ORDER BY report_period_end DESC
        """
    result = client.execute(query, {"buyer_id": buyer_id, "period_days": period_days})
    return [
        ProstheticReport(
            buyer_id=row[0],
            full_name=row[1],
            email=row[2],
            prosthetic_type=row[3],
            serial_number=row[4],
            total_usage_hours=row[5],
            total_movements=row[6],
            total_errors=row[7],
            avg_battery_level=row[8],
            last_telemetry_date=row[9],
            report_period_start=row[10],
            report_period_end=row[11],
        )
        for row in result
    ]


def load_reports_from_s3(key: str) -> Optional[tuple[List[ProstheticReport], datetime]]:
    s3 = get_s3_client()
    try:
        obj = s3.get_object(Bucket=S3_BUCKET, Key=key)
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") in ("404", "NoSuchKey"):
            return None
        raise
    body = json.loads(obj["Body"].read().decode("utf-8"))
    gen_raw = body.get("generated_at")
    generated_at = (
        datetime.fromisoformat(gen_raw.replace("Z", "+00:00"))
        if gen_raw
        else obj["LastModified"].replace(tzinfo=None)
    )
    reports = [ProstheticReport.model_validate(r) for r in body.get("reports", [])]
    return reports, generated_at


def save_reports_to_s3(
    key: str, reports: List[ProstheticReport], generated_at: datetime, period_days: int
) -> None:
    payload = {
        "reports": [r.model_dump(mode="json") for r in reports],
        "generated_at": generated_at.isoformat(),
        "period_days": period_days,
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    get_s3_client().put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=body,
        ContentType="application/json",
    )


def delete_all_cached_reports() -> int:
    s3 = get_s3_client()
    paginator = s3.get_paginator("list_objects_v2")
    deleted = 0
    for page in paginator.paginate(Bucket=S3_BUCKET, Prefix="reports/"):
        contents = page.get("Contents") or []
        if not contents:
            continue
        keys = [{"Key": o["Key"]} for o in contents]
        s3.delete_objects(Bucket=S3_BUCKET, Delete={"Objects": keys})
        deleted += len(keys)
    meta = json.dumps({"invalidated_at": datetime.utcnow().isoformat() + "Z"}).encode("utf-8")
    s3.put_object(
        Bucket=S3_BUCKET,
        Key="metadata/last_invalidation.json",
        Body=meta,
        ContentType="application/json",
    )
    return deleted


@app.get("/")
async def root():
    return {
        "service": "BionicPRO Reports API",
        "version": "1.1.0",
        "status": "running",
        "s3_cache": True,
    }


@app.get("/health")
async def health_check():
    try:
        client = get_clickhouse_client()
        client.execute("SELECT 1")
        ch_ok = True
    except Exception as e:
        logger.warning("Health: ClickHouse: %s", e)
        ch_ok = False
    try:
        get_s3_client().head_bucket(Bucket=S3_BUCKET)
        s3_ok = True
    except Exception as e:
        logger.warning("Health: S3: %s", e)
        s3_ok = False
    return {
        "status": "healthy" if ch_ok and s3_ok else "degraded",
        "clickhouse": "connected" if ch_ok else "error",
        "s3": "ok" if s3_ok else "error",
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/reports", response_model=ReportResponse)
async def get_user_reports(
    user: UserInfo = Depends(verify_token),
    period_days: int = 30,
) -> ReportResponse:
    if not user.buyer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Пользователь не связан с профилем покупателя",
        )
    if period_days < 1 or period_days > 365:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="period_days должен быть от 1 до 365",
        )

    key = report_object_key(user.buyer_id, period_days)
    cdn = cdn_url_for_report(user.buyer_id, period_days)
    logger.info(
        "Запрос отчётов %s buyer_id=%s period=%s",
        user.preferred_username,
        user.buyer_id,
        period_days,
    )

    cached = load_reports_from_s3(key)
    if cached is not None:
        reports, generated_at = cached
        logger.info("Отчёт из S3 (без ClickHouse): %s", key)
        return ReportResponse(
            reports=reports,
            cdn_url=cdn,
            generated_at=generated_at,
            cached=True,
            cache_key=key,
        )

    reports = fetch_reports_from_clickhouse(user.buyer_id, period_days)
    generated_at = datetime.utcnow()
    save_reports_to_s3(key, reports, generated_at, period_days)
    logger.info("Отчёт сгенерирован из ClickHouse и сохранён в S3: %s", key)
    return ReportResponse(
        reports=reports,
        cdn_url=cdn,
        generated_at=generated_at,
        cached=False,
        cache_key=key,
    )


@app.get("/reports/summary")
async def get_reports_summary(user: UserInfo = Depends(verify_token)):
    if not user.buyer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Пользователь не связан с профилем покупателя",
        )
    try:
        client = get_clickhouse_client()
        query = """
            SELECT
                count() as total_reports,
                sum(total_usage_hours) as total_hours,
                sum(total_movements) as total_movements,
                sum(total_errors) as total_errors
            FROM user_reports_mart
            WHERE buyer_id = %(buyer_id)s
            """
        result = client.execute(query, {"buyer_id": user.buyer_id})
        if not result:
            return {
                "buyer_id": user.buyer_id,
                "total_reports": 0,
                "total_usage_hours": 0,
                "total_movements": 0,
                "total_errors": 0,
            }
        row = result[0]
        return {
            "buyer_id": user.buyer_id,
            "total_reports": row[0],
            "total_usage_hours": row[1],
            "total_movements": row[2],
            "total_errors": row[3],
        }
    except Exception as e:
        logger.error("Ошибка при получении сводки отчетов: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при получении сводки отчетов",
        )


@app.post("/internal/invalidate-reports-cache")
async def invalidate_reports_cache(
    x_webhook_secret: Optional[str] = Header(None, alias="X-Webhook-Secret"),
):
    if not x_webhook_secret or x_webhook_secret != WEBHOOK_SECRET:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Неверный секрет")
    n = delete_all_cached_reports()
    logger.info("Инвалидация кеша отчётов в S3, удалено объектов: %s", n)
    return {"status": "ok", "deleted_objects": n}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
