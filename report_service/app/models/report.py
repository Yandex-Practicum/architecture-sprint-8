# app/models/report.py
from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional, List


class ReportRequest(BaseModel):
    user_id: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class ReportResponse(BaseModel):
    user_id: str
    prosthetic_id: str
    report_date: date
    total_usage_minutes: float
    avg_response_time_ms: float
    battery_cycles: int
    movements_count: int
    successful_movements: int
    failed_movements: int
    calibration_count: int
    data_volume_mb: float

    class Config:
        from_attributes = True


class ReportListResponse(BaseModel):
    user_id: str
    reports: List[ReportResponse]
    total_days: int
    generated_at: datetime = datetime.now()