"""
Чтение витрины отчётности из ClickHouse (задание 4).
"""
from __future__ import annotations

import os
from datetime import date, datetime, timezone
from typing import Any

import clickhouse_connect

_client: Any = None


def get_client():
    global _client
    if _client is None:
        _client = clickhouse_connect.get_client(
            host=os.environ.get("CLICKHOUSE_HOST", "localhost"),
            port=int(os.environ.get("CLICKHOUSE_PORT", "8123")),
            database=os.environ.get("CLICKHOUSE_DATABASE", "reporting"),
            username=os.environ.get("CLICKHOUSE_USER", "default"),
            password=os.environ.get("CLICKHOUSE_PASSWORD") or "",
        )
    return _client


def mart_footprint() -> tuple[date | None, datetime | None]:
    """Снимок витрины: макс. день и время обновления (для S3-ключа и подсказок)."""
    client = get_client()
    r = client.query(
        """
        SELECT max(stat_date), max(updated_at)
        FROM reporting.mart_user_prosthesis_daily
        """
    )
    if not r.result_rows or r.result_rows[0][0] is None:
        return None, None
    d, u = r.result_rows[0][0], r.result_rows[0][1]
    if u is not None and u.tzinfo is None:
        u = u.replace(tzinfo=timezone.utc)
    elif u is not None:
        u = u.astimezone(timezone.utc)
    return d, u


def mart_rows_for_subject(subject: str) -> list[tuple[Any, ...]]:
    """Агрегаты по дням для пользователя (на случай нескольких строк за день в MergeTree)."""
    client = get_client()
    r = client.query(
        """
        SELECT
            stat_date,
            sum(active_hours) AS active_hours,
            sum(steps) AS steps,
            anyLast(prosthesis_model) AS prosthesis_model,
            anyLast(crm_region) AS crm_region
        FROM reporting.mart_user_prosthesis_daily
        WHERE user_subject = {sub:String}
        GROUP BY stat_date
        ORDER BY stat_date DESC
        LIMIT 366
        """,
        parameters={"sub": subject},
    )
    return list(r.result_rows)
