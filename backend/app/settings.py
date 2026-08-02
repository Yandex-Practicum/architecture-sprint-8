from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки приложения"""
    
    # Keycloak
    keycloak_url: str = "http://keycloak:8080"
    keycloak_realm: str = "reports-realm"
    public_key_path: str = "/app/certs/public.pem"
    
    # ClickHouse
    clickhouse_host: str = "clickhouse"
    clickhouse_port: int = 8123
    clickhouse_user: str = "default"
    clickhouse_password: str = "clickhouse"
    clickhouse_db: str = "default"
    clickhouse_table: str = "reports"
    
    # Общие настройки
    debug: bool = False
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )


settings = Settings()


def get_public_key() -> str:
    """Загружает публичный ключ из файла"""
    try:
        key_path = Path(settings.public_key_path)
        if not key_path.exists():
            raise FileNotFoundError(f"Public key file not found: {key_path}")
        
        with open(key_path, "r") as f:
            return f.read()
    except Exception as e:
        raise RuntimeError(f"Failed to load public key: {e}")