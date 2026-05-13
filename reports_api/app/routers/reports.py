from fastapi import APIRouter, Depends, HTTPException, Query
from datetime import datetime, timedelta
from app.dependencies import get_current_user
from app.db.clickhouse_client import get_clickhouse_client

router = APIRouter()


@router.get("/reports/{user_id}")
async def get_report(
        user_id: str,
        from_date: str = Query(..., description="YYYY-MM-DD"),
        to_date: str = Query(..., description="YYYY-MM-DD"),
        current_user: dict = Depends(get_current_user)
):
    # RBAC: пользователь может запрашивать только свои отчёты
    if "administrator" not in current_user.get("roles", []):
        if current_user.get("username") != user_id:
            raise HTTPException(status_code=403, detail="Access denied: you can only request your own reports")

    # Валидация формата дат
    try:
        from_dt = datetime.strptime(from_date, "%Y-%m-%d")
        to_dt = datetime.strptime(to_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    yesterday = (datetime.now() - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    if from_dt > yesterday:
        # raise HTTPException(status_code=400, detail="from_date must be before or equal to to_date")
        logger.warning(f"User {user_id} requested future date: {to_date}")

    # Нельзя запрашивать будущие даты (Airflow ещё не обработал)
    yesterday = (datetime.now() - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    if to_dt > yesterday:
        raise HTTPException(
            status_code=400,
            detail=f"Reports are available only up to {yesterday.strftime('%Y-%m-%d')}. "
                   f"Data for today is not yet processed by Airflow."
        )

    # Ограничение периода (максимум 90 дней)
    if (to_dt - from_dt).days > 90:
        raise HTTPException(status_code=400, detail="Maximum report period is 90 days")

    # Запрос в ClickHouse
    ch = get_clickhouse_client()

    query = """
            SELECT
                date, total_movements, avg_signal_quality, min_battery_level, calibration_count
            FROM daily_user_stats
            WHERE user_id = %(user_id)s
              AND date BETWEEN %(from_date)s \
              AND %(to_date)s
            ORDER BY date \
            """

    try:
        result = ch.execute(
            query,
            {'user_id': user_id, 'from_date': from_date, 'to_date': to_date}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    if not result:
        return {
            "user_id": user_id,
            "period": {"from": from_date, "to": to_date},
            "stats": [],
            "message": "No data available for the selected period. Reports are generated daily and may take up to 24 hours to appear after prosthetic use."
        }

    return {
        "user_id": user_id,
        "period": {"from": from_date, "to": to_date},
        "stats": [
            {
                "date": str(row[0]),
                "total_movements": row[1],
                "avg_signal_quality": row[2],
                "min_battery_level": row[3],
                "calibration_count": row[4]
            }
            for row in result
        ]
    }