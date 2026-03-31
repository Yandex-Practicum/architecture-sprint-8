"""
Сервис отчётов: чтение витрины OLAP только для пользователя из JWT (sub).
"""
from __future__ import annotations

import os
from datetime import date, datetime, timezone
from typing import Any

import jwt
import psycopg2
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from jwt import PyJWKClient

app = FastAPI(title="BionicPRO Reports API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ALLOW_ORIGINS", "http://localhost:3000,http://localhost:8181").split(","),
    allow_credentials=True,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)

OLAP_DSN = os.environ.get("OLAP_DSN", "postgresql://olap:olap@localhost:5435/olap")
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


def _mart_footprint(cur) -> tuple[date | None, datetime | None]:
    """Границы витрины после последнего прогона ETL (Airflow): только этот период доступен API."""
    cur.execute(
        """
        SELECT MAX(stat_date), MAX(updated_at)
        FROM reporting.mart_user_prosthesis_daily
        """
    )
    row = cur.fetchone()
    if not row:
        return None, None
    return row[0], row[1]


@app.get("/reports")
def get_my_report(subject: str = Depends(current_subject)) -> dict[str, Any]:
    """
    Отчёт только по текущему пользователю (sub из access token).
    Данные читаются из витрины без online-агрегации; за пределами загруженного в OLAP периода строк нет.
    """
    conn = psycopg2.connect(OLAP_DSN)
    try:
        with conn.cursor() as cur:
            mart_max_date, mart_last_refresh = _mart_footprint(cur)
            cur.execute(
                """
                SELECT stat_date, active_hours, steps, prosthesis_model, crm_region
                FROM reporting.mart_user_prosthesis_daily
                WHERE user_subject = %s
                ORDER BY stat_date DESC
                LIMIT 366
                """,
                (subject,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()

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
            "В витрине нет строк для вашего пользователя: либо ETL ещё не подставил ваш sub в источники, "
            "либо за выбранные дни данных не было. "
            + (
                f"В OLAP сейчас загружены дни не позднее {mart_max_iso} (последнее обновление витрины: {mart_refresh_iso}). "
                if mart_max_iso
                else "Витрина пуста — дождитесь успешного прогона DAG. "
            )
            + "Данные за будущие дни появятся только после следующих загрузок Airflow."
        )
    else:
        hint = (
            "Отчёт строится только по данным, уже попавшим в витрину после ETL; "
            f"сейчас в OLAP доступны дни не позднее {mart_max_iso}. "
            "Запросить «свежее», чем обработал DAG, нельзя — таких строк в mart ещё нет."
            if mart_max_iso
            else "Отчёт строится только по данным в витрине."
        )

    return {
        "userSubject": subject,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "hasData": len(series) > 0,
        "olap": {
            "martMaxStatDate": mart_max_iso,
            "martLastRefreshAt": mart_refresh_iso,
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
