from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    auth_service_url: str = "http://bionicpro-auth:8000"

    clickhouse_host: str = "clickhouse"
    clickhouse_port: int = 8123
    clickhouse_user: str = "default"
    clickhouse_password: str = ""
    clickhouse_database: str = "reports"

    # Источник витрины: "realtime" (CDC) или "airflow" (пакетный ETL)
    report_mart: str = "realtime"

    s3_endpoint: str = "http://minio:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_region: str = "us-east-1"
    s3_bucket: str = "reports"

    cdn_base_url: str = "http://localhost:8090"

    frontend_url: str = "http://localhost:3000"

    # Должно совпадать с cookie в bionicpro-auth
    session_cookie_name: str = "bionic_session"
    cookie_secure: bool = False
    cookie_samesite: str = "lax"
    session_ttl_seconds: int = 1800

    class Config:
        env_prefix = ""


settings = Settings()
