import os
import logging
from typing import Any

import httpx
import clickhouse_connect
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError

log = logging.getLogger("reports_api")

KEYCLOAK_URL  = os.getenv("KEYCLOAK_URL",   "http://keycloak:8080")
REALM         = os.getenv("KEYCLOAK_REALM", "reports-realm")
CH_HOST       = os.getenv("CLICKHOUSE_HOST", "clickhouse")

app = FastAPI(title="BionicPRO Reports API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

security = HTTPBearer()
_jwks_cache: dict | None = None


async def _get_jwks() -> dict:
    global _jwks_cache
    if _jwks_cache is None:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/certs"
            )
            resp.raise_for_status()
            _jwks_cache = resp.json()
    return _jwks_cache


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict[str, Any]:
    token = credentials.credentials
    try:
        jwks = await _get_jwks()
        payload = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
        )
    return payload


def _ch_client() -> clickhouse_connect.driver.Client:
    return clickhouse_connect.get_client(
        host=CH_HOST, port=8123, username="default", password=""
    )


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/reports")
async def get_report(user: dict = Depends(get_current_user)):
    roles: list[str] = user.get("realm_access", {}).get("roles", [])

    if "prothetic_user" not in roles and "administrator" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: role prothetic_user or administrator required",
        )

    user_id: str = user.get("preferred_username", "")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot determine user identity from token",
        )

    try:
        ch = _ch_client()
        result = ch.query(
            """
            SELECT
                user_id, username, first_name, last_name,
                prosthesis_id, prosthesis_type,
                report_date,
                total_movements,
                avg_signal_strength,
                avg_battery_level,
                avg_response_time_ms,
                most_common_movement
            FROM reports_mart
            WHERE user_id = {uid:String}
            ORDER BY report_date DESC
            LIMIT 30
            """,
            parameters={"uid": user_id},
        )
    except Exception as exc:
        log.exception("ClickHouse unavailable")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Data storage unavailable: {exc}",
        )

    if not result.result_rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No report data available yet. Please wait for the next scheduled ETL run.",
        )

    columns = [
        "user_id", "username", "first_name", "last_name",
        "prosthesis_id", "prosthesis_type", "report_date",
        "total_movements", "avg_signal_strength", "avg_battery_level",
        "avg_response_time_ms", "most_common_movement",
    ]

    rows = [
        {col: (str(val) if not isinstance(val, (int, float, bool)) else val)
         for col, val in zip(columns, row)}
        for row in result.result_rows
    ]

    return {"user_id": user_id, "report": rows}
