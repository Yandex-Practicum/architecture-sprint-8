import base64
import hashlib
import secrets
from urllib.parse import urlencode

import httpx

from .config import settings


def _realm_base(public: bool = False) -> str:
    base = settings.keycloak_public_url if public else settings.keycloak_url
    return f"{base}/realms/{settings.keycloak_realm}/protocol/openid-connect"


def generate_pkce_pair() -> tuple[str, str]:
    code_verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return code_verifier, code_challenge


def build_authorization_url(state: str, code_challenge: str) -> str:
    """Публичный адрес Keycloak: ссылка открывается в браузере пользователя,
    а не внутри docker-сети."""
    params = {
        "client_id": settings.keycloak_client_id,
        "response_type": "code",
        "scope": "openid",
        "redirect_uri": settings.auth_redirect_uri,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"{_realm_base(public=True)}/auth?{urlencode(params)}"


async def exchange_code(code: str, code_verifier: str) -> dict:
    data = {
        "grant_type": "authorization_code",
        "client_id": settings.keycloak_client_id,
        "client_secret": settings.keycloak_client_secret,
        "code": code,
        "redirect_uri": settings.auth_redirect_uri,
        "code_verifier": code_verifier,
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{_realm_base()}/token", data=data)
        resp.raise_for_status()
        return resp.json()


async def refresh_tokens(refresh_token: str) -> dict:
    data = {
        "grant_type": "refresh_token",
        "client_id": settings.keycloak_client_id,
        "client_secret": settings.keycloak_client_secret,
        "refresh_token": refresh_token,
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{_realm_base()}/token", data=data)
        resp.raise_for_status()
        return resp.json()


async def logout(refresh_token: str) -> None:
    data = {
        "client_id": settings.keycloak_client_id,
        "client_secret": settings.keycloak_client_secret,
        "refresh_token": refresh_token,
    }
    async with httpx.AsyncClient() as client:
        await client.post(f"{_realm_base()}/logout", data=data)


async def get_userinfo(access_token: str) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{_realm_base()}/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp.raise_for_status()
        return resp.json()
