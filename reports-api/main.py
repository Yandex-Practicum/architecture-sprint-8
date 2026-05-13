"""
BionicPRO Reports API  (v3 — ClickHouse backend)
=================================================
GET /reports  — returns a CDN URL pointing to the user's CSV report.

Flow:
  1. Validate Bearer JWT (Keycloak JWKS).
  2. Extract username from verified claims (access control: own data only).
  3. Query ClickHouse user_report_mart for the latest etl_updated_at date.
  4. Derive S3 key: reports/{username}/{etl_date}/report.csv
  5. If key exists in S3 → return CDN URL (cache HIT — no ClickHouse data read).
  6. Otherwise → query mart, generate CSV, upload to S3, return CDN URL (cache MISS).

ClickHouse mart: bionicpro.user_report_mart (SummingMergeTree)
  Reading uses GROUP BY + sum() to handle pre-merge partial rows correctly.
  avg_battery_level = total_battery_sum / event_count (computed at query time).
"""

import csv
import io
import logging
import os
from datetime import date, datetime
from typing import Annotated

import boto3
import clickhouse_connect
import httpx
from botocore.client import Config
from botocore.exceptions import ClientError
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwk, jwt

log = logging.getLogger("reports_api")
logging.basicConfig(level=logging.INFO)

# ── Config ────────────────────────────────────────────────────────────────────
KEYCLOAK_URL     = os.getenv("KEYCLOAK_URL",        "http://keycloak:8080")
KEYCLOAK_REALM   = os.getenv("KEYCLOAK_REALM",      "reports-realm")

CH_HOST          = os.getenv("CLICKHOUSE_HOST",     "clickhouse")
CH_PORT          = int(os.getenv("CLICKHOUSE_PORT", "8123"))
CH_DATABASE      = os.getenv("CLICKHOUSE_DB",       "bionicpro")
CH_USER          = os.getenv("CLICKHOUSE_USER",     "default")
CH_PASSWORD      = os.getenv("CLICKHOUSE_PASSWORD", "")

S3_ENDPOINT      = os.getenv("S3_ENDPOINT",         "http://minio:9000")
S3_ACCESS_KEY    = os.getenv("S3_ACCESS_KEY",        "minioadmin")
S3_SECRET_KEY    = os.getenv("S3_SECRET_KEY",        "minioadmin")
S3_BUCKET        = os.getenv("S3_BUCKET",            "bionicpro-reports")
CDN_BASE_URL     = os.getenv("CDN_BASE_URL",         "http://localhost:8100")

JWKS_URL = f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/certs"
ISSUER   = f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}"

app = FastAPI(title="BionicPRO Reports API", version="3.0.0")
security = HTTPBearer()

# ── JWKS cache ────────────────────────────────────────────────────────────────
_jwks_cache: dict | None = None


def get_jwks() -> dict:
    global _jwks_cache
    if _jwks_cache is None:
        try:
            resp = httpx.get(JWKS_URL, timeout=5)
            resp.raise_for_status()
            _jwks_cache = resp.json()
            log.info("JWKS loaded from %s", JWKS_URL)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Cannot reach Keycloak JWKS endpoint: {e}",
            )
    return _jwks_cache


def verify_token(token: str) -> dict:
    try:
        unverified_header = jwt.get_unverified_header(token)
    except JWTError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token header: {e}")

    kid = unverified_header.get("kid")
    jwks = get_jwks()
    matching_key = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)

    if matching_key is None:
        global _jwks_cache
        _jwks_cache = None
        matching_key = next((k for k in get_jwks().get("keys", []) if k.get("kid") == kid), None)
    if matching_key is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown token signing key")

    try:
        public_key = jwk.construct(matching_key)
        return jwt.decode(token, public_key, algorithms=["RS256"], issuer=ISSUER, options={"verify_aud": False})
    except JWTError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Token validation failed: {e}")


