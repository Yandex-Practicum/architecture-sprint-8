"""
BionicPRO Reports API
=====================
FastAPI сервис для предоставления отчетов по телеметрии бионических протезов

Функционал:
- Аутентификация через Keycloak (JWT токены)
- Авторизация: доступ только к своим данным
- Получение отчетов из ClickHouse OLAP
- CORS для фронтенд приложения

Endpoints:
- GET /healthz - проверка здоровья сервиса
- GET /reports - получение отчетов по телеметрии
"""

import os
import time
import requests
from typing import Optional, Dict, List, Any

from fastapi import FastAPI, HTTPException, Query, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from clickhouse_driver import Client

import jwt
from jwt import PyJWKClient, InvalidTokenError

# ============================================================================
# КОНФИГУРАЦИЯ ОКРУЖЕНИЯ
# ============================================================================

# Параметры подключения к ClickHouse (OLAP хранилище)
CH_HOST = os.getenv("CH_HOST", "clickhouse")
CH_PORT = int(os.getenv("CH_PORT", "9000"))  # Native TCP протокол
CH_DB = os.getenv("CH_DB", "default")
CH_USER = os.getenv("CH_USER", "clickhouse_user")
CH_PASSWORD = os.getenv("CH_PASSWORD", "clickhouse_pass")
MART_TABLE = os.getenv("MART_TABLE", "default.vw_user_telemetry_daily")

# Параметры Keycloak / OIDC для проверки JWT токенов
KEYCLOAK_ISSUER = os.getenv("KEYCLOAK_ISSUER", "http://keycloak:8080/realms/reports-realm")
JWKS_URL = os.getenv("JWKS_URL")  # URL для получения публичных ключей
OIDC_AUDIENCE = os.getenv("OIDC_AUDIENCE", "reports-backend")

# CORS настройки
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")

# ============================================================================
# ИНИЦИАЛИЗАЦИЯ ПРИЛОЖЕНИЯ
# ============================================================================

app = FastAPI(
    title="BionicPRO Reports API",
    version="1.0.0",
    description="API для получения отчетов по телеметрии бионических протезов"
)

# Настройка CORS для доступа из браузера
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],  # Разрешенные origins
    allow_credentials=True,  # Разрешить отправку cookies и Authorization header
    allow_methods=["GET", "POST", "OPTIONS"],  # Разрешенные HTTP методы
    allow_headers=["Authorization", "Content-Type", "Accept"],  # Разрешенные заголовки
    expose_headers=["Content-Disposition"]  # Заголовки доступные клиенту
)

# ============================================================================
# КЭШИРОВАНИЕ JWKS (JSON Web Key Set)
# ============================================================================

# Глобальные переменные для кэширования JWKS клиента
_jwks_client: Optional[PyJWKClient] = None
_last_discovery: float = 0.0
_DISCOVERY_TTL = 3600  # TTL кэша: 1 час


def _get_jwks_client() -> PyJWKClient:
    """
    Получить JWKS клиент для проверки подписи JWT токенов
    
    Кэширует клиент на 1 час для оптимизации производительности.
    Если JWKS_URL не задан, выполняет OIDC Discovery для получения URL.
    
    Returns:
        PyJWKClient: Клиент для получения публичных ключей Keycloak
        
    Raises:
        HTTPException: Если не удалось получить JWKS URL
    """
    global _jwks_client, _last_discovery
    
    # Проверка кэша
    if _jwks_client and (time.time() - _last_discovery) < _DISCOVERY_TTL:
        return _jwks_client
    
    jwks_url = JWKS_URL
    
    # Если URL не задан явно, выполнить OIDC Discovery
    if not jwks_url:
        try:
            discovery_url = f"{KEYCLOAK_ISSUER}/.well-known/openid-configuration"
            r = requests.get(discovery_url, timeout=5)
            r.raise_for_status()
            jwks_url = r.json()["jwks_uri"]
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"OIDC discovery failed: {e}"
            )
    
    # Создание и кэширование клиента
    _jwks_client = PyJWKClient(jwks_url)
    _last_discovery = time.time()
    
    return _jwks_client


# ============================================================================
# МОДЕЛИ ДАННЫХ
# ============================================================================

