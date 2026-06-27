from __future__ import annotations

import os
import re
from datetime import datetime, time, timedelta
from typing import Any, Iterable

import pendulum
import psycopg2
from airflow.decorators import dag, task
from airflow.operators.python import get_current_context
from clickhouse_driver import Client


DAG_ID = "bionicpro_reports_mart"
LOCAL_TZ = pendulum.timezone("Europe/Belgrade")

OLAP_DATABASE = os.getenv("REPORT_OLAP_DATABASE", "bionicpro")
CRM_DSN_ENV = "CRM_DB_DSN"
TELEMETRY_DSN_ENV = "TELEMETRY_DB_DSN"


def _checked_identifier(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise ValueError(f"Unsafe ClickHouse identifier: {value!r}")
    return f"`{value}`"


def _olap_table(name: str) -> str:
    return f"{_checked_identifier(OLAP_DATABASE)}.{_checked_identifier(name)}"


def _clickhouse_client(database: str = "default") -> Client:
    return Client(
        host=os.getenv("CLICKHOUSE_HOST", "clickhouse"),
        port=int(os.getenv("CLICKHOUSE_PORT", "9000")),
        user=os.getenv("CLICKHOUSE_USER", "default"),
        password=os.getenv("CLICKHOUSE_PASSWORD", ""),
        database=database,
        settings={"use_numpy": False},
    )


def _postgres_conn(dsn_env_name: str):
    dsn = os.getenv(dsn_env_name)
    if not dsn:
        raise RuntimeError(f"{dsn_env_name} is not configured")
    return psycopg2.connect(dsn)


def _utc_naive(value: Any) -> datetime:
    if hasattr(value, "in_timezone"):
        return value.in_timezone("UTC").replace(tzinfo=None)
    if value.tzinfo is not None:
        return value.astimezone(pendulum.timezone("UTC")).replace(tzinfo=None)
    return value


def _current_interval() -> tuple[datetime, datetime]:
    context = get_current_context()
    return (
        _utc_naive(context["data_interval_start"]),
        _utc_naive(context["data_interval_end"]),
    )


def _report_window(interval_end: datetime) -> tuple[datetime, datetime]:
    lookback_days = int(os.getenv("REPORT_MART_LOOKBACK_DAYS", "1"))
    last_affected_day = (interval_end - timedelta(microseconds=1)).date()
    first_affected_day = last_affected_day - timedelta(days=lookback_days - 1)

    return (
        datetime.combine(first_affected_day, time.min),
        datetime.combine(last_affected_day + timedelta(days=1), time.min),
    )


def _insert_rows(client: Client, table: str, columns: Iterable[str], rows: list[tuple[Any, ...]]) -> int:
    if not rows:
        return 0

    column_list = ", ".join(_checked_identifier(column) for column in columns)
    client.execute(f"INSERT INTO {table} ({column_list}) VALUES", rows)
    return len(rows)


@dag(
    dag_id=DAG_ID,
    description="Builds the BionicPRO user report mart from CRM and prosthesis telemetry.",
    schedule="0 * * * *",
    start_date=pendulum.datetime(2026, 1, 1, tz=LOCAL_TZ),
    catchup=False,
    max_active_runs=1,
    default_args={
        "owner": "bionicpro-data-platform",
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
    },
    tags=["bionicpro", "reports", "etl", "clickhouse"],
)
def bionicpro_reports_mart() -> None:
    @task
    def prepare_olap_schema() -> None:
        client = _clickhouse_client()
        database = _checked_identifier(OLAP_DATABASE)

        client.execute(f"CREATE DATABASE IF NOT EXISTS {database}")
        client = _clickhouse_client(database=OLAP_DATABASE)

        client.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {_olap_table("stg_crm_clients")}
            (
                client_id String,
                user_id String,
                prosthesis_id String,
                full_name String,
                email String,
                phone String,
                country LowCardinality(String),
                prosthesis_model String,
                order_status LowCardinality(String),
                fitted_at Nullable(DateTime),
                crm_updated_at DateTime,
                loaded_at DateTime
            )
            ENGINE = ReplacingMergeTree(loaded_at)
            ORDER BY (user_id, prosthesis_id)
            """
        )

        client.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {_olap_table("stg_telemetry_events")}
            (
                event_id String,
                prosthesis_id String,
                event_time DateTime,
                movement LowCardinality(String),
                response_ms Float64,
                battery_percent Float64,
                signal_quality Float64,
                error_code Nullable(String),
                source_updated_at DateTime,
                loaded_at DateTime
            )
            ENGINE = ReplacingMergeTree(loaded_at)
            PARTITION BY toYYYYMM(event_time)
            ORDER BY (prosthesis_id, event_time, event_id)
            """
        )

        client.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {_olap_table("report_user_prosthesis_daily")}
            (
                report_date Date,
                user_id String,
                client_id String,
                prosthesis_id String,
                full_name String,
                email String,
                country LowCardinality(String),
                prosthesis_model String,
                events_count UInt64,
                active_minutes UInt64,
                avg_response_ms Float64,
                p95_response_ms Float64,
                avg_battery_percent Float64,
                min_battery_percent Float64,
                avg_signal_quality Float64,
                error_events UInt64,
                last_event_at DateTime,
                mart_updated_at DateTime
            )
            ENGINE = ReplacingMergeTree(mart_updated_at)
            PARTITION BY toYYYYMM(report_date)
            ORDER BY (user_id, report_date, prosthesis_id)
            """
        )

    @task
    def extract_crm_clients() -> int:
        _, interval_end = _current_interval()
        loaded_at = datetime.utcnow()

        query = """
            SELECT
                c.client_id::text,
                c.user_id::text,
                p.prosthesis_id::text,
                concat_ws(' ', c.first_name, c.last_name) AS full_name,
                COALESCE(c.email, '') AS email,
                COALESCE(c.phone, '') AS phone,
                COALESCE(c.country, '') AS country,
                COALESCE(p.model, '') AS prosthesis_model,
                COALESCE(p.order_status, '') AS order_status,
                p.fitted_at,
                GREATEST(c.updated_at, p.updated_at) AS crm_updated_at
            FROM crm_clients c
            JOIN crm_prostheses p ON p.client_id = c.client_id
            WHERE GREATEST(c.updated_at, p.updated_at) < %(interval_end)s
        """

        conn = _postgres_conn(CRM_DSN_ENV)
        try:
            with conn.cursor() as cursor:
                cursor.execute(query, {"interval_end": interval_end})
                rows = [tuple(row) + (loaded_at,) for row in cursor.fetchall()]
        finally:
            conn.close()

        return _insert_rows(
            _clickhouse_client(database=OLAP_DATABASE),
            _olap_table("stg_crm_clients"),
            (
                "client_id",
                "user_id",
                "prosthesis_id",
                "full_name",
                "email",
                "phone",
                "country",
                "prosthesis_model",
                "order_status",
                "fitted_at",
                "crm_updated_at",
                "loaded_at",
            ),
            rows,
        )

    @task
    def extract_telemetry_events() -> int:
        _, interval_end = _current_interval()
        report_window_start, _ = _report_window(interval_end)
        loaded_at = datetime.utcnow()

        query = """
            SELECT
                event_id::text,
                prosthesis_id::text,
                event_time,
                COALESCE(movement, '') AS movement,
                COALESCE(response_ms, 0)::double precision,
                COALESCE(battery_percent, 0)::double precision,
                COALESCE(signal_quality, 0)::double precision,
                error_code,
                updated_at AS source_updated_at
            FROM prosthesis_telemetry
            WHERE event_time >= %(report_window_start)s
              AND event_time < %(interval_end)s
        """

        conn = _postgres_conn(TELEMETRY_DSN_ENV)
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    query,
                    {
                        "report_window_start": report_window_start,
                        "interval_end": interval_end,
                    },
                )
                rows = [tuple(row) + (loaded_at,) for row in cursor.fetchall()]
        finally:
            conn.close()

        return _insert_rows(
            _clickhouse_client(database=OLAP_DATABASE),
            _olap_table("stg_telemetry_events"),
            (
                "event_id",
                "prosthesis_id",
                "event_time",
                "movement",
                "response_ms",
                "battery_percent",
                "signal_quality",
                "error_code",
                "source_updated_at",
                "loaded_at",
            ),
            rows,
        )

    @task
    def build_report_mart() -> None:
        _, interval_end = _current_interval()
        report_window_start, report_window_end = _report_window(interval_end)
        client = _clickhouse_client(database=OLAP_DATABASE)

        client.execute(
            f"""
            ALTER TABLE {_olap_table("report_user_prosthesis_daily")}
            DELETE
            WHERE report_date >= toDate(%(report_window_start)s)
              AND report_date < toDate(%(report_window_end)s)
            """,
            {
                "report_window_start": report_window_start,
                "report_window_end": report_window_end,
            },
            settings={"mutations_sync": 1},
        )

        client.execute(
            f"""
            INSERT INTO {_olap_table("report_user_prosthesis_daily")}
            SELECT
                toDate(t.event_time) AS report_date,
                c.user_id,
                c.client_id,
                t.prosthesis_id,
                anyLast(c.full_name) AS full_name,
                anyLast(c.email) AS email,
                anyLast(c.country) AS country,
                anyLast(c.prosthesis_model) AS prosthesis_model,
                count() AS events_count,
                uniqExact(toStartOfMinute(t.event_time)) AS active_minutes,
                avg(t.response_ms) AS avg_response_ms,
                quantileTDigest(0.95)(t.response_ms) AS p95_response_ms,
                avg(t.battery_percent) AS avg_battery_percent,
                min(t.battery_percent) AS min_battery_percent,
                avg(t.signal_quality) AS avg_signal_quality,
                countIf(t.error_code IS NOT NULL AND t.error_code != '') AS error_events,
                max(t.event_time) AS last_event_at,
                now() AS mart_updated_at
            FROM {_olap_table("stg_telemetry_events")} AS t
            ANY INNER JOIN {_olap_table("stg_crm_clients")} FINAL AS c
                ON c.prosthesis_id = t.prosthesis_id
            WHERE t.event_time >= toDateTime(%(report_window_start)s)
              AND t.event_time < toDateTime(%(interval_end)s)
            GROUP BY
                report_date,
                c.user_id,
                c.client_id,
                t.prosthesis_id
            """,
            {
                "report_window_start": report_window_start,
                "interval_end": interval_end,
            },
        )

    schema = prepare_olap_schema()
    crm = extract_crm_clients()
    telemetry = extract_telemetry_events()
    mart = build_report_mart()

    schema >> [crm, telemetry]
    crm >> mart
    telemetry >> mart


bionicpro_reports_mart()
