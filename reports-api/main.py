import base64
import hashlib
import io
import json
import logging
import os
import time

from fastapi import FastAPI, HTTPException, Request, Response
import requests
from clickhouse_driver import Client
from pydantic import BaseModel
from datetime import date, datetime, timedelta
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
import valkey
from minio import Minio, S3Error


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
CLICKHOUSE_URL = os.getenv(
    "CLICKHOUSE_URL", "clickhouse://admin:admin@localhost:9431/default"
)

S3_ENDPOINT = os.getenv("S3_ENDPOINT", "localhost:9000")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY", "minio_user")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY", "minio_password")
S3_BUCKET = os.getenv("S3_BUCKET", "reports")

VALKEY_HOST = os.getenv("VALKEY_HOST", "localhost")
VALKEY_PORT = os.getenv("VALKEY_PORT", "6389")

CDN_URL = os.getenv("CDN_URL", "http://localhost:8088")

SECRET = "CHANGE_SECRET_KEY"

SESSION_TTL: int = 1800

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ch_client = Client.from_url(CLICKHOUSE_URL)

valkey_client = valkey.Valkey(host=VALKEY_HOST, port=VALKEY_PORT, db=0)
s3_client = Minio(
    S3_ENDPOINT, access_key=S3_ACCESS_KEY, secret_key=S3_SECRET_KEY, secure=False
)
policy = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {"AWS": "*"},
            "Action": ["s3:GetObject"],
            "Resource": [f"arn:aws:s3:::{S3_BUCKET}/*"],
        }
    ],
}
if not s3_client.bucket_exists(S3_BUCKET):
    s3_client.make_bucket(S3_BUCKET)
s3_client.set_bucket_policy(S3_BUCKET, json.dumps(policy))


def generate_signed_url(path, expires_in: int = 300):
    future = datetime.now() + timedelta(minutes=5)
    timestamp = str(int(time.mktime(future.timetuple())))

    hash_string = f"{timestamp}{path}{SECRET}"
    md5_hash = hashlib.md5(hash_string.encode("utf-8")).digest()

    security = (
        base64.b64encode(md5_hash)
        .replace(b"+", b"-")
        .replace(b"/", b"_")
        .replace(b"=", b"")
    )

    secure_url = f"{path}?st={security.decode('utf-8')}&e={timestamp}"
    return f"{CDN_URL}{secure_url}"


@app.get("/reports")
async def get_report(request: Request, response: Response):

    session_id = request.cookies.get("session_id")
    user_response = requests.get(
        f"{AUTH_SERVICE_URL}/auth/userinfo",
        cookies={"session_id": session_id},
        timeout=5,
    )
    if user_response.status_code == 200:
        data = user_response.json()
        email = data.get("email", None)
    else:
        raise HTTPException(
            status_code=user_response.status_code, detail=user_response.text
        )

    if not email:
        raise HTTPException(status_code=401, detail="Not authenticated")

    response.set_cookie(
        key="session_id",
        value=user_response.cookies.get("session_id"),
        httponly=True,
        # secure=True,
        samesite="lax",
        max_age=SESSION_TTL,
    )

    latest_date = valkey_client.get("latest_etl_date")
    if not latest_date:
        latest_date = str(int(time.time()))
        valkey_client.set("latest_etl_date", latest_date)
    else:
        latest_date = latest_date.decode("utf-8")

    object_key = f"{email}/{latest_date}.json"

    try:
        s3_client.stat_object(S3_BUCKET, object_key)
        path = f"/reports/{email}/{latest_date}.json"
        cdn_url = generate_signed_url(path)
        return {"report_url": cdn_url}
    except S3Error:
        pass
    except Exception as e:
        logging.exception(e)
        raise HTTPException(status_code=500)

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

    json_string = json.dumps(report.model_dump(mode="json"))
    json_bytes = json_string.encode("utf-8")
    data_length = len(json_bytes)

    data_stream = io.BytesIO(json_bytes)

    try:
        s3_client.put_object(
            S3_BUCKET,
            object_key,
            data_stream,
            data_length,
            content_type="application/json",
        )
    except S3Error as e:
        if e.response["Error"]["Code"] != "404":
            raise HTTPException(status_code=500, detail="S3 error")

    path = f"/reports/{email}/{latest_date}.json"
    cdn_url = generate_signed_url(path)

    return {"report_url": cdn_url}


def main():
    print("Hello from reports-api!")
    uvicorn.run("main:app", port=8001, host="0.0.0.0", reload=True)


if __name__ == "__main__":
    main()
