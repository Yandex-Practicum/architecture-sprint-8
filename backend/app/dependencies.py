import logging
from functools import lru_cache
from typing import Annotated

from clickhouse_connect.driver.client import Client
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt
from jose.exceptions import JWTClaimsError, JWTError

from app.db import get_clickhouse_client
from app.settings import get_public_key

logger = logging.getLogger(__name__)
security = HTTPBearer()


@lru_cache()
def load_public_key() -> str:
    """
    Загружает публичный ключ из файла с кешированием.
    """
    return get_public_key()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> str:
    """
    Проверяет JWT токен с использованием публичного ключа Keycloak.
    Возвращает username (preferred_username) из токена.
    """
    try:
        token = credentials.credentials
        public_key = load_public_key()
        
        payload = jwt.decode(
            token,
            public_key,
            algorithms=['RS256'],
            options={
                'verify_signature': True,
                'verify_aud': False,
                'verify_exp': True,
                'verify_iss': False,
            }
        )
        
        username = payload.get('preferred_username') or payload.get('sub')
        
        if not username:
            logger.error(f"Username not found in token. Available keys: {list(payload.keys())}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username not found in token"
            )
        
        logger.info(f"✅ Authenticated user: {username}")
        return username
        
    except JWTError as e:
        logger.error(f"JWT verification error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}"
        )
    except JWTClaimsError as e:
        logger.error(f"JWT claims error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token claims validation failed: {str(e)}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Authentication error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}"
        )

async def get_db_client() -> Client:
    """
    Возвращает клиент ClickHouse.
    Используется как зависимость для эндпоинтов.
    """
    return get_clickhouse_client()

CurrentUser = Annotated[str, Depends(get_current_user)]
DBClient = Annotated[Client, Depends(get_db_client)]