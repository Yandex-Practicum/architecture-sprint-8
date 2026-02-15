"""
Reports API для BionicPRO
Предоставляет эндпоинт для получения отчётов о работе протезов
"""
from fastapi import FastAPI, HTTPException, Depends, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse, StreamingResponse
import clickhouse_connect
import jwt
import requests
from typing import Optional
from datetime import datetime, timedelta
import io
import csv

app = FastAPI(title="BionicPRO Reports API", version="1.0.0")

# Конфигурация
KEYCLOAK_URL = "http://keycloak:8080"
KEYCLOAK_REALM = "reports-realm"
CLICKHOUSE_HOST = "clickhouse"
CLICKHOUSE_PORT = 8123
CLICKHOUSE_USER = "default"
CLICKHOUSE_PASSWORD = ""

security = HTTPBearer()

def get_keycloak_public_key():
    """Получение публичного ключа Keycloak для проверки JWT токенов"""
    try:
        response = requests.get(
            f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/certs"
        )
        response.raise_for_status()
        jwks = response.json()
        # В реальном приложении нужно правильно обработать JWKS
        # Для упрощения используем публичный ключ из конфигурации
        return jwks
    except Exception as e:
        print(f"Ошибка получения публичного ключа Keycloak: {e}")
        return None

def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    """
    Проверка и декодирование JWT токена от Keycloak
    """
    token = credentials.credentials
    
    try:
        # Получаем публичный ключ Keycloak
        # ВНИМАНИЕ: В продакшене необходимо правильно обработать JWKS
        # и проверять подпись токена!
        try:
            # Для разработки декодируем без проверки подписи
            # В продакшене необходимо использовать публичный ключ из Keycloak
            decoded_token = jwt.decode(
                token,
                options={"verify_signature": False}  # ВНИМАНИЕ: только для разработки!
            )
        except jwt.DecodeError:
            raise HTTPException(status_code=401, detail="Invalid token format")
        
        # Проверяем, что токен не истёк
        if 'exp' in decoded_token and decoded_token['exp'] < datetime.now().timestamp():
            raise HTTPException(status_code=401, detail="Token expired")
        
        return decoded_token
    except jwt.DecodeError:
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Token verification failed: {str(e)}")

def get_user_id_from_token(token_data: dict) -> str:
    """Извлечение user_id из токена"""
    # В Keycloak user_id может быть в разных полях
    user_id = token_data.get('preferred_username') or token_data.get('sub') or token_data.get('email')
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID not found in token")
    return user_id

@app.get("/health")
async def health_check():
    """Проверка здоровья сервиса"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/reports")
async def get_report(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    format: str = "json",
    token_data: dict = Depends(verify_token)
):
    """
    Получение отчёта о работе протеза для текущего пользователя
    
    Args:
        start_date: Начальная дата в формате YYYY-MM-DD (опционально)
        end_date: Конечная дата в формате YYYY-MM-DD (опционально)
        format: Формат отчёта (json или csv)
        token_data: Данные из JWT токена (автоматически извлекаются)
    
    Returns:
        Отчёт в запрошенном формате
    """
    # Извлекаем user_id из токена
    user_id = get_user_id_from_token(token_data)
    
    # Проверяем права доступа
    # Пользователь может получить только свой отчёт
    roles = token_data.get('realm_access', {}).get('roles', [])
    if 'prothetic_user' not in roles and 'user' not in roles and 'administrator' not in roles:
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions to access reports"
        )
    
    # Подключение к ClickHouse
    try:
        client = clickhouse_connect.get_client(
            host=CLICKHOUSE_HOST,
            port=CLICKHOUSE_PORT,
            username=CLICKHOUSE_USER,
            password=CLICKHOUSE_PASSWORD
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to connect to ClickHouse: {str(e)}"
        )
    
    # Формируем SQL запрос
    query = f"""
    SELECT 
        user_id,
        email,
        first_name,
        last_name,
        prosthesis_id,
        report_date,
        total_actions,
        avg_response_time,
        max_response_time,
        min_response_time,
        grasp_count,
        release_count,
        flex_count,
        avg_battery_level,
        avg_signal_quality,
        country,
        order_date,
        processed_at
    FROM reports_mart
    WHERE user_id = '{user_id}'
    """
    
    # Добавляем фильтры по датам, если указаны
    if start_date:
        query += f" AND report_date >= '{start_date}'"
    if end_date:
        query += f" AND report_date <= '{end_date}'"
    
    query += " ORDER BY report_date DESC, prosthesis_id"
    
    try:
        # Выполняем запрос
        result = client.query(query)
        
        # Преобразуем результат в список словарей
        columns = result.column_names
        rows = []
        for row in result.result_rows:
            rows.append(dict(zip(columns, row)))
        
        # Проверяем, что пользователь запрашивает только свои данные
        # (дополнительная проверка безопасности)
        for row in rows:
            if row.get('user_id') != user_id:
                raise HTTPException(
                    status_code=403,
                    detail="Access denied: You can only access your own reports"
                )
        
        # Если данных нет, возвращаем пустой отчёт
        if not rows:
            return JSONResponse(
                content={
                    "message": "No data available for the specified period",
                    "user_id": user_id,
                    "start_date": start_date,
                    "end_date": end_date,
                    "data": []
                }
            )
        
        # Формируем ответ в зависимости от формата
        if format.lower() == "csv":
            # Генерируем CSV
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
            
            return StreamingResponse(
                io.BytesIO(output.getvalue().encode('utf-8')),
                media_type="text/csv",
                headers={
                    "Content-Disposition": f"attachment; filename=report_{user_id}_{datetime.now().strftime('%Y%m%d')}.csv"
                }
            )
        else:
            # Возвращаем JSON
            return JSONResponse(
                content={
                    "user_id": user_id,
                    "start_date": start_date,
                    "end_date": end_date,
                    "total_records": len(rows),
                    "data": rows
                }
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve report: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
