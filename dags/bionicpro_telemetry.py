from __future__ import annotations

import logging
from typing import Optional

import clickhouse_connect
import pendulum
import psycopg2
from airflow.sdk import dag, task, BaseHook


@dag(
    schedule="@daily",
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    catchup=False,
    tags=["bionicpro"],
)
def bionicpro_telemetry() -> None:
    @task
    def extract(*, ds: Optional[str] = None) -> list[tuple[str, int, float, float]]:
        conn = BaseHook.get_connection("telemetry_db")
        client = psycopg2.connect(
            host=conn.host,
            port=conn.port,
            user=conn.login,
            password=conn.password,
            database=conn.schema,
        )
        cursor = client.cursor()
        cursor.execute("""
                       SELECT prosthesis_serial,
                              SUM(movements)               AS total_movements,
                              AVG(response_ms)             AS avg_response_ms,
                              SUM(active_seconds) / 3600.0 AS active_hours
                       FROM telemetry
                       WHERE DATE(recorded_at) = (DATE %s - INTERVAL '1 day')
                       GROUP BY prosthesis_serial
                       """, (ds,))
        rows = cursor.fetchall()
        cursor.close()
        client.close()

        return rows

    @task
    def load(
            summary_list: list[tuple[str, int, float, float]],
            *,
            ds: Optional[str] = None,
            ts: Optional[str] = None,
            run_id: Optional[str] = None,
    ) -> None:
        conn = BaseHook.get_connection("clickhouse_db")
        client = clickhouse_connect.get_client(
            host=conn.host,
            port=conn.port,
            username=conn.login,
            password=conn.password,
            database=conn.schema,
        )

        if ds is None:
            logging.error("ds is None, skipping load")
            return

        if ts is None:
            logging.error("ts is None, skipping load")
            return

        if run_id is None:
            logging.error("run_id is None, skipping load")
            return

        recorded_date = pendulum.Date.fromisoformat(ds)
        processed_at = pendulum.DateTime.fromisoformat(ts)
        client.insert(
            "daily_telemetry",
            [summary_element + (recorded_date, run_id, processed_at) for summary_element in summary_list],
            column_names=[
                "prosthesis_serial",
                "total_movements",
                "avg_response_ms",
                "active_hours",
                "recorded_date",
                "airflow_run_id",
                "processed_at",
            ],
        )

    data = extract()
    load(data)


bionicpro_telemetry()
