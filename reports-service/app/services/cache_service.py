"""
Redis cache service for Reports Service.
"""

import json
import logging
from typing import Optional, Any
from datetime import date

import redis

from app.config import get_settings

logger = logging.getLogger(__name__)


class CacheService:
    """Redis cache service for caching report data."""

    def __init__(self):
        self.settings = get_settings()
        self._client: Optional[redis.Redis] = None

    def _get_client(self) -> redis.Redis:
        """Get or create Redis client connection."""
        if self._client is None:
            self._client = redis.Redis(
                host=self.settings.redis_host,
                port=self.settings.redis_port,
                db=self.settings.redis_db,
                decode_responses=True,
            )
        return self._client

    def close(self):
        """Close the connection."""
        if self._client:
            self._client.close()
            self._client = None

    def _make_key(self, prefix: str, *args) -> str:
        """Create a cache key from prefix and arguments."""
        parts = [prefix] + [str(arg) for arg in args]
        return ":".join(parts)

    def _serialize(self, data: Any) -> str:
        """Serialize data to JSON string."""
        return json.dumps(data, default=str)

    def _deserialize(self, data: str) -> Any:
        """Deserialize JSON string to data."""
        return json.loads(data)

    def get(self, key: str) -> Optional[Any]:
        """
        Get cached value by key.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found
        """
        try:
            client = self._get_client()
            data = client.get(key)
            if data:
                logger.debug(f"Cache hit for key: {key}")
                return self._deserialize(data)
            logger.debug(f"Cache miss for key: {key}")
            return None
        except redis.RedisError as e:
            logger.warning(f"Redis get error: {e}")
            return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Set cached value with optional TTL.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (default from settings)

        Returns:
            True if successful
        """
        try:
            client = self._get_client()
            ttl = ttl or self.settings.cache_ttl_seconds
            data = self._serialize(value)
            client.setex(key, ttl, data)
            logger.debug(f"Cache set for key: {key}, ttl: {ttl}s")
            return True
        except redis.RedisError as e:
            logger.warning(f"Redis set error: {e}")
            return False

    def delete(self, key: str) -> bool:
        """Delete cached value by key."""
        try:
            client = self._get_client()
            client.delete(key)
            return True
        except redis.RedisError as e:
            logger.warning(f"Redis delete error: {e}")
            return False

    def invalidate_user_cache(self, user_id: str) -> int:
        """
        Invalidate all cached data for a user.

        Args:
            user_id: User identifier

        Returns:
            Number of keys deleted
        """
        try:
            client = self._get_client()
            pattern = f"reports:{user_id}:*"
            keys = client.keys(pattern)
            if keys:
                return client.delete(*keys)
            return 0
        except redis.RedisError as e:
            logger.warning(f"Redis invalidate error: {e}")
            return 0

    # ========================================================================
    # Report-specific cache methods
    # ========================================================================

    def get_reports_list(self, user_id: str) -> Optional[dict]:
        """Get cached reports list for user."""
        key = self._make_key("reports", user_id, "list")
        return self.get(key)

    def set_reports_list(self, user_id: str, data: dict) -> bool:
        """Cache reports list for user."""
        key = self._make_key("reports", user_id, "list")
        return self.set(key, data)

    def get_daily_report(self, user_id: str, report_date: date) -> Optional[dict]:
        """Get cached daily report."""
        key = self._make_key("reports", user_id, "daily", str(report_date))
        return self.get(key)

    def set_daily_report(self, user_id: str, report_date: date, data: dict) -> bool:
        """Cache daily report."""
        key = self._make_key("reports", user_id, "daily", str(report_date))
        return self.set(key, data)

    def get_user_summary(self, user_id: str) -> Optional[dict]:
        """Get cached user summary."""
        key = self._make_key("reports", user_id, "summary")
        return self.get(key)

    def set_user_summary(self, user_id: str, data: dict) -> bool:
        """Cache user summary."""
        key = self._make_key("reports", user_id, "summary")
        return self.set(key, data)

    def health_check(self) -> bool:
        """Check if Redis is available."""
        try:
            client = self._get_client()
            return client.ping()
        except redis.RedisError as e:
            logger.error(f"Redis health check failed: {e}")
            return False


# Singleton instance
_cache_service: Optional[CacheService] = None


def get_cache_service() -> CacheService:
    """Get singleton cache service instance."""
    global _cache_service
    if _cache_service is None:
        _cache_service = CacheService()
    return _cache_service
