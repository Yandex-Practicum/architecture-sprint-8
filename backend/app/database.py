from typing import Any, Dict, List

import httpx

from app.config import settings


async def clickhouse_query(sql: str) -> List[Dict[str, Any]]:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            settings.clickhouse_http_url,
            content=sql.encode("utf-8"),
            headers={"Content-Type": "text/plain"},
        )
        resp.raise_for_status()

    text = resp.text.strip()
    if not text:
        return []

    lines = text.splitlines()
    if len(lines) < 2:
        return []

    header_line = lines[0]
    columns = header_line.split("\t")
    data_lines = lines[2:]

    results: List[Dict[str, Any]] = []
    for line in data_lines:
        if not line.strip():
            continue
        values = line.split("\t")
        row: Dict[str, Any] = {}
        for col, raw in zip(columns, values):
            raw = raw.strip()
            if raw == "" or raw == "\\N":
                row[col] = None
            else:
                row[col] = raw
        results.append(row)
    return results


async def get_report_by_customer(customer_id: str) -> Dict[str, Any] | None:
    sql = f"""
        SELECT
            customer_id,
            customer_name,
            customer_email,
            prosthesis_model,
            region,
            purchase_date,
            warranty_end_date,
            warranty_status,
            total_usage_hours,
            avg_daily_usage_minutes,
            total_sessions,
            total_movements,
            avg_movements_per_session,
            total_errors,
            errors_per_session,
            last_active_date,
            battery_health_avg,
            most_common_movement,
            data_as_of_date
        FROM olap_db.prosthetics_data_mart
        WHERE customer_id = '{customer_id}'
        ORDER BY data_as_of_date DESC
        LIMIT 1
    """
    rows = await clickhouse_query(sql)
    return rows[0] if rows else None


async def get_all_reports() -> List[Dict[str, Any]]:
    sql = """
        SELECT
            customer_id,
            customer_name,
            customer_email,
            prosthesis_model,
            region,
            purchase_date,
            warranty_end_date,
            warranty_status,
            total_usage_hours,
            avg_daily_usage_minutes,
            total_sessions,
            total_movements,
            avg_movements_per_session,
            total_errors,
            errors_per_session,
            last_active_date,
            battery_health_avg,
            most_common_movement,
            data_as_of_date
        FROM olap_db.prosthetics_data_mart
        ORDER BY customer_id
    """
    return await clickhouse_query(sql)
