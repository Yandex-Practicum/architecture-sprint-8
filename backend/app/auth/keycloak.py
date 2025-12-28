"""
Аутентификация через Keycloak.

Валидирует JWT токен и извлекает информацию о пользователе.
Обеспечивает доступ только к собственным данным.
"""

import os
import logging
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Конфигурация Keycloak
KEYCLOAK_URL = os.getenv('KEYCLOAK_URL', 'http://keycloak:8080')
KEYCLOAK_REALM = os.getenv('KEYCLOAK_REALM', 'reports-realm')
KEYCLOAK_CLIENT_ID = os.getenv('KEYCLOAK_CLIENT_ID', 'reports-api')

# URL для получения публичных ключей
JWKS_URL = f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/certs"

# Security scheme
security = HTTPBearer()


class User(BaseModel):
    """Модель авторизованного пользователя."""
    id: str  # sub из токена
    username: str
    email: Optional[str] = None
    roles: list[str] = []


# Кэш для JWKS
_jwks_cache: Optional[dict] = None


async def get_jwks() -> dict:
    """Получение JWKS (публичных ключей) от Keycloak."""
    global _jwks_cache
    
    if _jwks_cache is not None:
        return _jwks_cache
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(JWKS_URL)
            response.raise_for_status()
            _jwks_cache = response.json()
            return _jwks_cache
    except Exception as e:
        logger.error(f"Failed to fetch JWKS: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service unavailable"
        )


def decode_token(token: str, jwks: dict) -> dict:
    """Декодирование и валидация JWT токена."""
    try:
        # Получаем заголовок токена для определения kid
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get('kid')
        
        # Находим соответствующий ключ
        rsa_key = None
        for key in jwks.get('keys', []):
            if key.get('kid') == kid:
                rsa_key = key
                break
        
        if rsa_key is None:
            raise JWTError("Unable to find appropriate key")
        
        # Декодируем токен
        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=['RS256'],
            audience='account',  # Keycloak default audience
            options={
                'verify_aud': False,  # Keycloak может не включать audience
                'verify_exp': True,
                'verify_iat': True,
            }
        )
        
        return payload
        
    except JWTError as e:
        logger.warning(f"JWT decode error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> User:
    """
    Получение текущего пользователя из JWT токена.
    
    Извлекает user_id (sub) из токена Keycloak.
    Этот user_id используется для ограничения доступа к отчётам.
    """
    token = credentials.credentials
    
    try:
        # Получаем JWKS
        jwks = await get_jwks()
        
        # Декодируем токен
        payload = decode_token(token, jwks)
        
        # Извлекаем данные пользователя
        user_id = payload.get('sub')
        username = payload.get('preferred_username', payload.get('sub'))
        email = payload.get('email')
        
        # Получаем роли из realm_access
        realm_access = payload.get('realm_access', {})
        roles = realm_access.get('roles', [])
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing user ID",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        logger.info(f"Authenticated user: {username} (id: {user_id})")
        
        return User(
            id=user_id,
            username=username,
            email=email,
            roles=roles
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

