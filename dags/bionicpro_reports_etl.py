from __future__ import annotations

from datetime import timedelta
import pendulum
import requests

from airflow.decorators import dag, task
from airflow.hooks.base import BaseHook
from airflow.providers.postgres.hooks.postgres import PostgresHook

# Вариант 1: clickhouse-connect (рекомендую)
import clickhouse_connect


TZ = "Europe/Brussels"

DEFAULT_ARGS = {
    "owner": "bionicpro",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}


def get_ch_client(conn_id: str = "ch_olap"):
    conn = BaseHook.get_connection(conn_id)
    return clickhouse_connect.get_client(
        host=conn.host,
        port=conn.port or 8123,
        username=conn.login,
        password=conn.password,
        database=conn.schema or "default",
        secure=(conn.extra_dejson.get("secure", False) is True),
    )


@dag(
    dag_id="bionicpro_reports_etl",
    description="ETL: CRM + telemetry -> OLAP mart for report service",
    default_args=DEFAULT_ARGS,
    start_date=pendulum.datetime(2026, 2, 1, tz=TZ),
    schedule="0 2 * * *",  # каждый день в 02:00 (локально)
    catchup=True,          # чтобы можно было догнать историю
    max_active_runs=1,     # важный антидубликат для витрин
    tags=["bionicpro", "reports", "etl", "olap"],
)
def bionicpro_reports_etl():

    @task
    def ensure_tables():
        ch = get_ch_client()
        ch.command("""
        CREATE TABLE IF NOT EXISTS stg_crm_customers
        (
          customer_id String,
          crm_user_id String,
          full_name String,
          email String,
          phone String,
          country String,
          city String,
          prosthesis_id String,
          contract_id String,
          updated_at DateTime
        )
        ENGINE = ReplacingMergeTree(updated_at)
        ORDER BY (customer_id);
        """)

        ch.command("""
        CREATE TABLE IF NOT EXISTS stg_telemetry_daily
        (
          day Date,
          prosthesis_id String,
          samples_count UInt64,
          active_seconds UInt64,
          movements_count UInt64,
          errors_count UInt64,
          avg_battery Float32,
          max_load Float32,
          updated_at DateTime
        )
        ENGINE = ReplacingMergeTree(updated_at)
        PARTITION BY toYYYYMM(day)
        ORDER BY (prosthesis_id, day);
        """)

        ch.command("""
        CREATE TABLE IF NOT EXISTS mart_user_daily_report
        (
          day Date,
          customer_id String,
          prosthesis_id String,
          full_name String,
          email String,
          phone String,
          country String,
          city String,
          contract_id String,
          samples_count UInt64,
          active_seconds UInt64,
          movements_count UInt64,
          errors_count UInt64,
          avg_battery Float32,
          max_load Float32,
          loaded_at DateTime
        )
        ENGINE = MergeTree
        PARTITION BY toYYYYMM(day)
        ORDER BY (customer_id, day);
        """)

    @task
    def extract_crm_customers(logical_date=None, data_interval_start=None, data_interval_end=None):
        """
        Вариант: забираем список клиентов из CRM API.
        Для Bitrix24 обычно это: /crm.contact.list или /crm.item.list (зависит от сущностей).
        """
        conn = BaseHook.get_connection("crm_http")
        base_url = conn.host.rstrip("/")
        token = conn.password or conn.extra_dejson.get("token")
        if not token:
            raise ValueError("No CRM token found in crm_http connection")


        start = data_interval_start
        end = data_interval_end

        url = f"{base_url}/customers"
        params = {
            "updated_from": start.to_iso8601_string(),
            "updated_to": end.to_iso8601_string(),
        }
        headers = {"Authorization": f"Bearer {token}"}

        r = requests.get(url, params=params, headers=headers, timeout=30)
        r.raise_for_status()
        payload = r.json()

        customers = payload.get("items", payload)

        rows = []
        for c in customers:
            rows.append((
                str(c.get("customer_id") or c.get("id")),
                str(c.get("crm_user_id") or ""),
                str(c.get("full_name") or ""),
                str(c.get("email") or ""),
                str(c.get("phone") or ""),
                str(c.get("country") or ""),
                str(c.get("city") or ""),
                str(c.get("prosthesis_id") or ""),  
                str(c.get("contract_id") or ""),
                str(c.get("updated_at") or end.to_iso8601_string()),
            ))

        return rows

    @task
    def load_crm_to_ch(customers_rows):
        if not customers_rows:
            return 0
        ch = get_ch_client()
        ch.insert(
            table="stg_crm_customers",
            data=customers_rows,
            column_names=[
                "customer_id","crm_user_id","full_name","email","phone","country","city",
                "prosthesis_id","contract_id","updated_at"
            ],
        )
        return len(customers_rows)

    @task
    def extract_telemetry_daily(data_interval_start=None, data_interval_end=None):
        """
        Агрегация телеметрии в Postgres за окно (день).
        Важно: агрегировать до загрузки в CH, чтобы витрина строилась быстро.
        """
        pg = PostgresHook(postgres_conn_id="pg_telemetry")

        sql = """
        SELECT
          DATE(ts) AS day,
          prosthesis_id::text AS prosthesis_id,
          COUNT(*)::bigint AS samples_count,
          SUM(CASE WHEN movement IS NOT NULL THEN 1 ELSE 0 END)::bigint AS movements_count,
          SUM(CASE WHEN is_error THEN 1 ELSE 0 END)::bigint AS errors_count,
          -- активность условно: количество секунд, где был хотя бы 1 сэмпл (пример)
          COUNT(DISTINCT date_trunc('second', ts))::bigint AS active_seconds,
          AVG(battery)::float AS avg_battery,
          MAX(load)::float AS max_load
        FROM telemetry_events
        WHERE ts >= %(start)s AND ts < %(end)s
        GROUP BY DATE(ts), prosthesis_id::text
        """
        rows = pg.get_records(
            sql,
            parameters={
                "start": data_interval_start.to_datetime_string(),
                "end": data_interval_end.to_datetime_string(),
            },
        )

        updated_at = pendulum.now(TZ).to_datetime_string()
        out = []
        for r in rows:
            out.append((
                r[0], r[1],
                int(r[2]), int(r[3]), int(r[4]), int(r[5]),
                float(r[6] or 0.0), float(r[7] or 0.0),
                updated_at
            ))
        return out

    @task
    def load_telemetry_to_ch(telemetry_rows):
        if not telemetry_rows:
            return 0
        ch = get_ch_client()
        ch.insert(
            table="stg_telemetry_daily",
            data=telemetry_rows,
            column_names=[
                "day","prosthesis_id",
                "samples_count","active_seconds","movements_count","errors_count",
                "avg_battery","max_load",
                "updated_at"
            ],
        )
        return len(telemetry_rows)

    @task
    def build_mart(data_interval_start=None, data_interval_end=None):
        """
        Строим витрину за окно (обычно сутки).
        Важно: делать idempotent build за период, чтобы повторный запуск не плодил дубли.
        """
        ch = get_ch_client()

        start_day = data_interval_start.date()
        end_day = data_interval_end.date()

        ch.command(
            "ALTER TABLE mart_user_daily_report DELETE WHERE day >= toDate(%(s)s) AND day < toDate(%(e)s)",
            parameters={"s": str(start_day), "e": str(end_day)},
        )

        ch.command(f"""
        INSERT INTO mart_user_daily_report
        SELECT
          t.day AS day,
          c.customer_id AS customer_id,
          t.prosthesis_id AS prosthesis_id,

          c.full_name,
          c.email,
          c.phone,
          c.country,
          c.city,
          c.contract_id,

          t.samples_count,
          t.active_seconds,
          t.movements_count,
          t.errors_count,
          t.avg_battery,
          t.max_load,

          now() AS loaded_at
        FROM stg_telemetry_daily t
        INNER JOIN
        (
          -- берём актуальную версию клиента по prosthesis_id
          SELECT *
          FROM stg_crm_customers
          QUALIFY row_number() OVER (PARTITION BY prosthesis_id ORDER BY updated_at DESC) = 1
        ) c
        ON c.prosthesis_id = t.prosthesis_id
        WHERE t.day >= toDate('{start_day}') AND t.day < toDate('{end_day}');
        """)

        return {"built_from": str(start_day), "built_to": str(end_day)}

    t0 = ensure_tables()
    crm_rows = extract_crm_customers()
    crm_loaded = load_crm_to_ch(crm_rows)

    tel_rows = extract_telemetry_daily()
    tel_loaded = load_telemetry_to_ch(tel_rows)

    mart = build_mart()

    t0 >> [crm_loaded, tel_loaded] >> mart


dag = bionicpro_reports_etl()
