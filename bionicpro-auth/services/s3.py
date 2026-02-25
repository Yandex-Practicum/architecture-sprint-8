import io
import json
import hashlib
import logging
from typing import Optional, Dict
from datetime import datetime

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class S3Service:
    """Service for working with S3-compatible storage (Minio/Ceph).

    Storage structure in bucket:
        reports/{email_hash}/{datamart_version}.json

    Where:
        - email_hash - SHA-256 of user email (privacy + convenience)
        - datamart_version - hash of last datamart update time,
          which provides automatic invalidation when ETL updates
    """

    def __init__(self, config):
        self.bucket_name = config.S3_BUCKET_NAME
        self.cdn_base_url = config.CDN_BASE_URL

        self.s3_client = boto3.client(
            's3',
            endpoint_url=config.S3_ENDPOINT_URL,
            aws_access_key_id=config.S3_ACCESS_KEY,
            aws_secret_access_key=config.S3_SECRET_KEY,
            region_name='us-east-1',
        )

        self._ensure_bucket_exists()

    def _ensure_bucket_exists(self):
        """Create bucket if it doesn't exist."""
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            logger.info(f"S3 bucket '{self.bucket_name}' already exists")
        except ClientError:
            try:
                self.s3_client.create_bucket(Bucket=self.bucket_name)
                policy = json.dumps({
                    "Version": "2012-10-17",
                    "Statement": [{
                        "Effect": "Allow",
                        "Principal": {"AWS": "*"},
                        "Action": ["s3:GetObject"],
                        "Resource": [f"arn:aws:s3:::{self.bucket_name}/*"]
                    }]
                })
                self.s3_client.put_bucket_policy(
                    Bucket=self.bucket_name, Policy=policy
                )
                logger.info(f"S3 bucket '{self.bucket_name}' created with public read policy")
            except ClientError as e:
                logger.error(f"Failed to create S3 bucket: {e}")
                raise

    @staticmethod
    def _hash_email(email: str) -> str:
        """Generate SHA-256 hash from email for S3 path."""
        return hashlib.sha256(email.lower().strip().encode()).hexdigest()

    @staticmethod
    def _hash_version(datamart_updated_at: str) -> str:
        """Generate short version hash for filename."""
        return hashlib.md5(datamart_updated_at.encode()).hexdigest()[:12]

    def _build_s3_key(self, email: str, datamart_updated_at: str) -> str:
        """Build S3 object key.

        Format: reports/{email_hash}/{version_hash}.json
        When datamart is updated, version_hash changes,
        which automatically invalidates old cache.
        """
        email_hash = self._hash_email(email)
        version_hash = self._hash_version(datamart_updated_at)
        return f"reports/{email_hash}/{version_hash}.json"

    def get_report(self, email: str, datamart_updated_at: str) -> Optional[Dict]:
        """Get report from S3 if it exists."""
        s3_key = self._build_s3_key(email, datamart_updated_at)
        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket_name, Key=s3_key
            )
            body = response['Body'].read().decode('utf-8')
            report = json.loads(body)
            logger.info(f"Report found in S3: {s3_key}")
            return report
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                logger.info(f"Report not found in S3: {s3_key}")
                return None
            logger.error(f"S3 get error: {e}")
            return None
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to parse report from S3: {e}")
            return None

    def put_report(self, email: str, datamart_updated_at: str, report: Dict) -> Optional[str]:
        """Save report to S3 and return CDN URL."""
        s3_key = self._build_s3_key(email, datamart_updated_at)
        try:
            report_json = json.dumps(report, ensure_ascii=False, indent=2)
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=report_json.encode('utf-8'),
                ContentType='application/json',
            )
            cdn_url = f"{self.cdn_base_url}/{self.bucket_name}/{s3_key}"
            logger.info(f"Report saved to S3: {s3_key}, CDN URL: {cdn_url}")
            return cdn_url
        except ClientError as e:
            logger.error(f"S3 put error: {e}")
            return None

    def get_cdn_url(self, email: str, datamart_updated_at: str) -> str:
        """Build CDN URL for report (without checking existence)."""
        s3_key = self._build_s3_key(email, datamart_updated_at)
        return f"{self.cdn_base_url}/{self.bucket_name}/{s3_key}"

    def delete_user_reports(self, email: str) -> int:
        """Delete all user reports from S3 (invalidation)."""
        email_hash = self._hash_email(email)
        prefix = f"reports/{email_hash}/"
        deleted_count = 0
        try:
            paginator = self.s3_client.get_paginator('list_objects_v2')
            for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix):
                objects = page.get('Contents', [])
                if objects:
                    delete_keys = [{'Key': obj['Key']} for obj in objects]
                    self.s3_client.delete_objects(
                        Bucket=self.bucket_name,
                        Delete={'Objects': delete_keys}
                    )
                    deleted_count += len(delete_keys)
            logger.info(f"Deleted {deleted_count} reports for email hash: {email_hash[:8]}...")
        except ClientError as e:
            logger.error(f"S3 delete error: {e}")
        return deleted_count

    def invalidate_all_reports(self) -> int:
        """Delete all reports from S3 (full invalidation after ETL)."""
        prefix = "reports/"
        deleted_count = 0
        try:
            paginator = self.s3_client.get_paginator('list_objects_v2')
            for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix):
                objects = page.get('Contents', [])
                if objects:
                    delete_keys = [{'Key': obj['Key']} for obj in objects]
                    self.s3_client.delete_objects(
                        Bucket=self.bucket_name,
                        Delete={'Objects': delete_keys}
                    )
                    deleted_count += len(delete_keys)
            logger.info(f"Full cache invalidation: deleted {deleted_count} reports")
        except ClientError as e:
            logger.error(f"S3 full invalidation error: {e}")
        return deleted_count
