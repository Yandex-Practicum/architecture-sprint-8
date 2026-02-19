from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    keycloak_url: str = Field(..., env="KEYCLOAK_URL")
    keycloak_realm: str = Field(..., env="KEYCLOAK_REALM")
    client_id: str = Field(..., env="CLIENT_ID")
    client_secret: str | None = Field(None, env="CLIENT_SECRET")
    self_url: str = Field(..., env="SELF_URL")
    redirect_path: str = Field(..., env="REDIRECT_PATH")
    logout_redirect_path: str = Field(..., env="LOGOUT_REDIRECT_PATH")
    frontend_url: str = Field(..., env="FRONTEND_URL")

    redis_url: str = Field("redis://redis:6379", env="REDIS_URL")
    session_ttl: int = 1800
    access_token_leeway: int = 120

    encryption_key: bytes = Field(..., env="ENCRYPTION_KEY")

    class Config:
        env_file = ".env"


settings = Settings()
