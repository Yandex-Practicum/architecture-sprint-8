import time
from typing import Optional
from urllib.parse import urlencode

import httpx

from .config import settings


class TokenResponse:
    def __init__(self, payload: dict):
        self.access_token: str = payload["access_token"]
        self.refresh_token: str = payload["refresh_token"]
        self.access_expires_at: float = time.time() + int(payload["expires_in"])
        self.refresh_expires_at: float = time.time() + int(payload["refresh_expires_in"])
        self.sub: Optional[str] = None
        self.preferred_username: Optional[str] = None


def build_authorization_url(state: str, code_challenge: str) -> str:
    params = {
        "client_id": settings.keycloak_client_id,
        "response_type": "code",
        "scope": "openid",
        "redirect_uri": settings.redirect_uri,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"{settings.authorization_endpoint}?{urlencode(params)}"


async def exchange_code_for_tokens(code: str, code_verifier: str) -> TokenResponse:
    data = {
        "grant_type": "authorization_code",
        "client_id": settings.keycloak_client_id,
        "code": code,
        "redirect_uri": settings.redirect_uri,
        "code_verifier": code_verifier,
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(settings.token_endpoint, data=data)
        response.raise_for_status()
        return TokenResponse(response.json())


async def refresh_tokens(refresh_token: str) -> TokenResponse:
    data = {
        "grant_type": "refresh_token",
        "client_id": settings.keycloak_client_id,
        "refresh_token": refresh_token,
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(settings.token_endpoint, data=data)
        response.raise_for_status()
        return TokenResponse(response.json())


async def revoke_refresh_token(refresh_token: str) -> None:
    data = {
        "client_id": settings.keycloak_client_id,
        "refresh_token": refresh_token,
    }
    async with httpx.AsyncClient() as client:
        await client.post(settings.logout_endpoint, data=data)
