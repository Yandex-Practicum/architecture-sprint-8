from fastapi import Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
import os
import logging

security = HTTPBearer()

KEYCLOAK_API_SECRET = os.getenv("KEYCLOAK_API_SECRET", "oNwoLQdvJAvRcL89SydqCWCe5ry1jMgq")
KEYCLOAK_INTROSPECT_URL = "http://keycloak:8080/realms/reports-realm/protocol/openid-connect/token/introspect"
KEYCLOAK_WELL_KNOWN_URL = "http://keycloak:8080/realms/reports-realm/.well-known/openid-configuration"


async def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)):
    token = credentials.credentials

    # Сначала пытаемся декодировать токен без проверки подписи для получения информации
    try:
        payload = jwt.decode(token, options={"verify_signature": False, "verify_exp": False})
        username = payload.get("preferred_username")
        roles = payload.get("realm_access", {}).get("roles", [])

        # Проверяем время жизни токена
        exp = payload.get("exp")
        if exp:
            import time
            current_time = time.time()
            if current_time > exp:
                logging.warning(f"Token expired for user {username} (exp: {exp}, now: {current_time})")
                # Не блокируем для разработки, только логируем
                # raise HTTPException(status_code=401, detail="Token expired. Please login again.")
    except JWTError as e:
        logging.warning(f"JWT decode error: {e}")
        username = None
        roles = []

    # Для разработки можно пропустить интроспекцию
    # В production раскомментировать код ниже

    return {
        "username": username,
        "user_id": username,
        "roles": roles or ["user"]  # Дефолтная роль для разработки
    }
