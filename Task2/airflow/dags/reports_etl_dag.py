"""
ETL-DAG для витрины отчётности BionicPRO.

Извлекает данные из CRM и из основной БД (телеметрия), объединяет в разрезе
клиентов и загружает в витрину OLAP (report_datamart) для быстрого доступа
к отчётам по пользователям.

Расписание: ежедневно в 02:00 (по времени сервера Airflow).
"""

from pathlib import Path

from airflow import DAG
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.operators.python import PythonOperator
from airflow.operators.empty import EmptyOperator
from airflow.utils.dates import days_ago

# Параметры по умолчанию для всех задач
DEFAULT_ARGS = {
    "owner": "bionicpro-reports",
    "retries": 2,
    "retry_delay": __import__("datetime").timedelta(minutes=2),
}

# Расписание: каждый день в 02:00
SCHEDULE_INTERVAL = "0 2 * * *"

# Connection IDs в Airflow (настраиваются в Admin → Connections)
CRM_CONN_ID = "crm_db"
MAIN_DB_CONN_ID = "main_db"
OLAP_CONN_ID = "olap_db"

# Директория с SQL (относительно DAG-файла)
SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def _ensure_olap_schema(**context):
    """Создаёт таблицы витрины и staging в OLAP, если их ещё нет."""
    sql_path = SQL_DIR / "01_schema_olap.sql"
    sql = sql_path.read_text()
    hook = PostgresHook(postgres_conn_id=OLAP_CONN_ID)
    conn = hook.get_conn()
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.close()


def _extract_crm(**context):
    """
    Extract: выгрузка данных о клиентах и устройствах из CRM в staging OLAP.
    Объединяем crm_customers и crm_devices по user_id.
    """
    hook_crm = PostgresHook(postgres_conn_id=CRM_CONN_ID)
    hook_olap = PostgresHook(postgres_conn_id=OLAP_CONN_ID)

    # Выбираем из CRM: клиенты + устройства (последняя запись по устройству на user_id)
    sql_extract = """
    SELECT
        c.user_id,
        d.device_id,
        c.full_name AS customer_name,
        c.email AS customer_email,
        c.contract_date,
        d.prosthesis_model,
        d.delivery_date
    FROM crm_customers c
    LEFT JOIN LATERAL (
        SELECT device_id, prosthesis_model, delivery_date
        FROM crm_devices
        WHERE user_id = c.user_id
        ORDER BY updated_at DESC
        LIMIT 1
    ) d ON TRUE
    """
    conn_crm = hook_crm.get_conn()
    with conn_crm.cursor() as cur:
        cur.execute(sql_extract)
        rows = cur.fetchall()
        columns = [desc[0] for desc in cur.description]
    conn_crm.close()

    # Записываем в staging OLAP (полная перезагрузка staging)
    conn_olap = hook_olap.get_conn()
    conn_olap.autocommit = True
    with conn_olap.cursor() as cur:
        cur.execute("TRUNCATE TABLE stg_crm")
        if rows:
            cur.executemany(
                """
                INSERT INTO stg_crm (user_id, device_id, customer_name, customer_email,
                    contract_date, prosthesis_model, delivery_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE SET
                    device_id = EXCLUDED.device_id,
                    customer_name = EXCLUDED.customer_name,
                    customer_email = EXCLUDED.customer_email,
                    contract_date = EXCLUDED.contract_date,
                    prosthesis_model = EXCLUDED.prosthesis_model,
                    delivery_date = EXCLUDED.delivery_date
                """,
                rows,
            )
    conn_olap.close()


