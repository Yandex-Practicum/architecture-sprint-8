from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import clickhouse_connect
from clickhouse_connect.driver.client import Client
import os
from .auth import get_current_user, AuthenticatedUser

from datetime import date, timedelta
from typing import Any

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins= ["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

def _get_clickhouse_client() -> Client:
    return clickhouse_connect.get_client(
        host=os.getenv('CLICKHOUSE_HOST', 'localhost'),
        port=os.getenv('CLICKHOUSE_PORT', 9000),
        username=os.getenv('CLICKHOUSE_USERNAME', 'default'),
        password=os.getenv('CLICKHOUSE_PASSWORD', ''),
        database=os.getenv('CLICKHOUSE_DATABASE', 'default')
    )

def _get_rows(query: str, parameters: dict[str, any] = None) -> list[dict[str, any]]:
    client = _get_clickhouse_client()
    result = client.query(query, parameters=parameters)
    return [dict(zip(result.column_names, row)) for row in result.result_rows]

@app.get("/health")
def healthcheck():
    _get_rows("SELECT 'ok' AS status")
    return {"status": "ok"}

@app.get("/reports")
def get_reports(
    user: AuthenticatedUser = Depends(get_current_user),
    start_date: date = date.today() - timedelta(days=7),
    end_date: date = date.today()
) ->dict[str, Any]:
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date must be before end_date")
    
    timePeriod = _get_rows(
        """SELECT
            count(*) AS total_events
           FROM report_date
           WHERE report_date >= %(start_date)s AND report_date <= %(end_date)s""",
        parameters={"start_date": start_date, "end_date": end_date}
    )[0]

    if timePeriod["total_events"] == 0:
        raise HTTPException(status_code=404, detail="No data found for the specified date range")
    
    parameters = {
        "email": user.email,
        "start_date": start_date,
        "end_date": end_date
    }

    summary = _get_rows(
        """SELECT
            any(user_id) AS user_id,
            any(full_name) AS full_name,
            email,
            avg(battery_level) AS avg_battery_level,
            avg(active_minutes) AS avg_active_minutes,
            count(*) AS total_events
           FROM report
           WHERE email = %(email)s AND report_date >= %(start_date)s AND report_date <= %(end_date)s
           GROUP BY email""",
        parameters=parameters
    )

    if not summary:
        raise HTTPException(status_code=404, detail="No data found for the specified user and date range")
    
    return {
        "user_id": summary[0]["user_id"],
        "full_name": summary[0]["full_name"],
        "email": summary[0]["email"],
        "avg_battery_level": summary[0]["avg_battery_level"],
        "avg_active_minutes": summary[0]["avg_active_minutes"],
        "total_events": timePeriod["total_events"]
    }