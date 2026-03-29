from __future__ import annotations

import os
from dataclasses import dataclass


def _as_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    auth_service_base_url: str = os.getenv("AUTH_SERVICE_BASE_URL", "http://bionicpro-auth:8000").rstrip("/")
    frontend_base_url: str = os.getenv("FRONTEND_BASE_URL", "https://localhost:3000").rstrip("/")
    clickhouse_host: str = os.getenv("CLICKHOUSE_HOST", "clickhouse")
    clickhouse_port: int = int(os.getenv("CLICKHOUSE_PORT", "8123"))
    clickhouse_database: str = os.getenv("CLICKHOUSE_DATABASE", "reporting")
    clickhouse_username: str = os.getenv("CLICKHOUSE_USERNAME", "default")
    clickhouse_password: str = os.getenv("CLICKHOUSE_PASSWORD", "")
    report_dataset_name: str = os.getenv("REPORT_DATASET_NAME", "user_daily_reports_cdc")
    s3_endpoint: str = os.getenv("S3_ENDPOINT", "minio:9000").rstrip("/")
    s3_access_key: str = os.getenv("S3_ACCESS_KEY", "minioadmin")
    s3_secret_key: str = os.getenv("S3_SECRET_KEY", "minioadmin")
    s3_bucket: str = os.getenv("S3_BUCKET", "bionicpro-reports")
    s3_secure: bool = _as_bool("S3_SECURE", False)
    cdn_base_url: str = os.getenv("CDN_BASE_URL", "https://localhost:3000/cdn").rstrip("/")
    report_object_prefix: str = os.getenv("REPORT_OBJECT_PREFIX", "reports").strip("/")
    report_object_key_secret: str = os.getenv(
        "REPORT_OBJECT_KEY_SECRET",
        "local-report-key-secret",
    )
