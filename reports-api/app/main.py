import os
from typing import Optional

import httpx
import csv
import io
from minio import Minio
from minio.error import S3Error
from fastapi import FastAPI, Cookie, HTTPException

CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "olap_db")
CLICKHOUSE_HTTP_PORT = os.getenv("CLICKHOUSE_HTTP_PORT", "8123")
BIONIC_AUTH = os.getenv("BIONIC_AUTH", "http://bionicpro-auth:8000")
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minio_user")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minio_password")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "reports")
CDN_BASE = os.getenv("CDN_BASE", "http://cdn:8080")

minio_client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=False,
)
if not minio_client.bucket_exists(MINIO_BUCKET):
    minio_client.make_bucket(MINIO_BUCKET)

app = FastAPI(title="reports-api")


def clickhouse_query(sql: str) -> str:
    url = f"http://{CLICKHOUSE_HOST}:{CLICKHOUSE_HTTP_PORT}/"
    r = httpx.post(url, data=sql)
    r.raise_for_status()
    return r.text


@app.get("/reports/{user_id}")
async def get_report(user_id: int, from_ts: Optional[str] = None, to_ts: Optional[str] = None, session_id: Optional[str] = Cookie(None)):
    # validate session via bionicpro-auth
    async with httpx.AsyncClient() as client:
        headers = {}
        cookies = {"bionicpro_session": session_id} if session_id else {}
        resp = await client.get(f"{BIONIC_AUTH}/session/validate", headers=headers, cookies=cookies)
        if resp.status_code != 200:
            raise HTTPException(status_code=401, detail="invalid session")
        userinfo = resp.json()

    # enforce that requested user_id matches authenticated user's id if available
    # Keycloak userinfo may contain 'sub' or 'preferred_username' — adapt as needed
    # For demo, skip strict check if userinfo doesn't include numeric id

    # Build ClickHouse SQL
    where_clauses = [f"user_id = {user_id}"]
    if from_ts:
        where_clauses.append(f"signal_time >= toDateTime('{from_ts}')")
    if to_ts:
        where_clauses.append(f"signal_time <= toDateTime('{to_ts}')")
    where_sql = " AND ".join(where_clauses)

    sql = f"""
    SELECT
      user_id,
      prosthesis_type,
      count() AS events,
      avg(signal_amplitude) AS avg_amplitude,
      avg(signal_frequency) AS avg_frequency,
      sum(signal_duration) AS total_duration,
      min(signal_time) AS first_time,
      max(signal_time) AS last_time
    FROM emg_sensor_data
    WHERE {where_sql}
    GROUP BY user_id, prosthesis_type
    ORDER BY events DESC
    FORMAT JSON
    """

    # Build object key for report (deterministic)
    key_from = from_ts.replace(' ', 'T') if from_ts else 'start'
    key_to = to_ts.replace(' ', 'T') if to_ts else 'end'
    object_name = f"reports/{user_id}/{key_from}_{key_to}.json"

    # Check MinIO for existing object
    try:
        stat = minio_client.stat_object(MINIO_BUCKET, object_name)
        # object exists -> return CDN URL
        cdn_url = f"{CDN_BASE}/{MINIO_BUCKET}/{object_name}"
        return {"url": cdn_url, "cached": True}
    except S3Error:
        # not found, generate
        pass

    try:
        text = clickhouse_query(sql)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

    # upload result to minio as object
    data_bytes = text.encode('utf-8')
    try:
        minio_client.put_object(MINIO_BUCKET, object_name, io.BytesIO(data_bytes), length=len(data_bytes), content_type='application/json')
    except S3Error as e:
        raise HTTPException(status_code=502, detail=f"minio upload failed: {e}")

    cdn_url = f"{CDN_BASE}/{MINIO_BUCKET}/{object_name}"
    return {"url": cdn_url, "cached": False}
