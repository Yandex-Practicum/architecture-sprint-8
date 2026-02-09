from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
import clickhouse_connect
import os
from typing import Optional, Dict
from datetime import datetime
import httpx

app = FastAPI(
    title="Reports API",
    description="API для получения отчетов из ClickHouse",
    version="1.0.0"
)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # В продакшене замените на конкретный адрес фронтенда
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Конфигурация
KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://localhost:8080")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "reports-realm")
CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "clickhouse")
CLICKHOUSE_PORT = int(os.getenv("CLICKHOUSE_PORT", 8123))
CLICKHOUSE_USER = os.getenv("CLICKHOUSE_USER", "default")
CLICKHOUSE_PASSWORD = os.getenv("CLICKHOUSE_PASSWORD", "")
CLICKHOUSE_DATABASE = os.getenv("CLICKHOUSE_DATABASE", "reports")

# Подключение к ClickHouse
def get_db():
    try:
        client = clickhouse_connect.get_client(
            host=CLICKHOUSE_HOST,
            port=CLICKHOUSE_PORT,
            username=CLICKHOUSE_USER,
            password=CLICKHOUSE_PASSWORD,
            database=CLICKHOUSE_DATABASE
        )
        return client
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Database connection failed: {str(e)}"
        )

# Упрощенная проверка токена (для разработки)
async def verify_token(authorization: Optional[str] = Header(None)) -> str:
    """Реальная проверка токена через Keycloak"""
    token = authorization.replace("Bearer ", "")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/userinfo",
                headers={"Authorization": f"Bearer {token}"}
            )

            if response.status_code == 200:
                user_info = response.json()
                return user_info.get("preferred_username") or user_info.get("email")
            else:
                raise HTTPException(status_code=401, detail="Invalid token")
    except Exception:
        raise HTTPException(status_code=401, detail="Token validation failed")

@app.get("/")
async def root():
    return {
        "service": "Reports API",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "reports": "/reports"
        }
    }

@app.get("/health")
async def health_check():
    try:
        db = get_db()
        result = db.query("SELECT 1 as status")
        db.close()
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "database": "connected"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "database": "disconnected",
            "error": str(e)
        }

@app.get("/reports")
async def get_user_report(username: str = Depends(verify_token)):
    """Получить отчет для авторизованного пользователя"""

    db = get_db()

    try:
        # Запрос последнего отчета для пользователя
        query = """
        SELECT 
            client_id,
            client_name,
            client_name,
            device_sn,
            min_response_speed,
            max_response_speed,
            avg_response_speed,
            min_battery_level,
            max_battery_level,
            total_signals,
            total_errors,
            report_date,
            manufacturing_date,
            days_in_use,
            created_at,
            updated_at
        FROM device_daily_report
        WHERE client_id = %(username)s
        ORDER BY report_date DESC
        LIMIT 1
        """
        print(f"Client_id: {username}")
        result = db.query(query, parameters={"username": username})


        if not result.result_rows:
            raise HTTPException(
                status_code=404,
                detail=f"No report found for user '{username}'"
            )

        # Форматируем результат
        columns = result.column_names
        row = result.result_rows[0]

        report = {}
        for i, column in enumerate(columns):
            value = row[i]
            # Конвертируем даты в строки
            if hasattr(value, 'isoformat'):
                report[column] = value.isoformat()
            elif isinstance(value, (int, float)):
                report[column] = value
            else:
                report[column] = str(value)

        return {
            "user": username,
            "report": report,
            "retrieved_at": datetime.utcnow().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching report: {str(e)}"
        )
    finally:
        db.close()

# Тестовый эндпоинт для проверки аутентификации
@app.get("/test-auth")
async def test_auth(username: str = Depends(verify_token)):
    return {
        "authenticated": True,
        "username": username,
        "message": "Token is valid"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000
    )