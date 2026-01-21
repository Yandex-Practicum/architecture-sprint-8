"""
FastAPI приложение для системы отчётов BionicPRO
Включает эндпоинт /reports для получения отчётов из ClickHouse
"""
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Optional
from datetime import date, datetime
from pydantic import BaseModel

from app.database import get_clickhouse_client
from app.auth import get_current_user_id
from app.reports import get_user_report, check_data_availability
from app.security import validate_user_id_from_token

app = FastAPI(
    title="BionicPRO Reports API",
    description="API для получения отчётов о работе протезов",
    version="1.0.0"
)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ReportResponse(BaseModel):
    """Модель ответа для отчёта"""
    user_id: int
    date_from: date
    date_to: date
    data: list[dict]
    summary: dict
    last_processed_date: Optional[date] = None
    last_processed_time: Optional[datetime] = None


class ErrorResponse(BaseModel):
    """Модель ответа для ошибки"""
    error: str
    message: str
    last_available_date: Optional[date] = None
    last_processed_time: Optional[datetime] = None


@app.get("/")
async def root():
    """Корневой эндпоинт"""
    return {
        "service": "BionicPRO Reports API",
        "version": "1.0.0",
        "endpoints": {
            "reports": "/reports",
            "health": "/health"
        }
    }


@app.get("/health")
async def health_check():
    """Проверка здоровья сервиса"""
    try:
        client = get_clickhouse_client()
        client.execute("SELECT 1")
        return {
            "status": "healthy",
            "clickhouse": "connected",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "clickhouse": "disconnected",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )


@app.get("/reports", response_model=ReportResponse)
async def get_reports(
    date_from: date,
    date_to: date,
    current_user_id: int = Depends(get_current_user_id)
):
    """
    Получить отчёт по пользователю за указанный период
    
    **Ограничение доступа**: Пользователь может запрашивать только свои отчёты.
    user_id автоматически извлекается из токена авторизации.
    
    Args:
        date_from: Начальная дата периода (YYYY-MM-DD)
        date_to: Конечная дата периода (YYYY-MM-DD)
        current_user_id: ID текущего пользователя (из токена, автоматически)
    
    Returns:
        ReportResponse: Отчёт с данными за период
    
    Raises:
        HTTPException 400: Неверные параметры запроса
        HTTPException 401: Невалидный токен или отсутствие авторизации
        HTTPException 403: Попытка запросить данные другого пользователя
        HTTPException 404: Данные за период ещё не обработаны
        HTTPException 500: Ошибка при получении отчёта
    """
    # Валидация дат
    if date_from > date_to:
        raise HTTPException(
            status_code=400,
            detail="date_from не может быть больше date_to"
        )
    
    # Проверка доступности данных
    availability = await check_data_availability(date_from, date_to)
    
    if not availability["available"]:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "data_not_available",
                "message": f"Данные за период {date_from} - {date_to} ещё не обработаны",
                "last_available_date": availability.get("last_available_date"),
                "last_processed_time": availability.get("last_processed_time")
            }
        )
    
    # Валидация user_id из токена
    validate_user_id_from_token(current_user_id)
    
    # Получение отчёта
    # Важно: current_user_id извлекается из токена и используется для фильтрации данных
    # Пользователь может запрашивать только свои отчёты
    try:
        report = await get_user_report(
            user_id=current_user_id,  # ID из токена - используется для фильтрации
            date_from=date_from,
            date_to=date_to,
            requested_user_id=current_user_id  # Явная проверка доступа
        )
        
        # Дополнительная проверка: убеждаемся, что возвращённые данные принадлежат пользователю
        if report["user_id"] != current_user_id:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "access_denied",
                    "message": "Доступ запрещён. Обнаружена попытка доступа к данным другого пользователя",
                    "current_user_id": current_user_id,
                    "returned_user_id": report["user_id"]
                }
            )
        
        return ReportResponse(**report)
    
    except HTTPException:
        # Пробрасываем HTTPException как есть (ошибки доступа, валидации и т.д.)
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при получении отчёта: {str(e)}"
        )


@app.get("/reports/availability")
async def check_reports_availability(
    date_from: date,
    date_to: date,
    current_user_id: int = Depends(get_current_user_id)
):
    """
    Проверить доступность данных за период
    
    **Ограничение доступа**: Проверка выполняется только для данных текущего пользователя.
    
    Args:
        date_from: Начальная дата периода
        date_to: Конечная дата периода
        current_user_id: ID текущего пользователя (из токена, автоматически)
    
    Returns:
        dict: Информация о доступности данных для текущего пользователя
    
    Raises:
        HTTPException 401: Невалидный токен или отсутствие авторизации
        HTTPException 403: Попытка проверить доступность данных другого пользователя
    """
    # Валидация дат
    if date_from > date_to:
        raise HTTPException(
            status_code=400,
            detail="date_from не может быть больше date_to"
        )
    
    # Проверка доступности данных (общая проверка для всех пользователей)
    availability = await check_data_availability(date_from, date_to)
    
    # Дополнительно проверяем доступность данных конкретно для этого пользователя
    from app.database import get_clickhouse_client
    client = get_clickhouse_client()
    
    try:
        query_user_data = """
            SELECT count() as count
            FROM bionicpro_reports.user_reports_mart
            WHERE user_id = %(user_id)s 
                AND date >= %(date_from)s 
                AND date <= %(date_to)s
        """
        
        result = client.execute(
            query_user_data,
            {
                "user_id": current_user_id,
                "date_from": date_from,
                "date_to": date_to
            }
        )
        
        user_data_count = result[0][0] if result else 0
        
        availability["user_specific"] = {
            "user_id": current_user_id,
            "has_data": user_data_count > 0,
            "records_count": user_data_count
        }
        
        return availability
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при проверке доступности данных: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
