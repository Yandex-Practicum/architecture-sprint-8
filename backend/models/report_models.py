from datetime import date
from typing import List
from pydantic import BaseModel


class ReportItem(BaseModel):
    report_date: date
    prosthesis_id: int
    total_active_sec: int
    avg_reaction_ms: float
    movements_count: int
    errors_count: int
    battery_avg_pct: float
    crm_country: str
    crm_segment: str
    crm_tariff: str


class ReportResponse(BaseModel):
    user_id: int
    from_date: date
    to_date: date
    items: List[ReportItem]