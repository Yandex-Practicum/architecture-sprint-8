from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field, validator


class ReportRequest(BaseModel):
    user_id: int = Field(..., description="User ID for report", gt=0)
    period: str = Field(..., description="Period in YYYY-MM format")
    
    @validator('period')
    def validate_period(cls, v):
        try:
            datetime.strptime(v, "%Y-%m")
            return v
        except ValueError:
            raise ValueError("Period must be in YYYY-MM format")


class ReportResponse(BaseModel):
    user_id: int
    device_id: str
    period_month: date
    full_name: str
    email: str
    country: str
    device_type: str
    
    total_signals: int
    myo_signals_count: int
    battery_checks_count: int
    actuator_events_count: int
    
    total_actions: int
    most_frequent_action: str
    action_frequency: int
    
    avg_processing_time_ms: float
    min_processing_time_ms: float
    max_processing_time_ms: float
    
    device_status: str
    warranty_until: date
    
    report_generated_at: datetime
    data_freshness_date: datetime
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": 1,
                "device_id": "DEV001",
                "period_month": "2026-01-01",
                "full_name": "Иван Иванов",
                "email": "ivan@example.com",
                "country": "Russia",
                "device_type": "Arm Prosthesis Model X",
                "total_signals": 15000,
                "myo_signals_count": 14500,
                "battery_checks_count": 300,
                "actuator_events_count": 200,
                "total_actions": 450,
                "most_frequent_action": "grip",
                "action_frequency": 150,
                "avg_processing_time_ms": 85.3,
                "min_processing_time_ms": 50.0,
                "max_processing_time_ms": 120.0,
                "device_status": "active",
                "warranty_until": "2027-12-31",
                "report_generated_at": "2026-02-18T06:30:00",
                "data_freshness_date": "2026-02-18T06:00:00"
            }
        }


class ErrorResponse(BaseModel):
    detail: str
    error_code: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    clickhouse_connected: bool
    timestamp: datetime
