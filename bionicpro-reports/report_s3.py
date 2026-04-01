"""
S3-совместимое хранилище (MinIO/Ceph): версионированные ключи отчётов и проверка наличия объекта.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import date, datetime
from typing import Any

import boto3
from botocore.exceptions import ClientError

_BUCKET = os.environ.get("S3_BUCKET", "reports")
_ENDPOINT = os.environ.get("S3_ENDPOINT_URL", "")
_REGION = os.environ.get("S3_REGION", "us-east-1")
_ACCESS = os.environ.get("S3_ACCESS_KEY", "")
_SECRET = os.environ.get("S3_SECRET_KEY", "")


def s3_enabled() -> bool:
    return os.environ.get("S3_ENABLED", "true").lower() in ("1", "true", "yes")


def _client() -> Any:
    if not _ENDPOINT or not _ACCESS or not _SECRET:
        raise RuntimeError("S3 is not configured (S3_ENDPOINT_URL, S3_ACCESS_KEY, S3_SECRET_KEY)")
    return boto3.client(
        "s3",
        endpoint_url=_ENDPOINT,
        aws_access_key_id=_ACCESS,
        aws_secret_access_key=_SECRET,
        region_name=_REGION,
    )


def subject_shard(subject: str) -> str:
    """Не подставляем raw sub в путь — только стабильный шард."""
    return hashlib.sha256(subject.encode("utf-8")).hexdigest()[:16]


def mart_snapshot_id(mart_max_date: date | None, mart_last_refresh: datetime | None) -> str:
    """
    Идентификатор снимка витрины после ETL. При новом прогоне DAG меняется MAX(updated_at) —
    новый ключ в S3, старые объекты не перезаписываются (естественная инвалидация CDN по URL).
    """
    raw = (
        f"{mart_max_date.isoformat() if mart_max_date else 'none'}"
        f"|{mart_last_refresh.isoformat() if mart_last_refresh else 'none'}"
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def object_key_for_report(subject: str, mart_max_date: date | None, mart_last_refresh: datetime | None) -> str:
    return f"v1/{subject_shard(subject)}/{mart_snapshot_id(mart_max_date, mart_last_refresh)}.json"


def head_exists(key: str) -> bool:
    try:
        _client().head_object(Bucket=_BUCKET, Key=key)
        return True
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        status = e.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        if code in ("404", "NoSuchKey", "NotFound") or status == 404:
            return False
        raise


def put_report_json(key: str, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    _client().put_object(
        Bucket=_BUCKET,
        Key=key,
        Body=body,
        ContentType="application/json; charset=utf-8",
        CacheControl="public, max-age=86400",
    )


def public_url(key: str) -> str:
    # По умолчанию — тот же хост, что и BFF, путь /reports-cdn (прокси на Nginx+MinIO), см. CdnProxyController.
    base = os.environ.get("CDN_PUBLIC_BASE", "http://localhost:8181/reports-cdn").rstrip("/")
    return f"{base}/{key}"
