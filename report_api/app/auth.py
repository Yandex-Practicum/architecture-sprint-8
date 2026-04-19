from dataclasses import dataclass
from functools import lru_cache
from typing import Any
import os

import httpx
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

bearer_scheme = HTTPBearer(auto_error=False)

@dataclass(frozen=True)
class AuthenticatedUser:
    username: str
    email: str | None
    roles: set[str]


@lru_cache
def get_openid_config() -> dict[str, Any]:
    openid_config_url = (
        f"{os.getenv('KEYCLOAK_URL', 'http://localhost:8080')}/realms/{os.getenv('KEYCLOAK_REALM', 'master')}/.well-known/openid-configuration"
    )
    response = httpx.get(openid_config_url)
    response.raise_for_status()
    return response.json()

@lru_cache
def get_jwk_client() -> PyJWKClient:
    jwks_uri = get_openid_config().get("jwks_uri")
    if not jwks_uri:
        raise RuntimeError("JWKS URI not found in OpenID configuration")
    return PyJWKClient(jwks_uri)

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> AuthenticatedUser:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authorization header missing")
    
    token = credentials.credentials
    jwk_client = get_jwk_client()
    try:
        signing_key = jwk_client.get_signing_key_from_jwt(token)
        decoded_token = jwt.decode(
            token, 
            signing_key.key, 
            algorithms=["RS256"], 
            audience=os.getenv('KEYCLOAK_AUDIENCE', 'report_api'),
            issuer=f"http://localhost:8080/realms/{os.getenv('KEYCLOAK_REALM', 'reports-realm')}",
            options={
                "require": ["exp", "iat", "iss", "sub"],
                "verify_aud": False
            }
        )
        return AuthenticatedUser(
            username=decoded_token.get("preferred_username"),
            email=decoded_token.get("email"),
            roles=set(decoded_token.get("realm_access", {}).get("roles", []))
        )
    except (jwt.PyJWTError, httpx.HTTPError) as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    
