"""
Reports API Service для BionicPRO
Предоставляет эндпоинт для получения отчетов о работе протезов
с авторизацией через Keycloak
"""
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import os
import logging

from clickhouse_driver import Client as ClickHouseClient
from jose import jwt, JWTError
import requests

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="BionicPRO Reports API",
    description="API для получения отчетов о работе протезов",
    version="1.0.0"
)

# CORS настройки
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:3000", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()

# Конфигурация
CLICKHOUSE_HOST = os.getenv('CLICKHOUSE_HOST', 'clickhouse')
CLICKHOUSE_PORT = int(os.getenv('CLICKHOUSE_PORT', 9000))
CLICKHOUSE_USER = os.getenv('CLICKHOUSE_USER', 'analytics_user')
CLICKHOUSE_PASSWORD = os.getenv('CLICKHOUSE_PASSWORD', 'analytics_password')
CLICKHOUSE_DB = os.getenv('CLICKHOUSE_DB', 'analytics_db')

KEYCLOAK_URL = os.getenv('KEYCLOAK_URL', 'http://keycloak:8080')
KEYCLOAK_REALM = os.getenv('KEYCLOAK_REALM', 'reports-realm')

# Модели данных
class ProstheticReport(BaseModel):
    """Модель отчета о работе протеза"""
    buyer_id: int
    full_name: str
    email: str
    prosthetic_type: str
    serial_number: str
    total_usage_hours: float
    total_movements: int
    total_errors: int
    avg_battery_level: float
    last_telemetry_date: datetime
    report_period_start: datetime
    report_period_end: datetime


class UserInfo(BaseModel):
    """Информация о пользователе из токена"""
    sub: str
    email: Optional[str] = None
    preferred_username: Optional[str] = None
    buyer_id: Optional[int] = None


def get_clickhouse_client() -> ClickHouseClient:
    """Создание клиента ClickHouse"""
    try:
        return ClickHouseClient(
            host=CLICKHOUSE_HOST,
            port=CLICKHOUSE_PORT,
            user=CLICKHOUSE_USER,
            password=CLICKHOUSE_PASSWORD,
            database=CLICKHOUSE_DB
        )
    except Exception as e:
        logger.error(f"Ошибка подключения к ClickHouse: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Сервис аналитики временно недоступен"
        )


