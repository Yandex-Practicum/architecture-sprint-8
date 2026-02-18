import logging
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
import requests

from .config import settings

logger = logging.getLogger(__name__)

security = HTTPBearer()

_jwks_cache: Optional[dict] = None


def get_jwks_keys() -> dict:
    global _jwks_cache
    
    if _jwks_cache is not None:
        return _jwks_cache
    
    keycloak_url = settings.KEYCLOAK_URL
    realm = settings.KEYCLOAK_REALM
    jwks_url = f"{keycloak_url}/realms/{realm}/protocol/openid-connect/certs"
    
    try:
        response = requests.get(jwks_url, timeout=5)
        response.raise_for_status()
        _jwks_cache = response.json()
        logger.info(f"Fetched JWKS from {jwks_url}")
        return _jwks_cache
    except Exception as e:
        logger.error(f"Failed to fetch JWKS from {jwks_url}: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service unavailable"
        )


def verify_jwt_token(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    token = credentials.credentials
    
    try:
        jwks = get_jwks_keys()
        
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")
        
        if not kid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing key ID"
            )
        
        rsa_key = None
        for key in jwks.get("keys", []):
            if key.get("kid") == kid:
                rsa_key = {
                    "kty": key["kty"],
                    "kid": key["kid"],
                    "use": key["use"],
                    "n": key["n"],
                    "e": key["e"]
                }
                break
        
        if not rsa_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: key not found"
            )
        
        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=["RS256"],
            audience=settings.KEYCLOAK_CLIENT_ID,
            options={
                "verify_signature": True,
                "verify_aud": True,
                "verify_exp": True
            }
        )
        
        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing user_id claim"
            )
        
        logger.info(f"JWT verified for user_id={user_id}")
        return {
            "user_id": int(user_id),
            "email": payload.get("email"),
            "username": payload.get("preferred_username"),
            "sub": payload.get("sub")
        }
        
    except JWTError as e:
        logger.warning(f"JWT verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error during JWT verification: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication error"
        )


def require_user_id_match(
    requested_user_id: int,
    current_user: dict = Depends(verify_jwt_token)
) -> dict:
    if current_user["user_id"] != requested_user_id:
        logger.warning(
            f"Authorization failed: user {current_user['user_id']} "
            f"attempted to access data for user {requested_user_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access your own reports"
        )
    
    return current_user
