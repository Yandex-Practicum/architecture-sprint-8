"""
Модуль для проверки безопасности и контроля доступа
"""
from fastapi import HTTPException
from typing import Optional


def verify_user_access(
    current_user_id: int,
    requested_user_id: Optional[int] = None,
    resource_user_id: Optional[int] = None
) -> None:
    """
    Проверить, что пользователь имеет доступ к запрашиваемому ресурсу
    
    Args:
        current_user_id: ID текущего пользователя (из токена)
        requested_user_id: Запрашиваемый user_id (если указан в запросе)
        resource_user_id: user_id ресурса (если известен из БД)
    
    Raises:
        HTTPException 403: Если доступ запрещён
    """
    # Проверка 1: Если указан requested_user_id, он должен совпадать с current_user_id
    if requested_user_id is not None and requested_user_id != current_user_id:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "access_denied",
                "message": "Доступ запрещён. Вы можете запрашивать только свои отчёты",
                "current_user_id": current_user_id,
                "requested_user_id": requested_user_id
            }
        )
    
    # Проверка 2: Если известен resource_user_id, он должен совпадать с current_user_id
    if resource_user_id is not None and resource_user_id != current_user_id:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "access_denied",
                "message": "Доступ запрещён. Ресурс принадлежит другому пользователю",
                "current_user_id": current_user_id,
                "resource_user_id": resource_user_id
            }
        )


def validate_user_id_from_token(user_id: int) -> None:
    """
    Валидация user_id, извлечённого из токена
    
    Args:
        user_id: ID пользователя из токена
    
    Raises:
        HTTPException 400: Если user_id невалиден
    """
    if user_id is None:
        raise HTTPException(
            status_code=400,
            detail="Не удалось определить ID пользователя из токена"
        )
    
    if not isinstance(user_id, int) or user_id <= 0:
        raise HTTPException(
            status_code=400,
            detail=f"Невалидный ID пользователя: {user_id}"
        )
