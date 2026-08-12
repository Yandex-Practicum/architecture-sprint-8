from typing import Optional

import clickhouse_connect

from .config import settings

_client = clickhouse_connect.get_client(
    host=settings.clickhouse_host,
    port=settings.clickhouse_port,
    username=settings.clickhouse_user,
    password=settings.clickhouse_password,
)

_COLUMNS = [
    "customer_id", "report_generated_at", "full_name", "region",
    "prosthesis_model", "events_count", "avg_myosignal_quality",
    "avg_recognition_latency_ms", "min_battery_level", "last_action_recognized",
]


def get_latest_report(customer_id: str) -> Optional[dict]:
    """Читает последнюю строку отчёта, обработанную ETL, для клиента.

    Всегда читает только предварительно агрегированную витрину - никогда не
    обращается к исходным базам CRM/телеметрии и не вычисляет агрегаты на лету.
    """
    query = f"""
        SELECT {", ".join(_COLUMNS)}
        FROM reports.user_report_mart_v2
        WHERE customer_id = {{customer_id:String}}
        ORDER BY report_generated_at DESC
        LIMIT 1
    """
    result = _client.query(query, parameters={"customer_id": customer_id})
    if not result.result_rows:
        return None
    row = result.result_rows[0]
    report = dict(zip(_COLUMNS, row))
    report["report_generated_at"] = report["report_generated_at"].isoformat()
    return report
