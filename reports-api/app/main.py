from __future__ import annotations

import csv
import io
import json
import logging
import re
from contextlib import asynccontextmanager
from datetime import date
from typing import Any

import clickhouse_connect
import httpx
from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import Settings
from .storage import ReportObjectStore


settings = Settings()
logger = logging.getLogger(__name__)
auth_client = httpx.AsyncClient(timeout=15.0)
clickhouse_client = None
object_store = ReportObjectStore(settings)
TABLE_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _get_clickhouse_client():
    global clickhouse_client
    if clickhouse_client is None:
        clickhouse_client = clickhouse_connect.get_client(
            host=settings.clickhouse_host,
            port=settings.clickhouse_port,
            database=settings.clickhouse_database,
            username=settings.clickhouse_username,
            password=settings.clickhouse_password,
        )
    return clickhouse_client


def _append_auth_headers(response: Response, auth_response: httpx.Response, request: Request | None = None) -> None:
    cookies = auth_response.headers.get_list("set-cookie")
    if request is not None:
        request.state.auth_set_cookies = cookies

    for value in cookies:
        response.headers.append("set-cookie", value)
    cache_control = auth_response.headers.get("cache-control")
    if cache_control:
        if request is not None:
            request.state.auth_cache_control = cache_control
        response.headers["Cache-Control"] = cache_control


def _append_stored_auth_headers(response: Response, request: Request) -> None:
    for value in getattr(request.state, "auth_set_cookies", []):
        response.headers.append("set-cookie", value)

    cache_control = getattr(request.state, "auth_cache_control", None)
    if cache_control:
        response.headers["Cache-Control"] = cache_control


def _report_table_name() -> str:
    table_name = settings.report_dataset_name
    if not TABLE_NAME_PATTERN.match(table_name):
        raise RuntimeError(f"Unsafe report dataset name configured: {table_name}")
    return table_name


async def _authenticate(request: Request, response: Response) -> dict[str, Any]:
    headers = {}
    cookie = request.headers.get("cookie")
    if cookie:
        headers["cookie"] = cookie

    auth_response = await auth_client.get(f"{settings.auth_service_base_url}/internal/session", headers=headers)
    _append_auth_headers(response, auth_response, request=request)

    if auth_response.status_code == 401:
        raise HTTPException(status_code=401, detail="Authentication is required.")
    auth_response.raise_for_status()
    return auth_response.json()["user"]


def _load_availability() -> dict[str, str]:
    result = _get_clickhouse_client().query(
        """
        SELECT
            dataset,
            available_from,
            available_to,
            loaded_at
        FROM reporting_load_windows
        WHERE dataset = {dataset:String}
        ORDER BY loaded_at DESC
        LIMIT 1
        """,
        parameters={"dataset": settings.report_dataset_name},
    )
    if not result.result_rows:
        raise HTTPException(status_code=503, detail="Report mart is not ready yet.")

    dataset, available_from, available_to, loaded_at = result.result_rows[0]
    return {
        "dataset": str(dataset),
        "availableFrom": available_from.isoformat(),
        "availableTo": available_to.isoformat(),
        "loadedAt": loaded_at.isoformat(),
    }


def _parse_period(
    availability: dict[str, str],
    date_from: str | None,
    date_to: str | None,
) -> tuple[date, date]:
    available_from = date.fromisoformat(availability["availableFrom"])
    available_to = date.fromisoformat(availability["availableTo"])
    requested_from = date.fromisoformat(date_from) if date_from else available_from
    requested_to = date.fromisoformat(date_to) if date_to else available_to

    if requested_from > requested_to:
        raise HTTPException(status_code=400, detail="date_from must be less than or equal to date_to.")

    if requested_from < available_from or requested_to > available_to:
        raise HTTPException(
            status_code=409,
            detail=(
                "Requested period is not available in OLAP yet. "
                f"Processed range: {availability['availableFrom']}..{availability['availableTo']}."
            ),
        )

    return requested_from, requested_to


def _load_report_rows(username: str, period_from: date, period_to: date) -> tuple[list[str], list[tuple[Any, ...]]]:
    table_name = _report_table_name()
    result = _get_clickhouse_client().query(
        f"""
        SELECT
            report_date,
            prosthesis_id,
            prosthesis_model,
            support_tier,
            country,
            usage_minutes,
            motion_events,
            average_battery_pct,
            average_signal_quality,
            calibration_sessions,
            alerts_count,
            last_service_date
        FROM {table_name}
        -- Keep ClickHouse placeholders escaped; only the table name is interpolated by Python.
        WHERE username = {{username:String}}
          AND report_date BETWEEN {{date_from:Date}} AND {{date_to:Date}}
        ORDER BY report_date, prosthesis_id
        """,
        parameters={
            "username": username,
            "date_from": period_from,
            "date_to": period_to,
        },
    )
    return result.column_names, result.result_rows


