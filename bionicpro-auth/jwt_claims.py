import logging

import jwt
from fastapi import HTTPException
from jwt import PyJWKClient

from settings import Settings

logger = logging.getLogger(__name__)


def jwks_url(settings: Settings) -> str:
    base = (settings.keycloak_internal_url or settings.keycloak_url).rstrip("/")
    return f"{base}/realms/{settings.keycloak_realm}/protocol/openid-connect/certs"


def expected_token_issuers(settings: Settings) -> tuple[str, ...]:
    public = f"{settings.keycloak_url.rstrip('/')}/realms/{settings.keycloak_realm}"
    internal_base = (settings.keycloak_internal_url or "").strip()
    if not internal_base:
        return (public,)
    internal = f"{internal_base.rstrip('/')}/realms/{settings.keycloak_realm}"
    return (public, internal) if internal != public else (public,)


def make_jwks_client(settings: Settings) -> PyJWKClient:
    return PyJWKClient(jwks_url(settings))


def preferred_username_from_access_token(
    jwks_client: PyJWKClient,
    settings: Settings,
    access_token: str,
) -> str:
    issuers = expected_token_issuers(settings)
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(access_token)
        payload = jwt.decode(
            access_token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=issuers,
            options={"verify_aud": False},
        )
    except jwt.PyJWTError as e:
        logger.warning("access token validation failed: %s", e)
        raise HTTPException(status_code=401, detail="invalid access token") from e

    raw = payload.get("preferred_username")
    if raw is None or not str(raw).strip():
        raise HTTPException(status_code=401, detail="token missing preferred_username")
    return str(raw).strip()
