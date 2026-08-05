from __future__ import annotations

import json
from datetime import timedelta

import requests
from airflow.decorators import dag, task
from airflow.providers.postgres.hooks.postgres import PostgresHook
from pendulum import datetime as pendulum_datetime

CLICKHOUSE_URL = "http://clickhouse:8123/"
CRM_CONN_ID = "crm_db"


@dag(
    dag_id="crm_telemetry_etl",
    description="Aggregate telemetry into ClickHouse; customer dimension now arrives via CDC",
    schedule="@hourly",
    start_date=pendulum_datetime(2026, 8, 1, tz="UTC"),
    catchup=False,
    default_args={"retries": 1, "retry_delay": timedelta(minutes=2)},
    tags=["bionicpro", "reports"],
)
def crm_telemetry_etl():

    @task
    def aggregate_telemetry(data_interval_start=None, data_interval_end=None) -> list[dict]:
        hook = PostgresHook(postgres_conn_id=CRM_CONN_ID)
        rows = hook.get_records(
            """
            SELECT customer_username,
                   count(id) AS events_count,
                   avg(latency_ms) AS avg_latency_ms,
                   avg(signal_quality) AS avg_signal_quality
            FROM telemetry_events
            WHERE event_time >= %(period_start)s AND event_time < %(period_end)s
            GROUP BY customer_username
            """,
            parameters={"period_start": data_interval_start, "period_end": data_interval_end},
        )
        return [
            {
                "username": r[0],
                "events_count": r[1],
                "avg_latency_ms": float(r[2]),
                "avg_signal_quality": float(r[3]),
                "period_start": data_interval_start.strftime("%Y-%m-%d %H:%M:%S"),
                "period_end": data_interval_end.strftime("%Y-%m-%d %H:%M:%S"),
            }
            for r in rows
        ]

    @task
    def load_telemetry_agg(rows: list[dict], data_interval_start=None, data_interval_end=None):
        if not rows:
            return

        usernames = ",".join(f"'{r['username']}'" for r in rows)
        period_start = data_interval_start.strftime("%Y-%m-%d %H:%M:%S")
        delete_query = (
            f"ALTER TABLE reports.telemetry_agg DELETE "
            f"WHERE period_start = '{period_start}' AND username IN ({usernames})"
        )
        delete_resp = requests.post(CLICKHOUSE_URL, data=delete_query)
        delete_resp.raise_for_status()

        payload = "\n".join(json.dumps(row) for row in rows)
        insert_resp = requests.post(
            CLICKHOUSE_URL,
            params={"query": "INSERT INTO reports.telemetry_agg FORMAT JSONEachRow"},
            data=payload,
        )
        insert_resp.raise_for_status()

    load_telemetry_agg(aggregate_telemetry())


crm_telemetry_etl()
