"""
Модуль для авторизации через Keycloak
"""
import os
import httpx
from fastapi import HTTPException, Depends, Header
from typing import Optional

# Параметры Keycloak
KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://keycloak:8080")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "reports-realm")


async def verify_token(token: str) -> dict:
    """
    Проверить токен через Keycloak
    
    Args:
        token: JWT токен
    
    Returns:
        dict: Информация о пользователе из токена
    
    Raises:
        HTTPException: Если токен невалиден
    """
    try:
        # print("Token is ", token)

        # Проверка токена через Keycloak
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/userinfo",
                headers={"Authorization": f"Bearer {token}"},
                timeout=5.0
            )
            if response.status_code != 200:
                raise HTTPException(
                    status_code=401,
                    detail="Невалидный токен доступа"
                )
            return response.json()
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Ошибка подключения к Keycloak: {str(e)}"
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=401,
            detail=f"Ошибка проверки токена: {str(e)}"
        ) from e


async def get_current_user_id(
    authorization: Optional[str] = Header(None)
) -> int:
    """
    Получить ID текущего пользователя из токена
    
    Args:
        authorization: Bearer токен из заголовка Authorization
    
    Returns:
        int: ID пользователя
    
    Raises:
        HTTPException: Если токен отсутствует или невалиден
    """
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Токен доступа не предоставлен"
        )
    
    # Извлечение токена из заголовка "Bearer <token>"
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise HTTPException(
                status_code=401,
                detail="Неверный формат токена. Используйте: Bearer <token>"
            )
    except ValueError as e:
        raise HTTPException(
            status_code=401,
            detail="Неверный формат заголовка Authorization"
        ) from e
    
    # Проверка токена через Keycloak userinfo endpoint
    user_info = await verify_token(token)
    # print("User info:", user_info)

    # Извлечение crm_user_id из user_info
    # Keycloak возвращает 'sub' как ID пользователя, но может быть в формате UUID
    # Для упрощения, используем preferred_username или sub
    # В реальном приложении crm_user_id должен быть в токене или БД
    
    # Пытаемся получить crm_user_id из preferred_username (если это число)
    # или из кастомного claim 'crm_user_id'
    user_id_str = (
        user_info.get("crm_user_id") or  # Кастомный claim
        user_info.get("preferred_username") or  # Username
        user_info.get("sub", "")  # Subject (обычно UUID)
    )
    
    # Пытаемся преобразовать в int
    try:
        # Если это число в строке
        if user_id_str.isdigit():
            return int(user_id_str)
        # Если это UUID или другой формат, используем хеш для получения числового ID
        # В production нужно использовать маппинг user_id в БД
        import hashlib
        # Используем первые 8 символов хеша как числовой ID (для демонстрации)
        hash_obj = hashlib.md5(user_id_str.encode())
        hash_hex = hash_obj.hexdigest()
        # Преобразуем первые 8 символов в int (по модулю для ограничения размера)
        user_id = int(hash_hex[:8], 16) % 1000000  # Ограничиваем до 6 цифр
        return user_id
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(
            status_code=400,
            detail="Не удалось определить ID пользователя из токена. Убедитесь, что токен содержит user_id или preferred_username"
        ) from e
