"""
BionicPRO ETL DAG — формирование витрины отчётности fact_user_report.

Пайплайн:
  1. Extract: извлечение данных телеметрии из PostgreSQL (БД датчиков)
  2. Extract: извлечение данных клиентов из CRM DB
  3. Transform: объединение данных по user_id, агрегация телеметрии
  4. Load: запись витрины в OLAP БД (PostgreSQL)
  5. Export: выгрузка JSON-отчётов в S3 (MinIO) для кеширования
  6. Invalidate: очистка кеша Nginx через reports-api

Расписание: ежедневно в 03:00 UTC (инкрементальная загрузка за предыдущий день)
"""

import json
import os
from datetime import datetime, timedelta

import boto3
import requests
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook

SENSOR_DB_CONN = "sensor_db"
CRM_DB_CONN = "crm_db"
OLAP_DB_CONN = "olap_db"

S3_ENDPOINT = os.environ.get("S3_ENDPOINT", "http://minio:9000")
S3_ACCESS_KEY = os.environ.get("S3_ACCESS_KEY", "minioadmin")
S3_SECRET_KEY = os.environ.get("S3_SECRET_KEY", "minioadmin")
S3_BUCKET = os.environ.get("S3_BUCKET", "reports")

REPORTS_API_URL = os.environ.get("REPORTS_API_URL", "http://reports-api:8001")

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
        duration_min = float(row[4] or 0)
        gestures = int(row[5] or 0)
        quality = float(row[6] or 0)

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
    """Загрузка витрины fact_user_report в OLAP (PostgreSQL).

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
        "DELETE FROM fact_user_report WHERE report_date = %s",
        (report_date,),
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

    # Обновляем Materialized View витрины после загрузки новых данных
    cursor = conn.cursor()
    cursor.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_user_report")
    conn.commit()
    cursor.close()
    conn.close()

    print(f"[load_to_olap] Загружено {len(report_rows)} строк за {report_date}, MV обновлён")


# ========================== EXPORT TO S3 ==================================


def export_reports_to_s3(**context):
    """Выгрузка отчётов в S3 (MinIO) для кеширования.

    Структура хранения в S3:
      {user_id}/daily/{report_date}.json   — отчёт за один день
      {user_id}/meta/date-range.json       — доступный диапазон дат

    После ETL пользователи получают отчёты прямо из S3 через
    Nginx reverse proxy, минуя OLAP.
    """
    report_rows = context["ti"].xcom_pull(
        key="report_rows", task_ids="transform_data"
    )
    report_date = context["ds"]

    if not report_rows:
        print(f"[export_to_s3] Нет данных для экспорта за {report_date}")
        return

    s3 = boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=S3_ACCESS_KEY,
        aws_secret_access_key=S3_SECRET_KEY,
    )

    exported_count = 0
    user_ids = set()

    for row in report_rows:
        uid = row[0]
        user_ids.add(uid)

        report = {
            "user_id": uid,
            "report_date": str(row[1]),
            "session_count": row[2],
            "avg_wear_time_min": row[3],
            "total_gestures": row[4],
            "avg_myosignal_quality": row[5],
            "order_status": row[6],
            "prosthesis_model": row[7],
            "last_contact_date": str(row[8]) if row[8] else None,
        }

        # Сохраняем дневной отчёт: {user_id}/daily/{report_date}.json
        s3_key = f"{uid}/daily/{report_date}.json"
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=json.dumps(report, ensure_ascii=False),
            ContentType="application/json",
        )
        exported_count += 1

    # Обновляем метаданные диапазона дат для каждого пользователя
    hook = PostgresHook(postgres_conn_id=OLAP_DB_CONN)
    conn = hook.get_conn()
    cursor = conn.cursor()

    for uid in user_ids:
        cursor.execute(
            "SELECT MIN(report_date), MAX(report_date) "
            "FROM fact_user_report WHERE user_id = %s",
            (uid,),
        )
        min_date, max_date = cursor.fetchone()

        meta = {
            "user_id": uid,
            "has_data": min_date is not None,
            "available_from": str(min_date) if min_date else None,
            "available_to": str(max_date) if max_date else None,
        }

        s3.put_object(
            Bucket=S3_BUCKET,
            Key=f"{uid}/meta/date-range.json",
            Body=json.dumps(meta, ensure_ascii=False),
            ContentType="application/json",
        )

    cursor.close()
    conn.close()

    print(f"[export_to_s3] Экспортировано {exported_count} отчётов для {len(user_ids)} пользователей за {report_date}")


# ======================== INVALIDATE CACHE ================================


def invalidate_cdn_cache(**context):
    """Инвалидация кеша CDN/Nginx через reports-api.

    После обновления данных в OLAP и перегенерации файлов в S3
    необходимо очистить кеш Nginx, чтобы пользователи получали
    актуальные данные.

    Стратегия инвалидации:
    - Точечная: очищаем кеш только для пользователей, чьи данные обновились
    - Полная: если точечная не удалась, выполняем полную очистку
    """
    report_rows = context["ti"].xcom_pull(
        key="report_rows", task_ids="transform_data"
    )

    if not report_rows:
        print("[invalidate_cache] Нет обновлённых данных — инвалидация не требуется")
        return

    # Собираем user_id, чьи данные обновились
    updated_user_ids = list({row[0] for row in report_rows})

    purge_url = f"{REPORTS_API_URL}/cache/purge"
    errors = []

    # Точечная инвалидация по пользователям
    for uid in updated_user_ids:
        try:
            resp = requests.post(
                purge_url,
                json={"user_id": uid},
                timeout=10,
            )
            if resp.status_code == 200:
                print(f"[invalidate_cache] Кеш очищен для user_id={uid}")
            else:
                errors.append(f"user_id={uid}: HTTP {resp.status_code}")
        except requests.RequestException as e:
            errors.append(f"user_id={uid}: {e}")

    if errors:
        print(f"[invalidate_cache] Ошибки точечной инвалидации: {errors}")
        # Fallback: полная очистка кеша
        try:
            resp = requests.post(purge_url, json={}, timeout=30)
            print(f"[invalidate_cache] Полная очистка кеша: HTTP {resp.status_code}")
        except requests.RequestException as e:
            print(f"[invalidate_cache] Ошибка полной очистки: {e}")
    else:
        print(f"[invalidate_cache] Успешно инвалидировано для {len(updated_user_ids)} пользователей")


# =============================== DAG =======================================

with DAG(
    dag_id="bionic_etl_reporting",
    default_args=default_args,
    description="ETL: телеметрия + CRM → витрина fact_user_report в OLAP → S3 → cache invalidation",
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

    t_export_s3 = PythonOperator(
        task_id="export_reports_to_s3",
        python_callable=export_reports_to_s3,
    )

    t_invalidate = PythonOperator(
        task_id="invalidate_cdn_cache",
        python_callable=invalidate_cdn_cache,
    )

    # Граф зависимостей:
    # extract_sensor_data ─┐
    #                      ├──► transform_data ──► load_to_olap ──► export_to_s3 ──► invalidate_cache
    # extract_crm_data ────┘
    [t_extract_sensor, t_extract_crm] >> t_transform >> t_load >> t_export_s3 >> t_invalidate
