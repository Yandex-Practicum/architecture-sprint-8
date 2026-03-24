import datetime
import decimal
from typing import Iterable

from clickhouse_connect.driver.query import QueryResult


def _format_value(value) -> str:
    if isinstance(value, datetime.datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, decimal.Decimal):
        return format(value, "f")
    return str(value)


def report_to_csv_stream(result: QueryResult) -> Iterable[str]:
    yield ",".join(result.column_names) + "\n"
    for row in result.result_rows:
        yield ",".join(_format_value(value) for value in row) + "\n"