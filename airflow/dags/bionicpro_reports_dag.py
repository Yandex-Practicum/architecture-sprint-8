from __future__ import annotations

import csv
import pathlib
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator


CLICKHOUSE_URL = "http://clickhouse:8123"
DATABASE = "bionicpro"
DATA_DIR = pathlib.Path(__file__).parent / "data"


def clickhouse(sql: str, database: str | None = DATABASE) -> str:
    params = {"query": sql}
    if database:
        params["database"] = database
    url = f"{CLICKHOUSE_URL}/?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, data=b"", timeout=30) as response:
        return response.read().decode("utf-8")


def quote(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def create_tables() -> None:
    clickhouse("CREATE DATABASE IF NOT EXISTS bionicpro", database=None)
    clickhouse(
        """
        CREATE TABLE IF NOT EXISTS crm_customers
        (
            user_id String,
            user_name String,
            email String,
            prosthesis_id String,
            country_code LowCardinality(String),
            updated_at DateTime
        )
        ENGINE = MergeTree
        ORDER BY (user_id, prosthesis_id)
        """
    )
    clickhouse(
        """
        CREATE TABLE IF NOT EXISTS prosthesis_telemetry
        (
            event_time DateTime,
            user_id String,
            prosthesis_id String,
            movement String,
            reaction_ms UInt16,
            battery_level UInt8
        )
        ENGINE = MergeTree
        ORDER BY (user_id, prosthesis_id, event_time)
        """
    )
    clickhouse(
        """
        CREATE TABLE IF NOT EXISTS report_mart
        (
            user_id String,
            user_name String,
            email String,
            prosthesis_id String,
            period_start DateTime,
            period_end DateTime,
            events_count UInt64,
            avg_reaction_ms Float64,
            min_battery_level UInt8,
            last_prepared_at DateTime
        )
        ENGINE = ReplacingMergeTree(last_prepared_at)
        ORDER BY (user_id, prosthesis_id, period_end)
        """
    )


def load_crm() -> None:
    rows = []
    with (DATA_DIR / "crm_customers.csv").open() as file:
        for row in csv.DictReader(file):
            rows.append(
                "("
                + ", ".join(
                    [
                        quote(row["user_id"]),
                        quote(row["user_name"]),
                        quote(row["email"]),
                        quote(row["prosthesis_id"]),
                        quote(row["country_code"]),
                        quote(row["updated_at"]),
                    ]
                )
                + ")"
            )

    clickhouse("TRUNCATE TABLE crm_customers")
    clickhouse(
        """
        INSERT INTO crm_customers
        (user_id, user_name, email, prosthesis_id, country_code, updated_at)
        VALUES
        """
        + ", ".join(rows)
    )


def load_telemetry() -> None:
    rows = []
    with (DATA_DIR / "prosthesis_telemetry.csv").open() as file:
        for row in csv.DictReader(file):
            rows.append(
                "("
                + ", ".join(
                    [
                        quote(row["event_time"]),
                        quote(row["user_id"]),
                        quote(row["prosthesis_id"]),
                        quote(row["movement"]),
                        row["reaction_ms"],
                        row["battery_level"],
                    ]
                )
                + ")"
            )

    clickhouse("TRUNCATE TABLE prosthesis_telemetry")
    clickhouse(
        """
        INSERT INTO prosthesis_telemetry
        (event_time, user_id, prosthesis_id, movement, reaction_ms, battery_level)
        VALUES
        """
        + ", ".join(rows)
    )


def build_report_mart() -> None:
    clickhouse("TRUNCATE TABLE report_mart")
    clickhouse(
        """
        INSERT INTO report_mart
        SELECT
            c.user_id,
            c.user_name,
            c.email,
            c.prosthesis_id,
            min(t.event_time) AS period_start,
            max(t.event_time) AS period_end,
            count() AS events_count,
            round(avg(t.reaction_ms), 2) AS avg_reaction_ms,
            min(t.battery_level) AS min_battery_level,
            now() AS last_prepared_at
        FROM crm_customers AS c
        INNER JOIN prosthesis_telemetry AS t
            ON c.user_id = t.user_id
            AND c.prosthesis_id = t.prosthesis_id
        GROUP BY
            c.user_id,
            c.user_name,
            c.email,
            c.prosthesis_id
        """
    )


with DAG(
    dag_id="bionicpro_reports_etl",
    description="Prepare BionicPRO report mart from CRM and prosthesis telemetry",
    start_date=datetime(2026, 6, 18),
    schedule_interval="0 * * * *",
    catchup=False,
    default_args={
        "owner": "bionicpro",
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
    },
    tags=["bionicpro", "reports"],
) as dag:
    create_tables_task = PythonOperator(
        task_id="create_clickhouse_tables",
        python_callable=create_tables,
    )

    load_crm_task = PythonOperator(
        task_id="load_crm_customers",
        python_callable=load_crm,
    )

    load_telemetry_task = PythonOperator(
        task_id="load_prosthesis_telemetry",
        python_callable=load_telemetry,
    )

    build_mart_task = PythonOperator(
        task_id="build_report_mart",
        python_callable=build_report_mart,
    )

    create_tables_task >> [load_crm_task, load_telemetry_task] >> build_mart_task
