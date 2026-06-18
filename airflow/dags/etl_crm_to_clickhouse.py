"""
ETL: CRM + телеметрия датчиков -> витрина отчётности в ClickHouse.

Расписание: ежедневно в 03:00 по локальному времени Airflow.
Запуск за вчерашние сутки (data_interval_start..data_interval_end).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from airflow.decorators import dag, task
from airflow.models import Variable
from airflow.providers.apache.cassandra.hooks.cassandra import CassandraHook
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.providers.common.sql.operators.sql import SQLExecuteQueryOperator


DAG_ID = "etl_crm_to_clickhouse"
SQL_DIR = Path(__file__).resolve().parent.parent / "sql"

CRM_CONN_ID = "crm_postgres"
CASSANDRA_CONN_ID = "sensor_cassandra"
CLICKHOUSE_CONN_ID = "clickhouse"


default_args = {
    "owner": "bionicpro",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=10),
    "execution_timeout": timedelta(hours=2),
}


@dag(
    dag_id=DAG_ID,
    default_args=default_args,
    description="ETL: CRM + sensor telemetry -> ClickHouse datamart",
    schedule_interval="0 3 * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["bionicpro", "etl", "clickhouse"],
)
def etl_crm_to_clickhouse():

    create_datamart = SQLExecuteQueryOperator(
        task_id="create_datamart",
        conn_id=CLICKHOUSE_CONN_ID,
        sql=(SQL_DIR / "datamart_schema.sql").read_text(encoding="utf-8"),
    )

    @task
    def extract_crm(**context) -> str:
        """Достаём из CRM пользователей и протезы, обновлённые с прошлого запуска."""
        ds_start = context["data_interval_start"].isoformat()
        sql_template = (SQL_DIR / "extract_crm.sql").read_text(encoding="utf-8")
        sql = sql_template.replace("{{ data_interval_start }}", ds_start)

        hook = PostgresHook(postgres_conn_id=CRM_CONN_ID)
        df = hook.get_pandas_df(sql)

        out_path = f"/tmp/{DAG_ID}/crm_{context['ds_nodash']}.parquet"
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(out_path, index=False)
        logging.info("CRM rows: %s -> %s", len(df), out_path)
        return out_path

    @task
    def extract_sensor_telemetry(**context) -> str:
        """Тянем телеметрию из Cassandra за вчерашние сутки."""
        start: datetime = context["data_interval_start"]
        end: datetime = context["data_interval_end"]

        hook = CassandraHook(cassandra_conn_id=CASSANDRA_CONN_ID)
        session = hook.get_conn()
        try:
            stmt = session.prepare(
                """
                SELECT user_id,
                       prosthesis_id,
                       event_time,
                       signal_strength,
                       battery_percent,
                       is_error,
                       session_id
                FROM bionicpro.sensor_events
                WHERE event_time >= ? AND event_time < ?
                ALLOW FILTERING
                """
            )
            rows = session.execute(stmt, [start, end])
        finally:
            session.cluster.shutdown()

        df = pd.DataFrame([r._asdict() for r in rows])
        out_path = f"/tmp/{DAG_ID}/sensors_{context['ds_nodash']}.parquet"
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(out_path, index=False)
        logging.info("Sensor rows: %s -> %s", len(df), out_path)
        return out_path

    @task
    def build_datamart(crm_path: str, sensors_path: str, **context) -> str:
        """
        Группируем телеметрию по (user_id, report_date) и джойним с CRM.
        Получаем плоскую витрину: одна строка = пользователь + протез + дата.
        """
        crm = pd.read_parquet(crm_path)
        sensors = pd.read_parquet(sensors_path)

        if sensors.empty:
            logging.warning("No sensor data for %s", context["ds"])
            df = crm.copy()
            df["report_date"] = pd.to_datetime(context["ds"]).date()
            df["sessions_count"] = 0
            df["total_active_minutes"] = 0
            df["avg_signal_strength"] = None
            df["max_signal_strength"] = None
            df["error_events_count"] = 0
            df["battery_avg_percent"] = None
            df["actuator_cycles_total"] = 0
        else:
            sensors["event_time"] = pd.to_datetime(sensors["event_time"])
            sensors["report_date"] = sensors["event_time"].dt.date

            agg = (
                sensors.groupby(["user_id", "prosthesis_id", "report_date"], as_index=False)
                .agg(
                    sessions_count=("session_id", "nunique"),
                    total_active_minutes=(
                        "event_time",
                        lambda s: int((s.max() - s.min()).total_seconds() // 60),
                    ),
                    avg_signal_strength=("signal_strength", "mean"),
                    max_signal_strength=("signal_strength", "max"),
                    error_events_count=("is_error", "sum"),
                    battery_avg_percent=("battery_percent", "mean"),
                    actuator_cycles_total=("event_time", "count"),
                )
            )

            df = agg.merge(
                crm,
                on=["user_id", "prosthesis_id"],
                how="inner",
            )

        df["report_date"] = pd.to_datetime(df["report_date"]).dt.strftime("%Y-%m-%d")

        out_path = f"/tmp/{DAG_ID}/datamart_{context['ds_nodash']}.json"
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        df.to_json(out_path, orient="records", date_format="iso")
        logging.info("Datamart rows: %s -> %s", len(df), out_path)
        return out_path

    @task
    def load_to_clickhouse(datamart_path: str, **context) -> int:
        """Загружаем витрину в ClickHouse. Партиция: toYYYYMM(report_date)."""
        import clickhouse_connect

        with open(datamart_path, "r", encoding="utf-8") as f:
            rows = json.load(f)

        if not rows:
            logging.warning("Nothing to load")
            return 0

        ds = context["ds_nodash"]
        client = clickhouse_connect.get_client(
            host=Variable.get("clickhouse_host"),
            port=int(Variable.get("clickhouse_port", "8123")),
            username=Variable.get("clickhouse_user"),
            password=Variable.get("clickhouse_password"),
            database="bionicpro_dm",
        )

        client.command(
            f"ALTER TABLE bionicpro_dm.prosthesis_user_report "
            f"DELETE WHERE report_date = '{ds}'"
        )

        columns = [
            "user_id",
            "user_email",
            "user_first_name",
            "user_last_name",
            "user_country",
            "prosthesis_id",
            "prosthesis_model",
            "prosthesis_serial",
            "report_date",
            "sessions_count",
            "total_active_minutes",
            "avg_signal_strength",
            "max_signal_strength",
            "error_events_count",
            "battery_avg_percent",
            "actuator_cycles_total",
        ]
        data = [
            [
                r.get(c) for c in columns
            ]
            for r in rows
        ]

        client.insert(
            table="prosthesis_user_report",
            data=data,
            column_names=columns,
            database="bionicpro_dm",
        )
        logging.info("Loaded %s rows into ClickHouse", len(data))
        return len(data)

    crm_path = extract_crm()
    sensors_path = extract_sensor_telemetry()
    datamart_path = build_datamart(crm_path, sensors_path)

    create_datamart >> datamart_path
    load_to_clickhouse(datamart_path)


etl_crm_to_clickhouse()