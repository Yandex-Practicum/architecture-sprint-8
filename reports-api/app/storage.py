from __future__ import annotations

import hashlib
import hmac
import json
from io import BytesIO
from urllib.parse import quote

from minio import Minio
from minio.error import S3Error

from .config import Settings


def _public_read_policy(bucket_name: str) -> str:
    return json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"AWS": ["*"]},
                    "Action": ["s3:GetBucketLocation"],
                    "Resource": [f"arn:aws:s3:::{bucket_name}"],
                },
                {
                    "Effect": "Allow",
                    "Principal": {"AWS": ["*"]},
                    "Action": ["s3:GetObject"],
                    "Resource": [f"arn:aws:s3:::{bucket_name}/*"],
                },
            ],
        }
    )


def _version_token(loaded_at: str) -> str:
    cleaned = loaded_at.replace("-", "").replace(":", "").replace(".", "")
    return cleaned.replace("+00:00", "Z").replace("T", "T")


class ReportObjectStore:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = Minio(
            endpoint=settings.s3_endpoint,
            access_key=settings.s3_access_key,
            secret_key=settings.s3_secret_key,
            secure=settings.s3_secure,
        )
        self._bucket_ready = False

    def build_object_key(
        self,
        username: str,
        availability: dict[str, str],
        date_from: str,
        date_to: str,
        report_format: str,
    ) -> str:
        digest = hmac.new(
            self._settings.report_object_key_secret.encode("utf-8"),
            username.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return (
            f"{self._settings.report_object_prefix}/"
            f"{availability['dataset']}/"
            f"v={_version_token(availability['loadedAt'])}/"
            f"u={digest[:24]}/"
            f"{date_from}_{date_to}.{report_format}"
        )

    def build_cdn_url(self, object_key: str) -> str:
        encoded_key = quote(object_key, safe="/=_-")
        return f"{self._settings.cdn_base_url}/{self._settings.s3_bucket}/{encoded_key}"

    def object_exists(self, object_key: str) -> bool:
        self._ensure_bucket()
        try:
            self._client.stat_object(self._settings.s3_bucket, object_key)
            return True
        except S3Error as error:
            if error.code in {"NoSuchKey", "NoSuchObject", "NoSuchBucket"}:
                return False
            status_code = getattr(getattr(error, "response", None), "status", None)
            if status_code == 404:
                return False
            raise RuntimeError("Unable to read report object from S3.") from error

    def put_report(
        self,
        object_key: str,
        content: bytes,
        content_type: str,
        metadata: dict[str, str] | None = None,
    ) -> None:
        self._ensure_bucket()
        try:
            self._client.put_object(
                bucket_name=self._settings.s3_bucket,
                object_name=object_key,
                data=BytesIO(content),
                length=len(content),
                content_type=content_type,
                metadata=metadata,
            )
        except S3Error as error:
            raise RuntimeError("Unable to upload report object to S3.") from error

    def _ensure_bucket(self) -> None:
        if self._bucket_ready:
            return

        try:
            if not self._client.bucket_exists(self._settings.s3_bucket):
                self._client.make_bucket(self._settings.s3_bucket)
            self._client.set_bucket_policy(
                self._settings.s3_bucket,
                _public_read_policy(self._settings.s3_bucket),
            )
        except S3Error as error:
            raise RuntimeError("Unable to prepare S3 bucket for reports.") from error

        self._bucket_ready = True
