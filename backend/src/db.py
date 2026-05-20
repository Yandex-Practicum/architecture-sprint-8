from typing import Any

import clickhouse_driver

from src.config import CLICKHOUSE_DB, CLICKHOUSE_HOST, CLICKHOUSE_PORT

_COLUMNS = [
    "user_id", "device_id", "client_name", "client_email",
    "prosthesis_model", "purchase_date", "total_sessions",
    "total_movements", "last_activity", "avg_signal_quality", "report_date",
]


def get_client() -> clickhouse_driver.Client:
    return clickhouse_driver.Client(
        host=CLICKHOUSE_HOST,
        port=CLICKHOUSE_PORT,
        database=CLICKHOUSE_DB,
    )


def rows_to_dicts(rows: list[tuple]) -> list[dict[str, Any]]:
    result = []
    for row in rows:
        item: dict[str, Any] = dict(zip(_COLUMNS, row))
        for date_field in ("purchase_date", "last_activity", "report_date"):
            if item.get(date_field) is not None:
                item[date_field] = str(item[date_field])
        result.append(item)
    return result
