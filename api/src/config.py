import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    API_TITLE: str = "BionicPRO Reports API"
    API_VERSION: str = "1.0.0"
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    
    CLICKHOUSE_HOST: str = os.getenv("CLICKHOUSE_HOST", "localhost")
    CLICKHOUSE_PORT: int = int(os.getenv("CLICKHOUSE_PORT", "8123"))
    CLICKHOUSE_USER: str = os.getenv("CLICKHOUSE_USER", "default")
    CLICKHOUSE_PASSWORD: str = os.getenv("CLICKHOUSE_PASSWORD", "clickhouse")
    CLICKHOUSE_DATABASE: str = os.getenv("CLICKHOUSE_DATABASE", "bionicpro")
    
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
    JWT_ALGORITHM: str = "RS256"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
