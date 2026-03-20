from datetime import datetime, timedelta

from airflow import DAG
from airflow.providers.postgres.hooks.postgres import PostgresHook

import clickhouse_connect

from airflow.operators.python import PythonOperator


DEFAULT_ARGS = {
    "owner": "airflow",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=1),
}

CRM_CONN_ID = "crm_postgres"
TELEMETRY_CONN_ID = "telemetry_postgres"


def load_raw_to_clickhouse(**context):
    # подключаемся к Postgres
    crm_hook = PostgresHook(postgres_conn_id=CRM_CONN_ID)
    telemetry_hook = PostgresHook(postgres_conn_id=TELEMETRY_CONN_ID)

    crm_sql = """
        SELECT
            u.id       AS user_id,
            u.external_id,
            u.full_name,
            p.id       AS prosthesis_id,
            p.serial_number
        FROM crm_prostheses p
        JOIN crm_users u ON u.id = p.user_id;
    """
    crm_rows = crm_hook.get_records(crm_sql)

    telemetry_sql = """
        SELECT
            event_time,
            serial_number,
            load_value,
            duration_sec
        FROM telemetry_events;
    """
    telemetry_rows = telemetry_hook.get_records(telemetry_sql)

    # строим словарь prosthesis serial_number -> (user_id, external_id, full_name, prosthesis_id)
    prosthesis_map = {}
    for user_id, external_id, full_name, prosthesis_id, serial_number in crm_rows:
        prosthesis_map[serial_number] = {
            "user_id": str(user_id),
            "external_id": external_id,
            "full_name": full_name,
            "prosthesis_id": str(prosthesis_id),
            "serial_number": serial_number,
        }

    # готовим данные для заливки в ClickHouse user_usage_raw
    records = []
    for event_time, serial_number, load_value, duration_sec in telemetry_rows:
        meta = prosthesis_map.get(serial_number)
        if not meta:
            continue  # телеметрия по неизвестному протезу — пропускаем или логируем
        event_date = event_time.date()
        records.append(
            (
                meta["user_id"],
                meta["external_id"],
                meta["full_name"],
                meta["prosthesis_id"],
                meta["serial_number"],
                event_date,
                event_time.replace(tzinfo=None),  # ClickHouse DateTime без TZ
                float(load_value),
                int(duration_sec),
            )
        )

    client = clickhouse_connect.get_client(
        host="clickhouse",
        port=8123,
        username="ch_user",
        password="ch_pass",
        database="reports",
    )

    # очищаем staging и заливаем новые данные (в демо можно full refresh)
    client.command("TRUNCATE TABLE reports.user_usage_raw")
    if records:
        client.insert(
            "reports.user_usage_raw",
            records,
            column_names=[
                "user_id",
                "external_id",
                "full_name",
                "prosthesis_id",
                "serial_number",
                "event_date",
                "event_time",
                "load_value",
                "duration_sec",
            ],
        )


def build_daily_mart(**context):
    client = clickhouse_connect.get_client(
        host="clickhouse",
        port=8123,
        username="ch_user",
        password="ch_pass",
        database="reports",
    )

    # full refresh витрины для демо; в реале можно инкрементально по датам
    client.command("TRUNCATE TABLE reports.user_usage_daily")

    agg_sql = """
        INSERT INTO reports.user_usage_daily
        SELECT
            user_id,
            external_id,
            full_name,
            prosthesis_id,
            serial_number,
            event_date,
            sum(duration_sec)              AS total_duration_sec,
            avg(load_value)                AS avg_load,
            max(load_value)                AS max_load,
            count(*)                       AS events_count
        FROM reports.user_usage_raw
        GROUP BY
            user_id,
            external_id,
            full_name,
            prosthesis_id,
            serial_number,
            event_date
    """
    client.command(agg_sql)


with DAG(
    dag_id="bionicpro_reports_etl",
    default_args=DEFAULT_ARGS,
    description="ETL: CRM + telemetry -> ClickHouse mart for reports-api",
    schedule_interval="*/5 * * * *",  # каждые 5 минут
    start_date=datetime(2026, 3, 19),
    catchup=False,
    tags=["bionicpro", "reports"],
) as dag:

    load_raw = PythonOperator(
        task_id="load_raw_to_clickhouse",
        python_callable=load_raw_to_clickhouse,
        provide_context=True,
    )

    build_mart = PythonOperator(
        task_id="build_daily_mart",
        python_callable=build_daily_mart,
        provide_context=True,
    )

    load_raw >> build_mart
