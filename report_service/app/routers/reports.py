# app/routers/reports.py
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from datetime import date, datetime, timedelta
import logging
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Импортируем зависимости
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.dependencies import get_current_user, verify_user_access
from app.db.clickhouse import clickhouse_client


# Pydantic модели
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
    reports: list[ReportResponse]
    total_days: int
    generated_at: datetime = datetime.now()


router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/{user_id}", response_model=ReportListResponse)
async def get_user_reports(
        user_id: str,
        start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
        end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
        current_user: dict = Depends(get_current_user)
):
    """
    Получить отчёты пользователя.
    Доступ только к своим отчётам (или для администраторов).
    """
    # Проверка прав доступа
    await verify_user_access(user_id, current_user)

    # Если даты не указаны, берём последние 30 дней
    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=30)

    logger.info(f"Fetching reports for user {user_id} from {start_date} to {end_date}")

    # Получаем данные из ClickHouse
    try:
        reports_data = clickhouse_client.get_user_reports(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date
        )

        if not reports_data:
            logger.info(f"No reports found for user {user_id}")
            return ReportListResponse(
                user_id=user_id,
                reports=[],
                total_days=0
            )

        # Преобразуем в Pydantic модели
        reports = [ReportResponse(**report) for report in reports_data]

        return ReportListResponse(
            user_id=user_id,
            reports=reports,
            total_days=len(reports)
        )

    except Exception as e:
        logger.error(f"Error fetching reports: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching reports: {str(e)}"
        )


@router.get("/{user_id}/latest", response_model=ReportResponse)
async def get_latest_report(
        user_id: str,
        current_user: dict = Depends(get_current_user)
):
    """Получить последний доступный отчёт пользователя"""
    # Проверка прав доступа
    await verify_user_access(user_id, current_user)

    try:
        reports = clickhouse_client.get_user_reports(
            user_id=user_id,
            start_date=date(2000, 1, 1),  # очень старая дата
            end_date=date.today()
        )

        if not reports:
            raise HTTPException(
                status_code=404,
                detail="No reports found for this user"
            )

        # Берём первый (самый новый, т.к. сортировка DESC)
        return ReportResponse(**reports[0])

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching latest report: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching report: {str(e)}"
        )