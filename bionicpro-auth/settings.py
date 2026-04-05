from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    keycloak_url: str = Field(
        default="http://localhost:8080",
        description="Public Keycloak URL for browser redirects.",
    )
    keycloak_internal_url: str | None = Field(
        default=None,
        description="Server-side URL (e.g. http://keycloak:8080 in Docker).",
    )

    keycloak_realm: str = "reports-realm"
    keycloak_client_id: str = "reports-frontend"
    redis_url: str = "redis://localhost:6379/0"
    pkce_state_secret: str = ""
    pkce_ttl_seconds: int = Field(default=600, ge=60, le=3600)
    access_token_refresh_skew_seconds: int = Field(default=30, ge=0, le=300)
    session_ttl_seconds: int = Field(default=1800, ge=60)
    cookie_name: str = "bionicpro_session"
    cookie_secure: bool = False
    frontend_url: str = "http://localhost:3000"
    public_base_url: str = "http://localhost:8000"
    reports_api_base_url: str = "http://localhost:8001"
    pkce_key_prefix: str = "pkce:"
    session_key_prefix: str = "session:"


settings = Settings()
