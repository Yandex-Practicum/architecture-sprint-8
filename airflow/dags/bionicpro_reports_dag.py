import os
import random
from datetime import datetime, timedelta
from dateutil import tz
from dateutil.parser import isoparse

from airflow import DAG
from airflow.decorators import task
from airflow.models import Variable
from airflow.utils.trigger_rule import TriggerRule
from airflow.providers.postgres.hooks.postgres import PostgresHook

from clickhouse_driver import Client

import psycopg2
from psycopg2 import OperationalError

DAG_ID = "bionicpro_reports_dag"
SCHEDULE = "15 * * * *"
START_DATE = datetime(2025, 1, 1, 0, 0, tzinfo=tz.gettz("Europe/Moscow"))


def ch_client():
    return Client(
        host=os.getenv("CLICKHOUSE_HOST", "clickhouse"),
        port=int(os.getenv("CLICKHOUSE_PORT", "9000")),
        user=os.getenv("CLICKHOUSE_USER", "default"),
        password=os.getenv("CLICKHOUSE_PASSWORD", ""),
        database=os.getenv("CLICKHOUSE_DB", "bionicpro"),
        settings={"use_numpy": False},
    )


DDL_DB = """
CREATE DATABASE IF NOT EXISTS bionicpro;
"""

DDL_CRM = """
CREATE TABLE IF NOT EXISTS bionicpro.crm_customers
(
  customer_id String,
  full_name   String,
  email       String,
  country     String,
  updated_at  DateTime
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (customer_id);
"""

DDL_TELEMETRY = """
CREATE TABLE IF NOT EXISTS bionicpro.telemetry_events
(
  ts              DateTime,
  customer_id     String,
  prosthesis_id   String,
  response_ms     Float64,
  is_error        UInt8,
  battery_level   Float64
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(ts)
ORDER BY (customer_id, prosthesis_id, ts);
"""

DDL_MART = """
CREATE TABLE IF NOT EXISTS bionicpro.user_daily_telemetry
(
  event_date        Date,
  customer_id       String,
  prosthesis_id     String,
  full_name         String,
  country           String,
  events            UInt64,
  err_events        UInt64,
  avg_response_ms   Float64,
  p95_response_ms   Float64,
  avg_battery_level Float64,
  last_update       DateTime
)
ENGINE = ReplacingMergeTree(last_update)
PARTITION BY toYYYYMM(event_date)
ORDER BY (event_date, customer_id, prosthesis_id);
"""

