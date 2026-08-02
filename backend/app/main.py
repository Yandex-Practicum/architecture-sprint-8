from datetime import date, timedelta

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from app.dependencies import CurrentUser, DBClient
from app.schemas import DailyMetric, ReportResponse
from app.settings import settings

app = FastAPI(
    title="Reports Service",
    version="1.0.0",
    description="Сервис отчетов по телеметрии бионических протезов",
    debug=settings.debug,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", tags=["root"])
async def root():
    """Корневой эндпоинт с информацией о сервисе"""
    return {
        "service": "Prosthetic Reports Service",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }

@app.get("/api/reports", tags=["reports"], response_model=ReportResponse)
async def get_report(
    username: CurrentUser,
    client: DBClient,
    period_from: date | None = None,
    period_to: date | None = None,
):
    """
    Возвращает отчёт по телеметрии для текущего пользователя.
    
    - **period_from**: начало периода
    - **period_to**: конец периода
    """
    if not period_to:
        period_to = date.today()  # noqa: DTZ011
    if not period_from:
        period_from = period_to - timedelta(weeks=52)
    
    # Проверяем, что даты корректны
    if period_from > period_to:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="period_from must be less than or equal to period_to"
        )
    
    table = settings.clickhouse_table
    
    # 1. Получаем основную информацию о пользователе
    user_info_query = f"""
    SELECT 
        username,
        user_email as email,
        prosthetic_id
    FROM {table}
    WHERE username = '{username}'
    LIMIT 1
    """
    
    user_info = client.query(user_info_query).result_rows
    
    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User '{username}' not found in the system"
        )
    
    user_email = user_info[0][1]
    prosthetic_id = user_info[0][2]
    
    metrics_query = f"""
    SELECT 
        metric_date,
        avg_response_time_ms,
        max_response_time_ms,
        signals_count,
        battery_avg_level
    FROM {table}
    WHERE username = '{username}'
        AND metric_date BETWEEN '{period_from}' AND '{period_to}'
    ORDER BY metric_date
    """
    
    metrics_result = client.query(metrics_query).result_rows
    
    metrics = [
        DailyMetric(
            metric_date=row[0],
            avg_response_time_ms=row[1],
            max_response_time_ms=row[2],
            signals_count=row[3],
            battery_avg_level=row[4]
        )
        for row in metrics_result
    ]
    
    return ReportResponse(
        username=username,
        email=user_email,
        prosthetic_id=prosthetic_id,
        period_from=period_from,
        period_to=period_to,
        metrics=metrics
    )