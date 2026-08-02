from datetime import datetime
from pathlib import Path

import pandas as pd
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.common.sql.operators.sql import SQLExecuteQueryOperator

CLICKHOUSE_TABLE = "reports"


def generate_insert_queries():
    DATA_DIR = Path("/opt/airflow/dags/data")
    CLIENTS_CSV = DATA_DIR / "clients.csv"
    METRICS_CSV = DATA_DIR / "metrics.csv"
    SQL_DIR = Path("/opt/airflow/dags/sql")
    SQL_DIR.mkdir(exist_ok=True)

    clients_df = pd.read_csv(CLIENTS_CSV)
    metrics_df = pd.read_csv(METRICS_CSV)

    metrics_df["timestamp"] = pd.to_datetime(metrics_df["timestamp"])
    metrics_df["metric_date"] = metrics_df["timestamp"].dt.date

    aggregated = (
        metrics_df.groupby(["username", "metric_date"])
        .agg(
            avg_response_time_ms=("response_time_ms", "mean"),
            max_response_time_ms=("response_time_ms", "max"),
            signals_count=("response_time_ms", "count"),
            battery_avg_level=("battery_level", "mean"),
        )
        .reset_index()
    )

    aggregated["avg_response_time_ms"] = aggregated["avg_response_time_ms"].round(2)
    aggregated["battery_avg_level"] = (
        aggregated["battery_avg_level"].round(0).astype(int)
    )

    result_df = aggregated.merge(
        clients_df[["username", "email", "prosthetic_id"]], on="username", how="left"
    )

    def format_row(row):
        return "('{}', '{}', {}, {}, {}, {}, '{}', '{}')".format(
            row['username'].replace("'", "''"),
            row['metric_date'],
            row['avg_response_time_ms'],
            row['max_response_time_ms'],
            row['signals_count'],
            row['battery_avg_level'],
            row['email'].replace("'", "''"),
            row['prosthetic_id'].replace("'", "''")
        )
    
    values_str = ",\n".join(result_df.apply(format_row, axis=1).tolist())
    
    insert_query = f"""
    INSERT INTO {CLICKHOUSE_TABLE} (
        username, metric_date, avg_response_time_ms, max_response_time_ms,
        signals_count, battery_avg_level, user_email, prosthetic_id
    ) VALUES
    {values_str}
    """
    
    SQL_FILE = SQL_DIR / "insert_queries.sql"
    with open(SQL_FILE, "w") as f:
        f.write(insert_query)
    
    print(f"Generated {len(result_df)} rows in single INSERT")


with DAG(
    "prosthetic_reports_dag",
    start_date=datetime(2026, 6, 1),  # noqa: DTZ001
    schedule_interval="0 * * * *",
    catchup=False,
    max_active_runs=1,
    description="Формирование отчетов по биопротезам",
) as dag:
    create_table = SQLExecuteQueryOperator(
        task_id="create_table",
        sql=f"""
        CREATE TABLE IF NOT EXISTS {CLICKHOUSE_TABLE} (
            username String,
            metric_date Date,
            avg_response_time_ms Float32,
            max_response_time_ms Float32,
            signals_count UInt32,
            battery_avg_level UInt8,
            user_email String,
            prosthetic_id String
        ) ENGINE = MergeTree()
        PARTITION BY toYYYYMM(metric_date)
        ORDER BY (username, metric_date)
        SETTINGS index_granularity = 8192
        """,
        conn_id="clickhouse_default",
    )

    generate_queries = PythonOperator(
        task_id="generate_insert_queries", python_callable=generate_insert_queries
    )

    run_insert_queries = SQLExecuteQueryOperator(
        task_id="insert_rows",
        sql="sql/insert_queries.sql",
        conn_id="clickhouse_default",
        split_statements=True,
    )

    # Порядок выполнения
    create_table >> generate_queries >> run_insert_queries
