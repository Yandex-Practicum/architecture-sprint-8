"""
BionicPRO ETL DAG — загрузка данных из CRM (Postgres) в ClickHouse
и построение витрины user_daily_telemetry.

Расписание: каждый час (минута 15).
"""

import json
import os
import random
from datetime import datetime, timedelta

import boto3
from airflow import DAG
from airflow.models import Variable
from airflow.operators.python import PythonOperator

import psycopg2
from clickhouse_driver import Client as CHClient

CRM_CONN = "postgresql://airflow:airflow@postgres:5432/crm"
CH_HOST = "clickhouse"
CH_PORT = 9000
CH_USER = "airflow"
CH_PASSWORD = "airflow"
CH_DATABASE = "bionicpro"

default_args = {
    "owner": "bionicpro",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


def _ch():
    return CHClient(host=CH_HOST, port=CH_PORT, user=CH_USER, password=CH_PASSWORD)


# ---------------------------------------------------------------
# Task: создание схемы в ClickHouse
# ---------------------------------------------------------------
def ensure_schema():
    ch = _ch()
    ch.execute(f"CREATE DATABASE IF NOT EXISTS {CH_DATABASE}")
    ch.execute(f"""
        CREATE TABLE IF NOT EXISTS {CH_DATABASE}.crm_customers (
            customer_id String,
            full_name   String,
            email       String,
            phone       String,
            created_at  DateTime DEFAULT now()
        ) ENGINE = ReplacingMergeTree()
        ORDER BY customer_id
    """)
    ch.execute(f"""
        CREATE TABLE IF NOT EXISTS {CH_DATABASE}.telemetry_events (
            event_id       String,
            customer_id    String,
            event_ts       DateTime,
            signal_strength Float64,
            movement_type   String,
            battery_level   Float64
        ) ENGINE = MergeTree()
        ORDER BY (customer_id, event_ts)
    """)
    ch.execute(f"""
        CREATE TABLE IF NOT EXISTS {CH_DATABASE}.user_daily_telemetry (
            customer_id        String,
            report_date        Date,
            total_events       UInt64,
            avg_signal_strength Float64,
            active_hours       Float64,
            movement_count     UInt64,
            updated_at         DateTime DEFAULT now()
        ) ENGINE = ReplacingMergeTree(updated_at)
        ORDER BY (customer_id, report_date)
    """)


# ---------------------------------------------------------------
# Task: создание CRM БД и таблицы в Postgres (если нет)
# ---------------------------------------------------------------
def ensure_crm_db_and_table():
    conn = psycopg2.connect("postgresql://airflow:airflow@postgres:5432/airflow")
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM pg_database WHERE datname = 'crm'")
    if not cur.fetchone():
        cur.execute("CREATE DATABASE crm")
    cur.close()
    conn.close()

    conn = psycopg2.connect(CRM_CONN)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            customer_id VARCHAR(50) PRIMARY KEY,
            full_name   VARCHAR(200),
            email       VARCHAR(200),
            phone       VARCHAR(50),
            created_at  TIMESTAMP DEFAULT NOW()
        )
    """)
    cur.close()
    conn.close()


# ---------------------------------------------------------------
# Task: заполнение CRM тестовыми данными
# ---------------------------------------------------------------
def seed_crm():
    already = Variable.get("SEED_CRM_DONE", default_var="false")
    if already == "true":
        return

    conn = psycopg2.connect(CRM_CONN)
    conn.autocommit = True
    cur = conn.cursor()
    customers = [
        ("c1", "Prothetic One", "prothetic1@example.com", "+70001111111"),
        ("c2", "Prothetic Two", "prothetic2@example.com", "+70002222222"),
        ("c3", "Prothetic Three", "prothetic3@example.com", "+70003333333"),
    ]
    for c in customers:
        cur.execute(
            """INSERT INTO customers (customer_id, full_name, email, phone)
               VALUES (%s, %s, %s, %s)
               ON CONFLICT (customer_id) DO NOTHING""",
            c,
        )
    cur.close()
    conn.close()
    Variable.set("SEED_CRM_DONE", "true")


# ---------------------------------------------------------------
# Task: загрузка CRM → ClickHouse (инкрементально)
# ---------------------------------------------------------------
def extract_load_crm():
    watermark = Variable.get("CRM_WATERMARK", default_var="1970-01-01 00:00:00")

    conn = psycopg2.connect(CRM_CONN)
    cur = conn.cursor()
    cur.execute(
        "SELECT customer_id, full_name, email, phone, created_at "
        "FROM customers WHERE created_at > %s ORDER BY created_at",
        (watermark,),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()

    if not rows:
        return

    ch = _ch()
    ch.execute(
        f"INSERT INTO {CH_DATABASE}.crm_customers "
        "(customer_id, full_name, email, phone, created_at) VALUES",
        [(r[0], r[1], r[2], r[3], r[4]) for r in rows],
    )
    Variable.set("CRM_WATERMARK", str(rows[-1][4]))


# ---------------------------------------------------------------
# Task: генерация тестовых данных телеметрии
# ---------------------------------------------------------------
def seed_telemetry():
    already = Variable.get("SEED_TELEMETRY_DONE", default_var="false")
    if already == "true":
        return

    ch = _ch()
    events = []
    movement_types = ["grip", "release", "point", "wave", "rotate"]
    for cid in ["c1", "c2", "c3"]:
        base = datetime.now() - timedelta(days=90)
        for day_offset in range(90):
            day = base + timedelta(days=day_offset)
            n_events = random.randint(20, 100)
            for i in range(n_events):
                ts = day + timedelta(hours=random.randint(6, 22), minutes=random.randint(0, 59))
                events.append((
                    f"{cid}-{day_offset}-{i}",
                    cid,
                    ts,
                    round(random.uniform(0.3, 1.0), 4),
                    random.choice(movement_types),
                    round(random.uniform(20, 100), 1),
                ))

    ch.execute(
        f"INSERT INTO {CH_DATABASE}.telemetry_events "
        "(event_id, customer_id, event_ts, signal_strength, movement_type, battery_level) VALUES",
        events,
    )
    Variable.set("SEED_TELEMETRY_DONE", "true")


# ---------------------------------------------------------------
# Task: обновление витрины user_daily_telemetry
# ---------------------------------------------------------------
def refresh_mart():
    days_back = int(Variable.get("AGG_DAYS_BACK", default_var="7"))
    ch = _ch()

    ch.execute(f"""
        ALTER TABLE {CH_DATABASE}.user_daily_telemetry
        DELETE WHERE report_date >= today() - {days_back}
    """)

    ch.execute(f"""
        INSERT INTO {CH_DATABASE}.user_daily_telemetry
            (customer_id, report_date, total_events, avg_signal_strength,
             active_hours, movement_count)
        SELECT
            customer_id,
            toDate(event_ts)                              AS report_date,
            count()                                       AS total_events,
            round(avg(signal_strength), 4)                AS avg_signal_strength,
            round(uniqExact(toHour(event_ts)), 1)         AS active_hours,
            count()                                       AS movement_count
        FROM {CH_DATABASE}.telemetry_events
        WHERE toDate(event_ts) >= today() - {days_back}
        GROUP BY customer_id, report_date
    """)


# ---------------------------------------------------------------
# Task: явное заполнение витрины user_report_mv
# ---------------------------------------------------------------
def populate_report_mv():
    ch = _ch()
    ch.execute(f"""
        INSERT INTO {CH_DATABASE}.user_report_mv
        SELECT
            t.customer_id,
            c.full_name,
            c.email,
            toDate(t.event_ts)                       AS report_date,
            count()                                   AS total_events,
            round(avg(t.signal_strength), 4)          AS avg_signal_strength,
            round(uniqExact(toHour(t.event_ts)), 1)   AS active_hours,
            count()                                   AS movement_count
        FROM {CH_DATABASE}.telemetry_events AS t
        INNER JOIN {CH_DATABASE}.crm_customers_cdc AS c
            ON t.customer_id = c.customer_id
        GROUP BY t.customer_id, c.full_name, c.email, toDate(t.event_ts)
    """)


# ---------------------------------------------------------------
# Task: инвалидация S3-кеша после обновления витрины
# ---------------------------------------------------------------
S3_ENDPOINT = os.getenv("S3_ENDPOINT", "http://minio:9000")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY", "minioadmin")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY", "minioadmin")
S3_BUCKET = os.getenv("S3_BUCKET", "reports")


def invalidate_s3_cache():
    s3 = boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=S3_ACCESS_KEY,
        aws_secret_access_key=S3_SECRET_KEY,
    )
    resp = s3.list_objects_v2(Bucket=S3_BUCKET, Prefix="reports/")
    for obj in resp.get("Contents", []):
        if obj["Key"].endswith("/latest.json"):
            s3.delete_object(Bucket=S3_BUCKET, Key=obj["Key"])
            print(f"Deleted cached report: {obj['Key']}")


# ---------------------------------------------------------------
# Task: записать метку времени последнего успешного ETL
# ---------------------------------------------------------------
def done_marker():
    ch = _ch()
    ch.execute(f"CREATE DATABASE IF NOT EXISTS {CH_DATABASE}")
    ch.execute(f"""
        CREATE TABLE IF NOT EXISTS {CH_DATABASE}.etl_metadata (
            key   String,
            value String,
            ts    DateTime DEFAULT now()
        ) ENGINE = ReplacingMergeTree(ts)
        ORDER BY key
    """)
    ch.execute(
        f"INSERT INTO {CH_DATABASE}.etl_metadata (key, value) VALUES",
        [("last_etl_run", datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))],
    )
    print("ETL complete, timestamp recorded")


# ---------------------------------------------------------------
# DAG
# ---------------------------------------------------------------
with DAG(
    dag_id="bionicpro_reports_dag",
    default_args=default_args,
    description="ETL: CRM + Telemetry → ClickHouse mart",
    schedule_interval="15 * * * *",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["bionicpro", "etl", "reports"],
) as dag:

    t_schema = PythonOperator(task_id="ensure_schema", python_callable=ensure_schema)
    t_crm_db = PythonOperator(task_id="ensure_crm_db_and_table", python_callable=ensure_crm_db_and_table)
    t_seed_crm = PythonOperator(task_id="seed_crm", python_callable=seed_crm)
    t_extract = PythonOperator(task_id="extract_load_crm", python_callable=extract_load_crm)
    t_seed_tel = PythonOperator(task_id="seed_telemetry", python_callable=seed_telemetry)
    t_mart = PythonOperator(task_id="refresh_mart", python_callable=refresh_mart)
    t_populate_mv = PythonOperator(task_id="populate_report_mv", python_callable=populate_report_mv)
    t_invalidate = PythonOperator(task_id="invalidate_s3_cache", python_callable=invalidate_s3_cache)
    t_done = PythonOperator(task_id="done_marker", python_callable=done_marker)

    t_schema >> t_crm_db >> t_seed_crm >> t_extract >> t_seed_tel >> t_mart >> t_populate_mv >> t_invalidate >> t_done
