import os


class Settings:
    keycloak_internal_url: str = os.environ.get("KEYCLOAK_INTERNAL_URL", "http://keycloak:8080")
    keycloak_realm: str = os.environ.get("KEYCLOAK_REALM", "reports-realm")
    expected_audience: str = os.environ.get("EXPECTED_AUDIENCE", "reports-api")
    expected_issuer: str = os.environ.get(
        "EXPECTED_ISSUER", "https://localhost:8443/realms/reports-realm"
    )

    clickhouse_host: str = os.environ.get("CLICKHOUSE_HOST", "clickhouse")
    clickhouse_port: int = int(os.environ.get("CLICKHOUSE_PORT", "8123"))
    clickhouse_user: str = os.environ.get("CLICKHOUSE_USER", "reports")
    clickhouse_password: str = os.environ.get("CLICKHOUSE_PASSWORD", "reports_password")

    s3_endpoint_url: str = os.environ.get("S3_ENDPOINT_URL", "http://minio:9000")
    s3_access_key: str = os.environ.get("S3_ACCESS_KEY", "minio_user")
    s3_secret_key: str = os.environ.get("S3_SECRET_KEY", "minio_password")
    s3_bucket: str = os.environ.get("S3_BUCKET", "reports")
    # Базовый URL, по которому браузер обращается к кэширующему reverse proxy
    # (Nginx), стоящему перед MinIO и эмулирующему CDN.
    cdn_base_url: str = os.environ.get("CDN_BASE_URL", "http://localhost:8090")
    # HMAC-ключ для вывода непредсказуемых ключей/ссылок объектов на отчёты.
    report_link_secret: str = os.environ.get(
        "REPORT_LINK_SECRET", "dev-report-link-secret-change-in-production"
    )

    redis_url: str = os.environ.get("REDIS_URL", "redis://redis:6379/1")
    pointer_cache_ttl_seconds: int = int(os.environ.get("POINTER_CACHE_TTL_SECONDS", "300"))

    @property
    def jwks_url(self) -> str:
        return f"{self.keycloak_internal_url}/realms/{self.keycloak_realm}/protocol/openid-connect/certs"


settings = Settings()
