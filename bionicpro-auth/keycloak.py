import logging
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException

from settings import Settings

logger = logging.getLogger(__name__)


class KeycloakClient:
    def __init__(self, settings: Settings) -> None:
        self._s = settings

    def _realm_base_public(self) -> str:
        base = self._s.keycloak_url.rstrip("/")
        return f"{base}/realms/{self._s.keycloak_realm}/protocol/openid-connect"

    def _realm_base_internal(self) -> str:
        base = (self._s.keycloak_internal_url or self._s.keycloak_url).rstrip("/")
        return f"{base}/realms/{self._s.keycloak_realm}/protocol/openid-connect"

    def auth_url(self) -> str:
        return f"{self._realm_base_public()}/auth"

    def token_url(self) -> str:
        return f"{self._realm_base_internal()}/token"

    def oauth_callback_uri(self) -> str:
        return f"{self._s.public_base_url.rstrip('/')}/auth/callback"

    def build_authorize_url(self, *, state: str, code_challenge: str) -> str:
        params = {
            "client_id": self._s.keycloak_client_id,
            "redirect_uri": self.oauth_callback_uri(),
            "response_type": "code",
            "scope": "openid",
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        return f"{self.auth_url()}?{urlencode(params)}"

    async def exchange_authorization_code(
        self, *, code: str, code_verifier: str
    ) -> dict:
        try:
            async with httpx.AsyncClient() as http:
                token_resp = await http.post(
                    self.token_url(),
                    data={
                        "grant_type": "authorization_code",
                        "client_id": self._s.keycloak_client_id,
                        "code": code,
                        "redirect_uri": self.oauth_callback_uri(),
                        "code_verifier": code_verifier,
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
        except httpx.RequestError as e:
            logger.exception("token request failed: %s", e)
            raise HTTPException(
                status_code=502, detail="token endpoint unreachable"
            ) from e
        if token_resp.is_error:
            logger.error(
                "token exchange failed: %s %s",
                token_resp.status_code,
                token_resp.text[:500],
            )
            raise HTTPException(status_code=400, detail="token exchange failed")
        return token_resp.json()

    async def refresh(self, refresh_token: str) -> dict:
        try:
            async with httpx.AsyncClient() as http:
                token_resp = await http.post(
                    self.token_url(),
                    data={
                        "grant_type": "refresh_token",
                        "client_id": self._s.keycloak_client_id,
                        "refresh_token": refresh_token,
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
        except httpx.RequestError as e:
            logger.exception("refresh request failed: %s", e)
            raise HTTPException(
                status_code=502, detail="token endpoint unreachable"
            ) from e
        if token_resp.is_error:
            logger.warning(
                "refresh failed: %s %s",
                token_resp.status_code,
                token_resp.text[:300],
            )
            raise HTTPException(status_code=401, detail="session expired")
        return token_resp.json()
