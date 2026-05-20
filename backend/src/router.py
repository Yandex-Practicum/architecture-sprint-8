from fastapi import APIRouter, Depends, HTTPException, status

from src.auth import get_current_user
from src.db import get_client, rows_to_dicts

router = APIRouter()


@router.get("/reports")
async def get_report(user_id: str = Depends(get_current_user)) -> dict:
    try:
        client = get_client()
        rows = client.execute(
            """
            SELECT
                user_id, device_id, client_name, client_email,
                prosthesis_model, purchase_date,
                total_sessions, total_movements, last_activity,
                avg_signal_quality, report_date
            FROM user_report_mart
            WHERE user_id = %(user_id)s
            ORDER BY report_date DESC
            LIMIT 30
            """,
            {"user_id": user_id},
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Database error: {exc}")

    if not rows:
        return {
            "user_id": user_id,
            "message": "No report data available yet. The ETL pipeline may not have run for this user.",
            "data": [],
        }

    return {"user_id": user_id, "data": rows_to_dicts(rows)}


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}
