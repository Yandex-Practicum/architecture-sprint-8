from datetime import date

from pydantic import BaseModel


class DailyMetric(BaseModel):
    """Метрика за один день"""
    metric_date: date
    avg_response_time_ms: float
    max_response_time_ms: float
    signals_count: int
    battery_avg_level: int


class ReportResponse(BaseModel):
    """Ответ с отчетом по пользователю"""
    username: str
    email: str
    prosthetic_id: str
    period_from: date
    period_to: date
    metrics: list[DailyMetric]


class ErrorResponse(BaseModel):
    """Стандартный ответ с ошибкой"""
    detail: str
    status_code: int | None = None