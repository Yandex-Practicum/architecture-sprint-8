"""BionicPRO Reports API — serves user prosthetic usage reports from ClickHouse OLAP."""

from datetime import date
from typing import Optional

import clickhouse_connect
from fastapi import FastAPI, Depends, HTTPException, Query

from config import settings
from auth import validate_token
import s3_cache

app = FastAPI(title="BionicPRO Reports API")

_ch_client = None


def get_ch_client():
    global _ch_client
    if _ch_client is None:
        _ch_client = clickhouse_connect.get_client(
            host=settings.CLICKHOUSE_HOST,
            port=settings.CLICKHOUSE_PORT,
            database=settings.CLICKHOUSE_DB,
        )
    return _ch_client


@app.get("/reports")
async def get_reports(
    claims: dict = Depends(validate_token),
    force_refresh: bool = Query(False, description="Bypass S3 cache"),
    date_from: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
):
    """
    Get usage reports for the authenticated user.
    Users can only access their own reports (user_id from JWT 'sub' or 'preferred_username').
    """
    # Extract user identity from JWT claims
    user_id = claims.get("preferred_username") or claims.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Cannot determine user identity")

    # Check user role — only prothetic_user and administrator can access reports
    roles = claims.get("realm_access", {}).get("roles", [])
    if "prothetic_user" not in roles and "administrator" not in roles:
        raise HTTPException(
            status_code=403, detail="Insufficient permissions to access reports"
        )

    # Check S3 cache first (unless force_refresh)
    if not force_refresh and not date_from and not date_to:
        cached_url = s3_cache.check_cache(user_id)
        if cached_url:
            return {
                "user_id": user_id,
                "source": "cache",
                "download_url": cached_url,
                "message": "Report retrieved from cache. Use force_refresh=true for fresh data.",
            }

    # Check ETL metadata to see what period has been processed
    ch = get_ch_client()
    try:
        etl_result = ch.query(
            "SELECT max(last_run) as last_run FROM bionicpro.etl_metadata WHERE pipeline_name = 'etl_reports' AND status = 'success'"
        )
        last_etl_run = etl_result.result_rows[0][0] if etl_result.result_rows else None
    except Exception:
        last_etl_run = None

    # Build query — use report_datamart (CDC-fed) first, fall back to reports (ETL-fed)
    query_table = "bionicpro.report_datamart"
    where_clauses = ["user_id = {user_id:String}"]
    params = {"user_id": user_id}

    if date_from:
        where_clauses.append("order_date >= {date_from:String}")
        params["date_from"] = date_from
    if date_to:
        where_clauses.append("order_date <= {date_to:String}")
        params["date_to"] = date_to

    where_sql = " AND ".join(where_clauses)

    try:
        result = ch.query(
            f"SELECT * FROM {query_table} FINAL WHERE {where_sql} ORDER BY order_date DESC",
            parameters=params,
        )
    except Exception:
        # Fall back to reports table if report_datamart is empty
        query_table = "bionicpro.reports"
        where_clauses_reports = ["user_id = {user_id:String}"]
        if date_from:
            where_clauses_reports.append("report_date >= {date_from:String}")
        if date_to:
            where_clauses_reports.append("report_date <= {date_to:String}")
        where_sql_reports = " AND ".join(where_clauses_reports)

        result = ch.query(
            f"SELECT user_id, user_email, device_id, product_name, report_date, order_status, "
            f"total_usage_hours, active_movements, battery_cycles, avg_signal_strength, error_count "
            f"FROM {query_table} WHERE {where_sql_reports} ORDER BY report_date DESC",
            parameters=params,
        )

    # Format response
    columns = result.column_names
    reports = []
    for row in result.result_rows:
        report = dict(zip(columns, row))
        # Convert date objects to strings
        for k, v in report.items():
            if isinstance(v, date):
                report[k] = v.isoformat()
        reports.append(report)

    # Store in S3 cache if this is a full (no date filter) request
    download_url = None
    if reports and not date_from and not date_to:
        download_url = s3_cache.store_report(user_id, reports)

    response = {
        "user_id": user_id,
        "source": "olap",
        "reports": reports,
        "total_records": len(reports),
    }
    if download_url:
        response["download_url"] = download_url
    if last_etl_run:
        response["last_etl_run"] = str(last_etl_run)
    if not reports:
        response["message"] = (
            "No reports found. Data may not yet be processed by the ETL pipeline."
        )

    return response


@app.get("/health")
async def health():
    return {"status": "ok"}