with DAG(
    dag_id=DAG_ID,
    schedule=SCHEDULE,
    start_date=START_DATE,
    catchup=False,
    max_active_runs=1,
    default_args={"owner": "data-platform", "retries": 1, "retry_delay": timedelta(minutes=5)},
    tags=["bionicpro", "etl", "reports"],
) as dag:

    @task
    def ensure_schema():
        cli = ch_client()
        cli.execute(DDL_DB)
        cli.execute(DDL_CRM)
        cli.execute(DDL_TELEMETRY)
        cli.execute(DDL_MART)

    @task
    def ensure_crm_db_and_table():
        """
        Гарантирует наличие БД crm и таблицы customers в Postgres (CRM).
        Использует параметры из Connection 'crm_postgres' (host/port/user/password).
        Если БД crm отсутствует - создаёт через системную БД 'postgres'.
        """
        conn = PostgresHook(postgres_conn_id="crm_postgres").get_connection("crm_postgres")
        host = conn.host or "postgres"
        port = int(conn.port or 5432)
        user = conn.login or "airflow"
        password = conn.password or "airflow"
        target_db = conn.schema or "crm"

        def _connect(dbname: str):
            return psycopg2.connect(host=host, port=port, dbname=dbname, user=user, password=password)

        try:
            crm_conn = _connect(target_db)
        except OperationalError as e:
            if 'database "{}" does not exist'.format(target_db) in str(
                e
            ) or 'database "' + target_db + '" does not exist' in str(e):
                admin = _connect("postgres")
                admin.autocommit = True
                with admin.cursor() as cur:
                    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (target_db,))
                    row = cur.fetchone()
                    if not row:
                        cur.execute(f'CREATE DATABASE "{target_db}"')
                admin.close()
                crm_conn = _connect(target_db)
            else:
                raise

        crm_conn.autocommit = True
        with crm_conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS customers (
                  customer_id  text PRIMARY KEY,
                  full_name    text,
                  email        text,
                  country      text,
                  updated_at   timestamp NOT NULL
                );
            """
            )
        crm_conn.close()

    @task
    def seed_crm(n_customers: int = 4):
        """
        Одноразово заливает в CRM (Postgres) несколько клиентов.
        Управляется Variable 'SEED_DATA': 'true' => заливаем и сразу ставим 'false'.
        """
        if Variable.get("SEED_DATA", default_var="true").lower() != "true":
            return "skip"

        hook = PostgresHook(postgres_conn_id="crm_postgres")
        conn = hook.get_connection("crm_postgres")
        host = conn.host or "postgres"
        port = int(conn.port or 5432)
        user = conn.login or "airflow"
        password = conn.password or "airflow"
        dbname = conn.schema or "crm"

        with psycopg2.connect(host=host, port=port, dbname=dbname, user=user, password=password) as pg:
            pg.autocommit = True
            with pg.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS customers (
                      customer_id  text PRIMARY KEY,
                      full_name    text,
                      email        text,
                      country      text,
                      updated_at   timestamp NOT NULL
                    );
                """
                )
                base = [
                    ("c1", "Alex Ivanov", "alex@example.com", "RU"),
                    ("c2", "Ivan Smirnov", "ivan@example.com", "RU"),
                    ("c3", "Anton Petrov", "anton@example.com", "RU"),
                    ("c4", "Elena Sidorova", "elena@example.com", "RU"),
                ][:n_customers]
                for cid, name, email, country in base:
                    cur.execute(
                        """
                        INSERT INTO customers (customer_id, full_name, email, country, updated_at)
                        VALUES (%s, %s, %s, %s, now())
                        ON CONFLICT (customer_id) DO UPDATE
                        SET full_name=EXCLUDED.full_name,
                            email=EXCLUDED.email,
                            country=EXCLUDED.country,
                            updated_at=EXCLUDED.updated_at;
                    """,
                        (cid, name, email, country),
                    )

        Variable.set("SEED_DATA", "false")
        return "seeded"

    @task
    def seed_telemetry(events_per_customer: int = 6):
        """
        Заливает демо-телеметрию в ClickHouse для существующих клиентов.
        Запускается, когда Variable 'SEED_DATA' == 'false' (после сидирования CRM).
        При необходимости генерацию данных можно регулировать через значение SEED_DATA.
        """
        if Variable.get("SEED_DATA", default_var="false").lower() != "false":
            return "skip"

        hook = PostgresHook(postgres_conn_id="crm_postgres")
        rows = hook.get_records("SELECT customer_id FROM customers ORDER BY customer_id")
        customer_ids = [r[0] for r in rows] if rows else []

        if not customer_ids:
            return "no_customers"

        cli = ch_client()
        now = datetime.utcnow()
        data = []
        for cid in customer_ids:
            prosthesis_ids = [f"p{random.randint(1,2)}"]
            for pid in prosthesis_ids:
                for j in range(events_per_customer):
                    ts = now - timedelta(minutes=random.randint(1, 10), seconds=random.randint(0, 59))
                    response = random.choice([120, 150, 180, 220, 300, 450])
                    is_err = 1 if random.random() < 0.2 else 0
                    battery = random.choice([88.0, 85.0, 82.0, 80.0, 78.0])
                    data.append((ts, cid, pid, float(response), int(is_err), float(battery)))

        if data:
            cli.execute(
                """
                INSERT INTO bionicpro.telemetry_events
                (ts, customer_id, prosthesis_id, response_ms, is_error, battery_level)
                VALUES
            """,
                data,
            )
        return f"inserted:{len(data)}"

    @task
    def extract_load_crm():
        """
        Инкрементально выгружаем клиентов из CRM (Postgres) в ClickHouse.
        Используем Variable 'CRM_WATERMARK'. Перекрытие окна - +5 минут.
        """
        hook = PostgresHook(postgres_conn_id="crm_postgres")
        wm_raw = Variable.get("CRM_WATERMARK", default_var="1970-01-01T00:00:00")
        wm = isoparse(wm_raw)
        now_ = datetime.utcnow()
        upper = now_ + timedelta(minutes=5)

        sql = """
            SELECT customer_id, full_name, email, country, updated_at
            FROM customers
            WHERE updated_at > %s AND updated_at <= %s
            ORDER BY updated_at ASC
        """
        rows = hook.get_records(sql, parameters=(wm, upper))
        if rows:
            cli = ch_client()
            cli.execute(
                """
                INSERT INTO bionicpro.crm_customers (customer_id, full_name, email, country, updated_at)
                VALUES
            """,
                rows,
            )
            max_updated = max(r[-1] for r in rows)
            Variable.set("CRM_WATERMARK", max_updated.replace(tzinfo=None).isoformat())
        else:
            Variable.set("CRM_WATERMARK", upper.replace(tzinfo=None).isoformat())

    @task
    def refresh_mart(days_back: int = int(Variable.get("AGG_DAYS_BACK", default_var="2"))):
        """
        Пересчёт витрины «пользователь * день * протез».
        Стратегия: удаляем пересекающееся окно, затем вставляем агрегацию.
        """
        cli = ch_client()
        end_dt = datetime.utcnow().date() + timedelta(days=1)
        start_dt = end_dt - timedelta(days=days_back)

        cli.execute(
            "ALTER TABLE bionicpro.user_daily_telemetry DELETE WHERE event_date >= toDate(%(s)s) AND event_date < toDate(%(e)s)",
            {"s": start_dt.strftime("%Y-%m-%d"), "e": end_dt.strftime("%Y-%m-%d")},
        )

        insert_sql = """
        INSERT INTO bionicpro.user_daily_telemetry
        SELECT
          toDate(e.ts)                    AS event_date,
          e.customer_id                   AS customer_id,
          e.prosthesis_id                 AS prosthesis_id,
          any(c.full_name)                AS full_name,
          any(c.country)                  AS country,
          count()                         AS events,
          sum(e.is_error)                 AS err_events,
          avg(e.response_ms)              AS avg_response_ms,
          quantile(0.95)(e.response_ms)   AS p95_response_ms,
          avg(e.battery_level)            AS avg_battery_level,
          now()                           AS last_update
        FROM bionicpro.telemetry_events e
        ANY LEFT JOIN bionicpro.crm_customers c
          ON c.customer_id = e.customer_id
        WHERE e.ts >= toDateTime(%(s)s) AND e.ts < toDateTime(%(e)s)
        GROUP BY event_date, customer_id, prosthesis_id
        """
        cli.execute(
            insert_sql,
            {
                "s": f"{start_dt} 00:00:00",
                "e": f"{end_dt} 00:00:00",
            },
        )

    @task(trigger_rule=TriggerRule.ALL_DONE)
    def done_marker():
        return "ok"

    (
        ensure_schema()
        >> ensure_crm_db_and_table()
        >> seed_crm()
        >> extract_load_crm()
        >> seed_telemetry()
        >> refresh_mart()
        >> done_marker()
    )