def _rows_to_json(columns: list[str], rows: list[tuple[Any, ...]]) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for row in rows:
        item: dict[str, Any] = {}
        for column, value in zip(columns, row):
            if isinstance(value, date):
                item[column] = value.isoformat()
            else:
                item[column] = value
        payload.append(item)
    return payload


def _rows_to_csv(columns: list[str], rows: list[tuple[Any, ...]]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(columns)
    for row in rows:
        writer.writerow(
            [value.isoformat() if isinstance(value, date) else value for value in row]
        )
    return buffer.getvalue()


def _render_report_document(
    user: dict[str, Any],
    availability: dict[str, str],
    period_from: date,
    period_to: date,
    report_format: str,
) -> tuple[bytes, str]:
    columns, rows = _load_report_rows(user["username"], period_from, period_to)
    if not rows:
        raise HTTPException(status_code=404, detail="No report data is available for the selected period.")

    if report_format == "json":
        payload = {
            "user": {
                "username": user["username"],
                "email": user.get("email"),
                "fullName": user.get("fullName"),
            },
            "availability": availability,
            "period": {
                "dateFrom": period_from.isoformat(),
                "dateTo": period_to.isoformat(),
            },
            "rows": _rows_to_json(columns, rows),
        }
        return json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8"

    content = _rows_to_csv(columns, rows)
    return content.encode("utf-8"), "text/csv; charset=utf-8"


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await auth_client.aclose()
    if clickhouse_client is not None:
        clickhouse_client.close()


app = FastAPI(title="reports-api", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_base_url],
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    response = JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
    if exc.headers:
        for name, value in exc.headers.items():
            response.headers[name] = value
    _append_stored_auth_headers(response, request)
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "Unhandled exception while processing reports-api request",
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    response = JSONResponse({"detail": "Internal Server Error"}, status_code=500)
    _append_stored_auth_headers(response, request)
    return response


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/reports/availability")
async def report_availability(request: Request, response: Response) -> JSONResponse:
    user = await _authenticate(request, response)
    availability = _load_availability()
    payload = {
        "user": {
            "username": user["username"],
            "email": user.get("email"),
            "fullName": user.get("fullName"),
        },
        "availability": availability,
    }
    return JSONResponse(payload, headers=dict(response.headers))


@app.get("/reports")
async def reports(
    request: Request,
    response: Response,
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    report_format: str = Query(default="csv", alias="format", pattern="^(csv|json)$"),
) -> JSONResponse:
    user = await _authenticate(request, response)
    availability = _load_availability()
    period_from, period_to = _parse_period(availability, date_from, date_to)
    object_key = object_store.build_object_key(
        username=user["username"],
        availability=availability,
        date_from=period_from.isoformat(),
        date_to=period_to.isoformat(),
        report_format=report_format,
    )

    try:
        cache_hit = object_store.object_exists(object_key)
        if not cache_hit:
            content, content_type = _render_report_document(
                user=user,
                availability=availability,
                period_from=period_from,
                period_to=period_to,
                report_format=report_format,
            )
            object_store.put_report(
                object_key=object_key,
                content=content,
                content_type=content_type,
                metadata={
                    "dataset": availability["dataset"],
                    "loaded-at": availability["loadedAt"],
                    "date-from": period_from.isoformat(),
                    "date-to": period_to.isoformat(),
                    "report-format": report_format,
                },
            )
    except RuntimeError as error:
        logger.error("S3/CDN report delivery failed: %s", error)
        raise HTTPException(status_code=503, detail=str(error)) from error

    payload = {
        "user": {
            "username": user["username"],
            "email": user.get("email"),
            "fullName": user.get("fullName"),
        },
        "availability": availability,
        "period": {
            "dateFrom": period_from.isoformat(),
            "dateTo": period_to.isoformat(),
        },
        "delivery": {
            "provider": "cdn",
            "bucket": settings.s3_bucket,
            "objectKey": object_key,
            "format": report_format,
            "fileName": (
                f"report-{user['username']}-"
                f"{period_from.isoformat()}_{period_to.isoformat()}.{report_format}"
            ),
            "cacheHit": cache_hit,
            "cacheVersion": availability["loadedAt"],
            "downloadUrl": object_store.build_cdn_url(object_key),
        },
    }
    return JSONResponse(payload, headers=dict(response.headers))
