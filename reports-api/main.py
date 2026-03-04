import os

from fastapi import FastAPI, HTTPException, Request
import requests
from clickhouse_driver import Client
from pydantic import BaseModel
from datetime import date, datetime
import uvicorn
from fastapi.middleware.cors import CORSMiddleware


class ReportResponse(BaseModel):
    user_id: int
    full_name: str
    email: str
    age: int
    gender: str
    country: str
    prosthesis_type: str
    avg_signal_frequency: float
    avg_signal_duration: float
    avg_signal_amplitude: float
    total_signals: int
    last_signal_time: datetime
    report_date: date


app = FastAPI(title="ReportsAPI Service")

AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://localhost:8000")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
CLICKHOUSE_URL = os.getenv("CLICKHOUSE_URL", "clickhouse://admin:admin@localhost:9431/default")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


ch_client = Client.from_url(CLICKHOUSE_URL)


@app.get("/reports")
async def get_report(request: Request):

    session_id = request.cookies.get("session_id")
    response = requests.get(
        f"{AUTH_SERVICE_URL}/auth/userinfo",
        cookies={"session_id": session_id},
        timeout=5,
    )
    if response.status_code == 200:
        data = response.json()
        email = data.get("email", None)
    else:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if not email:
        raise HTTPException(status_code=401, detail="Not authenticated")

    rows = ch_client.execute(f"""
        SELECT user_id, full_name, email, age, gender, country,
               prosthesis_type, avg_signal_frequency, avg_signal_duration,
               avg_signal_amplitude, total_signals, last_signal_time, report_date
        FROM user_reports
        WHERE email = '{email}'
        ORDER BY report_date DESC
        LIMIT 1
    """)

    if not rows:
        raise HTTPException(status_code=404, detail="Report not found")

    row = rows[0]

    report = ReportResponse(
        user_id=row[0],
        full_name=row[1],
        email=row[2],
        age=row[3],
        gender=row[4],
        country=row[5],
        prosthesis_type=row[6],
        avg_signal_frequency=row[7],
        avg_signal_duration=row[8],
        avg_signal_amplitude=row[9],
        total_signals=row[10],
        last_signal_time=row[11],
        report_date=row[12],
    )
    return report


def main():
    print("Hello from reports-api!")
    uvicorn.run("main:app", port=8001, host="0.0.0.0", reload=True)


if __name__ == "__main__":
    main()
