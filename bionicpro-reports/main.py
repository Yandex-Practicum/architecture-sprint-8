"""
Сервис отчётов: витрина в ClickHouse (CDC → Kafka → KafkaEngine + MV), чтение по JWT (sub).
Кэш JSON в S3 + ссылка на CDN при промахе.
"""
from __future__ import annotations

import os
from datetime import date, datetime, timezone
from typing import Any

import jwt
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from jwt import PyJWKClient

import ch_reporting
from report_s3 import head_exists, mart_snapshot_id, object_key_for_report, public_url, put_report_json, s3_enabled

app = FastAPI(title="BionicPRO Reports API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ALLOW_ORIGINS", "http://localhost:3000,http://localhost:8181").split(","),
    allow_credentials=True,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)

KEYCLOAK_ISSUER = os.environ.get(
    "KEYCLOAK_ISSUER", "http://localhost:8080/realms/reports-realm"
)
KEYCLOAK_JWKS_URI = os.environ.get(
    "KEYCLOAK_JWKS_URI",
    "http://localhost:8080/realms/reports-realm/protocol/openid-connect/certs",
)

_jwks_client: PyJWKClient | None = None


def jwks() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = PyJWKClient(KEYCLOAK_JWKS_URI, cache_keys=True)
    return _jwks_client


def decode_access_token(token: str) -> dict[str, Any]:
    signing_key = jwks().get_signing_key_from_jwt(token)
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        issuer=KEYCLOAK_ISSUER,
        options={"verify_aud": False},
    )


def current_subject(authorization: str | None = Header(None)) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Требуется Bearer access token")
    token = authorization[7:].strip()
    try:
        payload = decode_access_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Недействительный токен")
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="В токене нет sub")
    return str(sub)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def _build_payload(
    subject: str,
    mart_max_date: date | None,
    mart_last_refresh: datetime | None,
    rows: list[tuple],
) -> dict[str, Any]:
    series = [
        {
            "statDate": r[0].isoformat() if r[0] else None,
            "activeHours": float(r[1]) if r[1] is not None else 0.0,
            "steps": int(r[2]) if r[2] is not None else 0,
            "prosthesisModel": r[3],
            "crmRegion": r[4],
        }
        for r in rows
    ]
    total_hours = sum(p["activeHours"] for p in series)
    total_steps = sum(p["steps"] for p in series)

    stat_dates = [r[0] for r in rows if r[0] is not None]
    user_min = min(stat_dates) if stat_dates else None
    user_max = max(stat_dates) if stat_dates else None

    mart_max_iso = mart_max_date.isoformat() if mart_max_date else None
    if mart_last_refresh is not None:
        mlr = mart_last_refresh
        if mlr.tzinfo is None:
            mlr = mlr.replace(tzinfo=timezone.utc)
        mart_refresh_iso = mlr.astimezone(timezone.utc).isoformat()
    else:
        mart_refresh_iso = None

    if len(series) == 0:
        hint = (
            "В витрине ClickHouse нет строк для вашего пользователя: проверьте данные в CRM OLTP, "
            "репликацию Debezium→Kafka и наполнение витрины. "
            + (
                f"Сейчас в витрине есть дни не позднее {mart_max_iso} (обновление: {mart_refresh_iso}). "
                if mart_max_iso
                else "Витрина пуста — дождитесь загрузки CRM (Airflow) и прохождения CDC. "
            )
        )
    else:
        hint = (
            "Отчёт из витрины ClickHouse (данные приходят из CRM через CDC, без тяжёлых выгрузок в OLTP); "
            f"доступны дни не позднее {mart_max_iso}."
            if mart_max_iso
            else "Отчёт строится по данным витрины."
        )

    return {
        "userSubject": subject,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "hasData": len(series) > 0,
        "olap": {
            "martMaxStatDate": mart_max_iso,
            "martLastRefreshAt": mart_refresh_iso,
            "store": "clickhouse",
        },
        "userSeriesRange": {
            "minStatDate": user_min.isoformat() if user_min else None,
            "maxStatDate": user_max.isoformat() if user_max else None,
        }
        if user_min and user_max
        else None,
        "coverageHint": hint,
        "totals": {
            "activeHours": round(total_hours, 4),
            "steps": total_steps,
        },
        "series": series,
    }


@app.get("/reports")
def get_my_report(subject: str = Depends(current_subject)) -> dict[str, Any]:
    """
    Лёгкий запрос к ClickHouse (снимок витрины), затем S3 HEAD при включённом кэше.
    """
    mart_max_date, mart_last_refresh = ch_reporting.mart_footprint()
    snapshot = mart_snapshot_id(mart_max_date, mart_last_refresh)
    key = object_key_for_report(subject, mart_max_date, mart_last_refresh)

    if s3_enabled() and head_exists(key):
        return {
            "cacheStatus": "hit",
            "reportUrl": public_url(key),
            "martSnapshotId": snapshot,
        }

    rows = ch_reporting.mart_rows_for_subject(subject)
    body = _build_payload(subject, mart_max_date, mart_last_refresh, rows)

    if s3_enabled():
        try:
            put_report_json(key, body)
        except Exception as e:
            raise HTTPException(
                status_code=503,
                detail=f"Не удалось записать отчёт в S3: {e!s}",
            ) from e

    out: dict[str, Any] = dict(body)
    out["cacheStatus"] = "miss" if s3_enabled() else "bypass"
    out["reportUrl"] = public_url(key) if s3_enabled() else None
    out["martSnapshotId"] = snapshot
    return out
