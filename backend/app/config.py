from pydantic_settings import BaseSettings
from typing import Optional, List

class Settings(BaseSettings):
    # ClickHouse
    CLICKHOUSE_HOST: str = "clickhouse"
    CLICKHOUSE_PORT: int = 8123
    CLICKHOUSE_USER: str = "airflow"
    CLICKHOUSE_PASSWORD: str = "airflow123"
    CLICKHOUSE_DB: str = "reports_db"
    
    # Keycloak
    KEYCLOAK_URL: str = "http://localhost:8080"
    KEYCLOAK_REALM: str = "reports-realm"
    KEYCLOAK_CLIENT_ID: str = "reports-api"
    KEYCLOAK_PUBLIC_KEY: str = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA6DuM3P5qTlh5UhUl1hno
FJ/Wwh49UL0ApiHCnapaBPJhLJg6dxzsKaob+OCUGQflJpthRc0i7eFepwHJvlBU
eUgNCh9bEwKsQBU6/Mh4BZ5m+Y5SSwy275JNds1qJKR2dkqTXFE3Wc7ftK3KC1gl
zFgP/oVmvQ2Vxl9SGqX2fEs4to+joN8q/Zf+mRyYQBg9cVKRk0Z9Gfu4VVwVzlI8
TewgARxQlEArG9PnqUP2p4t7+QvsBbcNYeHlJI6VAHQ5ZutLQVSWOSpEOY+q1Zuf
DUxQvchv1OvdGk56Qcl8/NX8rqn26su9ZyiB/bzK9OdD5DHeHeiZxdHCAHFPo0ec
xQIDAQAB
-----END PUBLIC KEY-----"""
    
    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:3001"]
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()