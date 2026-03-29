from __future__ import annotations

import os
from datetime import datetime, timedelta

import clickhouse_connect
import pendulum
import psycopg2
from airflow.decorators import dag, task
from airflow.operators.python import get_current_context


TELEMETRY_DB_DSN = os.environ["TELEMETRY_DB_DSN"]
CLICKHOUSE_HOST = os.environ["CLICKHOUSE_HOST"]
CLICKHOUSE_PORT = int(os.environ.get("CLICKHOUSE_PORT", "8123"))
CLICKHOUSE_DATABASE = os.environ.get("CLICKHOUSE_DATABASE", "reporting")
CLICKHOUSE_USERNAME = os.environ.get("CLICKHOUSE_USERNAME", "default")
CLICKHOUSE_PASSWORD = os.environ.get("CLICKHOUSE_PASSWORD", "")
REPORT_DATASET_NAME = os.environ.get("REPORT_DATASET_NAME", "user_daily_reports_cdc")


def _fetch_rows(dsn: str, query: str, params: tuple | None = None) -> list[dict]:
    with psycopg2.connect(dsn) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            columns = [description[0] for description in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _clickhouse_client():
    return clickhouse_connect.get_client(
        host=CLICKHOUSE_HOST,
        port=CLICKHOUSE_PORT,
        database=CLICKHOUSE_DATABASE,
        username=CLICKHOUSE_USERNAME,
        password=CLICKHOUSE_PASSWORD,
    )


def _object_exists(client, object_name: str, object_type: str) -> bool:
    result = client.query(
        """
        SELECT count()
        FROM system.tables
        WHERE database = 'reporting'
          AND name = {name:String}
          AND engine = {engine:String}
        """,
        parameters={"name": object_name, "engine": object_type},
    )
    return bool(result.result_rows and result.result_rows[0][0] > 0)


@dag(
    dag_id="bionicpro_reporting_etl",
    schedule="*/15 * * * *",
    start_date=pendulum.datetime(2026, 3, 1, tz="UTC"),
    catchup=False,
    tags=["bionicpro", "reporting"],
)
def bionicpro_reporting_etl():
    @task()
    def ensure_reporting_schema() -> None:
        client = _clickhouse_client()
        client.command("CREATE DATABASE IF NOT EXISTS reporting")
        client.command(
            """
            CREATE TABLE IF NOT EXISTS reporting.telemetry_daily_rollups (
                prosthesis_id String,
                report_date Date,
                usage_minutes UInt32,
                motion_events UInt32,
                average_battery_pct Float32,
                average_signal_quality Float32,
                calibration_sessions UInt32,
                alerts_count UInt32,
                loaded_at DateTime
            )
            ENGINE = ReplacingMergeTree(loaded_at)
            ORDER BY (prosthesis_id, report_date)
            """
        )
        client.command(
            """
            CREATE TABLE IF NOT EXISTS reporting.user_daily_reports_cdc (
                username String,
                email String,
                full_name String,
                country String,
                city String,
                prosthesis_id String,
                prosthesis_model String,
                support_tier String,
                fitted_at Date,
                last_service_date Date,
                report_date Date,
                usage_minutes UInt32,
                motion_events UInt32,
                average_battery_pct Float32,
                average_signal_quality Float32,
                calibration_sessions UInt32,
                alerts_count UInt32,
                loaded_at DateTime
            )
            ENGINE = ReplacingMergeTree(loaded_at)
            ORDER BY (username, report_date, prosthesis_id)
            """
        )
        client.command(
            """
            CREATE TABLE IF NOT EXISTS reporting.reporting_load_windows (
                dataset String,
                available_from Date,
                available_to Date,
                loaded_at DateTime,
                dag_run_id String
            )
            ENGINE = ReplacingMergeTree(loaded_at)
            ORDER BY dataset
            """
        )

        required_objects = [
            ("crm_customers_current", "View"),
            ("crm_prostheses_current", "View"),
            ("user_daily_reports_cdc_mv", "MaterializedView"),
        ]
        missing = [
            name
            for name, engine in required_objects
            if not _object_exists(client, name, engine)
        ]
        client.close()

        if missing:
            raise ValueError(
                "ClickHouse CDC schema is not initialized. Missing objects: "
                + ", ".join(missing)
                + ". Apply clickhouse/init/01_reporting_cdc.sql or restart ClickHouse with a clean volume."
            )

    @task()
    def build_reporting_mart() -> dict[str, str]:
        context = get_current_context()
        processed_to = context["data_interval_end"].date() - timedelta(days=1)
        loaded_at = datetime.utcnow().replace(microsecond=0)

        telemetry_rows = _fetch_rows(
            TELEMETRY_DB_DSN,
            """
            SELECT
                prosthesis_id,
                DATE(event_ts) AS report_date,
                SUM(usage_minutes) AS usage_minutes,
                SUM(motion_events) AS motion_events,
                ROUND(AVG(battery_pct)::numeric, 2) AS average_battery_pct,
                ROUND(AVG(signal_quality)::numeric, 3) AS average_signal_quality,
                SUM(calibration_sessions) AS calibration_sessions,
                SUM(alerts_count) AS alerts_count
            FROM telemetry_events
            WHERE DATE(event_ts) <= %s
            GROUP BY prosthesis_id, DATE(event_ts)
            ORDER BY prosthesis_id, DATE(event_ts)
            """,
            (processed_to,),
        )

        if not telemetry_rows:
            raise ValueError("Telemetry rows are missing, reporting load cannot proceed.")

        telemetry_columns = [
            "prosthesis_id",
            "report_date",
            "usage_minutes",
            "motion_events",
            "average_battery_pct",
            "average_signal_quality",
            "calibration_sessions",
            "alerts_count",
            "loaded_at",
        ]
        telemetry_values = [
            [
                row["prosthesis_id"],
                row["report_date"],
                int(row["usage_minutes"]),
                int(row["motion_events"]),
                float(row["average_battery_pct"]),
                float(row["average_signal_quality"]),
                int(row["calibration_sessions"]),
                int(row["alerts_count"]),
                loaded_at,
            ]
            for row in telemetry_rows
        ]

        client = _clickhouse_client()
        client.command("TRUNCATE TABLE reporting.telemetry_daily_rollups")
        client.command("TRUNCATE TABLE reporting.user_daily_reports_cdc")
        client.command("TRUNCATE TABLE reporting.reporting_load_windows")
        client.insert(
            "reporting.telemetry_daily_rollups",
            telemetry_values,
            column_names=telemetry_columns,
        )

        mart_stats = client.query(
            """
            SELECT
                min(report_date),
                max(report_date),
                count()
            FROM reporting.user_daily_reports_cdc
            """
        )
        available_from, available_to, mart_row_count = mart_stats.result_rows[0]
        if mart_row_count == 0:
            client.close()
            raise ValueError(
                "CDC mart is empty after telemetry load. "
                "Check Debezium connector, Kafka topics, and ClickHouse consumer views."
            )

        client.insert(
            "reporting.reporting_load_windows",
            [[REPORT_DATASET_NAME, available_from, available_to, loaded_at, context["run_id"]]],
            column_names=["dataset", "available_from", "available_to", "loaded_at", "dag_run_id"],
        )
        client.close()
        return {
            "available_from": available_from.isoformat(),
            "available_to": available_to.isoformat(),
            "loaded_at": loaded_at.isoformat(),
            "rows_loaded": str(mart_row_count),
        }

    ensure_reporting_schema() >> build_reporting_mart()


bionicpro_reporting_etl()