class AuthenticatedUser:
    """
    Модель аутентифицированного пользователя
    
    Attributes:
        sub: Subject (уникальный ID пользователя из Keycloak)
        preferred_username: Предпочитаемое имя пользователя
        email: Email адрес пользователя
    """
    def __init__(
        self,
        sub: str,
        preferred_username: Optional[str] = None,
        email: Optional[str] = None
    ):
        self.sub = sub
        self.preferred_username = preferred_username
        self.email = email


def get_current_user(
    authorization: str = Header(..., convert_underscores=False)
) -> AuthenticatedUser:
    """
    Dependency для получения текущего аутентифицированного пользователя
    
    Проверяет JWT токен из заголовка Authorization:
    - Валидирует подпись через JWKS
    - Проверяет срок действия (exp)
    - Проверяет издателя (iss)
    - Извлекает информацию о пользователе
    
    Args:
        authorization: Заголовок Authorization (Bearer <token>)
        
    Returns:
        AuthenticatedUser: Объект с данными пользователя
        
    Raises:
        HTTPException 401: Если токен невалиден или истек
    """
    # Проверка формата заголовка
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing Authorization header"
        )
    
    # Извлечение токена
    token = authorization.split(" ", 1)[1]

    try:
        # Получение JWKS клиента
        jwks_client = _get_jwks_client()
        
        # Извлечение заголовка токена (без проверки подписи)
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")  # Key ID
        alg = unverified_header.get("alg", "RS256")  # Алгоритм подписи
        
        # Получение публичного ключа из JWKS по kid
        if kid:
            signing_key = jwks_client.get_signing_key(kid).key
        else:
            signing_key = jwks_client.get_signing_key_from_jwt(token).key
        
        # Декодирование и валидация токена
        payload = jwt.decode(
            token,
            signing_key,
            algorithms=[alg],
            issuer=KEYCLOAK_ISSUER,
            options={
                "verify_signature": True,  # Проверить подпись
                "verify_exp": True,  # Проверить срок действия
                "verify_aud": False,  # Не проверять audience (токен от frontend клиента)
                "verify_iss": True  # Проверить издателя
            },
        )
        
        # Извлечение данных пользователя из payload
        sub = payload.get("sub")
        preferred_username = payload.get("preferred_username")
        email = payload.get("email")
        
        # Проверка наличия идентификатора
        if not sub and not preferred_username:
            raise HTTPException(
                status_code=401,
                detail="Unauthorized: missing subject"
            )
        
        # Возврат объекта пользователя
        return AuthenticatedUser(
            sub=sub or preferred_username,
            preferred_username=preferred_username,
            email=email
        )
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Unauthorized: {e}")
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Unauthorized: {e}")


def get_clickhouse_client() -> Client:
    """
    Создать клиент для подключения к ClickHouse
    
    Использует Native TCP протокол (порт 9000) для максимальной производительности.
    
    Returns:
        Client: Клиент ClickHouse для выполнения запросов
    """
    return Client(
        host=CH_HOST,
        port=CH_PORT,
        database=CH_DB,
        user=CH_USER,
        password=CH_PASSWORD,
        settings={"use_numpy": False},  # Отключить numpy для совместимости
    )


# ============================================================================
# ENDPOINTS
# ============================================================================

@app.get("/healthz")
def healthcheck() -> Dict[str, Any]:
    """
    Проверка здоровья сервиса
    
    Проверяет:
    - Доступность API
    - Подключение к ClickHouse
    
    Returns:
        dict: Статус сервиса и результат проверки БД
        
    Raises:
        HTTPException 500: Если ClickHouse недоступен
    """
    try:
        client = get_clickhouse_client()
        pong = client.execute("SELECT 1")
        client.disconnect()
        return {
            "status": "ok",
            "database": "connected",
            "db_response": pong[0][0]
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Database connection failed: {str(e)}"
        )


