"""Reports API: JWT (Keycloak) + витрина ClickHouse (только строки текущего пользователя по sub)."""

from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx
import jwt
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from jwt import PyJWKClient

KEYCLOAK_INTERNAL = os.environ.get(
    "KEYCLOAK_INTERNAL_URL", "http://keycloak:8080"
).rstrip("/")
KEYCLOAK_REALM = os.environ.get("KEYCLOAK_REALM", "reports-realm")
# Токен с браузера обычно с iss = публичный URL Keycloak (localhost:8090)
ALLOWED_ISSUERS = [
    x.strip()
    for x in os.environ.get(
        "KEYCLOAK_ISSUER",
        "http://localhost:8090/realms/reports-realm,http://keycloak:8080/realms/reports-realm",
    ).split(",")
    if x.strip()
]

CLICKHOUSE_HTTP = os.environ.get(
    "CLICKHOUSE_HTTP_URL", "http://host.docker.internal:8123"
).rstrip("/")
CLICKHOUSE_USER = os.environ.get("CLICKHOUSE_USER", "default")
CLICKHOUSE_PASSWORD = os.environ.get("CLICKHOUSE_PASSWORD", "bionicpro_local")

JWKS_URL = f"{KEYCLOAK_INTERNAL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/certs"
_jwk_client = PyJWKClient(JWKS_URL)

_SUB_SAFE = re.compile(r"^[a-zA-Z0-9._:-]+$")

# Совпадают с keycloak/realm-export.json (prothetic1 / prothetic2) и CRM seed
DEMO_SUB_PROTHETIC1 = "1c8027a3-dc09-420a-a798-4fcea26bb5e3"
DEMO_SUB_PROTHETIC2 = "3d9147b2-ea11-4c9f-b61d-7789aabbcc02"

app = FastAPI(title="BionicPRO Reports API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get(
        "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
    ).split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _decode_bearer(authorization: str | None) -> dict[str, Any]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    token = authorization[7:].strip()
    try:
        key = _jwk_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            key.key,
            algorithms=["RS256"],
            options={
                "verify_aud": False,
                "verify_iss": False,
            },
        )
    except jwt.PyJWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}") from e
    iss = payload.get("iss")
    if iss not in ALLOWED_ISSUERS:
        raise HTTPException(status_code=401, detail="Unexpected token issuer")
    sub = payload.get("sub")
    if not sub or not isinstance(sub, str):
        raise HTTPException(status_code=401, detail="Token has no sub")
    if not _SUB_SAFE.match(sub):
        raise HTTPException(status_code=400, detail="Invalid sub format")
    return payload


def _ch_post_sql(sql: str) -> str:
    """Сырой ответ тела ClickHouse (FORMAT JSON)."""
    auth = (CLICKHOUSE_USER, CLICKHOUSE_PASSWORD)
    with httpx.Client(timeout=60.0) as client:
        r = client.post(
            f"{CLICKHOUSE_HTTP}/",
            auth=auth,
            content=sql.encode("utf-8"),
            headers={"Content-Type": "text/plain; charset=utf-8"},
        )
        if r.status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail=f"ClickHouse error {r.status_code}: {r.text[:500]}",
            )
        return r.text


def _mart_total_rows_ch() -> int:
    raw = _ch_post_sql(
        "SELECT count() AS c FROM bionicpro.mart_user_prosthesis_report FORMAT JSON"
    )
    try:
        rows = json.loads(raw).get("data") or []
        if not rows:
            return 0
        v = rows[0].get("c", 0)
        return int(v)
    except (json.JSONDecodeError, ValueError, TypeError, IndexError):
        return -1


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/reports/mart")
@app.get("/reports")
def reports_mart(authorization: str | None = Header(None)) -> dict[str, Any]:
    """
    Строки витрины bionicpro.mart_user_prosthesis_report только для keycloak_sub = sub из JWT.
    """
    payload = _decode_bearer(authorization)
    sub = payload["sub"]
    sub_lit = sub.replace("\\", "\\\\").replace("'", "\\'")
    sql = (
        "SELECT report_date, keycloak_sub, customer_id, prosthesis_id, serial_number, "
        "model, orders_count, orders_sum, telemetry_events, avg_signal_quality, loaded_at "
        f"FROM bionicpro.mart_user_prosthesis_report WHERE keycloak_sub = '{sub_lit}' "
        "ORDER BY report_date DESC, prosthesis_id "
        "LIMIT 500 FORMAT JSON"
    )
    raw = _ch_post_sql(sql)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(status_code=502, detail="ClickHouse returned non-JSON") from None
    row_count = parsed.get("rows", len(parsed.get("data", [])))
    mart_total = _mart_total_rows_ch()
    return {
        "sub": sub,
        "preferred_username": payload.get("preferred_username"),
        "rows": parsed.get("data", []),
        "row_count": row_count,
        "mart_total_rows": mart_total,
        "demo_keycloak_sub": {
            "prothetic1": DEMO_SUB_PROTHETIC1,
            "prothetic2": DEMO_SUB_PROTHETIC2,
        },
        "sub_matches_demo": {
            "prothetic1": sub == DEMO_SUB_PROTHETIC1,
            "prothetic2": sub == DEMO_SUB_PROTHETIC2,
        },
    }
