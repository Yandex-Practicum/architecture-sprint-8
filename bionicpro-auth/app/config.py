from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    keycloak_url: str = "http://keycloak:8080"
    keycloak_realm: str = "reports-realm"
    keycloak_client_id: str = "bionicpro-auth"
    keycloak_client_secret: str = "bionicpro-auth-secret"

    # Публичный адрес Keycloak — для редиректов в браузере, а не внутри docker-сети
    keycloak_public_url: str = "http://localhost:8080"

    auth_redirect_uri: str = "http://localhost:8000/auth/callback"

    frontend_url: str = "http://localhost:3000"

    redis_url: str = "redis://redis:6379/0"

    # Fernet-ключ: base64, 32 байта
    encryption_key: str = "NBnPZMOrISn4LdWib8wZ43PGG00Y_mhsCiekC8HWMeY="

    session_cookie_name: str = "bionic_session"
    session_ttl_seconds: int = 1800  # заведомо больше времени жизни access_token
    cookie_secure: bool = False  # True в проде (https)
    cookie_samesite: str = "lax"

    class Config:
        env_prefix = ""


settings = Settings()
