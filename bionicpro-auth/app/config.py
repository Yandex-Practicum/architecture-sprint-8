import os


class Settings:
    keycloak_internal_url: str = os.environ.get("KEYCLOAK_INTERNAL_URL", "http://keycloak:8080")
    keycloak_public_url: str = os.environ.get("KEYCLOAK_PUBLIC_URL", "http://localhost:8080")
    keycloak_realm: str = os.environ.get("KEYCLOAK_REALM", "reports-realm")
    keycloak_client_id: str = os.environ.get("KEYCLOAK_CLIENT_ID", "reports-frontend")

    redis_url: str = os.environ.get("REDIS_URL", "redis://redis:6379/0")

    session_cookie_name: str = os.environ.get("SESSION_COOKIE_NAME", "bpro_session")
    session_ttl_seconds: int = int(os.environ.get("SESSION_TTL_SECONDS", "1800"))
    # Обновляем access_token немного раньше фактического истечения срока действия, чтобы избежать гонки.
    access_token_refresh_margin_seconds: int = int(os.environ.get("ACCESS_TOKEN_REFRESH_MARGIN_SECONDS", "10"))

    frontend_url: str = os.environ.get("FRONTEND_URL", "http://localhost:3000")
    auth_service_base_url: str = os.environ.get("AUTH_SERVICE_BASE_URL", "http://localhost:4000")
    reports_api_url: str = os.environ.get("REPORTS_API_URL", "http://reports-api:8000")

    # Симметричный ключ для шифрования refresh_token при хранении в Redis (Fernet, 32 url-safe base64 байта).
    # Задано фиксированное значение по умолчанию для локальной разработки, чтобы стек запускался из коробки; в реальном окружении обязательно переопределить.
    token_encryption_key: str = os.environ.get(
        "TOKEN_ENCRYPTION_KEY", "Z2xpvVqLhq3s6E4b8m5f1nQxWc0aRt7uYd9pKj2Ns8I="
    )

    cookie_secure: bool = os.environ.get("COOKIE_SECURE", "true").lower() == "true"

    @property
    def authorization_endpoint(self) -> str:
        return f"{self.keycloak_public_url}/realms/{self.keycloak_realm}/protocol/openid-connect/auth"

    @property
    def token_endpoint(self) -> str:
        return f"{self.keycloak_internal_url}/realms/{self.keycloak_realm}/protocol/openid-connect/token"

    @property
    def logout_endpoint(self) -> str:
        return f"{self.keycloak_internal_url}/realms/{self.keycloak_realm}/protocol/openid-connect/logout"

    @property
    def redirect_uri(self) -> str:
        return f"{self.auth_service_base_url}/callback"


settings = Settings()
