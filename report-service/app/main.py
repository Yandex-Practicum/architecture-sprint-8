from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List
import clickhouse_connect
import os
import base64
import json

app = FastAPI(title="BionicPRO Report Service", version="1.0.0")

# CORS для фронтенда
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключение к ClickHouse
clickhouse_client = clickhouse_connect.get_client(
    host=os.getenv("CLICKHOUSE_HOST", "clickhouse"),
    port=int(os.getenv("CLICKHOUSE_PORT", "8123")),
    username=os.getenv("CLICKHOUSE_USER", "default"),
    password=os.getenv("CLICKHOUSE_PASSWORD", "secret"),
    database=os.getenv("CLICKHOUSE_DB", "bionicpro")
)

# Pydantic модели
class ReportData(BaseModel):
    user_id: str
    prosthesis_id: str
    recorded_at: datetime
    movement_type: str
    battery_level: float
    crm_user_name: str
    crm_region: str

class ReportResponse(BaseModel):
    user_id: str
    prosthesis_id: str
    reports: List[ReportData]
    generated_at: datetime

def decode_jwt_payload(token: str) -> dict:
    """Декодирует JWT токен без проверки подписи"""
    try:
        # JWT состоит из 3 частей, разделённых точками
        parts = token.split('.')
        if len(parts) != 3:
            raise HTTPException(status_code=401, detail="Invalid token format")
        
        # Декодируем payload (вторая часть)
        payload_b64 = parts[1]
        # Добавляем padding если нужно
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += '=' * padding
        
        payload_bytes = base64.urlsafe_b64decode(payload_b64)
        payload = json.loads(payload_bytes)
        return payload
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")

def get_current_user(request: Request) -> dict:
    """Извлекает пользователя из JWT токена"""
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    
    token = auth_header.replace("Bearer ", "")
    
    try:
        payload = decode_jwt_payload(token)
        return payload
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Token decode error: {str(e)}")

@app.get("/health")
def health_check():
    """Проверка работоспособности сервиса"""
    return {"status": "ok", "service": "report-service"}

@app.get("/api/reports/{user_id}", response_model=ReportResponse)
def get_user_reports(user_id: str, current_user: dict = Depends(get_current_user)):
    """
    Получение отчёта для пользователя.
    RBAC: пользователь может видеть только свои данные.
    """
    # ВАЖНО: используем preferred_username вместо sub (UUID)
    token_user_id = current_user.get("preferred_username") or current_user.get("sub")
    
    if not token_user_id:
        raise HTTPException(status_code=403, detail="Cannot extract user ID from token")
    
    # RBAC проверка: пользователь может запросить только свой отчёт
    if token_user_id != user_id:
        raise HTTPException(
            status_code=403, 
            detail="Access denied: you can only view your own reports"
        )
    
    try:
        # Запрос к ClickHouse
        query = """
            SELECT user_id, prosthesis_id, recorded_at, movement_type, 
                   battery_level, crm_user_name, crm_region
            FROM prosthesis_reports_mart
            WHERE user_id = {user_id: String}
            ORDER BY recorded_at DESC
        """
        
        result = clickhouse_client.query(query, {"user_id": user_id})
        
        if not result.result_rows:
            raise HTTPException(
                status_code=404, 
                detail=f"No reports found for user {user_id}. "
                       "Data may not be processed yet by ETL pipeline."
            )
        
        # Преобразуем результат в список моделей
        reports = []
        for row in result.result_rows:
            reports.append(ReportData(
                user_id=row[0],
                prosthesis_id=row[1],
                recorded_at=row[2],
                movement_type=row[3],
                battery_level=row[4],
                crm_user_name=row[5],
                crm_region=row[6]
            ))
        
        return ReportResponse(
            user_id=user_id,
            prosthesis_id=reports[0].prosthesis_id,
            reports=reports,
            generated_at=datetime.now()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/api/reports/{user_id}/download")
def download_report(user_id: str, current_user: dict = Depends(get_current_user)):
    """
    Скачивание отчёта в формате JSON.
    """
    # ВАЖНО: используем preferred_username вместо sub (UUID)
    token_user_id = current_user.get("preferred_username") or current_user.get("sub")
    
    if not token_user_id:
        raise HTTPException(status_code=403, detail="Cannot extract user ID from token")
    
    # RBAC проверка
    if token_user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    try:
        query = """
            SELECT user_id, prosthesis_id, recorded_at, movement_type, 
                   battery_level, crm_user_name, crm_region
            FROM prosthesis_reports_mart
            WHERE user_id = {user_id: String}
            ORDER BY recorded_at DESC
        """
        
        result = clickhouse_client.query(query, {"user_id": user_id})
        
        if not result.result_rows:
            raise HTTPException(status_code=404, detail="No data available")
        
        # Формируем JSON с правильным преобразованием типов
        data = []
        for row in result.result_rows:
            data.append({
                "user_id": str(row[0]),
                "prosthesis_id": str(row[1]),
                "recorded_at": row[2].isoformat() if hasattr(row[2], 'isoformat') else str(row[2]),
                "movement_type": str(row[3]),
                "battery_level": float(row[4]),
                "crm_user_name": str(row[5]),
                "crm_region": str(row[6])
            })
        
        return JSONResponse(
            content={
                "user_id": user_id,
                "generated_at": datetime.now().isoformat(),
                "total_records": len(data),
                "reports": data
            },
            headers={
                "Content-Disposition": f"attachment; filename=report_{user_id}.json"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)