from dataclasses import dataclass, field
from typing import Any, Dict, List

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from jose.constants import Algorithms
from jose import jwk as jose_jwk

from app.config import settings

security = HTTPBearer()


@dataclass
class UserInfo:
    sub: str
    username: str
    email: str = ""
    roles: List[str] = field(default_factory=list)


_jwks_cache: dict | None = None


async def _fetch_jwks() -> dict:
    global _jwks_cache
    if _jwks_cache is not None:
        return _jwks_cache
    async with httpx.AsyncClient() as client:
        resp = await client.get(settings.keycloak_jwks_url)
        resp.raise_for_status()
        _jwks_cache = resp.json()
    return _jwks_cache


def _invalidate_jwks_cache() -> None:
    global _jwks_cache
    _jwks_cache = None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> UserInfo:
    token = credentials.credentials
    try:
        jwks = await _fetch_jwks()
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")
        if not kid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token missing 'kid' header",
            )

        jwk_data: Dict[str, Any] | None = None
        for key in jwks.get("keys", []):
            if key.get("kid") == kid:
                jwk_data = key
                break

        if not jwk_data:
            _invalidate_jwks_cache()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unable to find signing key",
            )

        rsa_key = jose_jwk.construct(jwk_data, algorithm="RS256")
        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=[Algorithms.RS256],
            audience="account",
            options={"verify_aud": False},
        )

        realm_access = payload.get("realm_access", {})
        roles = realm_access.get("roles", [])

        user = UserInfo(
            sub=payload.get("sub", ""),
            username=payload.get("preferred_username", ""),
            email=payload.get("email", ""),
            roles=roles,
        )
        return user

    except JWTError as e:
        _invalidate_jwks_cache()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
        )
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Keycloak unreachable: {str(e)}",
        )
