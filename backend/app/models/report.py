"""Модели данных для отчётов."""

from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional, List


class ReportData(BaseModel):
    """Данные отчёта по пользователю."""
    user_id: str
    username: str
    email: str
    first_name: str
    last_name: str
    prosthetic_model: str
    report_date: date
    total_usage_hours: float
    movement_count: int
    avg_response_time_ms: float
    battery_cycles: int
    calibration_count: int
    last_sync_at: datetime
    etl_processed_at: datetime


class ReportResponse(BaseModel):
    """Ответ API с отчётом."""
    success: bool
    user_id: str
    reports: List[ReportData]
    total_count: int
    message: Optional[str] = None


class ErrorResponse(BaseModel):
    """Ответ с ошибкой."""
    success: bool = False
    error: str
    detail: Optional[str] = None

