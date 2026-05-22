from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_title: str = "BionicPRO Reports API"
    app_version: str = "1.0.0"

    clickhouse_host: str = "clickhouse"
    clickhouse_port: int = 8123
    clickhouse_user: str = "olap_user"
    clickhouse_password: str = "olap_password"
    clickhouse_database: str = "olap_db"

    keycloak_url: str = "http://keycloak:8080"
    keycloak_realm: str = "reports-realm"

    host: str = "0.0.0.0"
    port: int = 8000

    @property
    def clickhouse_http_url(self) -> str:
        return (
            f"http://{self.clickhouse_host}:{self.clickhouse_port}"
            f"?user={self.clickhouse_user}"
            f"&password={self.clickhouse_password}"
            f"&database={self.clickhouse_database}"
            f"&default_format=TabSeparatedWithNamesAndTypes"
        )

    @property
    def keycloak_jwks_url(self) -> str:
        return (
            f"{self.keycloak_url}/realms/{self.keycloak_realm}/protocol/openid-connect/certs"
        )

    model_config = {"env_prefix": "BPRO_", "env_file": ".env"}


settings = Settings()
