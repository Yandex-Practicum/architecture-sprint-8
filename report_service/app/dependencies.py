# app/dependencies.py
from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from keycloak import KeycloakOpenID
import os
import logging

logger = logging.getLogger(__name__)

# Настройка безопасности
security = HTTPBearer()

# Загружаем настройки из окружения
KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://localhost:8080")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "reports-realm")
KEYCLOAK_CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "reports-api")

# Инициализация Keycloak клиента
keycloak_openid = KeycloakOpenID(
    server_url=KEYCLOAK_URL,
    client_id=KEYCLOAK_CLIENT_ID,
    realm_name=KEYCLOAK_REALM,
    verify=True
)


async def get_current_user(
        credentials: HTTPAuthorizationCredentials = Security(security)
) -> dict:
    """Проверка JWT токена и получение информации о пользователе"""
    token = credentials.credentials

    try:
        # Для отладки
        logger.info(f"Validating token: {token[:20]}...")

        # Валидация токена
        user_info = keycloak_openid.introspect(token)

        if not user_info.get('active'):
            raise HTTPException(
                status_code=401,
                detail="Token is not active"
            )

        # Возвращаем информацию о пользователе
        return {
            'sub': user_info.get('sub'),
            'username': user_info.get('preferred_username'),
            'email': user_info.get('email'),
            'roles': user_info.get('realm_access', {}).get('roles', [])
        }

    except Exception as e:
        logger.error(f"Token validation error: {e}")
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication credentials"
        )


async def verify_user_access(
        target_user_id: str,
        current_user: dict = Depends(get_current_user)
) -> bool:
    """Проверка, что пользователь запрашивает только свои данные"""
    # Извлекаем user_id из токена (sub или username)
    current_user_id = current_user.get('sub') or current_user.get('username')

    logger.info(f"Access check: user {current_user_id} trying to access {target_user_id}")

    if current_user_id != target_user_id:
        # Проверяем, может быть это администратор?
        if 'administrator' not in current_user.get('roles', []):
            raise HTTPException(
                status_code=403,
                detail="Access denied: You can only access your own reports"
            )

    return True