import os
import base64
import json
from datetime import date
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query, Header, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from clickhouse_driver import Client


def get_ch_client() -> Client:
    """
    Создаёт клиент ClickHouse.
    По умолчанию ходим на localhost:9000 (порт проброшен из docker-compose Airflow).
    При необходимости можно переопределить через переменные окружения.
    """
    return Client(
        host=os.getenv("CLICKHOUSE_HOST", "localhost"),
        port=int(os.getenv("CLICKHOUSE_PORT", "9000")),
        user=os.getenv("CLICKHOUSE_USER", "airflow"),
        password=os.getenv("CLICKHOUSE_PASSWORD", "airflow"),
        database=os.getenv("CLICKHOUSE_DB", "bionicpro"),
        settings={"use_numpy": False},
    )


class DailyTelemetry(BaseModel):
    event_date: date
    prosthesis_id: str
    events: int
    err_events: int
    avg_response_ms: float
    p95_response_ms: float
    avg_battery_level: float


class UserReport(BaseModel):
    customer_id: str
    full_name: str
    country: str
    days: List[DailyTelemetry]


class AuthenticatedUser(BaseModel):
    """
    Упрощённая модель аутентифицированного пользователя
    на основе access token Keycloak.
    """

    username: str
    roles: List[str]


PROTHETIC_ROLE = "prothetic_user"

USERNAME_TO_CUSTOMER_ID = {
    "prothetic1": "c1",
    "prothetic2": "c2",
    "prothetic3": "c3",
}


def _decode_jwt_no_verify(token: str) -> dict:
    """
    Минимальное декодирование payload части JWT без проверки подписи.
    """
    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("token must have 3 parts")

        payload_b64 = parts[1]
        # Добавляем padding, если он был убран
        payload_b64 += "=" * (-len(payload_b64) % 4)
        payload_bytes = base64.urlsafe_b64decode(payload_b64.encode("utf-8"))
        return json.loads(payload_bytes.decode("utf-8"))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token",
        ) from exc


def get_current_user(
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> AuthenticatedUser:
    """
    Извлекает пользователя из заголовка Authorization: Bearer <access_token>.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )

    if not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header",
        )

    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Empty access token",
        )

    claims = _decode_jwt_no_verify(token)
    username = claims.get("preferred_username") or claims.get("sub")
    roles = claims.get("realm_access", {}).get("roles", []) or []

    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has no username",
        )

    if not isinstance(roles, list):
        roles = list(roles)

    return AuthenticatedUser(username=username, roles=roles)


app = FastAPI(
    title="BionicPRO Reports API",
    description="Сервис выдачи отчётов по данным из OLAP (ClickHouse)",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/reports", response_model=UserReport)
def get_report(
    customer_id: Optional[str] = Query(
        default=None,
        description=(
            "ID клиента (customer_id) в витрине user_daily_telemetry. "
            "При наличии аутентификации реальное значение берётся из токена."
        ),
    ),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Возвращает готовый отчёт по пользователю из витрины bionicpro.user_daily_telemetry.

    Ограничения доступа:
    - Только аутентифицированные пользователи с ролью `prothetic_user`;
    - Пользователь может получить отчёт только по себе
      (customer_id определяется на основе его аккаунта в Keycloak).
    """

    if PROTHETIC_ROLE not in current_user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Report access is allowed only for prosthetic users",
        )

    mapped_cid = USERNAME_TO_CUSTOMER_ID.get(current_user.username)
    if not mapped_cid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No report is bound to current user",
        )

    if customer_id is not None and customer_id != mapped_cid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: cannot access other user's report",
        )

    cid = mapped_cid

    client = get_ch_client()

    rows = client.execute(
        """
        SELECT
          event_date,
          prosthesis_id,
          events,
          err_events,
          avg_response_ms,
          p95_response_ms,
          avg_battery_level,
          customer_id,
          full_name,
          country
        FROM bionicpro.user_daily_telemetry
        WHERE customer_id = %(cid)s
        ORDER BY event_date, prosthesis_id
        """,
        {"cid": cid},
    )

    if not rows:
        raise HTTPException(status_code=404, detail="Report not found for given customer_id")

    first_row = rows[0]
    _, _, _, _, _, _, _, customer_id_value, full_name, country = first_row

    days: List[DailyTelemetry] = []
    for (
        event_date,
        prosthesis_id,
        events,
        err_events,
        avg_response_ms,
        p95_response_ms,
        avg_battery_level,
        _cid,
        _full_name,
        _country,
    ) in rows:
        days.append(
            DailyTelemetry(
                event_date=event_date,
                prosthesis_id=prosthesis_id,
                events=events,
                err_events=err_events,
                avg_response_ms=avg_response_ms,
                p95_response_ms=p95_response_ms,
                avg_battery_level=avg_battery_level,
            )
        )

    return UserReport(
        customer_id=customer_id_value,
        full_name=full_name,
        country=country,
        days=days,
    )