def _extract_telemetry(**context):
    """
    Extract: агрегация телеметрии по пользователям из основной БД и запись в staging OLAP.
    Считаем сессии, время использования, события (в т.ч. ошибки и калибровки) за период.
    """
    from datetime import datetime, timedelta

    # Период: последние 30 дней до даты запуска DAG (или логическая дата)
    logical_date = context["logical_date"]
    period_end = logical_date
    period_start = period_end - timedelta(days=30)

    hook_main = PostgresHook(postgres_conn_id=MAIN_DB_CONN_ID)
    hook_olap = PostgresHook(postgres_conn_id=OLAP_CONN_ID)

    sql_agg = """
    WITH sessions_agg AS (
        SELECT
            user_id,
            device_id,
            COUNT(*) AS session_count,
            COALESCE(SUM(duration_seconds), 0)::BIGINT AS total_usage_seconds,
            MAX(ended_at) AS last_session_end
        FROM telemetry_sessions
        WHERE started_at >= %(period_start)s AND started_at < %(period_end)s
        GROUP BY user_id, device_id
    ),
    events_agg AS (
        SELECT
            user_id,
            device_id,
            COUNT(*) AS event_count,
            COUNT(*) FILTER (WHERE event_type = 'error') AS error_count,
            COUNT(*) FILTER (WHERE event_type = 'calibration') AS calibration_count,
            MAX(event_ts) AS last_event_ts
        FROM telemetry_events
        WHERE event_ts >= %(period_start)s AND event_ts < %(period_end)s
        GROUP BY user_id, device_id
    ),
    combined AS (
        SELECT
            COALESCE(s.user_id, e.user_id) AS user_id,
            COALESCE(s.device_id, e.device_id) AS device_id,
            COALESCE(s.session_count, 0) AS session_count,
            COALESCE(s.total_usage_seconds, 0) AS total_usage_seconds,
            COALESCE(e.event_count, 0) AS event_count,
            COALESCE(e.error_count, 0) AS error_count,
            COALESCE(e.calibration_count, 0) AS calibration_count,
            GREATEST(s.last_session_end, e.last_event_ts) AS last_activity_utc
        FROM sessions_agg s
        FULL OUTER JOIN events_agg e ON s.user_id = e.user_id AND s.device_id = e.device_id
    )
    SELECT user_id, device_id, session_count, total_usage_seconds, event_count,
           error_count, calibration_count, last_activity_utc
    FROM combined
    """
    params = {
        "period_start": period_start,
        "period_end": period_end,
    }

    conn_main = hook_main.get_conn()
    with conn_main.cursor() as cur:
        cur.execute(sql_agg, params)
        rows = cur.fetchall()
    conn_main.close()

    conn_olap = hook_olap.get_conn()
    conn_olap.autocommit = True
    with conn_olap.cursor() as cur:
        cur.execute("TRUNCATE TABLE stg_telemetry")
        for r in rows:
            cur.execute(
                """
                INSERT INTO stg_telemetry (user_id, device_id, session_count, total_usage_seconds,
                    event_count, error_count, calibration_count, last_activity_utc, period_start, period_end)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE SET
                    device_id = EXCLUDED.device_id,
                    session_count = EXCLUDED.session_count,
                    total_usage_seconds = EXCLUDED.total_usage_seconds,
                    event_count = EXCLUDED.event_count,
                    error_count = EXCLUDED.error_count,
                    calibration_count = EXCLUDED.calibration_count,
                    last_activity_utc = EXCLUDED.last_activity_utc,
                    period_start = EXCLUDED.period_start,
                    period_end = EXCLUDED.period_end
                """,
                (
                    r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7],
                    period_start, period_end,
                ),
            )
    conn_olap.close()


def _transform_and_load(**context):
    """
    Transform & Load: объединение staging (CRM + телеметрия) и запись в витрину report_datamart.
    Полная перезапись витрины из текущих staging-таблиц (по одному срезу на пользователя).
    """
    hook = PostgresHook(postgres_conn_id=OLAP_CONN_ID)
    conn = hook.get_conn()
    conn.autocommit = True
    sql = """
    INSERT INTO report_datamart (
        user_id, device_id, customer_name, customer_email, contract_date, prosthesis_model,
        delivery_date, session_count, total_usage_seconds, event_count, error_count,
        calibration_count, period_start, period_end, last_activity_utc, updated_at
    )
    SELECT
        COALESCE(c.user_id, t.user_id) AS user_id,
        COALESCE(c.device_id, t.device_id) AS device_id,
        c.customer_name,
        c.customer_email,
        c.contract_date,
        c.prosthesis_model,
        c.delivery_date,
        COALESCE(t.session_count, 0) AS session_count,
        COALESCE(t.total_usage_seconds, 0) AS total_usage_seconds,
        COALESCE(t.event_count, 0) AS event_count,
        COALESCE(t.error_count, 0) AS error_count,
        COALESCE(t.calibration_count, 0) AS calibration_count,
        t.period_start,
        t.period_end,
        t.last_activity_utc,
        NOW() AT TIME ZONE 'UTC' AS updated_at
    FROM stg_crm c
    FULL OUTER JOIN stg_telemetry t ON c.user_id = t.user_id
    ON CONFLICT (user_id) DO UPDATE SET
        device_id = EXCLUDED.device_id,
        customer_name = EXCLUDED.customer_name,
        customer_email = EXCLUDED.customer_email,
        contract_date = EXCLUDED.contract_date,
        prosthesis_model = EXCLUDED.prosthesis_model,
        delivery_date = EXCLUDED.delivery_date,
        session_count = EXCLUDED.session_count,
        total_usage_seconds = EXCLUDED.total_usage_seconds,
        event_count = EXCLUDED.event_count,
        error_count = EXCLUDED.error_count,
        calibration_count = EXCLUDED.calibration_count,
        period_start = EXCLUDED.period_start,
        period_end = EXCLUDED.period_end,
        last_activity_utc = EXCLUDED.last_activity_utc,
        updated_at = EXCLUDED.updated_at
    """
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.close()


with DAG(
    dag_id="reports_etl",
    default_args=DEFAULT_ARGS,
    schedule_interval=SCHEDULE_INTERVAL,
    start_date=days_ago(1),
    catchup=False,
    tags=["bionicpro", "reports", "etl"],
) as dag:

    start = EmptyOperator(task_id="start")

    init_schema = PythonOperator(
        task_id="init_olap_schema",
        python_callable=_ensure_olap_schema,
    )

    extract_crm = PythonOperator(
        task_id="extract_crm",
        python_callable=_extract_crm,
    )

    extract_telemetry = PythonOperator(
        task_id="extract_telemetry",
        python_callable=_extract_telemetry,
    )

    transform_and_load = PythonOperator(
        task_id="transform_and_load",
        python_callable=_transform_and_load,
    )

    end = EmptyOperator(task_id="end")

    start >> init_schema >> [extract_crm, extract_telemetry] >> transform_and_load >> end
