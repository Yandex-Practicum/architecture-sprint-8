"""JWT token validation using Keycloak JWKS."""

import time
from typing import Optional

import httpx
from jose import jwt, JWTError
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from config import settings

security = HTTPBearer()

# Cache for JWKS keys
_jwks_cache: dict = {}
_jwks_cache_time: float = 0
JWKS_CACHE_TTL = 300  # 5 minutes


async def _get_jwks() -> dict:
    """Fetch and cache Keycloak JWKS."""
    global _jwks_cache, _jwks_cache_time

    if _jwks_cache and (time.time() - _jwks_cache_time) < JWKS_CACHE_TTL:
        return _jwks_cache

    async with httpx.AsyncClient() as client:
        resp = await client.get(settings.keycloak_jwks_url)
        if resp.status_code != 200:
            raise HTTPException(status_code=500, detail="Failed to fetch JWKS")
        _jwks_cache = resp.json()
        _jwks_cache_time = time.time()
        return _jwks_cache


async def validate_token(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> dict:
    """
    Validate Bearer JWT token from Keycloak.
    Returns decoded token claims including 'sub', 'preferred_username', 'realm_access'.
    """
    token = credentials.credentials

    jwks = await _get_jwks()

    try:
        # Decode header to find the key ID
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")

        # Find matching key
        rsa_key = None
        for key in jwks.get("keys", []):
            if key.get("kid") == kid:
                rsa_key = key
                break

        if not rsa_key:
            raise HTTPException(status_code=401, detail="Token signing key not found")

        # Verify and decode
        claims = jwt.decode(
            token,
            rsa_key,
            algorithms=["RS256"],
            issuer=settings.keycloak_issuer,
            options={
                "verify_aud": False,  # Keycloak doesn't always set aud correctly
                "verify_exp": True,
            },
        )

        return claims

    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Token validation failed: {str(e)}")
