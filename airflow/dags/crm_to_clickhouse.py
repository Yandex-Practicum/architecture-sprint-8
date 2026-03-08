"""
Airflow DAG: ETL CRM PostgreSQL → ClickHouse
Задание 2, Задача 2.

Что делает:
  1. extract_from_crm   — читает данные из CRM DB за последний час
  2. load_to_clickhouse — пишет сырые данные в ClickHouse (таблица raw_telemetry)
  3. build_user_summary — строит/обновляет витрину user_reports_summary
                          (агрегаты по пользователям за каждый день)

Витрина спроектирована для быстрого доступа:
  - ReplacingMergeTree по (user_id, prosthesis_id, report_date)
  - Report API делает простой SELECT без вычислений в реальном времени
"""

from datetime import datetime, timedelta
import json

from airflow import DAG
from airflow.operators.python import PythonOperator

default_args = {
    "owner": "bionicpro",
    "depends_on_past": False,
    "start_date": datetime(2026, 1, 1),
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

dag = DAG(
    "crm_to_clickhouse",
    default_args=default_args,
    description="ETL: CRM PostgreSQL → ClickHouse витрина отчётов",
    schedule_interval="0 * * * *",   # каждый час
    catchup=False,
    tags=["bionicpro", "etl", "reports"],
)


def extract_from_crm(**context):
    """
    Читает из CRM данные о пользователях, протезах и телеметрии
    за последние 2 часа (с перекрытием для надёжности).
    """
    import psycopg2
    import psycopg2.extras

    conn = psycopg2.connect(
        host="crm-db", port=5432,
        dbname="crm_db", user="crm_user", password="crm_password",
    )
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Витрина объединяет: клиенты CRM + протезы + телеметрия
    cursor.execute("""
        SELECT
            u.id::text           AS user_id,
            u.username,
            u.email,
            p.id::text           AS prosthesis_id,
            p.model,
            p.created_at         AS prosthesis_created_at,
            t.recorded_at,
            t.signal_value::float8,
            t.movement_type,
            t.response_ms::float8
        FROM users u
        JOIN prostheses p ON u.id = p.user_id
        LEFT JOIN telemetry t ON p.id = t.prosthesis_id
        WHERE t.recorded_at >= NOW() - INTERVAL '2 hours'
    """)

    rows = [dict(r) for r in cursor.fetchall()]
    cursor.close()
    conn.close()

    # XCom передаёт данные между задачами
    context["ti"].xcom_push(key="crm_rows", value=rows)
    print(f"Extracted {len(rows)} rows from CRM")
    return len(rows)


def load_to_clickhouse(**context):
    """
    Пишет сырые данные в raw_telemetry для хранения истории.
    """
    import clickhouse_connect

    rows = context["ti"].xcom_pull(key="crm_rows")
    if not rows:
        print("No data to load")
        return 0

    client = clickhouse_connect.get_client(
        host="clickhouse", port=8123,
        username="default", password="clickhouse",
        database="bionicpro",
    )

    # Создаём таблицу, если не существует
    client.command("""
        CREATE TABLE IF NOT EXISTS bionicpro.raw_telemetry (
            user_id              String,
            username             String,
            email                String,
            prosthesis_id        String,
            model                String,
            prosthesis_created_at DateTime,
            recorded_at          DateTime,
            signal_value         Float64,
            movement_type        String,
            response_ms          Float64,
            _loaded_at           DateTime DEFAULT now()
        ) ENGINE = MergeTree()
        PARTITION BY toYYYYMM(recorded_at)
        ORDER BY (user_id, prosthesis_id, recorded_at)
    """)

    # Вставка пакетом
    columns = [
        "user_id", "username", "email", "prosthesis_id", "model",
        "prosthesis_created_at", "recorded_at",
        "signal_value", "movement_type", "response_ms",
    ]
    data = [[r[c] for c in columns] for r in rows]
    client.insert("bionicpro.raw_telemetry", data, column_names=columns)

    print(f"Loaded {len(rows)} rows into raw_telemetry")
    return len(rows)


def build_user_summary(**context):
    """
    Строит/обновляет витрину user_reports_summary.
    ReplacingMergeTree автоматически дедуплицирует записи по ключу.

    Эту витрину читает Report API — без тяжёлых вычислений в реальном времени.
    """
    import clickhouse_connect

    client = clickhouse_connect.get_client(
        host="clickhouse", port=8123,
        username="default", password="clickhouse",
        database="bionicpro",
    )

    # Витрина — ReplacingMergeTree: при дублях по ключу оставляет последнюю версию
    client.command("""
        CREATE TABLE IF NOT EXISTS bionicpro.user_reports_summary (
            user_id          String,
            username         String,
            email            String,
            prosthesis_id    String,
            model            String,
            total_movements  UInt64,
            avg_response_ms  Float64,
            min_response_ms  Float64,
            max_response_ms  Float64,
            last_activity    DateTime,
            report_date      Date
        ) ENGINE = ReplacingMergeTree()
        ORDER BY (user_id, prosthesis_id, report_date)
    """)

    # Агрегируем вчерашние данные (уже полные — DAG строит витрину за вчера)
    client.command("""
        INSERT INTO bionicpro.user_reports_summary
        SELECT
            user_id,
            any(username)        AS username,
            any(email)           AS email,
            prosthesis_id,
            any(model)           AS model,
            count()              AS total_movements,
            avg(response_ms)     AS avg_response_ms,
            min(response_ms)     AS min_response_ms,
            max(response_ms)     AS max_response_ms,
            max(recorded_at)     AS last_activity,
            toDate(recorded_at)  AS report_date
        FROM bionicpro.raw_telemetry
        WHERE toDate(recorded_at) = yesterday()
        GROUP BY user_id, prosthesis_id, toDate(recorded_at)
    """)
    print("User summary rebuilt for yesterday")


# ─── Граф задач ──────────────────────────────────────────────────────────────
extract_task = PythonOperator(
    task_id="extract_from_crm",
    python_callable=extract_from_crm,
    provide_context=True,
    dag=dag,
)

load_task = PythonOperator(
    task_id="load_to_clickhouse",
    python_callable=load_to_clickhouse,
    provide_context=True,
    dag=dag,
)

summary_task = PythonOperator(
    task_id="build_user_summary",
    python_callable=build_user_summary,
    provide_context=True,
    dag=dag,
)

# extract → load → summary (строго последовательно)
extract_task >> load_task >> summary_task