def get_current_username(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> str:
    claims = verify_token(credentials.credentials)
    username = claims.get("preferred_username") or claims.get("sub")
    if not username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No username in token")
    return username


# ── ClickHouse helpers ────────────────────────────────────────────────────────

def _ch():
    return clickhouse_connect.get_client(
        host=CH_HOST, port=CH_PORT,
        database=CH_DATABASE, username=CH_USER, password=CH_PASSWORD,
        connect_timeout=5,
    )


def get_latest_etl_date(username: str) -> date | None:
    """Return DATE of most recent mart row for this user, or None."""
    result = _ch().query(
        "SELECT max(etl_updated_at) FROM user_report_mart WHERE username = {u:String}",
        parameters={"u": username},
    )
    val = result.first_row[0] if result.first_row else None
    return val.date() if val else None


def get_report_rows(username: str) -> list[dict]:
    """
    Query the mart with GROUP BY + sum() to handle pre-merge SummingMergeTree state.
    avg_battery_level = total_battery_sum / event_count.
    """
    result = _ch().query(
        """
        SELECT
            username,
            report_date,
            any(full_name)                       AS full_name,
            any(device_serial)                   AS device_serial,
            any(device_model)                    AS device_model,
            round(sum(total_active_hours), 2)    AS total_active_hours,
            round(
              if(sum(event_count) > 0,
                 sum(total_battery_sum) / sum(event_count),
                 0), 2)                          AS avg_battery_level,
            sum(total_steps)                     AS total_steps,
            sum(event_count)                     AS event_count,
            max(etl_updated_at)                  AS etl_updated_at
        FROM user_report_mart
        WHERE username = {u:String}
        GROUP BY username, report_date
        ORDER BY report_date DESC
        """,
        parameters={"u": username},
    )
    cols = result.column_names
    return [dict(zip(cols, row)) for row in result.result_rows]


def build_csv(rows: list[dict]) -> bytes:
    buf = io.StringIO()
    fieldnames = [
        "report_date", "full_name", "device_serial", "device_model",
        "total_active_hours", "avg_battery_level", "total_steps",
        "event_count", "etl_updated_at",
    ]
    writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8")


# ── S3 helpers ────────────────────────────────────────────────────────────────

def _s3():
    return boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=S3_ACCESS_KEY,
        aws_secret_access_key=S3_SECRET_KEY,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )


def s3_key(username: str, etl_date: date) -> str:
    return f"reports/{username}/{etl_date}/report.csv"


def s3_exists(key: str) -> bool:
    try:
        _s3().head_object(Bucket=S3_BUCKET, Key=key)
        return True
    except ClientError:
        return False


def s3_upload(key: str, csv_bytes: bytes) -> None:
    _s3().put_object(
        Bucket=S3_BUCKET, Key=key, Body=csv_bytes,
        ContentType="text/csv",
        CacheControl="public, max-age=3600",
    )
    log.info("Uploaded %s (%d bytes)", key, len(csv_bytes))


def cdn_url(key: str) -> str:
    return f"{CDN_BASE_URL}/{S3_BUCKET}/{key}"


# ── Endpoint ──────────────────────────────────────────────────────────────────

@app.get("/reports")
def get_report(username: Annotated[str, Depends(get_current_username)]) -> JSONResponse:
    """
    Returns JSON with CDN URL to the user's CSV report.

    Response (data available):
      {"report_url": "http://cdn/...", "etl_date": "2024-01-15", "cached": true}

    Response (no data yet):
      {"report_url": null, "message": "No data yet — CDC pipeline may still be processing."}
    """
    # 1. Check if there is any mart data for this user
    try:
        etl_date = get_latest_etl_date(username)
    except Exception as e:
        log.error("ClickHouse error for user %s: %s", username, e)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Report database unavailable")

    if etl_date is None:
        return JSONResponse({
            "report_url": None,
            "message": "No data yet — CDC pipeline may still be processing the initial snapshot.",
        })

    key = s3_key(username, etl_date)

    # 2. S3 cache check
    try:
        if s3_exists(key):
            log.info("S3 HIT for %s (key=%s)", username, key)
            return JSONResponse({"report_url": cdn_url(key), "etl_date": str(etl_date), "cached": True})
    except Exception as e:
        log.warning("S3 check failed, falling back to generation: %s", e)

    # 3. Cache MISS — generate from ClickHouse, upload to S3
    log.info("S3 MISS for %s — generating from ClickHouse", username)
    try:
        rows = get_report_rows(username)
    except Exception as e:
        log.error("ClickHouse query failed for %s: %s", username, e)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Report database unavailable")

    csv_bytes = build_csv(rows)

    try:
        s3_upload(key, csv_bytes)
    except Exception as e:
        log.error("S3 upload failed for %s: %s", username, e)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Report storage unavailable")

    return JSONResponse({"report_url": cdn_url(key), "etl_date": str(etl_date), "cached": False})


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
