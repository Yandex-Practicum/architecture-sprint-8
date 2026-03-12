from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends

from security.jwt_service import get_current_user_id
from service.report_service import ReportService
from models.report_models import ReportResponse

router = APIRouter()

report_service = ReportService()


@router.get("/reports/me", response_model=ReportResponse)
def get_my_report(
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    current_user_id: int = Depends(get_current_user_id),
):

    if to_date is None:
        to_date = date.today()

    if from_date is None:
        from_date = to_date.fromordinal(max(to_date.toordinal() - 6, 1))
    return report_service.get_report(
        user_id=current_user_id,
        from_date=from_date,
        to_date=to_date,
    )