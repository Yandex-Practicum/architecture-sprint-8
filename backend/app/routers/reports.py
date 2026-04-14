from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from datetime import date, datetime
from pydantic import BaseModel
import httpx
import json
from app.config import settings
from app.auth import get_current_user
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/reports", tags=["reports"])

class ReportResponse(BaseModel):
    user_uuid: str
    user_name: str
    prosthesis_id: str
    report_date: date
    total_usage_seconds: int
    avg_response_time_ms: float
    movements_count: int
    battery_cycles: int
    last_telemetry_time: datetime
    firmware_version: str
    region: str

@router.get("", response_model=list[ReportResponse])
async def get_reports(
    user_uuid: Optional[str] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: dict = Depends(get_current_user)
):
    """Получение отчётов о работе протезов."""
    target_uuid = user_uuid or current_user["sub"]
    logger.info(f"🔍 Querying ClickHouse for user: {target_uuid}")
    
    url = f"http://{settings.CLICKHOUSE_HOST}:{settings.CLICKHOUSE_PORT}/"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        
        test_query = "SELECT 1"
        test_response = await client.post(
            url,
            params={"query": test_query},
            auth=(settings.CLICKHOUSE_USER, settings.CLICKHOUSE_PASSWORD)
        )
        logger.info(f"Test query status: {test_response.status_code}, text: {test_response.text}")
        
        
        query = f"""
            SELECT 
                user_uuid, user_name, prosthesis_id, toString(report_date) as report_date,
                total_usage_seconds, avg_response_time_ms, movements_count,
                battery_cycles, toString(last_telemetry_time) as last_telemetry_time,
                firmware_version, region
            FROM reports_db.prosthesis_report 
            WHERE user_uuid = '{target_uuid}'
            ORDER BY report_date DESC
        """
        
        response = await client.post(
            url,
            params={"query": query, "default_format": "JSONEachRow"},
            auth=(settings.CLICKHOUSE_USER, settings.CLICKHOUSE_PASSWORD)
        )
        
        logger.info(f"Main query status: {response.status_code}")
        
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=f"ClickHouse error: {response.text}")
        
        data = response.text.strip()
        if not data:
            return []
        
        reports = []
        for line in data.split('\n'):
            if line.strip():
                row = json.loads(line)
                reports.append({
                    "user_uuid": row['user_uuid'],
                    "user_name": row['user_name'],
                    "prosthesis_id": row['prosthesis_id'],
                    "report_date": row['report_date'],
                    "total_usage_seconds": int(row['total_usage_seconds']),
                    "avg_response_time_ms": float(row['avg_response_time_ms']),
                    "movements_count": int(row['movements_count']),
                    "battery_cycles": int(row['battery_cycles']),
                    "last_telemetry_time": row['last_telemetry_time'],
                    "firmware_version": row['firmware_version'],
                    "region": row['region']
                })
        return reports