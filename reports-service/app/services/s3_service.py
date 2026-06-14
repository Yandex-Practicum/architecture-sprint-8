"""
S3 Service for Reports Storage.

Provides functionality to store and retrieve pre-generated reports from S3-compatible
object storage (MinIO). Reports are stored in JSON format and served via CDN.

Storage Structure:
    reports-bucket/
    ├── {user_id}/
    │   ├── list/
    │   │   └── reports.json       # List of available reports
    │   ├── summary/
    │   │   └── summary.json       # User's overall summary
    │   └── daily/
    │       └── {YYYY-MM-DD}/
    │           └── report.json    # Daily detailed report

Cache Invalidation:
    - Reports are regenerated when requested and not found in S3
    - ETL process can trigger cache invalidation via /api/reports/invalidate endpoint
    - CDN caches with 5-minute TTL (aligned with Redis cache)

Задание 3: Снижение нагрузки на базу данных
"""

import json
import logging
from datetime import date
from typing import Optional, Any
from functools import lru_cache

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, NoCredentialsError

from app.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()


class S3Service:
    """Service for storing and retrieving reports from S3/MinIO."""

    def __init__(self):
        """Initialize S3 client."""
        self._client = None
        self._bucket = settings.s3_bucket_name
        self._cdn_base_url = settings.cdn_base_url
        self._cdn_enabled = settings.cdn_enabled

    @property
    def client(self):
        """Lazy initialization of S3 client."""
        if self._client is None:
            try:
                self._client = boto3.client(
                    "s3",
                    endpoint_url=settings.s3_endpoint_url,
                    aws_access_key_id=settings.s3_access_key,
                    aws_secret_access_key=settings.s3_secret_key,
                    region_name=settings.s3_region,
                    config=Config(
                        signature_version="s3v4",
                        retries={"max_attempts": 3, "mode": "standard"},
                    ),
                )
                logger.info(f"S3 client initialized: {settings.s3_endpoint_url}")
            except Exception as e:
                logger.error(f"Failed to initialize S3 client: {e}")
                raise
        return self._client

    def health_check(self) -> bool:
        """Check S3/MinIO connectivity."""
        try:
            self.client.head_bucket(Bucket=self._bucket)
            return True
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            logger.warning(f"S3 health check failed: {error_code}")
            return False
        except Exception as e:
            logger.error(f"S3 health check error: {e}")
            return False

    # ========================================================================
    # Key Generation
    # ========================================================================

    def _get_reports_list_key(self, user_id: str) -> str:
        """Generate S3 key for reports list."""
        return f"{user_id}/list/reports.json"

    def _get_summary_key(self, user_id: str) -> str:
        """Generate S3 key for user summary."""
        return f"{user_id}/summary/summary.json"

    def _get_daily_report_key(self, user_id: str, report_date: date) -> str:
        """Generate S3 key for daily report."""
        return f"{user_id}/daily/{report_date.isoformat()}/report.json"

    # ========================================================================
    # CDN URL Generation
    # ========================================================================

    def get_cdn_url(self, s3_key: str) -> str:
        """
        Generate CDN URL for an S3 object.

        CDN URL structure: {cdn_base_url}/reports/{s3_key}
        Nginx CDN proxies /reports/ to MinIO bucket.
        """
        return f"{self._cdn_base_url}/reports/{s3_key}"

    def get_reports_list_cdn_url(self, user_id: str) -> str:
        """Get CDN URL for reports list."""
        return self.get_cdn_url(self._get_reports_list_key(user_id))

    def get_summary_cdn_url(self, user_id: str) -> str:
        """Get CDN URL for user summary."""
        return self.get_cdn_url(self._get_summary_key(user_id))

    def get_daily_report_cdn_url(self, user_id: str, report_date: date) -> str:
        """Get CDN URL for daily report."""
        return self.get_cdn_url(self._get_daily_report_key(user_id, report_date))

    # ========================================================================
    # Object Existence Checks
    # ========================================================================

    def object_exists(self, s3_key: str) -> bool:
        """Check if object exists in S3."""
        try:
            self.client.head_object(Bucket=self._bucket, Key=s3_key)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            logger.error(f"Error checking object existence: {e}")
            return False

    def reports_list_exists(self, user_id: str) -> bool:
        """Check if reports list exists for user."""
        return self.object_exists(self._get_reports_list_key(user_id))

    def summary_exists(self, user_id: str) -> bool:
        """Check if summary exists for user."""
        return self.object_exists(self._get_summary_key(user_id))

    def daily_report_exists(self, user_id: str, report_date: date) -> bool:
        """Check if daily report exists."""
        return self.object_exists(self._get_daily_report_key(user_id, report_date))

    # ========================================================================
    # Store Operations
    # ========================================================================

    def _put_json_object(self, s3_key: str, data: dict) -> bool:
        """Store JSON data in S3."""
        try:
            json_data = json.dumps(data, ensure_ascii=False, default=str)
            self.client.put_object(
                Bucket=self._bucket,
                Key=s3_key,
                Body=json_data.encode("utf-8"),
                ContentType="application/json",
                CacheControl="max-age=300",  # 5 minutes, aligned with Redis cache
            )
            logger.info(f"Stored object: s3://{self._bucket}/{s3_key}")
            return True
        except ClientError as e:
            logger.error(f"Failed to store object {s3_key}: {e}")
            return False

    def store_reports_list(self, user_id: str, data: dict) -> Optional[str]:
        """
        Store reports list in S3 and return CDN URL.

        Args:
            user_id: User identifier
            data: Reports list data

        Returns:
            CDN URL if successful, None otherwise
        """
        s3_key = self._get_reports_list_key(user_id)
        if self._put_json_object(s3_key, data):
            return self.get_cdn_url(s3_key)
        return None

    def store_summary(self, user_id: str, data: dict) -> Optional[str]:
        """
        Store user summary in S3 and return CDN URL.

        Args:
            user_id: User identifier
            data: Summary data

        Returns:
            CDN URL if successful, None otherwise
        """
        s3_key = self._get_summary_key(user_id)
        if self._put_json_object(s3_key, data):
            return self.get_cdn_url(s3_key)
        return None

    def store_daily_report(
        self, user_id: str, report_date: date, data: dict
    ) -> Optional[str]:
        """
        Store daily report in S3 and return CDN URL.

        Args:
            user_id: User identifier
            report_date: Report date
            data: Daily report data

        Returns:
            CDN URL if successful, None otherwise
        """
        s3_key = self._get_daily_report_key(user_id, report_date)
        if self._put_json_object(s3_key, data):
            return self.get_cdn_url(s3_key)
        return None

    # ========================================================================
    # Retrieve Operations
    # ========================================================================

    def _get_json_object(self, s3_key: str) -> Optional[dict]:
        """Retrieve JSON data from S3."""
        try:
            response = self.client.get_object(Bucket=self._bucket, Key=s3_key)
            data = json.loads(response["Body"].read().decode("utf-8"))
            logger.debug(f"Retrieved object: s3://{self._bucket}/{s3_key}")
            return data
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                logger.debug(f"Object not found: {s3_key}")
                return None
            logger.error(f"Failed to retrieve object {s3_key}: {e}")
            return None

    def get_reports_list(self, user_id: str) -> Optional[dict]:
        """Get reports list from S3."""
        return self._get_json_object(self._get_reports_list_key(user_id))

    def get_summary(self, user_id: str) -> Optional[dict]:
        """Get user summary from S3."""
        return self._get_json_object(self._get_summary_key(user_id))

    def get_daily_report(self, user_id: str, report_date: date) -> Optional[dict]:
        """Get daily report from S3."""
        return self._get_json_object(self._get_daily_report_key(user_id, report_date))

    # ========================================================================
    # Cache Invalidation
    # ========================================================================

    def _delete_object(self, s3_key: str) -> bool:
        """Delete object from S3."""
        try:
            self.client.delete_object(Bucket=self._bucket, Key=s3_key)
            logger.info(f"Deleted object: s3://{self._bucket}/{s3_key}")
            return True
        except ClientError as e:
            logger.error(f"Failed to delete object {s3_key}: {e}")
            return False

    def invalidate_reports_list(self, user_id: str) -> bool:
        """Invalidate reports list cache for user."""
        return self._delete_object(self._get_reports_list_key(user_id))

    def invalidate_summary(self, user_id: str) -> bool:
        """Invalidate summary cache for user."""
        return self._delete_object(self._get_summary_key(user_id))

    def invalidate_daily_report(self, user_id: str, report_date: date) -> bool:
        """Invalidate daily report cache."""
        return self._delete_object(self._get_daily_report_key(user_id, report_date))

    def invalidate_user_cache(self, user_id: str) -> int:
        """
        Invalidate all cached reports for a user.

        This deletes all objects under the user's prefix in S3.
        Used after ETL updates user's data.

        Returns:
            Number of deleted objects
        """
        deleted_count = 0
        prefix = f"{user_id}/"

        try:
            # List all objects with user's prefix
            paginator = self.client.get_paginator("list_objects_v2")
            pages = paginator.paginate(Bucket=self._bucket, Prefix=prefix)

            objects_to_delete = []
            for page in pages:
                if "Contents" in page:
                    for obj in page["Contents"]:
                        objects_to_delete.append({"Key": obj["Key"]})

            if not objects_to_delete:
                logger.info(f"No objects to delete for user: {user_id}")
                return 0

            # Delete objects in batches of 1000 (S3 limit)
            for i in range(0, len(objects_to_delete), 1000):
                batch = objects_to_delete[i : i + 1000]
                response = self.client.delete_objects(
                    Bucket=self._bucket, Delete={"Objects": batch}
                )
                deleted_count += len(response.get("Deleted", []))

            logger.info(f"Invalidated {deleted_count} objects for user: {user_id}")
            return deleted_count

        except ClientError as e:
            logger.error(f"Failed to invalidate cache for user {user_id}: {e}")
            return deleted_count

    def invalidate_all_users_cache(self, user_ids: list[str]) -> dict:
        """
        Invalidate cache for multiple users (batch operation for ETL).

        Args:
            user_ids: List of user IDs to invalidate

        Returns:
            Dict with user_id -> deleted_count mapping
        """
        results = {}
        for user_id in user_ids:
            results[user_id] = self.invalidate_user_cache(user_id)
        return results

    def close(self):
        """Close S3 client (cleanup)."""
        if self._client:
            # boto3 client doesn't require explicit close
            self._client = None
            logger.info("S3 client closed")


# Singleton instance
_s3_service: Optional[S3Service] = None


def get_s3_service() -> S3Service:
    """Get S3 service singleton."""
    global _s3_service
    if _s3_service is None:
        _s3_service = S3Service()
    return _s3_service
