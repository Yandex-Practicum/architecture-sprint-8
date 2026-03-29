from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _as_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    keycloak_base_url: str = os.getenv("KEYCLOAK_BASE_URL", "http://localhost:8080").rstrip("/")
    keycloak_public_base_url: str = os.getenv("KEYCLOAK_PUBLIC_BASE_URL", "").rstrip("/")
    keycloak_realm: str = os.getenv("KEYCLOAK_REALM", "reports-realm")
    keycloak_client_id: str = os.getenv("KEYCLOAK_CLIENT_ID", "bionicpro-auth")
    keycloak_client_secret: str = os.getenv("KEYCLOAK_CLIENT_SECRET", "")
    auth_external_base_url: str = os.getenv(
        "AUTH_EXTERNAL_BASE_URL",
        "https://localhost:3000/api",
    ).rstrip("/")
    frontend_base_url: str = os.getenv("FRONTEND_BASE_URL", "https://localhost:3000").rstrip("/")
    session_cookie_name: str = os.getenv("AUTH_SESSION_COOKIE_NAME", "bionicpro_session")
    auth_flow_cookie_name: str = os.getenv("AUTH_FLOW_COOKIE_NAME", "bionicpro_auth_flow")
    session_ttl_seconds: int = int(os.getenv("AUTH_SESSION_TTL_SECONDS", "28800"))
    auth_request_ttl_seconds: int = int(os.getenv("AUTH_REQUEST_TTL_SECONDS", "300"))
    access_token_refresh_skew_seconds: int = int(
        os.getenv("ACCESS_TOKEN_REFRESH_SKEW_SECONDS", "20")
    )
    cookie_secure: bool = _as_bool("AUTH_COOKIE_SECURE", True)
    cookie_samesite: str = os.getenv("AUTH_COOKIE_SAMESITE", "lax")
    token_encryption_key: str = os.getenv("TOKEN_ENCRYPTION_KEY", "")
    profile_db_path: Path = Path(os.getenv("PROFILE_DB_PATH", "/app/data/profiles.db"))

    @property
    def realm_url(self) -> str:
        return f"{self.keycloak_base_url}/realms/{self.keycloak_realm}"

    @property
    def public_realm_url(self) -> str:
        base_url = self.keycloak_public_base_url or self.keycloak_base_url
        return f"{base_url}/realms/{self.keycloak_realm}"

    @property
    def authorization_endpoint(self) -> str:
        return f"{self.public_realm_url}/protocol/openid-connect/auth"

    @property
    def token_endpoint(self) -> str:
        return f"{self.realm_url}/protocol/openid-connect/token"

    @property
    def userinfo_endpoint(self) -> str:
        return f"{self.realm_url}/protocol/openid-connect/userinfo"

    @property
    def logout_endpoint(self) -> str:
        return f"{self.realm_url}/protocol/openid-connect/logout"

    @property
    def redirect_uri(self) -> str:
        return f"{self.auth_external_base_url}/auth/callback"
