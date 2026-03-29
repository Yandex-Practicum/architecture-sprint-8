from __future__ import annotations

import os
from typing import Any

import clickhouse_connect
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from app.auth import get_current_claims


def get_clickhouse_client():
    return clickhouse_connect.get_client(
        host=os.environ["CLICKHOUSE_HOST"],
        port=int(os.environ["CLICKHOUSE_PORT"]),
        username=os.environ.get("CLICKHOUSE_USERNAME", "default"),
        password=os.environ.get("CLICKHOUSE_PASSWORD", ""),
        database=os.environ.get("CLICKHOUSE_DATABASE", "default"),
    )


app = FastAPI(title="BionicPRO Reports API")

allowed_origins = [origin.strip() for origin in os.environ.get("ALLOWED_ORIGINS", "").split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/reports")
def get_reports(claims: dict[str, Any] = Depends(get_current_claims)) -> dict[str, Any]:
    username = claims.get("preferred_username")
    subject = claims.get("sub")

    client = get_clickhouse_client()
    result = client.query(
        f"""
        SELECT
            keycloak_username,
            full_name,
            email,
            country_code,
            prosthesis_code,
            model_name,
            activated_at,
            telemetry_from,
            telemetry_to,
            total_events,
            total_active_minutes,
            total_grip_actions,
            avg_signal,
            avg_battery_level,
            report_generated_at
        FROM {os.environ.get('REPORTS_TABLE', 'reports_user_summary')}
        WHERE keycloak_username = %(username)s
        ORDER BY prosthesis_code
        """,
        parameters={"username": username},
    )
    client.close()

    rows = []
    for row in result.named_results():
        rows.append(
            {
                "keycloak_username": row["keycloak_username"],
                "full_name": row["full_name"],
                "email": row["email"],
                "country_code": row["country_code"],
                "prosthesis_code": row["prosthesis_code"],
                "model_name": row["model_name"],
                "activated_at": row["activated_at"].isoformat(),
                "telemetry_from": row["telemetry_from"].isoformat(),
                "telemetry_to": row["telemetry_to"].isoformat(),
                "total_events": row["total_events"],
                "total_active_minutes": row["total_active_minutes"],
                "total_grip_actions": row["total_grip_actions"],
                "avg_signal": row["avg_signal"],
                "avg_battery_level": row["avg_battery_level"],
                "report_generated_at": row["report_generated_at"].isoformat(),
            }
        )

    return {
        "subject": subject,
        "preferred_username": username,
        "reports": rows,
    }
