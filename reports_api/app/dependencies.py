from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt
import logging
import httpx
from functools import lru_cache
from jose import jwk

logger = logging.getLogger(__name__)
security = HTTPBearer()

# Keycloak configuration
KEYCLOAK_URL = "http://keycloak:8080/realms/reports-realm"
JWKS_URL = f"{KEYCLOAK_URL}/protocol/openid-connect/certs"


@lru_cache(maxsize=1)
def get_jwks():
    """Получение JWKS (публичных ключей) из Keycloak с кэшированием"""
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(JWKS_URL)
            response.raise_for_status()
            jwks = response.json()
            logger.info("Successfully fetched JWKS from Keycloak")
            return jwks
    except Exception as e:
        logger.error(f"Failed to fetch JWKS: {e}")
        raise HTTPException(status_code=500, detail="Unable to fetch authentication keys")


def get_public_key(kid: str):
    """Получение публичного ключа по kid (key ID)"""
    jwks = get_jwks()
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            public_key = jwk.construct(key)
            return public_key.to_pem().decode("utf-8")
    return None


async def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)):
    token = credentials.credentials
    logger.info(f"Validating token (first 50 chars): {token[:50]}...")

    try:
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")

        if not kid:
            logger.warning("No kid in token header, trying without signature verification")
            payload = jwt.decode(
                token,
                options={"verify_signature": False, "verify_exp": True}
            )
        else:
            public_key = get_public_key(kid)
            if not public_key:
                logger.warning(f"Public key not found for kid: {kid}")
                payload = jwt.decode(
                    token,
                    options={"verify_signature": False, "verify_exp": True}
                )
            else:
                payload = jwt.decode(
                    token,
                    public_key,
                    algorithms=["RS256"],
                    options={"verify_exp": True}
                )

        username = payload.get("preferred_username") or payload.get("sub")
        roles = payload.get("realm_access", {}).get("roles", [])

        if not roles and username:
            roles = ["user"]

        if not username:
            logger.error("No username found in token payload")
            raise HTTPException(status_code=401, detail="Invalid token: missing user")

        logger.info(f"Token accepted for user: {username}, roles: {roles}")
        return {"username": username, "user_id": username, "roles": roles}

    except jwt.ExpiredSignatureError:
        logger.error("Token has expired")
        raise HTTPException(status_code=401, detail="Token has expired. Please login again.")
    except jwt.JWTError as e:
        logger.error(f"JWT decode error: {e}")
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected token validation error: {e}")
        raise HTTPException(status_code=401, detail="Authentication failed")
