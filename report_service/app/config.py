# app/config.py
import os
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Настройки приложения
    app_name: str = "BionicPRO Report Service"
    environment: str = os.getenv("ENVIRONMENT", "development")
    debug: bool = os.getenv("DEBUG", "False").lower() == "true"

    # Настройки Keycloak (для валидации токенов)
    keycloak_url: str = os.getenv("KEYCLOAK_URL", "http://keycloak:8080")
    keycloak_realm: str = os.getenv("KEYCLOAK_REALM", "reports-realm")
    keycloak_client_id: str = os.getenv("KEYCLOAK_CLIENT_ID", "reports-api")

    # Настройки ClickHouse
    clickhouse_host: str = os.getenv("CLICKHOUSE_HOST", "clickhouse")
    clickhouse_port: int = int(os.getenv("CLICKHOUSE_PORT", "8123"))
    clickhouse_database: str = os.getenv("CLICKHOUSE_DATABASE", "reports")
    clickhouse_user: str = os.getenv("CLICKHOUSE_USER", "default")
    clickhouse_password: str = os.getenv("CLICKHOUSE_PASSWORD", "")

    # Настройки CORS
    cors_origins: list = ["http://localhost:3000"]


settings = Settings()