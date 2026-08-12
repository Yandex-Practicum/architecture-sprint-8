import hashlib
import hmac
import json

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from .config import settings

_s3 = boto3.client(
    "s3",
    endpoint_url=settings.s3_endpoint_url,
    aws_access_key_id=settings.s3_access_key,
    aws_secret_access_key=settings.s3_secret_key,
    config=Config(signature_version="s3v4"),
    region_name="us-east-1",
)

_BUCKET = settings.s3_bucket


def ensure_bucket():
    try:
        _s3.head_bucket(Bucket=_BUCKET)
    except ClientError:
        _s3.create_bucket(Bucket=_BUCKET)
        # Объекты адресуются непредсказуемым токеном на каждый отчёт (см.
        # object_key_for ниже), поэтому анонимный GET по точному ключу
        # безопасен - именно это позволяет Nginx/CDN отдавать закэшированные
        # отчёты без повторной проверки авторизации на каждый запрос.
        policy = {
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": "*",
                "Action": "s3:GetObject",
                "Resource": f"arn:aws:s3:::{_BUCKET}/reports/*",
            }],
        }
        _s3.put_bucket_policy(Bucket=_BUCKET, Policy=json.dumps(policy))


def object_key_for(customer_id: str, report_generated_at: str) -> str:
    """Детерминированный, непредсказуемый ключ объекта для одного обработанного отчёта.

    Ключ строится из (customer_id, report_generated_at): новый прогон Airflow -
    меняющий report_generated_at - естественным образом даёт новый ключ, поэтому
    кэш CDN инвалидируется неявно, без ручной очистки.
    """
    digest = hmac.new(
        settings.report_link_secret.encode("utf-8"),
        f"{customer_id}:{report_generated_at}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"reports/{digest}.json"


def get_cached_report_url(object_key: str) -> str | None:
    try:
        _s3.head_object(Bucket=_BUCKET, Key=object_key)
    except ClientError:
        return None
    return f"{settings.cdn_base_url}/{_BUCKET}/{object_key}"


def store_report(object_key: str, report: dict) -> str:
    _s3.put_object(
        Bucket=_BUCKET,
        Key=object_key,
        Body=json.dumps(report).encode("utf-8"),
        ContentType="application/json",
    )
    return f"{settings.cdn_base_url}/{_BUCKET}/{object_key}"
