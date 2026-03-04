from datetime import datetime, timedelta
import logging
from airflow import DAG
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.operators.python import PythonOperator
from airflow_clickhouse_plugin.operators.clickhouse import ClickHouseOperator
from airflow_clickhouse_plugin.hooks.clickhouse import ClickHouseHook
import pandas as pd


default_args = {
    "owner": "bionicpro",
    "depends_on_past": False,
    "start_date": datetime(2025, 1, 1),
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


def extract_crm(**context):
    """Извлечение данных из CRM PostgreSQL"""
    pg_hook = PostgresHook(postgres_conn_id="crm_db")

    sql = """
        SELECT id, name, email, age, gender, country, address, phone
        FROM customers
    """

    df = pg_hook.get_pandas_df(sql)

    if not df.empty:
        df.to_json("/tmp/crm_data.json", orient="records", date_format="iso")

        context["task_instance"].xcom_push(key="crm_has_data", value=True)
    else:
        context["task_instance"].xcom_push(key="crm_has_data", value=False)
        logging.info("Нет новых данных в CRM")


def extract_telemetry(**context):
    """Извлечение данных телеметрии из PostgreSQL"""
    pg_hook = PostgresHook(postgres_conn_id="telemetry_db")

    last_signal = context["task_instance"].xcom_pull(key="last_telemetry_time")
    if not last_signal:
        last_signal = datetime(2000, 1, 1)

    if isinstance(last_signal, str):
        last_signal = datetime.fromisoformat(last_signal)

    sql = """
        SELECT user_id, prosthesis_type, muscle_group, 
               signal_frequency, signal_duration, signal_amplitude, signal_time
        FROM telemetry
        WHERE signal_time > %(last_signal)s
    """

    df = pg_hook.get_pandas_df(sql, parameters={"last_signal": last_signal})

    if not df.empty:
        df["signal_time"] = df["signal_time"].astype(str)
        df.to_json("/tmp/telemetry_data.json", orient="records", date_format="iso")

        max_time = pd.to_datetime(df["signal_time"]).max()
        context["task_instance"].xcom_push(
            key="last_telemetry_time", value=max_time.isoformat()
        )
        context["task_instance"].xcom_push(key="telemetry_has_data", value=True)
    else:
        context["task_instance"].xcom_push(key="telemetry_has_data", value=False)
        logging.info("Нет новых данных в телеметрии")


def transform_data(**context):
    """Трансформация и объединение данных"""
    crm_has_data = context["task_instance"].xcom_pull(
        task_ids="extract_crm", key="crm_has_data"
    )
    telemetry_has_data = context["task_instance"].xcom_pull(
        task_ids="extract_telemetry", key="telemetry_has_data"
    )

    if not crm_has_data or not telemetry_has_data:
        logging.info("Нет данных для трансформации")
        with open("/tmp/no_data_for_transform", "w") as f:
            f.write("no_data")
        return

    crm_df = pd.read_json("/tmp/crm_data.json")
    telemetry_df = pd.read_json("/tmp/telemetry_data.json")

    if "signal_time" in telemetry_df.columns:
        telemetry_df["signal_time"] = pd.to_datetime(telemetry_df["signal_time"])

    agg_telemetry = (
        telemetry_df.groupby("user_id")
        .agg(
            prosthesis_type=("prosthesis_type", "first"),
            avg_signal_frequency=("signal_frequency", "mean"),
            avg_signal_duration=("signal_duration", "mean"),
            avg_signal_amplitude=("signal_amplitude", "mean"),
            total_signals=("signal_frequency", "count"),
            last_signal_time=("signal_time", "max"),
        )
        .reset_index()
    )

    agg_telemetry["avg_signal_frequency"] = agg_telemetry["avg_signal_frequency"].round(
        2
    )
    agg_telemetry["avg_signal_duration"] = agg_telemetry["avg_signal_duration"].round(2)
    agg_telemetry["avg_signal_amplitude"] = agg_telemetry["avg_signal_amplitude"].round(
        2
    )

    report_df = pd.merge(
        crm_df, agg_telemetry, left_on="id", right_on="user_id", how="inner"
    )

    if report_df.empty:
        logging.info("Нет совпадающих записей после объединения")
        return

    report_df["report_date"] = datetime.now().date()

    final_df = report_df[
        [
            "user_id",
            "report_date",
            "name",
            "email",
            "age",
            "gender",
            "country",
            "prosthesis_type",
            "avg_signal_frequency",
            "avg_signal_duration",
            "avg_signal_amplitude",
            "total_signals",
            "last_signal_time",
        ]
    ].rename(columns={"name": "full_name"})

    final_df = final_df.where(pd.notnull(final_df), None)

    final_df.to_json("/tmp/report_data.json", orient="records", date_format="iso")

    context["task_instance"].xcom_push(key="records_count", value=len(final_df))


create_table_sql = """
CREATE TABLE IF NOT EXISTS user_reports (
    user_id UInt32,
    report_date Date,
    full_name String,
    email String,
    age UInt8,
    gender String,
    country String,
    prosthesis_type String,
    avg_signal_frequency Float32,
    avg_signal_duration Float32,
    avg_signal_amplitude Float32,
    total_signals UInt32,
    last_signal_time DateTime
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(report_date)
ORDER BY (user_id, report_date);
"""


def load_to_clickhouse(**context):
    """Загрузка данных в ClickHouse через hook"""
    if not context["task_instance"].xcom_pull(
        task_ids="transform_data", key="records_count"
    ):
        logging.info("Нет данных для загрузки")
        return

    df = pd.read_json("/tmp/report_data.json")

    if df.empty:
        logging.info("DataFrame пуст")
        return

    ch_hook = ClickHouseHook(
        clickhouse_conn_id="olap_db", database="default"
    )

    df["report_date"] = pd.to_datetime(df["report_date"]).dt.date
    df["last_signal_time"] = pd.to_datetime(df["last_signal_time"])
    df["user_id"] = df["user_id"].astype(int)
    df["age"] = df["age"].astype(int)
    df["total_signals"] = df["total_signals"].astype(int)
    df["avg_signal_frequency"] = df["avg_signal_frequency"].astype(float)
    df["avg_signal_duration"] = df["avg_signal_duration"].astype(float)
    df["avg_signal_amplitude"] = df["avg_signal_amplitude"].astype(float)

    records = [tuple(x) for x in df.to_numpy()]

    ch_hook.execute("INSERT INTO user_reports VALUES", records)

    logging.info(f"Загружено {len(records)} записей в ClickHouse")


with DAG(
    "bionicpro_etl_reports",
    default_args=default_args,
    description="ETL for user reports from CRM and telemetry",
    schedule="*/5 * * * *",
    max_active_runs=1,
    catchup=False,
    tags=["bionicpro", "reports"],
) as dag:
    create_table = ClickHouseOperator(
        task_id="create_clickhouse_table",
        clickhouse_conn_id="olap_db",
        sql=create_table_sql,
        database="default",
    )

    extract_crm_task = PythonOperator(
        task_id="extract_crm",
        python_callable=extract_crm,
    )

    extract_telemetry_task = PythonOperator(
        task_id="extract_telemetry",
        python_callable=extract_telemetry,
    )

    transform_task = PythonOperator(
        task_id="transform_data",
        python_callable=transform_data,
    )

    load_using_hook = PythonOperator(
        task_id="load_using_hook",
        python_callable=load_to_clickhouse,
    )

    def cleanup(**context):
        import os

        files = [
            "/tmp/crm_data.json",
            "/tmp/telemetry_data.json",
            "/tmp/report_data.json",
        ]
        for file in files:
            if os.path.exists(file):
                os.remove(file)
        logging.info("Временные файлы удалены")

    cleanup_task = PythonOperator(
        task_id="cleanup_temp_files",
        python_callable=cleanup,
        trigger_rule="all_done",
    )

    extract_crm_task >> transform_task
    extract_telemetry_task >> transform_task
    create_table >> load_using_hook
    transform_task >> load_using_hook >> cleanup_task
