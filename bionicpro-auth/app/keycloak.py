from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qsl, urlencode

import httpx

from .config import Settings


@dataclass(frozen=True)
class TokenSet:
    access_token: str
    refresh_token: str
    expires_in: int
    refresh_expires_in: int
    scope: str
    token_type: str


class KeycloakClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._http = httpx.AsyncClient(timeout=15.0)

    async def close(self) -> None:
        await self._http.aclose()

    def build_authorization_url(self, state: str, code_challenge: str) -> str:
        params = {
            "client_id": self._settings.keycloak_client_id,
            "redirect_uri": self._settings.redirect_uri,
            "response_type": "code",
            "scope": "openid profile email",
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        return f"{self._settings.authorization_endpoint}?{urlencode(params)}"

    async def exchange_code(self, code: str, code_verifier: str) -> TokenSet:
        payload = {
            "grant_type": "authorization_code",
            "client_id": self._settings.keycloak_client_id,
            "code": code,
            "code_verifier": code_verifier,
            "redirect_uri": self._settings.redirect_uri,
        }
        if self._settings.keycloak_client_secret:
            payload["client_secret"] = self._settings.keycloak_client_secret
        response = await self._http.post(self._settings.token_endpoint, data=payload)
        response.raise_for_status()
        return self._as_token_set(response.json())

    async def refresh_tokens(self, refresh_token: str) -> TokenSet:
        payload = {
            "grant_type": "refresh_token",
            "client_id": self._settings.keycloak_client_id,
            "refresh_token": refresh_token,
        }
        if self._settings.keycloak_client_secret:
            payload["client_secret"] = self._settings.keycloak_client_secret
        response = await self._http.post(self._settings.token_endpoint, data=payload)
        response.raise_for_status()
        return self._as_token_set(response.json())

    async def userinfo(self, access_token: str) -> dict[str, Any]:
        response = await self._http.get(
            self._settings.userinfo_endpoint,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        return response.json()

    async def broker_token(self, provider_alias: str, access_token: str) -> dict[str, Any]:
        response = await self._http.get(
            f"{self._settings.realm_url}/broker/{provider_alias}/token",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        return self._decode_token_payload(response)

    async def yandex_userinfo(self, access_token: str) -> dict[str, Any]:
        response = await self._http.get(
            "https://login.yandex.ru/info",
            params={"format": "json"},
            headers={"Authorization": f"OAuth {access_token}"},
        )
        response.raise_for_status()
        return response.json()

    async def logout(self, refresh_token: str) -> None:
        payload = {
            "client_id": self._settings.keycloak_client_id,
            "refresh_token": refresh_token,
        }
        if self._settings.keycloak_client_secret:
            payload["client_secret"] = self._settings.keycloak_client_secret
        response = await self._http.post(self._settings.logout_endpoint, data=payload)
        response.raise_for_status()

    @staticmethod
    def _as_token_set(payload: dict[str, Any]) -> TokenSet:
        return TokenSet(
            access_token=payload["access_token"],
            refresh_token=payload["refresh_token"],
            expires_in=int(payload.get("expires_in", 0)),
            refresh_expires_in=int(payload.get("refresh_expires_in", 0)),
            scope=payload.get("scope", ""),
            token_type=payload.get("token_type", "Bearer"),
        )

    @staticmethod
    def _decode_token_payload(response: httpx.Response) -> dict[str, Any]:
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            return response.json()

        payload = dict(parse_qsl(response.text, keep_blank_values=True))
        if payload:
            return payload

        raise ValueError("Unsupported broker token response format.")
