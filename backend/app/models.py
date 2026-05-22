from datetime import date, datetime
from typing import Any, Dict

from pydantic import BaseModel, ConfigDict


class ProstheticsReport(BaseModel):
    customer_id: str
    customer_name: str
    customer_email: str | None = None
    prosthesis_model: str
    region: str | None = None
    purchase_date: date | None = None
    warranty_end_date: date | None = None
    warranty_status: str | None = None
    total_usage_hours: float = 0.0
    avg_daily_usage_minutes: float = 0.0
    total_sessions: int = 0
    total_movements: int = 0
    avg_movements_per_session: float = 0.0
    total_errors: int = 0
    errors_per_session: float = 0.0
    last_active_date: date | None = None
    battery_health_avg: float = 0.0
    most_common_movement: str = "unknown"
    data_as_of_date: date | None = None

    model_config = ConfigDict(from_attributes=True)


class ErrorResponse(BaseModel):
    detail: str


class ReportListResponse(BaseModel):
    count: int
    reports: list[ProstheticsReport]


class ReportQueryParams(BaseModel):
    customer_id: str | None = None
    format: str = "json"


def row_to_report(row: Dict[str, Any]) -> ProstheticsReport:
    def _val(key: str) -> Any:
        v = row.get(key)
        if isinstance(v, str) and v.strip() == "":
            return None
        return v

    return ProstheticsReport(
        customer_id=_val("customer_id") or "",
        customer_name=_val("customer_name") or "",
        customer_email=_val("customer_email"),
        prosthesis_model=_val("prosthesis_model") or "",
        region=_val("region"),
        purchase_date=_val("purchase_date"),
        warranty_end_date=_val("warranty_end_date"),
        warranty_status=_val("warranty_status"),
        total_usage_hours=float(_val("total_usage_hours") or 0),
        avg_daily_usage_minutes=float(_val("avg_daily_usage_minutes") or 0),
        total_sessions=int(_val("total_sessions") or 0),
        total_movements=int(_val("total_movements") or 0),
        avg_movements_per_session=float(_val("avg_movements_per_session") or 0),
        total_errors=int(_val("total_errors") or 0),
        errors_per_session=float(_val("errors_per_session") or 0),
        last_active_date=_val("last_active_date"),
        battery_health_avg=float(_val("battery_health_avg") or 0),
        most_common_movement=_val("most_common_movement") or "unknown",
        data_as_of_date=_val("data_as_of_date"),
    )
