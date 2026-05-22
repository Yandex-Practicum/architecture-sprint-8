from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth import UserInfo, get_current_user
from app.database import get_all_reports, get_report_by_customer
from app.models import ProstheticsReport, ReportListResponse, row_to_report

router = APIRouter(prefix="/reports", tags=["reports"])

_ADMIN_ROLES = {"administrator"}


@router.get("", response_model=ProstheticsReport | ReportListResponse)
async def get_report(
    customer_id: str | None = Query(
        default=None,
        description="Фильтр по ID клиента. Для обычных пользователей — только свой customer_id.",
    ),
    user: UserInfo = Depends(get_current_user),
):
    is_admin = bool(_ADMIN_ROLES & set(user.roles))

    if customer_id:
        if not is_admin and user.customer_id and customer_id != user.customer_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Доступ запрещён: можно запрашивать только свой отчёт",
            )
        row = await get_report_by_customer(customer_id)
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Отчёт для клиента {customer_id} не найден",
            )
        return row_to_report(row)

    if not is_admin:
        effective_cid = user.customer_id or user.username
        row = await get_report_by_customer(effective_cid)
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Отчёт для пользователя {user.username} не найден",
            )
        return row_to_report(row)

    rows = await get_all_reports()
    reports = [row_to_report(r) for r in rows]
    return ReportListResponse(count=len(reports), reports=reports)
