"""
BionicPRO Reports API

Бэкенд-сервис для получения отчётов о работе протезов.
Данные читаются из витрины report_user_prosthesis в ClickHouse (OLAP).
Аутентификация через JWT-токен Keycloak.
"""

import os
from datetime import date
from typing import Optional

import jwt
import requests
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from clickhouse_driver import Client as CHClient

# =============================================
# Конфигурация
# =============================================

KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://keycloak:8080")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "reports-realm")
CH_HOST = os.getenv("CLICKHOUSE_HOST", "clickhouse")
CH_PORT = int(os.getenv("CLICKHOUSE_PORT", "9000"))

# Маппинг пользователей Keycloak → client_id в CRM
# В продакшене это было бы в БД
USER_CLIENT_MAP = {
    "prothetic1": "CLT-001",
    "prothetic2": "CLT-002",
    "prothetic3": "CLT-003",
}

# =============================================
# App
# =============================================

app = FastAPI(title="BionicPRO Reports API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["GET"],
    allow_headers=["Authorization"],
)

security = HTTPBearer()

# Кеш для публичного ключа Keycloak
_keycloak_public_key: Optional[str] = None


def get_keycloak_public_key() -> str:
    """Получить RSA public key из Keycloak realm для валидации JWT."""
    global _keycloak_public_key
    if _keycloak_public_key:
        return _keycloak_public_key

    url = f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    raw_key = resp.json()["public_key"]

    _keycloak_public_key = (
        f"-----BEGIN PUBLIC KEY-----\n{raw_key}\n-----END PUBLIC KEY-----"
    )
    return _keycloak_public_key


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """Валидация JWT-токена и извлечение информации о пользователе."""
    token = credentials.credentials
    try:
        public_key = get_keycloak_public_key()
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")

    # 1. Проверка роли: только prothetic_user имеет доступ к отчётам
    realm_roles = payload.get("realm_access", {}).get("roles", [])
    if "prothetic_user" not in realm_roles:
        raise HTTPException(
            status_code=403,
            detail="Access denied: role 'prothetic_user' is required",
        )

    # 2. Определение client_id: пользователь видит только свои отчёты
    username = payload.get("preferred_username", "")
    client_id = USER_CLIENT_MAP.get(username)

    if not client_id:
        raise HTTPException(
            status_code=403,
            detail="No prosthesis data linked to this account",
        )

    return {"username": username, "client_id": client_id, "roles": realm_roles}


def get_clickhouse() -> CHClient:
    """Создать подключение к ClickHouse."""
    return CHClient(host=CH_HOST, port=CH_PORT)


# =============================================
# Endpoints
# =============================================


@app.get("/reports")
def get_reports(
    user: dict = Depends(get_current_user),
    date_from: Optional[date] = Query(None, description="Начало периода"),
    date_to: Optional[date] = Query(None, description="Конец периода"),
):
    """
    Получить отчёт о работе протезов текущего пользователя.

    Данные читаются из витрины report_user_prosthesis в ClickHouse.
    Пользователь видит только свои данные (фильтрация по client_id из токена).
    Отчёт доступен только за период, обработанный Airflow ETL.
    """
    ch = get_clickhouse()
    client_id = user["client_id"]

    # Определяем период, обработанный Airflow (min/max даты в витрине)
    period_rows = ch.execute(
        """
        SELECT min(report_date), max(report_date)
        FROM report_user_prosthesis
        WHERE client_id = %(client_id)s
        """,
        {"client_id": client_id},
    )
    available_from = period_rows[0][0] if period_rows[0][0] else None
    available_to = period_rows[0][1] if period_rows[0][1] else None

    # Если в витрине нет данных для этого пользователя
    if not available_from:
        return {
            "user": user["username"],
            "client_id": client_id,
            "available_period": None,
            "warning": "Данные ещё не обработаны Airflow. Отчёт будет доступен после выполнения ETL.",
            "total_records": 0,
            "reports": [],
        }

    # Проверяем, не выходит ли запрошенный период за обработанные данные
    avail_from_iso = available_from.isoformat()
    avail_to_iso = available_to.isoformat()
    warning = None

    out_before = date_from and date_from < available_from
    out_after = date_to and date_to > available_to
    # Запрос начинается после конца доступных данных
    starts_after = date_from and date_from > available_to

    if starts_after:
        warning = (
            f"Данные доступны только по {avail_to_iso}. "
            f"Запрошенный период ({date_from.isoformat()}) ещё не обработан Airflow."
        )
    elif out_before and out_after:
        warning = (
            f"Данные доступны только за период {avail_from_iso} — {avail_to_iso}. "
            f"Запрошенный диапазон выходит за пределы обработанных Airflow данных."
        )
    elif out_before:
        warning = f"Данные доступны только с {avail_from_iso}. Более ранние даты ещё не обработаны Airflow."
    elif out_after:
        warning = f"Данные доступны только по {avail_to_iso}. Более поздние даты ещё не обработаны Airflow."

    # Основной запрос — только в пределах обработанного периода
    query = """
        SELECT
            client_id,
            client_name,
            email,
            prosthesis_id,
            prosthesis_model,
            report_date,
            total_movements,
            avg_response_time_ms,
            avg_signal_strength,
            avg_battery_level,
            active_minutes,
            anomaly_count
        FROM report_user_prosthesis
        WHERE client_id = %(client_id)s
    """
    params: dict = {"client_id": client_id}

    if date_from:
        query += " AND report_date >= %(date_from)s"
        params["date_from"] = date_from.isoformat()
    if date_to:
        query += " AND report_date <= %(date_to)s"
        params["date_to"] = date_to.isoformat()

    query += " ORDER BY prosthesis_id, report_date DESC"

    rows = ch.execute(query, params)

    reports = [
        {
            "client_id": row[0],
            "client_name": row[1],
            "email": row[2],
            "prosthesis_id": row[3],
            "prosthesis_model": row[4],
            "report_date": row[5].isoformat(),
            "total_movements": row[6],
            "avg_response_time_ms": row[7],
            "avg_signal_strength": row[8],
            "avg_battery_level": row[9],
            "active_minutes": row[10],
            "anomaly_count": row[11],
        }
        for row in rows
    ]

    result = {
        "user": user["username"],
        "client_id": client_id,
        "available_period": {
            "from": available_from.isoformat(),
            "to": available_to.isoformat(),
        },
        "total_records": len(reports),
        "reports": reports,
    }
    if warning:
        result["warning"] = warning

    return result


@app.get("/health")
def health():
    """Health check."""
    return {"status": "ok"}
