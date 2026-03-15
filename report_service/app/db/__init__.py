# app/db/__init__.py
from app.db.clickhouse import clickhouse_client

__all__ = ["clickhouse_client"]