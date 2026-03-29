from __future__ import annotations

import os

import jwt
from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient


security = HTTPBearer(auto_error=True)


def get_current_claims(credentials: HTTPAuthorizationCredentials = Security(security)) -> dict:
    token = credentials.credentials
    jwks_client = PyJWKClient(os.environ["KEYCLOAK_JWKS_URL"])

    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=os.environ["KEYCLOAK_EXPECTED_ISSUER"],
            options={"verify_aud": False},
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}") from exc
