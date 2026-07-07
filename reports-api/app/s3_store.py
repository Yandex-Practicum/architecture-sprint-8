"""Хранилище готовых отчётов в S3 (Minio).

version в ключе {username}/{version}.json — версия витрины; её смена (новый
прогон ETL) даёт новый ключ, что инвалидирует кеш в S3/CDN. Bucket с анонимным
чтением, чтобы CDN (Nginx) отдавал объекты без подписи по стабильному URL.
"""
import json
import time

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from .config import settings

_s3 = boto3.client(
    "s3",
    endpoint_url=settings.s3_endpoint,
    aws_access_key_id=settings.s3_access_key,
    aws_secret_access_key=settings.s3_secret_key,
    region_name=settings.s3_region,
    config=Config(signature_version="s3v4"),
)


def _public_read_policy() -> str:
    return json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"AWS": ["*"]},
                    "Action": ["s3:GetObject"],
                    "Resource": [f"arn:aws:s3:::{settings.s3_bucket}/*"],
                }
            ],
        }
    )


def ensure_bucket(retries: int = 10, delay: float = 2.0) -> None:
    """Ретраи ждут готовности Minio на старте сервиса."""
    last_err: Exception | None = None
    for _ in range(retries):
        try:
            try:
                _s3.head_bucket(Bucket=settings.s3_bucket)
            except ClientError:
                _s3.create_bucket(Bucket=settings.s3_bucket)
            _s3.put_bucket_policy(
                Bucket=settings.s3_bucket, Policy=_public_read_policy()
            )
            return
        except Exception as exc:  # noqa: BLE001 — Minio может быть ещё не поднят
            last_err = exc
            time.sleep(delay)
    if last_err:
        raise last_err


def exists(key: str) -> bool:
    try:
        _s3.head_object(Bucket=settings.s3_bucket, Key=key)
        return True
    except ClientError:
        return False


def put_json(key: str, obj: dict) -> None:
    _s3.put_object(
        Bucket=settings.s3_bucket,
        Key=key,
        Body=json.dumps(obj, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json",
    )
