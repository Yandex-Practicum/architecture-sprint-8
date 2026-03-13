from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    CLICKHOUSE_HOST: str = "clickhouse"
    CLICKHOUSE_PORT: int = 8123
    CLICKHOUSE_DB: str = "bionicpro"
    KEYCLOAK_URL: str = "http://keycloak:8080"
    KEYCLOAK_EXTERNAL_URL: str = "http://localhost:8080"
    KEYCLOAK_REALM: str = "reports-realm"
    S3_ENDPOINT: str = "http://minio:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_BUCKET: str = "reports"
    CDN_BASE_URL: str = "http://localhost:8081/reports"

    @property
    def keycloak_jwks_url(self) -> str:
        return f"{self.KEYCLOAK_URL}/realms/{self.KEYCLOAK_REALM}/protocol/openid-connect/certs"

    @property
    def keycloak_issuer(self) -> str:
        """Issuer in JWT matches the external URL (how Keycloak issues tokens)."""
        return f"{self.KEYCLOAK_EXTERNAL_URL}/realms/{self.KEYCLOAK_REALM}"

    class Config:
        env_file = ".env"


settings = Settings()