@app.get("/reports")
def get_reports(
    user_external_id: str = Query(
        ...,
        description="Внешний ID пользователя (sub из Keycloak JWT)"
    ),
    from_date: Optional[str] = Query(
        None,
        description="Начальная дата фильтра (формат: YYYY-MM-DD)",
        regex=r'^\d{4}-\d{2}-\d{2}$'
    ),
    to_date: Optional[str] = Query(
        None,
        description="Конечная дата фильтра (формат: YYYY-MM-DD)",
        regex=r'^\d{4}-\d{2}-\d{2}$'
    ),
    prosthesis_id: Optional[int] = Query(
        None,
        description="Фильтр по ID протеза"
    ),
    limit: int = Query(
        365,
        ge=1,
        le=5000,
        description="Максимальное количество записей"
    ),
    current_user: AuthenticatedUser = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Получить отчет по телеметрии протезов пользователя
    
    Возвращает агрегированные данные по дням из ClickHouse витрины.
    Пользователь может получить только свои данные (проверка по user_external_id).

    Args:
        user_external_id: Внешний ID пользователя (должен совпадать с sub в токене)
        from_date: Начальная дата (опционально)
        to_date: Конечная дата (опционально)
        prosthesis_id: ID протеза для фильтрации (опционально)
        limit: Максимальное количество записей (по умолчанию 365)
        current_user: Аутентифицированный пользователь (из JWT)
        
    Returns:
        dict: Объект с полями:
            - user_external_id: ID пользователя
            - items: Список записей телеметрии
            
    Raises:
        HTTPException 401: Если пользователь не аутентифицирован
        HTTPException 403: Если пользователь пытается получить чужие данные
        HTTPException 500: Если произошла ошибка при запросе к ClickHouse
    """
    # ========================================================================
    # ПРОВЕРКА АВТОРИЗАЦИИ
    # ========================================================================
    # Пользователь может запрашивать только свои данные
    subject_ids = [
        v for v in [current_user.sub, current_user.preferred_username]
        if v
    ]
    
    if user_external_id not in subject_ids:
        raise HTTPException(
            status_code=403,
            detail="Forbidden: access only to own reports"
        )

    # ========================================================================
    # ПОСТРОЕНИЕ SQL ЗАПРОСА
    # ========================================================================
    
    # Базовое условие: фильтр по пользователю
    where_clauses = ["user_external_id = %(user_external_id)s"]
    params: Dict[str, Any] = {
        "user_external_id": user_external_id,
        "limit": limit
    }
    
    # Добавление опциональных фильтров
    if from_date:
        where_clauses.append("event_date >= toDate(%(from_date)s)")
        params["from_date"] = from_date
        
    if to_date:
        where_clauses.append("event_date <= toDate(%(to_date)s)")
        params["to_date"] = to_date
        
    if prosthesis_id is not None:
        where_clauses.append("prosthesis_id = %(prosthesis_id)s")
        params["prosthesis_id"] = prosthesis_id

    where_sql = " AND ".join(where_clauses)

    # SQL запрос к витрине данных
    sql = f"""
        SELECT
            toDate(event_date) as event_date,
            customer_id,
            user_external_id,
            full_name,
            prosthesis_id,
            events_cnt,
            avg_response_ms,
            err_cnt,
            battery_avg,
            min_response_ms,
            max_response_ms,
            p95_response_ms,
            min_battery
        FROM {MART_TABLE}
        WHERE {where_sql}
        ORDER BY event_date DESC, prosthesis_id
        LIMIT %(limit)s
    """

    # ========================================================================
    # ВЫПОЛНЕНИЕ ЗАПРОСА И ФОРМИРОВАНИЕ ОТВЕТА
    # ========================================================================
    
    try:
        # Подключение к ClickHouse
        client = get_clickhouse_client()
        
        # Выполнение запроса
        rows = client.execute(sql, params)
        
        # Закрытие соединения
        client.disconnect()
        
        # Формирование JSON ответа
        items: List[Dict[str, Any]] = []
        for r in rows:
            items.append({
                "event_date": str(r[0]),  # Дата события
                "customer_id": r[1],  # ID клиента
                "user_external_id": r[2],  # Внешний ID пользователя
                "full_name": r[3],  # Полное имя
                "prosthesis_id": r[4],  # ID протеза
                "events_cnt": r[5],  # Количество событий
                "avg_response_ms": float(r[6]) if r[6] is not None else 0.0,  # Среднее время отклика
                "err_cnt": r[7],  # Количество ошибок
                "battery_avg": float(r[8]) if r[8] is not None else 0.0,  # Средний заряд батареи
                # Дополнительные метрики производительности
                "min_response_ms": float(r[9]) if r[9] is not None else 0.0,  # Минимальное время отклика
                "max_response_ms": float(r[10]) if r[10] is not None else 0.0,  # Максимальное время отклика
                "p95_response_ms": float(r[11]) if r[11] is not None else 0.0,  # 95-й перцентиль
                "min_battery": float(r[12]) if r[12] is not None else 0.0,  # Минимальный заряд
            })
        
        return {
            "user_external_id": user_external_id,
            "items": items
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Database query failed: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
