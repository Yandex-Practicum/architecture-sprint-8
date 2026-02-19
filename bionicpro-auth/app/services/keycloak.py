import httpx
from urllib.parse import urlencode
import hashlib
import base64
import secrets
from app.config import settings


class KeycloakClient:
    def __init__(self):
        self.auth_url = f"{settings.keycloak_url}/realms/{settings.keycloak_realm}/protocol/openid-connect/auth"
        self.token_url = f"{settings.keycloak_url}/realms/{settings.keycloak_realm}/protocol/openid-connect/token"
        self.logout_url = f"{settings.keycloak_url}/realms/{settings.keycloak_realm}/protocol/openid-connect/logout"
        self.userinfo_url = f"{settings.keycloak_url}/realms/{settings.keycloak_realm}/protocol/openid-connect/userinfo"
        self.client_id = settings.client_id
        self.client_secret = settings.client_secret
        self.redirect_uri = f"{settings.self_url}/{settings.redirect_path}"
        self.logout_redirect_uri = (
            f"{settings.self_url}/{settings.logout_redirect_path}"
        )

    def generate_pkce_pair(self) -> tuple[str, str]:
        """Генерирует code_verifier и code_challenge (S256)"""
        code_verifier = secrets.token_urlsafe(64)
        code_challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest())
            .decode()
            .rstrip("=")
        )
        return code_verifier, code_challenge

    def get_authorization_url(self, state: str, code_challenge: str) -> str:
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": "openid profile email",
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        return f"{self.auth_url}?{urlencode(params)}"

    async def exchange_code(self, code: str, code_verifier: str) -> dict:
        """Обмен кода на токены"""
        data = {
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "code": code,
            "redirect_uri": self.redirect_uri,
            "code_verifier": code_verifier,
        }
        if self.client_secret:
            data["client_secret"] = self.client_secret

        async with httpx.AsyncClient() as client:
            resp = await client.post(self.token_url, data=data)
            resp.raise_for_status()
            return resp.json()

    async def refresh_access_token(self, refresh_token: str) -> dict:
        """Обновление access_token по refresh_token"""
        data = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "refresh_token": refresh_token,
        }
        if self.client_secret:
            data["client_secret"] = self.client_secret

        async with httpx.AsyncClient() as client:
            resp = await client.post(self.token_url, data=data)
            resp.raise_for_status()
            return resp.json()

    async def get_userinfo(self, access_token: str) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                self.userinfo_url, headers={"Authorization": f"Bearer {access_token}"}
            )
            resp.raise_for_status()
            return resp.json()

    def get_logout_url(self, id_token_hint: str = None) -> str:
        """Генерирует URL для logout в Keycloak"""
        params = {
            "client_id": self.client_id,
        }

        if id_token_hint:
            params["id_token_hint"] = id_token_hint

        params["post_logout_redirect_uri"] = self.logout_redirect_uri

        return f"{self.logout_url}?{urlencode(params)}"


keycloak_client = KeycloakClient()
