import json
from typing import Optional

import redis

from .config import settings

_redis = redis.from_url(settings.redis_url, decode_responses=True)

_PREFIX = "reports-api:latest:"


def get_cached_pointer(customer_id: str) -> Optional[dict]:
    """Короткоживущий указатель на последние известные report_generated_at/object_key
    для клиента. Позволяет повторным запросам полностью пропускать ClickHouse - TTL
    (короче часового цикла ETL) ограничивает, сколько времени запрос может идти
    без повторной проверки на наличие более свежего обработанного отчёта.
    """
    raw = _redis.get(_PREFIX + customer_id)
    return json.loads(raw) if raw else None


def set_cached_pointer(customer_id: str, report_generated_at: str, object_key: str) -> None:
    _redis.set(
        _PREFIX + customer_id,
        json.dumps({"report_generated_at": report_generated_at, "object_key": object_key}),
        ex=settings.pointer_cache_ttl_seconds,
    )
