from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from app.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
security = HTTPBearer()

async def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    """Валидация JWT токена с использованием статического публичного ключа."""
    token = credentials.credentials
    logger.info(f"=== Verifying token ===")
    
    try:
        unverified = jwt.get_unverified_claims(token)
        logger.info(f"Token issuer: {unverified.get('iss')}, sub: {unverified.get('sub')}")
        
        payload = jwt.decode(
            token,
            settings.KEYCLOAK_PUBLIC_KEY,
            algorithms=["RS256"],
            audience=unverified.get('aud'),
            issuer=unverified.get('iss'),
            options={"verify_exp": True, "verify_aud": False}
        )
        
        logger.info(f"✅ Token verified for user: {payload.get('preferred_username')}")
        return payload
    except JWTError as e:
        logger.error(f"❌ JWT verification failed: {e}")
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")

def get_current_user(payload: dict = Depends(verify_token)):
    """Извлечение информации о пользователе из токена."""
    return {
        "sub": payload.get("sub"),
        "preferred_username": payload.get("preferred_username"),
        "email": payload.get("email")
    }