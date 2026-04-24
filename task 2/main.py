# main.py (FastAPI)
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
import clickhouse_connect
from datetime import date, datetime, timedelta
import os

app = FastAPI(title="Bionic Report Service")
security = HTTPBearer()

# Настройки
CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "localhost")
KEYCLOAK_PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----..."""  # Публичный ключ Keycloak

# Подключение к ClickHouse
ch_client = clickhouse_connect.get_client(host=CLICKHOUSE_HOST, port=8123, database="bionic")

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, KEYCLOAK_PUBLIC_KEY, algorithms=["RS256"], audience="bionic-api")
        user_id = payload.get("sub")  # или кастомный claim
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        return int(user_id)  # предполагаем, что user_id в токене — числовой
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Could not validate credentials")

@app.get("/reports")
def get_report(
    current_user: int = Depends(get_current_user),
    start_date: date = Query(..., description="Начальная дата отчёта (YYYY-MM-DD)"),
    end_date: date = Query(..., description="Конечная дата отчёта (YYYY-MM-DD)")
):
    # Проверяем, что запрошенный период не превышает последнюю обработанную дату
    max_date_query = "SELECT max(report_date) FROM bionic.user_daily_report"
    last_processed = ch_client.query(max_date_query).first_row[0]
    if last_processed is None:
        raise HTTPException(status_code=404, detail="No data available yet")
    if end_date > last_processed:
        raise HTTPException(status_code=400, detail=f"Report data only up to {last_processed}. Please choose earlier end_date.")

    # Запрос витрины только для текущего пользователя
    query = """
        SELECT report_date, total_movements, avg_response_ms, battery_drain_pct, session_count, firmware_version
        FROM bionic.user_daily_report
        WHERE user_id = %(user_id)s AND report_date BETWEEN %(start)s AND %(end)s
        ORDER BY report_date
    """
    params = {"user_id": current_user, "start": start_date, "end": end_date}
    result = ch_client.query_df(query, parameters=params)
    if result.empty:
        raise HTTPException(status_code=404, detail="No reports found for this user and period")
    
    # Формируем JSON-отчёт
    report = {
        "user_id": current_user,
        "period": {"start": start_date.isoformat(), "end": end_date.isoformat()},
        "daily_stats": result.to_dict(orient="records"),
        "summary": {
            "total_movements": int(result["total_movements"].sum()),
            "avg_response_ms": round(result["avg_response_ms"].mean(), 2),
            "total_days": len(result)
        }
    }
    return report