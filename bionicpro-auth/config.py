from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Internal URL for server-to-server calls (token exchange, userinfo)
    KEYCLOAK_URL: str = "http://keycloak:8080"
    # External URL for browser redirects (authorization endpoint)
    KEYCLOAK_EXTERNAL_URL: str = "http://localhost:8080"
    KEYCLOAK_REALM: str = "reports-realm"
    CLIENT_ID: str = "bionicpro-bff"
    CLIENT_SECRET: str = "bff-secret-change-in-production"
    REDIRECT_URI: str = "http://localhost:8000/auth/callback"
    FRONTEND_URL: str = "http://localhost:3000"
    REDIS_URL: str = "redis://redis:6379/0"
    SESSION_COOKIE_NAME: str = "bionicpro_session"
    SESSION_MAX_AGE: int = 1800  # 30 minutes (> access_token lifetime)
    REPORTS_API_URL: str = "http://reports-api:8001"

    @property
    def _internal_openid_url(self) -> str:
        return f"{self.KEYCLOAK_URL}/realms/{self.KEYCLOAK_REALM}/protocol/openid-connect"

    @property
    def _external_openid_url(self) -> str:
        return f"{self.KEYCLOAK_EXTERNAL_URL}/realms/{self.KEYCLOAK_REALM}/protocol/openid-connect"

    @property
    def authorization_url(self) -> str:
        """Browser-facing URL — must be accessible from user's browser."""
        return f"{self._external_openid_url}/auth"

    @property
    def token_url(self) -> str:
        """Server-to-server URL — internal Docker network."""
        return f"{self._internal_openid_url}/token"

    @property
    def userinfo_url(self) -> str:
        """Server-to-server URL — internal Docker network."""
        return f"{self._internal_openid_url}/userinfo"

    @property
    def logout_url(self) -> str:
        """Server-to-server URL — internal Docker network."""
        return f"{self._internal_openid_url}/logout"

    @property
    def keycloak_jwks_url(self) -> str:
        """Server-to-server URL — internal Docker network."""
        return f"{self._internal_openid_url}/certs"

    class Config:
        env_file = ".env"


settings = Settings()
