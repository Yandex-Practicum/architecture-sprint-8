"""
BionicPRO ETL DAG — формирование витрины отчётности fact_user_report.

Пайплайн:
  1. Extract: извлечение данных телеметрии из PostgreSQL (БД датчиков)
  2. Extract: извлечение данных клиентов из CRM DB
  3. Transform: объединение данных по user_id, агрегация телеметрии
  4. Load: запись витрины в OLAP БД (ClickHouse)

Расписание: ежедневно в 03:00 UTC (инкрементальная загрузка за предыдущий день)
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook

# ---------------------------------------------------------------------------
# Подключения (задаются через env AIRFLOW__CONNECTIONS__ в docker-compose)
#   - sensor_db   : PostgreSQL, БД датчиков (sensor_data)
#   - crm_db      : PostgreSQL, БД CRM (crm_data)
#   - olap_db     : ClickHouse (OLAP)
# ---------------------------------------------------------------------------

SENSOR_DB_CONN = "sensor_db"
CRM_DB_CONN = "crm_db"
OLAP_DB_CONN = "olap_db"

default_args = {
    "owner": "bionic-data-team",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "email_on_failure": True,
    "email": ["data-alerts@bionicpro.local"],
}

# ============================= EXTRACT =====================================


def extract_sensor_data(**context):
    """Извлечение телеметрии датчиков за предыдущий день.

    Данные: сессии использования протеза, миосигналы, распознанные жесты,
    параметры протеза. Инкрементальная загрузка по дате.
    """
    execution_date = context["ds"]
    hook = PostgresHook(postgres_conn_id=SENSOR_DB_CONN)

    sql = """
        SELECT
            s.user_id,
            s.session_id,
            s.session_start,
            s.session_end,
            EXTRACT(EPOCH FROM (s.session_end - s.session_start)) / 60
                AS duration_min,
            s.gestures_count,
            s.avg_myosignal_quality,
            s.prosthesis_model
        FROM sessions s
        WHERE s.session_start::date = %(ds)s
        ORDER BY s.user_id, s.session_start
    """

    records = hook.get_records(sql, parameters={"ds": execution_date})
    context["ti"].xcom_push(key="sensor_data", value=records)
    print(f"[extract_sensor_data] Загружено {len(records)} записей за {execution_date}")


def extract_crm_data(**context):
    """Извлечение данных клиентов из CRM DB.

    Данные: профиль клиента, статус заказа, модель протеза,
    дата последнего обращения. Полная выгрузка (справочник).
    """
    hook = PostgresHook(postgres_conn_id=CRM_DB_CONN)

    sql = """
        SELECT
            c.user_id,
            c.full_name,
            o.order_status,
            o.prosthesis_model,
            c.last_contact_date
        FROM clients c
        LEFT JOIN orders o ON o.client_id = c.user_id
            AND o.is_latest = true
    """

    records = hook.get_records(sql)
    context["ti"].xcom_push(key="crm_data", value=records)
    print(f"[extract_crm_data] Загружено {len(records)} клиентов")


# ============================ TRANSFORM ====================================


def transform_data(**context):
    """Объединение телеметрии и CRM-данных. Агрегация по user_id за день.

    Результат — строки витрины fact_user_report:
      user_id, report_date, session_count, avg_wear_time_min,
      total_gestures, avg_myosignal_quality, order_status,
      prosthesis_model, last_contact_date
    """
    ti = context["ti"]
    sensor_rows = ti.xcom_pull(key="sensor_data", task_ids="extract_sensor_data")
    crm_rows = ti.xcom_pull(key="crm_data", task_ids="extract_crm_data")
    report_date = context["ds"]

    # Индекс CRM-данных по user_id
    crm_index = {}
    for row in crm_rows:
        uid, full_name, order_status, prosthesis_model, last_contact = row
        crm_index[uid] = {
            "order_status": order_status,
            "prosthesis_model": prosthesis_model,
            "last_contact_date": last_contact,
        }

    # Агрегация телеметрии по user_id
    user_agg = {}
    for row in sensor_rows:
        uid = row[0]
        duration_min = row[4] or 0
        gestures = row[5] or 0
        quality = row[6] or 0

        if uid not in user_agg:
            user_agg[uid] = {
                "session_count": 0,
                "total_duration": 0.0,
                "total_gestures": 0,
                "quality_sum": 0.0,
                "prosthesis_model": row[7],
            }
        agg = user_agg[uid]
        agg["session_count"] += 1
        agg["total_duration"] += duration_min
        agg["total_gestures"] += gestures
        agg["quality_sum"] += quality

    # Формирование строк витрины
    report_rows = []
    for uid, agg in user_agg.items():
        crm = crm_index.get(uid, {})
        avg_wear = (
            round(agg["total_duration"] / agg["session_count"], 2)
            if agg["session_count"] > 0
            else 0
        )
        avg_quality = (
            round(agg["quality_sum"] / agg["session_count"], 4)
            if agg["session_count"] > 0
            else 0
        )
        report_rows.append(
            (
                uid,
                report_date,
                agg["session_count"],
                avg_wear,
                agg["total_gestures"],
                avg_quality,
                crm.get("order_status"),
                crm.get("prosthesis_model") or agg["prosthesis_model"],
                crm.get("last_contact_date"),
            )
        )

    context["ti"].xcom_push(key="report_rows", value=report_rows)
    print(f"[transform_data] Сформировано {len(report_rows)} строк витрины за {report_date}")


# =============================== LOAD ======================================


def load_to_olap(**context):
    """Загрузка витрины fact_user_report в ClickHouse (OLAP).

    Стратегия: удаление данных за текущий день + вставка (идемпотентность).
    При повторном запуске DAG данные не дублируются.
    """
    report_rows = context["ti"].xcom_pull(
        key="report_rows", task_ids="transform_data"
    )
    report_date = context["ds"]

    if not report_rows:
        print(f"[load_to_olap] Нет данных для загрузки за {report_date}")
        return

    hook = PostgresHook(postgres_conn_id=OLAP_DB_CONN)
    conn = hook.get_conn()
    cursor = conn.cursor()

    # Удаляем старые данные за этот день (идемпотентность)
    cursor.execute(
        "ALTER TABLE fact_user_report DELETE WHERE report_date = %(dt)s",
        {"dt": report_date},
    )

    # Batch-вставка
    insert_sql = """
        INSERT INTO fact_user_report (
            user_id, report_date, session_count, avg_wear_time_min,
            total_gestures, avg_myosignal_quality, order_status,
            prosthesis_model, last_contact_date
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    cursor.executemany(insert_sql, report_rows)
    conn.commit()
    cursor.close()
    conn.close()

    print(f"[load_to_olap] Загружено {len(report_rows)} строк за {report_date}")


# =============================== DAG =======================================

with DAG(
    dag_id="bionic_etl_reporting",
    default_args=default_args,
    description="ETL: телеметрия + CRM → витрина fact_user_report в OLAP",
    schedule_interval="0 3 * * *",  # ежедневно в 03:00 UTC
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["bionic", "etl", "reporting"],
) as dag:

    t_extract_sensor = PythonOperator(
        task_id="extract_sensor_data",
        python_callable=extract_sensor_data,
    )

    t_extract_crm = PythonOperator(
        task_id="extract_crm_data",
        python_callable=extract_crm_data,
    )

    t_transform = PythonOperator(
        task_id="transform_data",
        python_callable=transform_data,
    )

    t_load = PythonOperator(
        task_id="load_to_olap",
        python_callable=load_to_olap,
    )

    # Граф зависимостей:
    # extract_sensor_data ─┐
    #                      ├──► transform_data ──► load_to_olap
    # extract_crm_data ────┘
    [t_extract_sensor, t_extract_crm] >> t_transform >> t_load
