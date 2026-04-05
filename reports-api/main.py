import json
import logging
import urllib.parse
from contextlib import asynccontextmanager
from datetime import date
from typing import Annotated

import boto3
import clickhouse_connect
from botocore.exceptions import ClientError
from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    clickhouse_host: str = "clickhouse"
    clickhouse_port: int = 8123
    clickhouse_user: str = "clickhouse_user"
    clickhouse_password: str = "clickhouse_password"
    clickhouse_database: str = "bionicpro"

    s3_endpoint_url: str = "http://minio:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin123"
    s3_bucket: str = "bionicpro-reports"
    s3_region: str = "us-east-1"
    cdn_public_base_url: str = "http://localhost:8090"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()

SQL_REPORTS = """
SELECT
    period_date,
    avg_temperature,
    avg_pulse,
    plan_code,
    data_watermark_date
FROM bionicpro.reports_mart
WHERE user_id = {uid:String}
ORDER BY period_date, mart_loaded_at
"""


class PeriodRow(BaseModel):
    period_date: date
    avg_temperature: float | None
    avg_pulse: float | None
    plan_code: str
    data_watermark_date: date


class ReportPayload(BaseModel):
    """Body stored in S3 and returned to clients."""

    user_id: str
    periods: list[PeriodRow]


class ReportLinkResponse(BaseModel):
    download_url: str


class ClickHouseUnavailableError(Exception):
    """Raised when the reports query against ClickHouse fails."""


def _object_key(user_id: str) -> str:
    safe = urllib.parse.quote(user_id.strip(), safe="")
    return f"reports/{safe}.json"


def _download_url(user_id: str) -> str:
    base = settings.cdn_public_base_url.rstrip("/")
    key = _object_key(user_id)
    return f"{base}/{settings.s3_bucket}/{key}"


def _s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
    )


def _fetch_periods(client, user_id: str) -> list[PeriodRow]:
    try:
        result = client.query(SQL_REPORTS, parameters={"uid": user_id})
    except Exception as e:
        logger.exception("ClickHouse query failed for user_id=%s", user_id)
        raise ClickHouseUnavailableError from e
    rows: list[PeriodRow] = []
    for tup in result.result_rows:
        rows.append(
            PeriodRow(
                period_date=tup[0],
                avg_temperature=tup[1],
                avg_pulse=tup[2],
                plan_code=tup[3],
                data_watermark_date=tup[4],
            )
        )
    return rows


def _report_exists_in_s3(s3, user_id: str) -> bool:
    key = _object_key(user_id)
    try:
        s3.head_object(Bucket=settings.s3_bucket, Key=key)
        return True
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if code in ("404", "NoSuchKey", "NotFound"):
            return False
        logger.warning("S3 head_object failed for key=%s: %s", key, e)
        return False
    except Exception as e:
        logger.warning("S3 head_object unexpected error for key=%s: %s", key, e)
        return False


def _try_put_report(s3, payload: ReportPayload) -> bool:
    key = _object_key(payload.user_id)
    body = json.dumps(
        payload.model_dump(mode="json"),
        ensure_ascii=False,
    ).encode("utf-8")
    try:
        s3.put_object(
            Bucket=settings.s3_bucket,
            Key=key,
            Body=body,
            ContentType="application/json",
            CacheControl="public, max-age=86400",
        )
        return True
    except Exception as e:
        logger.warning("S3 put_object failed for key=%s: %s", key, e)
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.clickhouse = clickhouse_connect.get_client(
        host=settings.clickhouse_host,
        port=settings.clickhouse_port,
        username=settings.clickhouse_user,
        password=settings.clickhouse_password,
        database=settings.clickhouse_database,
    )
    app.state.s3 = _s3_client()
    try:
        yield
    finally:
        app.state.clickhouse.close()


app = FastAPI(title="bionicpro-reports-api", lifespan=lifespan)


@app.get("/reports", response_model=ReportLinkResponse)
def reports(
    request: Request,
    x_user_id: Annotated[str, Header(alias="X-User-Id")],
):
    if not x_user_id.strip():
        raise HTTPException(status_code=422, detail="X-User-Id must not be empty")

    s3 = request.app.state.s3
    url = _download_url(x_user_id)
    if _report_exists_in_s3(s3, x_user_id):
        return ReportLinkResponse(download_url=url)

    client = request.app.state.clickhouse
    try:
        periods = _fetch_periods(client, x_user_id)
    except ClickHouseUnavailableError as e:
        raise HTTPException(
            status_code=503, detail="reports data source unavailable"
        ) from e.__cause__

    payload = ReportPayload(user_id=x_user_id, periods=periods)
    _try_put_report(s3, payload)
    return ReportLinkResponse(download_url=url)