def get_keycloak_public_key() -> str:
    """Получение публичного ключа Keycloak для проверки JWT"""
    try:
        url = f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        realm_info = response.json()
        public_key = realm_info.get('public_key')
        
        if not public_key:
            raise ValueError("Public key not found in realm info")
        
        # Форматируем публичный ключ
        return f"-----BEGIN PUBLIC KEY-----\n{public_key}\n-----END PUBLIC KEY-----"
    except Exception as e:
        logger.error(f"Ошибка получения публичного ключа Keycloak: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Сервис аутентификации недоступен"
        )


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> UserInfo:
    """Проверка и декодирование JWT токена"""
    token = credentials.credentials
    
    try:
        # Получаем публичный ключ Keycloak
        public_key = get_keycloak_public_key()
        
        # Декодируем и проверяем токен
        payload = jwt.decode(
            token,
            public_key,
            algorithms=['RS256'],
            audience='account',
            options={"verify_aud": False}  # Отключаем проверку audience для гибкости
        )
        
        # Извлекаем buyer_id из кастомных claims или атрибутов
        buyer_id = payload.get('buyer_id')
        if not buyer_id:
            # Попробуем получить из email (предполагая что email содержит buyer_id)
            email = payload.get('email', '')
            # Для демонстрации используем простую логику
            # В реальной системе buyer_id должен быть в атрибутах пользователя Keycloak
            preferred_username = payload.get('preferred_username', '')
            
            # Маппинг пользователей на buyer_id (для демонстрации)
            user_buyer_mapping = {
                'prothetic1': 648821,
                'prothetic2': 6488214,
                'admin1': 648801
            }
            buyer_id = user_buyer_mapping.get(preferred_username)
        
        return UserInfo(
            sub=payload.get('sub'),
            email=payload.get('email'),
            preferred_username=payload.get('preferred_username'),
            buyer_id=buyer_id
        )
    except JWTError as e:
        logger.error(f"Ошибка проверки токена: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Невалидный токен аутентификации",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        logger.error(f"Неожиданная ошибка при проверке токена: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ошибка аутентификации",
            headers={"WWW-Authenticate": "Bearer"},
        )


@app.get("/")
async def root():
    """Корневой эндпоинт"""
    return {
        "service": "BionicPRO Reports API",
        "version": "1.0.0",
        "status": "running"
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
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


@app.get("/reports", response_model=List[ProstheticReport])
async def get_user_reports(
    user: UserInfo = Depends(verify_token),
    period_days: int = 30
) -> List[ProstheticReport]:
    """
    Получение отчетов о работе протезов пользователя
    
    Пользователь может получить только свои отчеты.
    Доступ к отчетам других пользователей запрещен.
    
    Args:
        period_days: Период отчета в днях (по умолчанию 30)
    
    Returns:
        Список отчетов по протезам пользователя
    """
    if not user.buyer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Пользователь не связан с профилем покупателя"
        )
    
    logger.info(f"Запрос отчетов для пользователя {user.preferred_username} (buyer_id: {user.buyer_id})")
    
    try:
        client = get_clickhouse_client()
        
        # SQL запрос с фильтрацией по buyer_id пользователя
        # ВАЖНО: используем параметризованный запрос для безопасности
        query = """
        SELECT 
            buyer_id,
            full_name,
            email,
            prosthetic_type,
            serial_number,
            total_usage_hours,
            total_movements,
            total_errors,
            avg_battery_level,
            last_telemetry_date,
            report_period_start,
            report_period_end
        FROM user_reports_mart
        WHERE buyer_id = %(buyer_id)s
          AND report_period_end >= today() - INTERVAL %(period_days)s DAY
        ORDER BY report_period_end DESC
        """
        
        result = client.execute(
            query,
            {'buyer_id': user.buyer_id, 'period_days': period_days}
        )
        
        if not result:
            logger.info(f"Отчеты для пользователя {user.buyer_id} не найдены")
            return []
        
        # Преобразуем результаты в модели
        reports = [
            ProstheticReport(
                buyer_id=row[0],
                full_name=row[1],
                email=row[2],
                prosthetic_type=row[3],
                serial_number=row[4],
                total_usage_hours=row[5],
                total_movements=row[6],
                total_errors=row[7],
                avg_battery_level=row[8],
                last_telemetry_date=row[9],
                report_period_start=row[10],
                report_period_end=row[11]
            )
            for row in result
        ]
        
        logger.info(f"Найдено {len(reports)} отчетов для пользователя {user.buyer_id}")
        return reports
        
    except Exception as e:
        logger.error(f"Ошибка при получении отчетов: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при получении отчетов"
        )


@app.get("/reports/summary")
async def get_reports_summary(user: UserInfo = Depends(verify_token)):
    """
    Получение сводной информации по отчетам пользователя
    """
    if not user.buyer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Пользователь не связан с профилем покупателя"
        )
    
    try:
        client = get_clickhouse_client()
        
        query = """
        SELECT 
            count() as total_reports,
            sum(total_usage_hours) as total_hours,
            sum(total_movements) as total_movements,
            sum(total_errors) as total_errors
        FROM user_reports_mart
        WHERE buyer_id = %(buyer_id)s
        """
        
        result = client.execute(query, {'buyer_id': user.buyer_id})
        
        if not result:
            return {
                "total_reports": 0,
                "total_usage_hours": 0,
                "total_movements": 0,
                "total_errors": 0
            }
        
        row = result[0]
        return {
            "buyer_id": user.buyer_id,
            "total_reports": row[0],
            "total_usage_hours": row[1],
            "total_movements": row[2],
            "total_errors": row[3]
        }
        
    except Exception as e:
        logger.error(f"Ошибка при получении сводки отчетов: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при получении сводки отчетов"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
