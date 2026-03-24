import os
from typing import Any

import clickhouse_connect
from clickhouse_connect.driver.client import Client
from fastapi import HTTPException, status


def create_clickhouse_client() -> Client:
    try:
        return clickhouse_connect.get_client(
            host=os.getenv("CLICKHOUSE_HOST", "localhost"),
            port=int(os.getenv("CLICKHOUSE_PORT", "8123")),
            username=os.getenv("CLICKHOUSE_USER", "default"),
            password=os.getenv("CLICKHOUSE_PASSWORD", ""),
            database=os.getenv("CLICKHOUSE_DATABASE", "default"),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to connect to analytics store",
        ) from exc


def fetch_emg_report(client: Client) -> Any:
    try:
        return client.query(
            """
            SELECT
                user_id,
                name,
                email,
                country,
                age,
                gender,
                signals_total,
                prosthesis_types,
                avg_signal_amplitude,
                avg_signal_duration,
                first_signal_time,
                last_signal_time
            FROM reporting_customer_telemetry
            ORDER BY user_id
            """
        )
    except Exception as exc:
        logger.exception("ClickHouse query failed while building report")
        raise HTTPException(status_code=500, detail="Failed to build report") from exc