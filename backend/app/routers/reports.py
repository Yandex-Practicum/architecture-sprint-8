"""API роутер для отчётов с авторизацией."""

import logging
from datetime import date
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Depends

from app.models.report import ReportResponse, ErrorResponse
from app.services.clickhouse_service import clickhouse_service
from app.auth.keycloak import get_current_user, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get(
    "",
    response_model=ReportResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "No data found"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    },
    summary="Получить отчёт по текущему пользователю",
    description="""
    Возвращает отчёт **только для авторизованного пользователя**.
    
    User ID извлекается из JWT токена Keycloak.
    Пользователь может получить доступ только к собственным данным.
    
    ## Авторизация
    
    Требуется Bearer токен в заголовке:
    ```
    Authorization: Bearer <access_token>
    ```
    
    ## Ограничение доступа
    
    - Пользователь получает отчёт только по себе
    - User ID берётся из токена (claim `sub`), а не из параметров запроса
    - Невозможно запросить чужой отчёт
    """
)
async def get_my_reports(
    current_user: User = Depends(get_current_user),
    date_from: Optional[date] = Query(None, description="Начальная дата (YYYY-MM-DD)"),
    date_to: Optional[date] = Query(None, description="Конечная дата (YYYY-MM-DD)"),
    limit: int = Query(30, ge=1, le=365, description="Максимальное количество записей")
) -> ReportResponse:
    """
    Получение отчёта для текущего авторизованного пользователя.
    
    User ID извлекается из JWT токена - пользователь может получить
    доступ ТОЛЬКО к своим данным.
    """
    # User ID берётся из токена, не из параметров!
    user_id = current_user.username  # username соответствует user_id в витрине
    
    logger.info(
        f"User {current_user.username} (id: {current_user.id}) "
        f"requesting reports for themselves"
    )
    
    try:
        # Проверка последней даты ETL
        latest_etl_date = clickhouse_service.get_latest_etl_date()
        
        # Предупреждение если запрашиваются данные за будущий период
        if date_to and latest_etl_date and date_to > latest_etl_date:
            logger.warning(
                f"User {user_id} requested data up to {date_to}, "
                f"but latest ETL date is {latest_etl_date}"
            )
        
        # Получение отчётов из ClickHouse ТОЛЬКО для текущего пользователя
        reports = clickhouse_service.get_reports_by_user(
            user_id=user_id,
            date_from=date_from,
            date_to=date_to,
            limit=limit
        )
        
        if not reports:
            message = f"Нет данных для пользователя {user_id}"
            if latest_etl_date:
                message += f". Последняя обработка ETL: {latest_etl_date}"
            
            return ReportResponse(
                success=True,
                user_id=user_id,
                reports=[],
                total_count=0,
                message=message
            )
        
        return ReportResponse(
            success=True,
            user_id=user_id,
            reports=reports,
            total_count=len(reports),
            message=f"Данные актуальны на {latest_etl_date}" if latest_etl_date else None
        )
        
    except Exception as e:
        logger.error(f"Error getting reports for user {user_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка получения отчёта: {str(e)}"
        )


@router.get(
    "/status",
    summary="Статус данных",
    description="Проверка доступности данных и даты последнего ETL"
)
async def get_status(current_user: User = Depends(get_current_user)):
    """Получение статуса данных в OLAP (требует авторизации)."""
    logger.info(f"User {current_user.username} checking data status")
    
    try:
        latest_etl_date = clickhouse_service.get_latest_etl_date()
        
        return {
            "status": "ok",
            "user": current_user.username,
            "latest_etl_date": latest_etl_date.isoformat() if latest_etl_date else None,
            "message": "Данные доступны" if latest_etl_date else "Данные ещё не загружены"
        }
        
    except Exception as e:
        logger.error(f"Error checking status: {e}")
        return {
            "status": "error",
            "user": current_user.username,
            "latest_etl_date": None,
            "message": f"Ошибка подключения к OLAP: {str(e)}"
        }


@router.get(
    "/me",
    summary="Информация о текущем пользователе",
    description="Возвращает информацию о пользователе из JWT токена"
)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Получение информации о текущем авторизованном пользователе."""
    return {
        "user_id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "roles": current_user.roles
    }
